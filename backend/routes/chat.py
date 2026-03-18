"""聊天路由 — 机器人对话 API"""
import json
import datetime
from flask import Blueprint, request, jsonify
from extensions import db
from models import (Deployment, ConversationSession, ConversationMessage,
                    HandoffTicket)
from utils.auth import get_current_user, require_admin
from services.agents.support_responder import generate_reply
from services.usage_service import (
    record_session_usage, record_message_usage, record_handoff_usage,
)

bp = Blueprint("chat", __name__)


@bp.route("/api/chat/<int:deployment_id>/sessions", methods=["POST"])
def create_session(deployment_id):
    """创建新会话"""
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.status != "active":
        return jsonify({"error": "该机器人当前不可用"}), 400

    data = request.get_json(silent=True) or {}
    visitor_id = data.get("visitor_id", "")
    visitor_name = data.get("visitor_name", "访客")

    session = ConversationSession(
        deployment_id=deployment_id,
        visitor_id=visitor_id,
        visitor_name=visitor_name,
        status="active",
    )
    db.session.add(session)

    # 记录用量
    record_session_usage(deployment_id)
    db.session.commit()

    # 生成欢迎消息
    config = {}
    if deployment.config_json:
        try:
            config = json.loads(deployment.config_json)
        except (json.JSONDecodeError, TypeError):
            config = {}

    welcome = config.get("welcome_message",
                         f"您好！我是{deployment.deployment_name}的智能客服，请问有什么可以帮您？")
    welcome_msg = ConversationMessage(
        session_id=session.id,
        role="bot",
        content=welcome,
        confidence=1.0,
    )
    db.session.add(welcome_msg)
    session.message_count = 1
    db.session.commit()

    return jsonify({
        "session": session.to_dict(),
        "messages": [welcome_msg.to_dict()],
    }), 201


@bp.route("/api/chat/<int:deployment_id>/message", methods=["POST"])
def send_chat_message(deployment_id):
    """发送消息并获取机器人回复"""
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.status != "active":
        return jsonify({"error": "该机器人当前不可用"}), 400

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    content = (data.get("content") or "").strip()

    if not session_id or not content:
        return jsonify({"error": "请提供 session_id 和 content"}), 400

    session = ConversationSession.query.get(session_id)
    if not session or session.deployment_id != deployment_id:
        return jsonify({"error": "会话不存在"}), 404
    if session.status != "active":
        return jsonify({"error": "会话已结束"}), 400

    # 保存用户消息
    user_msg = ConversationMessage(
        session_id=session.id,
        role="visitor",
        content=content,
    )
    db.session.add(user_msg)
    session.message_count += 1
    record_message_usage(deployment_id)

    # 生成机器人回复
    result = generate_reply(deployment, content)

    source_doc_ids = json.dumps(result["source_doc_ids"]) if result["source_doc_ids"] else ""
    bot_msg = ConversationMessage(
        session_id=session.id,
        role="bot",
        content=result["reply"],
        confidence=result["confidence"],
        source_doc_ids=source_doc_ids,
    )
    db.session.add(bot_msg)
    session.message_count += 1
    record_message_usage(deployment_id)

    # 处理转人工
    handoff_ticket = None
    if result["should_handoff"]:
        session.status = "handoff"
        ticket = HandoffTicket(
            session_id=session.id,
            deployment_id=deployment_id,
            reason=result["handoff_reason"],
            status="pending",
        )
        db.session.add(ticket)
        record_handoff_usage(deployment_id)
        handoff_ticket = ticket

    db.session.commit()

    response = {
        "user_message": user_msg.to_dict(),
        "bot_message": bot_msg.to_dict(),
        "confidence": result["confidence"],
        "should_handoff": result["should_handoff"],
    }
    if handoff_ticket:
        response["handoff_ticket"] = handoff_ticket.to_dict()

    return jsonify(response), 200


