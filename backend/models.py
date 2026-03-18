"""SQLAlchemy 数据模型"""
import datetime
from extensions import db


ROLES = ["user", "operator", "admin"]

ORDER_STATUSES = ["pending", "paid", "active", "completed", "cancelled", "refunded"]

# 订单状态机: 当前状态 → 允许的目标状态
ORDER_TRANSITIONS = {
    "pending": ["paid", "cancelled"],
    "paid": ["active", "refunded"],
    "active": ["completed", "refunded"],
    "completed": [],
    "cancelled": [],
    "refunded": [],
}

DEPLOYMENT_STATUSES = [
    "pending_setup",   # 待配置
    "pending_review",  # 待审核
    "deploying",       # 部署中
    "active",          # 运行中
    "suspended",       # 已暂停
    "expired",         # 已过期
    "terminated",      # 已终止
]

DEPLOYMENT_TRANSITIONS = {
    "pending_setup": ["pending_review"],
    "pending_review": ["deploying", "pending_setup"],
    "deploying": ["active"],
    "active": ["suspended", "expired", "terminated"],
    "suspended": ["active", "terminated"],
    "expired": ["terminated"],
    "terminated": [],
}


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="user")  # user/operator/admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role or "user",
            "is_active": self.is_active if self.is_active is not None else True,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    icon = db.Column(db.String(100), nullable=False, default="mdi:briefcase")
    description = db.Column(db.String(200), default="")
    sort_order = db.Column(db.Integer, default=0)

    workers = db.relationship("Worker", backref="category", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "description": self.description,
            "worker_count": len(self.workers),
        }


