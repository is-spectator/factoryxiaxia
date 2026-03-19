"""机器人聊天、会话和指标路由"""
import datetime
import json

from flask import Blueprint, jsonify, request

from extensions import db
from models import ConversationMessage, ConversationSession, Deployment
from services.audit_service import record_audit
from services.deployment_service import (
    find_public_deployment,
    load_deployment_config,
    user_can_manage_deployment,
)
from services.guardrails_service import inspect_inbound_message, sanitize_outbound_message
from services.handoff_service import create_handoff_ticket
from services.prompt_service import render_support_prompt
from services.provider_service import get_chat_provider
from services.public_api_service import (
    build_public_request_context,
    evaluate_public_access,
    evaluate_public_quota,
    evaluate_public_rate_limits,
)
from services.rag_service import search_deployment_knowledge
from services.usage_meter_service import record_usage, summarize_deployment_usage
from utils.auth import get_current_user


bp = Blueprint("chat", __name__)


def _load_deployment_for_management(deployment_id):
    user = get_current_user()
    if not user:
        return None, None, (jsonify({"error": "请先登录"}), 401)

    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return user, None, (jsonify({"error": "部署实例不存在"}), 404)
    if not user_can_manage_deployment(user, deployment):
        return user, None, (jsonify({"error": "无权访问该部署实例"}), 403)
    return user, deployment, None