@bp.route("/api/chat/<int:deployment_id>/sessions", methods=["GET"])
def list_sessions(deployment_id):
    """获取会话列表"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.user_id != user.id:
        admin = require_admin()
        if not admin:
            return jsonify({"error": "无权查看"}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 50)
    status = request.args.get("status", type=str)

    query = ConversationSession.query.filter_by(deployment_id=deployment_id)
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(ConversationSession.started_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "sessions": [s.to_dict() for s in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/chat/<int:deployment_id>/sessions/<int:session_id>/messages", methods=["GET"])
def get_session_messages(deployment_id, session_id):
    """获取会话的所有消息"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.user_id != user.id:
        admin = require_admin()
        if not admin:
            return jsonify({"error": "无权查看"}), 403

    session = ConversationSession.query.get(session_id)
    if not session or session.deployment_id != deployment_id:
        return jsonify({"error": "会话不存在"}), 404

    messages = ConversationMessage.query.filter_by(
        session_id=session_id
    ).order_by(ConversationMessage.created_at).all()

    return jsonify({
        "session": session.to_dict(),
        "messages": [m.to_dict() for m in messages],
    }), 200


@bp.route("/api/chat/<int:deployment_id>/sessions/<int:session_id>/close", methods=["POST"])
def close_session(deployment_id, session_id):
    """关闭会话"""
    session = ConversationSession.query.get(session_id)
    if not session or session.deployment_id != deployment_id:
        return jsonify({"error": "会话不存在"}), 404

    data = request.get_json(silent=True) or {}
    satisfaction = data.get("satisfaction_score")
    if satisfaction and isinstance(satisfaction, int) and 1 <= satisfaction <= 5:
        session.satisfaction_score = satisfaction

    resolved = data.get("resolved")
    if resolved is not None:
        session.resolved = bool(resolved)

    session.status = "closed"
    session.ended_at = datetime.datetime.utcnow()
    db.session.commit()

    return jsonify({"message": "会话已关闭", "session": session.to_dict()}), 200


@bp.route("/api/chat/<int:deployment_id>/handoff", methods=["POST"])
def request_handoff(deployment_id):
    """访客主动请求转人工"""
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    reason = data.get("reason", "用户主动请求转人工")

    session = ConversationSession.query.get(session_id)
    if not session or session.deployment_id != deployment_id:
        return jsonify({"error": "会话不存在"}), 404

    session.status = "handoff"
    ticket = HandoffTicket(
        session_id=session.id,
        deployment_id=deployment_id,
        reason=reason,
        status="pending",
    )
    db.session.add(ticket)
    record_handoff_usage(deployment_id)

    # 发消息通知机器人所有者
    from services.messages import send_message
    send_message(deployment.user_id, "有用户请求转人工",
                 f"「{deployment.deployment_name}」有用户请求转人工，原因: {reason}",
                 "system")

    db.session.commit()
    return jsonify({"message": "已转人工", "ticket": ticket.to_dict()}), 200


# ===== 管理后台 =====

@bp.route("/api/admin/conversations", methods=["GET"])
def admin_list_conversations():
    """管理后台：所有会话"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status = request.args.get("status", type=str)
    deployment_id = request.args.get("deployment_id", type=int)

    query = ConversationSession.query
    if status:
        query = query.filter_by(status=status)
    if deployment_id:
        query = query.filter_by(deployment_id=deployment_id)
    query = query.order_by(ConversationSession.started_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "sessions": [s.to_dict() for s in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/admin/handoff-tickets", methods=["GET"])
def admin_list_handoff_tickets():
    """管理后台：转人工工单"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    status = request.args.get("status", "pending", type=str)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = HandoffTicket.query.filter_by(status=status)
    query = query.order_by(HandoffTicket.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "tickets": [t.to_dict() for t in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/admin/handoff-tickets/<int:ticket_id>/resolve", methods=["POST"])
def admin_resolve_handoff(ticket_id):
    """解决转人工工单"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    ticket = HandoffTicket.query.get(ticket_id)
    if not ticket:
        return jsonify({"error": "工单不存在"}), 404

    ticket.status = "resolved"
    ticket.resolved_at = datetime.datetime.utcnow()
    ticket.assigned_to = admin.username
    db.session.commit()

    return jsonify({"message": "已解决", "ticket": ticket.to_dict()}), 200
