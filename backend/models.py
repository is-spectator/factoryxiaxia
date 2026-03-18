"""SQLAlchemy 数据模型"""
import datetime
import json
from extensions import db


ROLES = ["user", "operator", "admin"]

ORDER_STATUSES = ["pending", "paid", "active", "completed", "cancelled", "refunded"]
WORKER_TYPES = ["general", "agent_service"]
DELIVERY_MODES = ["manual_service", "managed_deployment"]
ORDER_TYPES = ["rental", "agent_deployment"]
DEPLOYMENT_STATUSES = [
    "pending_setup", "pending_review", "active", "suspended", "expired",
]
KNOWLEDGE_BASE_STATUSES = ["draft", "active", "archived"]
DOCUMENT_STATUSES = ["draft", "published", "archived"]
SESSION_STATUSES = ["open", "handoff_requested", "closed"]
MESSAGE_ROLES = ["user", "assistant", "system"]
HANDOFF_STATUSES = ["open", "in_progress", "resolved", "cancelled"]
USAGE_METRIC_TYPES = ["message_in", "message_out", "knowledge_hit", "handoff"]

# 订单状态机: 当前状态 → 允许的目标状态
ORDER_TRANSITIONS = {
    "pending": ["paid", "cancelled"],
    "paid": ["active", "refunded"],
    "active": ["completed", "refunded"],
    "completed": [],
    "cancelled": [],
    "refunded": [],
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


class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    industry = db.Column(db.String(80), default="")
    status = db.Column(db.String(20), default="active")
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
    key = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    source_repo = db.Column(db.String(255), default="")
    source_path = db.Column(db.String(255), default="")
    prompt_template = db.Column(db.Text, default="")
    default_tools = db.Column(db.Text, default="[]")
    risk_level = db.Column(db.String(20), default="medium")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        try:
            default_tools = json.loads(self.default_tools or "[]")
        except (json.JSONDecodeError, TypeError):
            default_tools = []
        return {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "source_repo": self.source_repo,
            "source_path": self.source_path,
            "prompt_template": self.prompt_template,
            "default_tools": default_tools,
            "risk_level": self.risk_level,
            "is_active": self.is_active,
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
    status = db.Column(db.String(20), default="online")  # online/busy/offline
    worker_type = db.Column(db.String(30), default="general")
    delivery_mode = db.Column(db.String(30), default="manual_service")
    template_key = db.Column(db.String(80), nullable=True)
    rating = db.Column(db.Numeric(2, 1), default=5.0)
    total_orders = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    service_plans = db.relationship("ServicePlan", backref="worker", lazy=True)

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
            "status": self.status,
            "worker_type": self.worker_type or "general",
            "delivery_mode": self.delivery_mode or "manual_service",
            "template_key": self.template_key,
            "service_plans": [p.to_dict() for p in self.service_plans if p.is_active],
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
            "status": self.status,
            "worker_type": self.worker_type or "general",
            "delivery_mode": self.delivery_mode or "manual_service",
            "rating": float(self.rating) if self.rating else 5.0,
            "total_orders": self.total_orders,
        }


class ServicePlan(db.Model):
    __tablename__ = "service_plans"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    slug = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), default="")
    billing_cycle = db.Column(db.String(20), default="monthly")
    price = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(10), default="CNY")
    included_conversations = db.Column(db.Integer, default=500)
    max_handoffs = db.Column(db.Integer, default=50)
    channel_limit = db.Column(db.Integer, default=1)
    seat_limit = db.Column(db.Integer, default=1)
    default_duration_hours = db.Column(db.Integer, default=720)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("worker_id", "slug", name="uq_worker_plan_slug"),)

    def to_dict(self):
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "billing_cycle": self.billing_cycle,
            "price": float(self.price),
            "currency": self.currency,
            "included_conversations": self.included_conversations,
            "max_handoffs": self.max_handoffs,
            "channel_limit": self.channel_limit,
            "seat_limit": self.seat_limit,
            "default_duration_hours": self.default_duration_hours,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_no = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    service_plan_id = db.Column(db.Integer, db.ForeignKey("service_plans.id"), nullable=True)
    duration_hours = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    order_type = db.Column(db.String(30), default="rental")
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
    service_plan = db.relationship("ServicePlan", backref="orders", lazy=True)

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
            "service_plan_id": self.service_plan_id,
            "service_plan_name": self.service_plan.name if self.service_plan else None,
            "service_plan_slug": self.service_plan.slug if self.service_plan else None,
            "duration_hours": self.duration_hours,
            "total_amount": float(self.total_amount),
            "order_type": self.order_type or "rental",
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


