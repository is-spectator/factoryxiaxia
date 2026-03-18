"""部署服务 — 管理机器人实例生命周期"""
import json
import datetime
import hashlib
from extensions import db
from models import (Deployment, Organization, Order, Worker,
                    AgentTemplate, ServicePlan, KnowledgeBase,
                    DEPLOYMENT_TRANSITIONS)
from services.messages import send_message


def create_deployment(user, order, config=None):
    """支付成功后创建部署实例"""
    worker = Worker.query.get(order.worker_id)
    if not worker:
        return None, "员工不存在"

    # 查找或创建默认组织
    org = Organization.query.filter_by(owner_user_id=user.id).first()
    if not org:
        org = Organization(
            owner_user_id=user.id,
            name=f"{user.username} 的组织",
        )
        db.session.add(org)
        db.session.flush()

    # 查找 agent template
    template = None
    if worker.template_key:
        template = AgentTemplate.query.filter_by(key=worker.template_key, is_active=True).first()

    deployment = Deployment(
        organization_id=org.id,
        order_id=order.id,
        user_id=user.id,
        worker_id=worker.id,
        template_id=template.id if template else None,
        service_plan_id=order.service_plan_id,
        status="pending_setup",
        deployment_name=f"{worker.name} - {order.order_no}",
        config_json=json.dumps(config or {}, ensure_ascii=False),
    )
    db.session.add(deployment)
    db.session.flush()

    # 自动创建默认知识库
    kb = KnowledgeBase(
        deployment_id=deployment.id,
        name="默认知识库",
        status="draft",
    )
    db.session.add(kb)

    send_message(user.id, "机器人部署已创建",
                 f"您的机器人「{deployment.deployment_name}」已创建，请完成配置后提交审核。",
                 "order", order.id)

    return deployment, None


def update_deployment_config(deployment, config_data):
    """更新部署配置"""
    existing = {}
    if deployment.config_json:
        try:
            existing = json.loads(deployment.config_json)
        except (json.JSONDecodeError, TypeError):
            existing = {}

    existing.update(config_data)
    deployment.config_json = json.dumps(existing, ensure_ascii=False)
    return deployment


def submit_for_review(deployment):
    """提交部署审核"""
    if deployment.status != "pending_setup":
        return False, f"当前状态({deployment.status})不可提交审核"

    deployment.status = "pending_review"
    send_message(deployment.user_id, "机器人已提交审核",
                 f"「{deployment.deployment_name}」已提交审核，预计 1 个工作日内完成。",
                 "system")
    return True, None


def approve_deployment(deployment):
    """审核通过并部署"""
    if deployment.status != "pending_review":
        return False, f"当前状态({deployment.status})无法审核通过"

    deployment.status = "deploying"
    db.session.flush()

    # 生成嵌入代码
    embed_id = hashlib.md5(f"deploy-{deployment.id}".encode()).hexdigest()[:12]
    deployment.embed_code = (
        f'<script src="/chat-widget.js" data-deployment="{embed_id}"></script>'
    )
    deployment.status = "active"
    deployment.started_at = datetime.datetime.utcnow()

    # 激活知识库
    for kb in deployment.knowledge_bases:
        if kb.status == "draft":
            kb.status = "active"

    send_message(deployment.user_id, "机器人已上线",
                 f"「{deployment.deployment_name}」审核通过并已上线！请获取嵌入代码部署到您的网站。",
                 "system")
    return True, None


def suspend_deployment(deployment, reason=""):
    """暂停部署"""
    if "suspended" not in DEPLOYMENT_TRANSITIONS.get(deployment.status, []):
        return False, f"当前状态({deployment.status})无法暂停"

    deployment.status = "suspended"
    deployment.suspended_at = datetime.datetime.utcnow()
    send_message(deployment.user_id, "机器人已暂停",
                 f"「{deployment.deployment_name}」已暂停服务。原因: {reason or '未说明'}",
                 "system")
    return True, None
