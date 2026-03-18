"""部署管理路由 — 机器人实例的 CRUD 与生命周期"""
import json
import datetime
from flask import Blueprint, request, jsonify
from extensions import db
from models import (Deployment, KnowledgeBase, KnowledgeDocument,
                    ServicePlan, Worker, Order, DEPLOYMENT_TRANSITIONS)
from utils.auth import get_current_user, require_admin
from services.deployment_service import (
    create_deployment, update_deployment_config,
    submit_for_review, approve_deployment, suspend_deployment,
)
from services.usage_service import get_deployment_metrics
from services.messages import send_message

bp = Blueprint("deployments", __name__)


# ===== 用户侧 =====

@bp.route("/api/deployments", methods=["POST"])
def create_new_deployment():
    """支付完成后创建部署实例"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id")
    if not order_id:
        return jsonify({"error": "请提供订单ID"}), 400

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "无权操作此订单"}), 403
    if order.status not in ("paid", "active"):
        return jsonify({"error": "订单尚未支付或已完成"}), 400

    # 检查是否已创建过部署
    existing = Deployment.query.filter_by(order_id=order.id).first()
    if existing:
        return jsonify({"message": "部署已存在", "deployment": existing.to_dict()}), 200

    config = {
        "brand_name": data.get("brand_name", ""),
        "brand_tone": data.get("brand_tone", "专业、友善、高效"),
        "forbidden_topics": data.get("forbidden_topics", ""),
        "handoff_keywords": data.get("handoff_keywords", "转人工,找客服,投诉"),
    }

    deployment, error = create_deployment(user, order, config)
    if error:
        return jsonify({"error": error}), 400

    db.session.commit()
    return jsonify({"message": "部署创建成功", "deployment": deployment.to_dict()}), 201


@bp.route("/api/deployments", methods=["GET"])
def list_my_deployments():
    """我的机器人列表"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    per_page = min(per_page, 50)
    status = request.args.get("status", type=str)

    query = Deployment.query.filter_by(user_id=user.id)
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(Deployment.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "deployments": [d.to_dict() for d in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/deployments/<int:deploy_id>", methods=["GET"])
def get_deployment_detail(deploy_id):
    """部署详情"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deploy_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.user_id != user.id:
        admin = require_admin()
        if not admin:
            return jsonify({"error": "无权查看"}), 403

    result = deployment.to_dict()
    result["knowledge_bases"] = [kb.to_dict() for kb in deployment.knowledge_bases]

    plan = deployment.service_plan
    if plan:
        result["service_plan"] = plan.to_dict()

    return jsonify({"deployment": result}), 200


@bp.route("/api/deployments/<int:deploy_id>/config", methods=["PUT"])
def update_config(deploy_id):
    """更新部署配置（品牌语气、禁答规则等）"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deploy_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.user_id != user.id:
        return jsonify({"error": "无权操作"}), 403

    data = request.get_json(silent=True) or {}

    if "deployment_name" in data:
        deployment.deployment_name = data["deployment_name"]

    config_fields = ["brand_name", "brand_tone", "forbidden_topics",
                     "handoff_keywords", "handoff_email"]
    config_update = {k: data[k] for k in config_fields if k in data}
    if config_update:
        update_deployment_config(deployment, config_update)

    db.session.commit()
    return jsonify({"message": "配置已更新", "deployment": deployment.to_dict()}), 200


@bp.route("/api/deployments/<int:deploy_id>/publish", methods=["POST"])
def publish_deployment(deploy_id):
    """提交部署审核"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deploy_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.user_id != user.id:
        return jsonify({"error": "无权操作"}), 403

    ok, error = submit_for_review(deployment)
    if not ok:
        return jsonify({"error": error}), 400

    db.session.commit()
    return jsonify({"message": "已提交审核", "deployment": deployment.to_dict()}), 200


@bp.route("/api/deployments/<int:deploy_id>/metrics", methods=["GET"])
def deployment_metrics(deploy_id):
    """部署实例的使用统计"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deploy_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.user_id != user.id:
        admin = require_admin()
        if not admin:
            return jsonify({"error": "无权查看"}), 403

    days = request.args.get("days", 30, type=int)
    days = min(days, 90)
    metrics = get_deployment_metrics(deploy_id, days)
    return jsonify({"metrics": metrics}), 200


# ===== 知识库管理 =====

@bp.route("/api/deployments/<int:deploy_id>/knowledge-base", methods=["GET"])
def list_knowledge_bases(deploy_id):
    """列出部署的知识库"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deploy_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.user_id != user.id:
        admin = require_admin()
        if not admin:
            return jsonify({"error": "无权查看"}), 403

    kbs = KnowledgeBase.query.filter_by(deployment_id=deploy_id).all()
    result = []
    for kb in kbs:
        d = kb.to_dict()
        d["documents"] = [doc.to_dict() for doc in kb.documents]
        result.append(d)

    return jsonify({"knowledge_bases": result}), 200


@bp.route("/api/deployments/<int:deploy_id>/knowledge-base", methods=["POST"])
def upload_knowledge(deploy_id):
    """上传知识库文档"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deploy_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.user_id != user.id:
        return jsonify({"error": "无权操作"}), 403

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    doc_type = data.get("doc_type", "faq")

    if not title or not content:
        return jsonify({"error": "标题和内容不能为空"}), 400
    if doc_type not in ("faq", "article", "policy"):
        doc_type = "faq"

    # 使用默认知识库
    kb = KnowledgeBase.query.filter_by(deployment_id=deploy_id).first()
    if not kb:
        kb = KnowledgeBase(
            deployment_id=deploy_id,
            name="默认知识库",
            status="draft",
        )
        db.session.add(kb)
        db.session.flush()

    doc = KnowledgeDocument(
        knowledge_base_id=kb.id,
        title=title,
        content=content,
        doc_type=doc_type,
        status="pending",
    )
    db.session.add(doc)
    db.session.commit()

    return jsonify({"message": "文档已上传", "document": doc.to_dict()}), 201


@bp.route("/api/deployments/<int:deploy_id>/knowledge-base/batch", methods=["POST"])
def batch_upload_knowledge(deploy_id):
    """批量上传 FAQ"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    deployment = Deployment.query.get(deploy_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.user_id != user.id:
        return jsonify({"error": "无权操作"}), 403

    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    if not items or not isinstance(items, list):
        return jsonify({"error": "请提供 items 数组"}), 400

    kb = KnowledgeBase.query.filter_by(deployment_id=deploy_id).first()
    if not kb:
        kb = KnowledgeBase(deployment_id=deploy_id, name="默认知识库", status="draft")
        db.session.add(kb)
        db.session.flush()

    docs = []
    for item in items[:100]:  # 限制单次最多 100 条
        title = (item.get("title") or "").strip()
        content = (item.get("content") or "").strip()
        if not title or not content:
            continue
        doc = KnowledgeDocument(
            knowledge_base_id=kb.id,
            title=title,
            content=content,
            doc_type=item.get("doc_type", "faq"),
            status="pending",
        )
        db.session.add(doc)
        docs.append(doc)

    db.session.commit()
    return jsonify({
        "message": f"已上传 {len(docs)} 条文档",
        "documents": [d.to_dict() for d in docs],
    }), 201


# ===== 套餐查询 =====

@bp.route("/api/workers/<int:worker_id>/plans", methods=["GET"])
def get_worker_plans(worker_id):
    """获取员工的服务套餐"""
    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "员工不存在"}), 404

    plans = ServicePlan.query.filter_by(
        worker_id=worker_id, is_active=True
    ).order_by(ServicePlan.sort_order).all()

    return jsonify({"plans": [p.to_dict() for p in plans]}), 200


# ===== 管理后台 =====

@bp.route("/api/admin/deployments", methods=["GET"])
def admin_list_deployments():
    """管理后台：部署列表"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)
    status = request.args.get("status", type=str)

    query = Deployment.query
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(Deployment.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    deployments = []
    for d in pagination.items:
        item = d.to_dict()
        item["username"] = d.user.username if d.user else None
        deployments.append(item)

    return jsonify({
        "deployments": deployments,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/admin/deployments/<int:deploy_id>/approve", methods=["POST"])
def admin_approve_deployment(deploy_id):
    """审核通过"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    deployment = Deployment.query.get(deploy_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404

    # 同时审核通过知识库文档
    for kb in deployment.knowledge_bases:
        for doc in kb.documents:
            if doc.status == "pending":
                doc.status = "approved"

    ok, error = approve_deployment(deployment)
    if not ok:
        return jsonify({"error": error}), 400

    db.session.commit()
    return jsonify({"message": "已审核通过并上线", "deployment": deployment.to_dict()}), 200


@bp.route("/api/admin/deployments/<int:deploy_id>/reject", methods=["POST"])
def admin_reject_deployment(deploy_id):
    """审核拒绝"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    deployment = Deployment.query.get(deploy_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404
    if deployment.status != "pending_review":
        return jsonify({"error": "当前状态无法拒绝"}), 400

    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "审核未通过")

    deployment.status = "pending_setup"
    send_message(deployment.user_id, "机器人审核未通过",
                 f"「{deployment.deployment_name}」审核未通过，原因: {reason}。请修改后重新提交。",
                 "system")
    db.session.commit()
    return jsonify({"message": "已拒绝", "deployment": deployment.to_dict()}), 200


@bp.route("/api/admin/deployments/<int:deploy_id>/suspend", methods=["POST"])
def admin_suspend_deployment(deploy_id):
    """暂停部署"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    deployment = Deployment.query.get(deploy_id)
    if not deployment:
        return jsonify({"error": "部署不存在"}), 404

    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")

    ok, error = suspend_deployment(deployment, reason)
    if not ok:
        return jsonify({"error": error}), 400

    db.session.commit()
    return jsonify({"message": "已暂停", "deployment": deployment.to_dict()}), 200


@bp.route("/api/admin/knowledge-documents", methods=["GET"])
def admin_list_documents():
    """管理后台：知识库文档审核列表"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    status = request.args.get("status", "pending", type=str)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = KnowledgeDocument.query.filter_by(status=status)
    query = query.order_by(KnowledgeDocument.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "documents": [d.to_dict() for d in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/admin/knowledge-documents/<int:doc_id>/approve", methods=["POST"])
def admin_approve_document(doc_id):
    """审核通过文档"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    doc = KnowledgeDocument.query.get(doc_id)
    if not doc:
        return jsonify({"error": "文档不存在"}), 404

    doc.status = "approved"
    db.session.commit()
    return jsonify({"message": "已通过", "document": doc.to_dict()}), 200


@bp.route("/api/admin/knowledge-documents/<int:doc_id>/reject", methods=["POST"])
def admin_reject_document(doc_id):
    """拒绝文档"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    doc = KnowledgeDocument.query.get(doc_id)
    if not doc:
        return jsonify({"error": "文档不存在"}), 404

    doc.status = "rejected"
    db.session.commit()
    return jsonify({"message": "已拒绝", "document": doc.to_dict()}), 200