class Worker(db.Model):
    __tablename__ = "workers"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    avatar_icon = db.Column(db.String(100), default="mdi:robot-happy-outline")
    avatar_gradient_from = db.Column(db.String(30), default="#6A0DAD")
    avatar_gradient_to = db.Column(db.String(30), default="#00D2FF")
    level = db.Column(db.Integer, default=5)
    skills = db.Column(db.Text, default="")  # 逗号分隔
    description = db.Column(db.Text, default="")
    hourly_rate = db.Column(db.Numeric(10, 2), nullable=False)
    billing_unit = db.Column(db.String(20), default="时薪")
    worker_type = db.Column(db.String(20), default="generic")  # generic/agent
    delivery_mode = db.Column(db.String(20), default="manual")  # manual/semi_auto/auto
    template_key = db.Column(db.String(50), default="")  # 关联 agent_template.key
    status = db.Column(db.String(20), default="online")  # online/busy/offline
    rating = db.Column(db.Numeric(2, 1), default=5.0)
    total_orders = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "avatar_icon": self.avatar_icon,
            "avatar_gradient_from": self.avatar_gradient_from,
            "avatar_gradient_to": self.avatar_gradient_to,
            "level": self.level,
            "skills": [s.strip() for s in self.skills.split(",") if s.strip()] if self.skills else [],
            "description": self.description,
            "hourly_rate": float(self.hourly_rate),
            "billing_unit": self.billing_unit,
            "worker_type": self.worker_type or "generic",
            "delivery_mode": self.delivery_mode or "manual",
            "template_key": self.template_key or "",
            "status": self.status,
            "rating": float(self.rating) if self.rating else 5.0,
            "total_orders": self.total_orders,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_brief_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "avatar_icon": self.avatar_icon,
            "avatar_gradient_from": self.avatar_gradient_from,
            "avatar_gradient_to": self.avatar_gradient_to,
            "level": self.level,
            "skills": [s.strip() for s in self.skills.split(",") if s.strip()] if self.skills else [],
            "hourly_rate": float(self.hourly_rate),
            "billing_unit": self.billing_unit,
            "worker_type": self.worker_type or "generic",
            "delivery_mode": self.delivery_mode or "manual",
            "template_key": self.template_key or "",
            "status": self.status,
            "rating": float(self.rating) if self.rating else 5.0,
            "total_orders": self.total_orders,
        }


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_no = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    duration_hours = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    order_type = db.Column(db.String(20), default="rental")  # rental/subscription
    service_plan_id = db.Column(db.Integer, db.ForeignKey("service_plans.id"), nullable=True)
    status = db.Column(db.String(20), default="pending")
    remark = db.Column(db.Text, default="")
    paid_at = db.Column(db.DateTime, nullable=True)
    activated_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    refunded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow,
                           onupdate=datetime.datetime.utcnow)

    user = db.relationship("User", backref="orders", lazy=True)
    worker = db.relationship("Worker", backref="orders", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "order_no": self.order_no,
            "user_id": self.user_id,
            "worker_id": self.worker_id,
            "worker_name": self.worker.name if self.worker else None,
            "worker_icon": self.worker.avatar_icon if self.worker else None,
            "worker_gradient_from": self.worker.avatar_gradient_from if self.worker else None,
            "worker_gradient_to": self.worker.avatar_gradient_to if self.worker else None,
            "duration_hours": self.duration_hours,
            "total_amount": float(self.total_amount),
            "order_type": self.order_type or "rental",
            "service_plan_id": self.service_plan_id,
            "status": self.status,
            "remark": self.remark,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "refunded_at": self.refunded_at.isoformat() if self.refunded_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_no = db.Column(db.String(40), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.String(30), default="mock")  # mock/alipay/wechat
    status = db.Column(db.String(20), default="success")  # success/failed/refunded
    paid_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    refunded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    order = db.relationship("Order", backref="payments", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "payment_no": self.payment_no,
            "order_id": self.order_id,
            "amount": float(self.amount),
            "method": self.method,
            "status": self.status,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "refunded_at": self.refunded_at.isoformat() if self.refunded_at else None,
        }


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    content = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    user = db.relationship("User", backref="reviews", lazy=True)
    order = db.relationship("Order", backref="review", lazy=True, uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "worker_id": self.worker_id,
            "rating": self.rating,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, default="")
    msg_type = db.Column(db.String(30), default="system")  # system/order/review
    related_order_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "msg_type": self.msg_type,
            "related_order_id": self.related_order_id,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "worker_id", name="uq_user_worker"),)

    worker = db.relationship("Worker", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "worker": self.worker.to_brief_dict() if self.worker else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ===== 迭代 A: 机器人商品与部署模型 =====


class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    industry = db.Column(db.String(50), default="")
    status = db.Column(db.String(20), default="active")  # active/suspended
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    owner = db.relationship("User", backref="organizations", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "owner_user_id": self.owner_user_id,
            "name": self.name,
            "industry": self.industry,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentTemplate(db.Model):
    __tablename__ = "agent_templates"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    source_repo = db.Column(db.String(200), default="")
    source_path = db.Column(db.String(200), default="")
    prompt_template = db.Column(db.Text, default="")
    default_tools = db.Column(db.Text, default="")   # JSON 数组
    risk_level = db.Column(db.String(20), default="low")  # low/medium/high
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "source_repo": self.source_repo,
            "source_path": self.source_path,
            "risk_level": self.risk_level,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ServicePlan(db.Model):
    __tablename__ = "service_plans"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)  # Starter/Pro/Enterprise
    price = db.Column(db.Numeric(10, 2), nullable=False)
    billing_cycle = db.Column(db.String(20), default="monthly")  # monthly/yearly
    session_quota = db.Column(db.Integer, default=500)
    knowledge_base_limit = db.Column(db.Integer, default=1)
    channel_limit = db.Column(db.Integer, default=1)
    seat_limit = db.Column(db.Integer, default=1)       # 人工坐席数
    features = db.Column(db.Text, default="")            # JSON 数组
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    worker = db.relationship("Worker", backref="service_plans", lazy=True)

    def to_dict(self):
        import json
        features_list = []
        if self.features:
            try:
                features_list = json.loads(self.features)
            except (json.JSONDecodeError, TypeError):
                features_list = []
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "name": self.name,
            "price": float(self.price),
            "billing_cycle": self.billing_cycle,
            "session_quota": self.session_quota,
            "knowledge_base_limit": self.knowledge_base_limit,
            "channel_limit": self.channel_limit,
            "seat_limit": self.seat_limit,
            "features": features_list,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
        }


class Deployment(db.Model):
    __tablename__ = "deployments"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey("agent_templates.id"), nullable=True)
    service_plan_id = db.Column(db.Integer, db.ForeignKey("service_plans.id"), nullable=True)
    status = db.Column(db.String(20), default="pending_setup")
    deployment_name = db.Column(db.String(100), default="")
    channel_type = db.Column(db.String(30), default="web_chat")
    config_json = db.Column(db.Text, default="{}")  # 品牌语气、禁答规则等
    embed_code = db.Column(db.Text, default="")      # 挂件嵌入代码
    started_at = db.Column(db.DateTime, nullable=True)
    suspended_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow,
                           onupdate=datetime.datetime.utcnow)

    order = db.relationship("Order", backref="deployment", lazy=True, uselist=False)
    user = db.relationship("User", backref="deployments", lazy=True)
    worker = db.relationship("Worker", backref="deployments", lazy=True)
    template = db.relationship("AgentTemplate", backref="deployments", lazy=True)
    service_plan = db.relationship("ServicePlan", backref="deployments", lazy=True)

    def to_dict(self):
        import json
        config = {}
        if self.config_json:
            try:
                config = json.loads(self.config_json)
            except (json.JSONDecodeError, TypeError):
                config = {}
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "order_id": self.order_id,
            "user_id": self.user_id,
            "worker_id": self.worker_id,
            "worker_name": self.worker.name if self.worker else None,
            "template_id": self.template_id,
            "service_plan_id": self.service_plan_id,
            "plan_name": self.service_plan.name if self.service_plan else None,
            "status": self.status,
            "deployment_name": self.deployment_name,
            "channel_type": self.channel_type,
            "config": config,
            "embed_code": self.embed_code,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "suspended_at": self.suspended_at.isoformat() if self.suspended_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ===== 迭代 B: 知识库与会话体系 =====