class Deployment(db.Model):
    __tablename__ = "deployments"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey("agent_templates.id"), nullable=False)
    service_plan_id = db.Column(db.Integer, db.ForeignKey("service_plans.id"), nullable=True)
    status = db.Column(db.String(30), default="pending_setup")
    deployment_name = db.Column(db.String(120), nullable=False)
    channel_type = db.Column(db.String(30), default="web_widget")
    config_json = db.Column(db.Text, default="{}")
    started_at = db.Column(db.DateTime, nullable=True)
    suspended_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    organization = db.relationship("Organization", backref="deployments", lazy=True)
    order = db.relationship("Order", backref="deployment", lazy=True, uselist=False)
    user = db.relationship("User", backref="deployments", lazy=True)
    worker = db.relationship("Worker", backref="deployments", lazy=True)
    template = db.relationship("AgentTemplate", backref="deployments", lazy=True)
    service_plan = db.relationship("ServicePlan", backref="deployments", lazy=True)

    def to_dict(self):
        try:
            config = json.loads(self.config_json or "{}")
        except (json.JSONDecodeError, TypeError):
            config = {}
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "organization_name": self.organization.name if self.organization else None,
            "order_id": self.order_id,
            "user_id": self.user_id,
            "worker_id": self.worker_id,
            "worker_name": self.worker.name if self.worker else None,
            "template_id": self.template_id,
            "template_key": self.template.key if self.template else None,
            "service_plan_id": self.service_plan_id,
            "service_plan_name": self.service_plan.name if self.service_plan else None,
            "status": self.status,
            "deployment_name": self.deployment_name,
            "channel_type": self.channel_type,
            "config": config,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "suspended_at": self.suspended_at.isoformat() if self.suspended_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class KnowledgeBase(db.Model):
    __tablename__ = "knowledge_bases"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deployment_id = db.Column(db.Integer, db.ForeignKey("deployments.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), default="")
    status = db.Column(db.String(20), default="draft")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    published_at = db.Column(db.DateTime, nullable=True)

    deployment = db.relationship("Deployment", backref="knowledge_bases", lazy=True)
    documents = db.relationship("KnowledgeDocument", backref="knowledge_base", lazy=True)

    def to_dict(self):
        published_documents = [doc for doc in self.documents if doc.status == "published"]
        return {
            "id": self.id,
            "deployment_id": self.deployment_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "document_count": len(self.documents),
            "published_document_count": len(published_documents),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


class KnowledgeDocument(db.Model):
    __tablename__ = "knowledge_documents"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    knowledge_base_id = db.Column(db.Integer, db.ForeignKey("knowledge_bases.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    doc_type = db.Column(db.String(30), default="faq")
    source_name = db.Column(db.String(160), default="")
    content = db.Column(db.Text, nullable=False)
    char_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="draft")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "title": self.title,
            "doc_type": self.doc_type,
            "source_name": self.source_name,
            "content_preview": (self.content or "")[:160],
            "char_count": self.char_count,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ConversationSession(db.Model):
    __tablename__ = "conversation_sessions"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deployment_id = db.Column(db.Integer, db.ForeignKey("deployments.id"), nullable=False)
    visitor_name = db.Column(db.String(120), default="")
    visitor_contact = db.Column(db.String(160), default="")
    channel_type = db.Column(db.String(30), default="web_widget")
    status = db.Column(db.String(30), default="open")
    last_confidence = db.Column(db.Numeric(4, 3), nullable=True)
    needs_handoff = db.Column(db.Boolean, default=False)
    handoff_reason = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    deployment = db.relationship("Deployment", backref="conversation_sessions", lazy=True)
    messages = db.relationship("ConversationMessage", backref="session", lazy=True)
    handoff_tickets = db.relationship("HandoffTicket", backref="session", lazy=True)

    def to_dict(self, include_messages=False):
        data = {
            "id": self.id,
            "deployment_id": self.deployment_id,
            "visitor_name": self.visitor_name,
            "visitor_contact": self.visitor_contact,
            "channel_type": self.channel_type,
            "status": self.status,
            "last_confidence": float(self.last_confidence) if self.last_confidence is not None else None,
            "needs_handoff": self.needs_handoff,
            "handoff_reason": self.handoff_reason,
            "message_count": len(self.messages),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_messages:
            data["messages"] = [message.to_dict() for message in self.messages]
        return data


class ConversationMessage(db.Model):
    __tablename__ = "conversation_messages"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey("conversation_sessions.id"), nullable=False)
    role = db.Column(db.String(20), default="user")
    content = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.Numeric(4, 3), nullable=True)
    risk_level = db.Column(db.String(20), default="low")
    source_refs_json = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        try:
            source_refs = json.loads(self.source_refs_json or "[]")
        except (json.JSONDecodeError, TypeError):
            source_refs = []
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "confidence": float(self.confidence) if self.confidence is not None else None,
            "risk_level": self.risk_level,
            "source_refs": source_refs,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class HandoffTicket(db.Model):
    __tablename__ = "handoff_tickets"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deployment_id = db.Column(db.Integer, db.ForeignKey("deployments.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("conversation_sessions.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticket_no = db.Column(db.String(40), unique=True, nullable=False)
    status = db.Column(db.String(20), default="open")
    reason = db.Column(db.String(255), default="")
    summary = db.Column(db.Text, default="")
    request_source = db.Column(db.String(20), default="system")
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    deployment = db.relationship("Deployment", backref="handoff_tickets", lazy=True)
    user = db.relationship("User", backref="handoff_tickets", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "deployment_id": self.deployment_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "ticket_no": self.ticket_no,
            "status": self.status,
            "reason": self.reason,
            "summary": self.summary,
            "request_source": self.request_source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class UsageRecord(db.Model):
    __tablename__ = "usage_records"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deployment_id = db.Column(db.Integer, db.ForeignKey("deployments.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("conversation_sessions.id"), nullable=True)
    metric_type = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), default=1)
    unit = db.Column(db.String(20), default="count")
    meta_json = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    deployment = db.relationship("Deployment", backref="usage_records", lazy=True)

    def to_dict(self):
        try:
            meta = json.loads(self.meta_json or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return {
            "id": self.id,
            "deployment_id": self.deployment_id,
            "session_id": self.session_id,
            "metric_type": self.metric_type,
            "quantity": float(self.quantity) if self.quantity is not None else 0.0,
            "unit": self.unit,
            "meta": meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
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