def _run_chat_turn(deployment, data, actor_user_id=None, access_mode="deployment_id", access_details=None):
    if not deployment:
        return jsonify({"error": "部署实例不存在"}), 404
    if deployment.status != "active":
        return jsonify({"error": "机器人尚未发布上线"}), 400

    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    session_id = data.get("session_id")
    if session_id:
        session = ConversationSession.query.filter_by(
            id=session_id,
            deployment_id=deployment.id,
        ).first()
        if not session:
            return jsonify({"error": "会话不存在"}), 404
    else:
        session = ConversationSession(
            deployment_id=deployment.id,
            visitor_name=(data.get("visitor_name") or "").strip(),
            visitor_contact=(data.get("visitor_contact") or "").strip(),
            channel_type=(data.get("channel_type") or deployment.channel_type).strip() or deployment.channel_type,
            status="open",
        )
        db.session.add(session)
        db.session.flush()

    deployment_config = load_deployment_config(deployment)
    guardrails = inspect_inbound_message(message, deployment_config)
    stored_user_message = guardrails["masked_message"]

    user_message = ConversationMessage(
        session_id=session.id,
        role="user",
        content=stored_user_message,
        risk_level=guardrails["risk_level"],
        source_refs_json=json.dumps({
            "pii_findings": guardrails["pii_findings"],
            "forbidden_matches": guardrails["forbidden_matches"],
            "sensitive_matches": guardrails["sensitive_matches"],
        }, ensure_ascii=False),
    )
    db.session.add(user_message)

    snippets = []
    if not guardrails["blocked"]:
        snippets = search_deployment_knowledge(deployment, stored_user_message, limit=3)

    system_prompt = render_support_prompt(
        deployment.template,
        deployment,
        deployment_config,
        snippets,
        deployment_config,
    )
    provider = get_chat_provider(deployment_config.get("provider"))
    if guardrails["blocked"]:
        response = {
            "reply": guardrails["refusal_message"] or deployment_config["handoff_message"],
            "confidence": 0.08,
            "risk_level": guardrails["risk_level"],
            "should_handoff": True,
            "reason": guardrails["reason"] or "guardrails_blocked",
            "sources": [],
            "provider": "guardrails",
            "provider_meta": {
                "model": "guardrails",
                "latency_ms": 0,
                "usage": {},
                "status": "blocked",
                "fallback_used": False,
            },
        }
    else:
        response = provider.generate(system_prompt, stored_user_message, snippets, deployment_config)
        if guardrails["should_handoff"]:
            response["should_handoff"] = True
            response["risk_level"] = "high"
            response["reason"] = guardrails["reason"] or "guardrails_flagged"

    provider_meta = response.get("provider_meta") or {}
    assistant_source_refs = {
        "sources": response["sources"],
        "provider": response.get("provider"),
        "response_reason": response.get("reason"),
        "provider_meta": {
            "model": provider_meta.get("model"),
            "latency_ms": provider_meta.get("latency_ms"),
            "usage": provider_meta.get("usage") or {},
            "status": provider_meta.get("status"),
            "fallback_used": bool(provider_meta.get("fallback_used")),
            "request_id": provider_meta.get("request_id"),
        },
        "knowledge_hit_count": len(snippets),
    }

    assistant_reply = sanitize_outbound_message(response["reply"], deployment_config)
    assistant_message = ConversationMessage(
        session_id=session.id,
        role="assistant",
        content=assistant_reply,
        confidence=response["confidence"],
        risk_level=response["risk_level"],
        source_refs_json=json.dumps(assistant_source_refs, ensure_ascii=False),
    )
    db.session.add(assistant_message)

    session.last_confidence = response["confidence"]
    session.updated_at = datetime.datetime.utcnow()
    if response["should_handoff"]:
        session.needs_handoff = True
        session.status = "handoff_requested"
        session.handoff_reason = response["reason"]

    record_usage(
        deployment_id=deployment.id,
        session_id=session.id,
        metric_type="message_in",
        quantity=1,
    )
    record_usage(
        deployment_id=deployment.id,
        session_id=session.id,
        metric_type="message_out",
        quantity=1,
    )
    if snippets:
        record_usage(
            deployment_id=deployment.id,
            session_id=session.id,
            metric_type="knowledge_hit",
            quantity=len(snippets),
        )

    handoff_ticket = None
    if response["should_handoff"]:
        handoff_ticket, created = create_handoff_ticket(
            deployment,
            session,
            reason=response["reason"],
            summary=stored_user_message,
            request_source="system",
        )
        if created:
            record_usage(
                deployment_id=deployment.id,
                session_id=session.id,
                metric_type="handoff",
                quantity=1,
            )

    record_audit(
        action_type="chat.turn",
        resource_type="conversation_session",
        resource_id=session.id,
        actor_user_id=actor_user_id,
        deployment_id=deployment.id,
        summary=f"{deployment.deployment_name} 完成一轮会话",
        details={
            "access_mode": access_mode,
            "session_id": session.id,
            "provider": response.get("provider"),
            "confidence": response["confidence"],
            "risk_level": response["risk_level"],
            "should_handoff": response["should_handoff"],
            "response_reason": response.get("reason"),
            "provider_meta": provider_meta,
            "knowledge_hit_count": len(snippets),
            "pii_findings": guardrails["pii_findings"],
            "forbidden_matches": guardrails["forbidden_matches"],
            "sensitive_matches": guardrails["sensitive_matches"],
            "access_details": access_details or {},
        },
    )
    db.session.commit()
    return jsonify({
        "session": session.to_dict(),
        "assistant_message": assistant_message.to_dict(),
        "handoff_ticket": handoff_ticket.to_dict() if handoff_ticket else None,
    }), 200


@bp.route("/api/chat/<int:deployment_id>/message", methods=["POST"])
def send_chat_message(deployment_id):
    deployment = Deployment.query.get(deployment_id)
    data = request.get_json(silent=True) or {}
    return _run_chat_turn(deployment, data, access_mode="deployment_id")