class KnowledgeBase(db.Model):
    __tablename__ = "knowledge_bases"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deployment_id = db.Column(db.Integer, db.ForeignKey("deployments.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default="draft")  # draft/active/archived
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    deployment = db.relationship("Deployment", backref="knowledge_bases", lazy=True)

    def to_dict(self):
        doc_count = len(self.documents) if self.documents else 0
        return {
            "id": self.id,
            "deployment_id": self.deployment_id,
            "name": self.name,
            "status": self.status,
            "document_count": doc_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class KnowledgeDocument(db.Model):
    __tablename__ = "knowledge_documents"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    knowledge_base_id = db.Column(db.Integer, db.ForeignKey("knowledge_bases.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    doc_type = db.Column(db.String(20), default="faq")  # faq/article/policy
    status = db.Column(db.String(20), default="pending")  # pending/approved/rejected
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    knowledge_base = db.relationship("KnowledgeBase", backref="documents", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "title": self.title,
            "content": self.content,
            "doc_type": self.doc_type,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ConversationSession(db.Model):
    __tablename__ = "conversation_sessions"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deployment_id = db.Column(db.Integer, db.ForeignKey("deployments.id"), nullable=False)
    visitor_id = db.Column(db.String(100), default="")  # 访客标识
    visitor_name = db.Column(db.String(100), default="访客")
    status = db.Column(db.String(20), default="active")  # active/closed/handoff
    satisfaction_score = db.Column(db.Integer, nullable=True)  # 1-5
    message_count = db.Column(db.Integer, default=0)
    resolved = db.Column(db.Boolean, default=False)
    started_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)

    deployment = db.relationship("Deployment", backref="sessions", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "deployment_id": self.deployment_id,
            "visitor_id": self.visitor_id,
            "visitor_name": self.visitor_name,
            "status": self.status,
            "satisfaction_score": self.satisfaction_score,
            "message_count": self.message_count,
            "resolved": self.resolved,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


class ConversationMessage(db.Model):
    __tablename__ = "conversation_messages"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey("conversation_sessions.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # visitor/bot/agent
    content = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.Numeric(3, 2), nullable=True)  # 0.00-1.00
    source_doc_ids = db.Column(db.Text, default="")  # JSON 数组，引用的知识库文档
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    session = db.relationship("ConversationSession", backref="messages", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "confidence": float(self.confidence) if self.confidence else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class HandoffTicket(db.Model):
    __tablename__ = "handoff_tickets"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey("conversation_sessions.id"), nullable=False)
    deployment_id = db.Column(db.Integer, db.ForeignKey("deployments.id"), nullable=False)
    reason = db.Column(db.String(200), default="")
    status = db.Column(db.String(20), default="pending")  # pending/assigned/resolved/closed
    assigned_to = db.Column(db.String(100), default="")   # 人工坐席标识
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    session = db.relationship("ConversationSession", backref="handoff_tickets", lazy=True)
    deployment = db.relationship("Deployment", backref="handoff_tickets", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "deployment_id": self.deployment_id,
            "reason": self.reason,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class UsageRecord(db.Model):
    __tablename__ = "usage_records"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deployment_id = db.Column(db.Integer, db.ForeignKey("deployments.id"), nullable=False)
    record_date = db.Column(db.Date, nullable=False)
    session_count = db.Column(db.Integer, default=0)
    message_count = db.Column(db.Integer, default=0)
    handoff_count = db.Column(db.Integer, default=0)
    resolved_count = db.Column(db.Integer, default=0)
    avg_satisfaction = db.Column(db.Numeric(3, 2), nullable=True)

    deployment = db.relationship("Deployment", backref="usage_records", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "deployment_id": self.deployment_id,
            "record_date": self.record_date.isoformat() if self.record_date else None,
            "session_count": self.session_count,
            "message_count": self.message_count,
            "handoff_count": self.handoff_count,
            "resolved_count": self.resolved_count,
            "avg_satisfaction": float(self.avg_satisfaction) if self.avg_satisfaction else None,
        }
