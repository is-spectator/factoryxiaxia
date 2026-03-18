"""机器人聊天、会话和指标路由"""
import datetime
import json

from flask import Blueprint, jsonify, request

from extensions import db
from models import ConversationMessage, ConversationSession, Deployment
from services.agents.support_responder import generate_support_response
from services.deployment_service import user_can_manage_deployment
from services.handoff_service import create_handoff_ticket
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


@bp.route("/api/chat/<int:deployment_id>/message", methods=["POST"])
def send_chat_message(deployment_id):
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署实例不存在"}), 404
    if deployment.status != "active":
        return jsonify({"error": "机器人尚未发布上线"}), 400

    data = request.get_json(silent=True) or {}
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

    user_message = ConversationMessage(
        session_id=session.id,
        role="user",
        content=message,
        risk_level="low",
        source_refs_json="[]",
    )
    db.session.add(user_message)

    try:
        deployment_config = json.loads(deployment.config_json or "{}")
    except (json.JSONDecodeError, TypeError):
        deployment_config = {}

    snippets = search_deployment_knowledge(deployment, message, limit=3)
    response = generate_support_response(message, snippets, deployment_config)

    assistant_message = ConversationMessage(
        session_id=session.id,
        role="assistant",
        content=response["reply"],
        confidence=response["confidence"],
        risk_level=response["risk_level"],
        source_refs_json=json.dumps(response["sources"], ensure_ascii=False),
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
            summary=message,
            request_source="system",
        )
        if created:
            record_usage(
                deployment_id=deployment.id,
                session_id=session.id,
                metric_type="handoff",
                quantity=1,
            )

    db.session.commit()
    return jsonify({
        "session": session.to_dict(),
        "assistant_message": assistant_message.to_dict(),
        "handoff_ticket": handoff_ticket.to_dict() if handoff_ticket else None,
    }), 200


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

    db.session.commit()
    return jsonify({
        "message": "已提交转人工请求" if created else "转人工请求已存在",
        "handoff_ticket": ticket.to_dict(),
    }), 201 if created else 200
