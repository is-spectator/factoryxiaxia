"""组织与机器人部署路由"""
import datetime

from flask import Blueprint, jsonify, request

from extensions import db
from models import (
    AgentTemplate,
    AuditLog,
    Deployment,
    KnowledgeBase,
    KnowledgeDocument,
    Order,
    Organization,
)
from services.audit_service import record_audit
from services.deployment_service import (
    dump_deployment_config,
    ensure_public_token,
    load_deployment_config,
    normalize_deployment_config,
    publish_deployment,
    user_can_manage_deployment,
)
from services.messages import send_message
from utils.auth import get_current_user


bp = Blueprint("deployments", __name__)


def get_or_create_default_organization(user):
    org = Organization.query.filter_by(owner_user_id=user.id).order_by(Organization.id.asc()).first()
    if org:
        return org

    org = Organization(
        owner_user_id=user.id,
        name=f"{user.username} 的团队",
        status="active",
    )
    db.session.add(org)
    db.session.flush()
    return org


@bp.route("/api/organizations", methods=["GET"])
def list_organizations():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    orgs = Organization.query.filter_by(owner_user_id=user.id).order_by(Organization.id.desc()).all()
    return jsonify({"organizations": [org.to_dict() for org in orgs]}), 200


@bp.route("/api/organizations", methods=["POST"])
def create_organization():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    industry = (data.get("industry") or "").strip()

    if not name:
        return jsonify({"error": "组织名称不能为空"}), 400

    org = Organization(
        owner_user_id=user.id,
        name=name,
        industry=industry,
        status="active",
    )
    db.session.add(org)
    db.session.commit()
    return jsonify({"message": "组织创建成功", "organization": org.to_dict()}), 201


@bp.route("/api/deployments", methods=["GET"])
def list_deployments():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployments = Deployment.query.filter_by(user_id=user.id).order_by(Deployment.created_at.desc()).all()
    return jsonify({"deployments": [d.to_dict() for d in deployments]}), 200


@bp.route("/api/deployments/<int:deployment_id>", methods=["GET"])
def get_deployment_detail(deployment_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署实例不存在"}), 404
    if not user_can_manage_deployment(user, deployment):
        return jsonify({"error": "无权查看该部署实例"}), 403

    payload = deployment.to_dict()
    payload["knowledge_bases"] = [knowledge_base.to_dict() for knowledge_base in deployment.knowledge_bases]
    payload["audit_log_count"] = len(deployment.audit_logs)
    return jsonify({"deployment": payload}), 200


@bp.route("/api/orders/<int:order_id>/deployments", methods=["POST"])
def create_deployment(order_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "无权操作此订单"}), 403
    if order.order_type != "agent_deployment":
        return jsonify({"error": "当前订单不是机器人部署订单"}), 400
    if order.status not in ("paid", "active", "completed"):
        return jsonify({"error": "请先完成支付后再创建部署"}), 400

    existing = Deployment.query.filter_by(order_id=order.id).first()
    if existing:
        return jsonify({"message": "部署实例已存在", "deployment": existing.to_dict()}), 200

    worker = order.worker
    if not worker or not worker.template_key:
        return jsonify({"error": "该机器人尚未绑定可部署模板"}), 400

    template = AgentTemplate.query.filter_by(key=worker.template_key, is_active=True).first()
    if not template:
        return jsonify({"error": "模板不存在或未启用"}), 400

    data = request.get_json(silent=True) or {}
    organization_id = data.get("organization_id")
    deployment_name = (data.get("deployment_name") or "").strip() or f"{worker.name} 实例"
    channel_type = (data.get("channel_type") or "web_widget").strip() or "web_widget"
    config = data.get("config") or {}

    if not isinstance(config, dict):
        return jsonify({"error": "config 必须是对象"}), 400
    config = normalize_deployment_config(config)

    if organization_id:
        organization = Organization.query.filter_by(id=organization_id, owner_user_id=user.id).first()
        if not organization:
            return jsonify({"error": "组织不存在或无权使用"}), 404
    else:
        organization = get_or_create_default_organization(user)

    now = datetime.datetime.utcnow()
    deployment = Deployment(
        organization_id=organization.id,
        order_id=order.id,
        user_id=user.id,
        worker_id=worker.id,
        template_id=template.id,
        service_plan_id=order.service_plan_id,
        status="pending_setup",
        deployment_name=deployment_name,
        channel_type=channel_type,
        config_json="{}",
        started_at=now,
        expires_at=now + datetime.timedelta(hours=order.duration_hours),
    )
    ensure_public_token(deployment)
    deployment.config_json = dump_deployment_config(config, deployment=deployment)
    db.session.add(deployment)
    db.session.flush()

    if order.status == "paid":
        order.status = "active"
        order.activated_at = now

    send_message(
        user.id,
        "机器人部署已创建",
        f"订单 {order.order_no} 已生成部署实例「{deployment_name}」，请继续完成配置。",
        "system",
        order.id,
    )
    record_audit(
        action_type="deployment.created",
        resource_type="deployment",
        resource_id=deployment.id,
        actor_user_id=user.id,
        deployment_id=deployment.id,
        summary=f"创建部署实例 {deployment_name}",
        details={
            "order_id": order.id,
            "organization_id": organization.id,
            "channel_type": channel_type,
        },
    )
    db.session.commit()
    return jsonify({"message": "部署实例创建成功", "deployment": deployment.to_dict()}), 201