@bp.route("/api/public/chat/<string:public_token>/message", methods=["POST"])
def send_public_chat_message(public_token):
    deployment = find_public_deployment(public_token)
    access_context = build_public_request_context(request)
    deployment_config = load_deployment_config(deployment) if deployment else {}
    access_check = evaluate_public_access(deployment, deployment_config, access_context)
    if not access_check["allowed"]:
        if deployment:
            record_audit(
                action_type="chat.public_access_denied",
                resource_type="deployment",
                resource_id=deployment.id,
                deployment_id=deployment.id,
                summary=f"{deployment.deployment_name} 公开 API 访问被拒绝",
                details={
                    "reason": access_check["reason"],
                    "access_mode": "public_token",
                    "access_details": access_check["details"],
                },
                ip_address=access_context["ip_address"],
            )
            db.session.commit()
        return jsonify({"error": access_check["error"]}), access_check["status_code"]

    rate_limit_check = evaluate_public_rate_limits(deployment, access_context)
    if not rate_limit_check["allowed"]:
        record_audit(
            action_type="chat.public_access_denied",
            resource_type="deployment",
            resource_id=deployment.id,
            deployment_id=deployment.id,
            summary=f"{deployment.deployment_name} 公开 API 触发限流",
            details={
                "reason": rate_limit_check["reason"],
                "access_mode": "public_token",
                "access_details": access_context,
                "limit_details": rate_limit_check["details"],
            },
            ip_address=access_context["ip_address"],
        )
        db.session.commit()
        response = jsonify({"error": rate_limit_check["error"]})
        response.headers["Retry-After"] = str(rate_limit_check["details"]["retry_after"])
        return response, rate_limit_check["status_code"]

    quota_check = evaluate_public_quota(deployment)
    if not quota_check["allowed"]:
        record_audit(
            action_type="chat.public_access_denied",
            resource_type="deployment",
            resource_id=deployment.id,
            deployment_id=deployment.id,
            summary=f"{deployment.deployment_name} 套餐额度耗尽",
            details={
                "reason": quota_check["reason"],
                "access_mode": "public_token",
                "access_details": access_context,
                "quota_details": quota_check["details"],
            },
            ip_address=access_context["ip_address"],
        )
        db.session.commit()
        return jsonify({"error": quota_check["error"]}), quota_check["status_code"]

    data = request.get_json(silent=True) or {}
    return _run_chat_turn(
        deployment,
        data,
        access_mode="public_token",
        access_details={
            **access_context,
            "allowed_origins": access_check["details"]["allowed_origins"],
            "quota_remaining": quota_check["details"].get("quota_remaining"),
        },
    )


@bp.route("/api/chat/<int:deployment_id>/sessions", methods=["GET"])
def list_chat_sessions(deployment_id):
    user, deployment, error = _load_deployment_for_management(deployment_id)
    if error:
        return error

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)
    include_messages = request.args.get("include_messages", 0, type=int) == 1

    pagination = ConversationSession.query.filter_by(
        deployment_id=deployment.id
    ).order_by(
        ConversationSession.updated_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "sessions": [session.to_dict(include_messages=include_messages) for session in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/chat/<int:deployment_id>/metrics", methods=["GET"])
def get_chat_metrics(deployment_id):
    user, deployment, error = _load_deployment_for_management(deployment_id)
    if error:
        return error

    return jsonify({"metrics": summarize_deployment_usage(deployment.id)}), 200


@bp.route("/api/chat/<int:deployment_id>/handoff", methods=["POST"])
def request_handoff(deployment_id):
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署实例不存在"}), 404
    if deployment.status != "active":
        return jsonify({"error": "机器人尚未发布上线"}), 400

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    reason = (data.get("reason") or "").strip() or "manual_request"
    summary = (data.get("summary") or "").strip()
    if not session_id:
        return jsonify({"error": "请提供 session_id"}), 400

    session = ConversationSession.query.filter_by(
        id=session_id,
        deployment_id=deployment.id,
    ).first()
    if not session:
        return jsonify({"error": "会话不存在"}), 404

    current_user = get_current_user()
    request_source = "owner" if current_user and user_can_manage_deployment(current_user, deployment) else "manual"
    ticket, created = create_handoff_ticket(
        deployment,
        session,
        reason=reason,
        summary=summary,
        request_source=request_source,
    )
    if created:
        record_usage(
            deployment_id=deployment.id,
            session_id=session.id,
            metric_type="handoff",
            quantity=1,
        )
    record_audit(
        action_type="handoff.requested",
        resource_type="handoff_ticket",
        resource_id=ticket.ticket_no,
        actor_user_id=current_user.id if current_user else None,
        deployment_id=deployment.id,
        summary=f"提交转人工请求 {ticket.ticket_no}",
        details={
            "session_id": session.id,
            "reason": reason,
            "request_source": request_source,
        },
    )

    db.session.commit()
    return jsonify({
        "message": "已提交转人工请求" if created else "转人工请求已存在",
        "handoff_ticket": ticket.to_dict(),
    }), 201 if created else 200