@bp.route("/api/deployments/<int:deployment_id>/config", methods=["PUT"])
def update_deployment_config(deployment_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署实例不存在"}), 404
    if not user_can_manage_deployment(user, deployment):
        return jsonify({"error": "无权操作该部署实例"}), 403

    data = request.get_json(silent=True) or {}
    merged_config = load_deployment_config(deployment)
    if isinstance(data, dict):
        merged_config.update(data)
    config = normalize_deployment_config(merged_config, deployment=deployment)
    deployment.config_json = dump_deployment_config(config, deployment=deployment)
    record_audit(
        action_type="deployment.config_updated",
        resource_type="deployment",
        resource_id=deployment.id,
        actor_user_id=user.id,
        deployment_id=deployment.id,
        summary=f"更新部署配置 {deployment.deployment_name}",
        details={
            "brand_voice": config["brand_voice"],
            "provider": config["provider"],
            "forbidden_topics": config["forbidden_topics"],
            "sensitive_keywords": config["sensitive_keywords"],
            "pii_masking_enabled": config["pii_masking_enabled"],
        },
    )
    db.session.commit()
    return jsonify({"message": "配置已更新", "deployment": deployment.to_dict()}), 200


@bp.route("/api/deployments/<int:deployment_id>/audit-logs", methods=["GET"])
def list_deployment_audit_logs(deployment_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署实例不存在"}), 404
    if not user_can_manage_deployment(user, deployment):
        return jsonify({"error": "无权查看该部署实例"}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)

    pagination = AuditLog.query.filter_by(
        deployment_id=deployment.id
    ).order_by(
        AuditLog.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "audit_logs": [log.to_dict() for log in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/deployments/<int:deployment_id>/knowledge-base", methods=["POST"])
def upload_knowledge_base(deployment_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署实例不存在"}), 404
    if not user_can_manage_deployment(user, deployment):
        return jsonify({"error": "无权操作该部署实例"}), 403

    data = request.get_json(silent=True) or {}
    knowledge_base_id = data.get("knowledge_base_id")
    name = (data.get("name") or "").strip() or "默认知识库"
    description = (data.get("description") or "").strip()

    if knowledge_base_id:
        knowledge_base = KnowledgeBase.query.filter_by(
            id=knowledge_base_id,
            deployment_id=deployment.id,
        ).first()
        if not knowledge_base:
            return jsonify({"error": "知识库不存在"}), 404
    else:
        knowledge_base = KnowledgeBase.query.filter_by(
            deployment_id=deployment.id,
            name=name,
        ).order_by(KnowledgeBase.id.asc()).first()
        if not knowledge_base:
            knowledge_base = KnowledgeBase(
                deployment_id=deployment.id,
                name=name,
                description=description,
                status="draft",
            )
            db.session.add(knowledge_base)
            db.session.flush()
        elif description and not knowledge_base.description:
            knowledge_base.description = description

    documents_payload = data.get("documents")
    if not documents_payload:
        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()
        if not title or not content:
            return jsonify({"error": "请提供 documents 或单篇 title/content"}), 400
        documents_payload = [{
            "title": title,
            "content": content,
            "doc_type": data.get("doc_type", "faq"),
            "source_name": data.get("source_name", ""),
        }]

    if not isinstance(documents_payload, list) or not documents_payload:
        return jsonify({"error": "documents 必须是非空数组"}), 400

    created_documents = []
    for item in documents_payload:
        title = (item.get("title") or "").strip()
        content = (item.get("content") or "").strip()
        if not title or not content:
            return jsonify({"error": "每篇知识文档都需要 title 和 content"}), 400

        document = KnowledgeDocument(
            knowledge_base_id=knowledge_base.id,
            title=title,
            doc_type=(item.get("doc_type") or "faq").strip() or "faq",
            source_name=(item.get("source_name") or "").strip(),
            content=content,
            char_count=len(content),
            status="draft",
        )
        db.session.add(document)
        created_documents.append(document)

    db.session.commit()
    record_audit(
        action_type="knowledge.uploaded",
        resource_type="knowledge_base",
        resource_id=knowledge_base.id,
        actor_user_id=user.id,
        deployment_id=deployment.id,
        summary=f"上传知识库文档到 {knowledge_base.name}",
        details={
            "document_titles": [document.title for document in created_documents],
            "document_count": len(created_documents),
        },
    )
    db.session.commit()
    return jsonify({
        "message": "知识库文档上传成功，发布后生效",
        "knowledge_base": knowledge_base.to_dict(),
        "documents": [document.to_dict() for document in created_documents],
    }), 201


@bp.route("/api/deployments/<int:deployment_id>/publish", methods=["POST"])
def publish_deployment_route(deployment_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return jsonify({"error": "部署实例不存在"}), 404
    if not user_can_manage_deployment(user, deployment):
        return jsonify({"error": "无权操作该部署实例"}), 403

    try:
        knowledge_bases = publish_deployment(deployment)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    send_message(
        deployment.user_id,
        "机器人已发布",
        f"机器人「{deployment.deployment_name}」已发布上线，可开始对外提供服务。",
        "system",
        deployment.order_id,
    )
    record_audit(
        action_type="deployment.published",
        resource_type="deployment",
        resource_id=deployment.id,
        actor_user_id=user.id,
        deployment_id=deployment.id,
        summary=f"发布机器人 {deployment.deployment_name}",
        details={
            "knowledge_base_count": len(knowledge_bases),
            "public_token": deployment.public_token,
        },
    )
    db.session.commit()
    return jsonify({
        "message": "发布成功",
        "deployment": deployment.to_dict(),
        "knowledge_bases": [knowledge_base.to_dict() for knowledge_base in knowledge_bases],
    }), 200
