"""管理后台路由"""
import datetime
from flask import Blueprint, request, jsonify
from extensions import db
from models import (User, Worker, Category, Order, ROLES,
                    ORDER_STATUSES, ORDER_TRANSITIONS, AgentTemplate,
                    ServicePlan, Deployment, AuditLog)
from utils.auth import require_admin
from services.messages import send_message

bp = Blueprint("admin", __name__)


@bp.route("/api/admin/stats", methods=["GET"])
def admin_stats():
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    total_users = User.query.count()
    total_workers = Worker.query.count()
    total_orders = Order.query.count()
    total_revenue = db.session.query(db.func.coalesce(db.func.sum(Order.total_amount), 0)).filter(
        Order.status.in_(["paid", "active", "completed"])
    ).scalar()
    pending_orders = Order.query.filter_by(status="pending").count()
    active_orders = Order.query.filter_by(status="active").count()
    online_workers = Worker.query.filter_by(status="online").count()

    today = datetime.datetime.utcnow().date()
    daily_orders = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        start = datetime.datetime.combine(d, datetime.time.min)
        end = datetime.datetime.combine(d, datetime.time.max)
        count = Order.query.filter(Order.created_at.between(start, end)).count()
        revenue = db.session.query(db.func.coalesce(db.func.sum(Order.total_amount), 0)).filter(
            Order.created_at.between(start, end)
        ).scalar()
        daily_orders.append({"date": d.isoformat(), "count": count, "revenue": float(revenue)})

    cat_stats = db.session.query(
        Category.name, db.func.count(Order.id)
    ).join(Worker, Worker.category_id == Category.id).join(
        Order, Order.worker_id == Worker.id
    ).group_by(Category.name).all()

    return jsonify({
        "total_users": total_users,
        "total_workers": total_workers,
        "total_orders": total_orders,
        "total_revenue": float(total_revenue),
        "pending_orders": pending_orders,
        "active_orders": active_orders,
        "online_workers": online_workers,
        "daily_orders": daily_orders,
        "category_stats": [{"name": name, "count": count} for name, count in cat_stats],
    }), 200


@bp.route("/api/admin/users", methods=["GET"])
def admin_list_users():
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)
    keyword = request.args.get("keyword", "", type=str).strip()
    role = request.args.get("role", type=str)

    query = User.query
    if keyword:
        like_kw = f"%{keyword}%"
        query = query.filter(db.or_(User.username.like(like_kw), User.email.like(like_kw)))
    if role:
        query = query.filter_by(role=role)
    query = query.order_by(User.id.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "users": [u.to_dict() for u in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/admin/users/<int:user_id>", methods=["PUT"])
def admin_update_user(user_id):
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404

    data = request.get_json(silent=True) or {}

    if "role" in data and data["role"] in ROLES:
        if (admin.role or "user") != "admin" and data["role"] == "admin":
            return jsonify({"error": "仅超管可授予admin角色"}), 403
        user.role = data["role"]
    if "is_active" in data:
        if user.id == admin.id:
            return jsonify({"error": "不能禁用自己"}), 400
        user.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify({"message": "更新成功", "user": user.to_dict()}), 200


@bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def admin_delete_user(user_id):
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403
    if (admin.role or "user") != "admin":
        return jsonify({"error": "仅超管可删除用户"}), 403
    if user_id == admin.id:
        return jsonify({"error": "不能删除自己"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404

    order_count = Order.query.filter_by(user_id=user_id).count()
    if order_count > 0:
        user.is_active = False
        user.username = f"_deleted_{user.id}_{user.username}"
        db.session.commit()
        return jsonify({"message": "用户已禁用（存在关联订单，无法物理删除）"}), 200

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "删除成功"}), 200


@bp.route("/api/admin/workers", methods=["GET"])
def admin_list_workers():
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)
    keyword = request.args.get("keyword", "", type=str).strip()
    category_id = request.args.get("category_id", type=int)
    status = request.args.get("status", type=str)
    worker_type = request.args.get("worker_type", type=str)

    query = Worker.query
    if keyword:
        like_kw = f"%{keyword}%"
        query = query.filter(db.or_(Worker.name.like(like_kw), Worker.skills.like(like_kw)))
    if category_id:
        query = query.filter_by(category_id=category_id)
    if status:
        query = query.filter_by(status=status)
    if worker_type:
        query = query.filter_by(worker_type=worker_type)
    query = query.order_by(Worker.id.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "workers": [w.to_dict() for w in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/admin/workers", methods=["POST"])
def admin_create_worker():
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    category_id = data.get("category_id")
    hourly_rate = data.get("hourly_rate")

    if not name or not category_id or hourly_rate is None:
        return jsonify({"error": "名称、分类和单价为必填"}), 400

    cat = Category.query.get(category_id)
    if not cat:
        return jsonify({"error": "分类不存在"}), 400

    worker = Worker(
        name=name,
        category_id=category_id,
        avatar_icon=data.get("avatar_icon", "mdi:robot-happy-outline"),
        avatar_gradient_from=data.get("avatar_gradient_from", "#6A0DAD"),
        avatar_gradient_to=data.get("avatar_gradient_to", "#00D2FF"),
        level=data.get("level", 5),
        skills=data.get("skills", ""),
        description=data.get("description", ""),
        hourly_rate=hourly_rate,
        billing_unit=data.get("billing_unit", "时薪"),
        status=data.get("status", "online"),
        worker_type=data.get("worker_type", "general"),
        delivery_mode=data.get("delivery_mode", "manual_service"),
        template_key=data.get("template_key"),
    )
    db.session.add(worker)
    db.session.commit()
    return jsonify({"message": "创建成功", "worker": worker.to_dict()}), 201


@bp.route("/api/admin/workers/<int:worker_id>", methods=["PUT"])
def admin_update_worker(worker_id):
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "数字员工不存在"}), 404

    data = request.get_json(silent=True) or {}
    for field in ["name", "avatar_icon", "avatar_gradient_from", "avatar_gradient_to",
                  "skills", "description", "billing_unit", "status",
                  "worker_type", "delivery_mode", "template_key"]:
        if field in data:
            setattr(worker, field, data[field])
    if "category_id" in data:
        cat = Category.query.get(data["category_id"])
        if not cat:
            return jsonify({"error": "分类不存在"}), 400
        worker.category_id = data["category_id"]
    if "level" in data:
        worker.level = int(data["level"])
    if "hourly_rate" in data:
        worker.hourly_rate = data["hourly_rate"]

    db.session.commit()
    return jsonify({"message": "更新成功", "worker": worker.to_dict()}), 200


@bp.route("/api/admin/workers/<int:worker_id>", methods=["DELETE"])
def admin_delete_worker(worker_id):
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "数字员工不存在"}), 404

    has_orders = Order.query.filter_by(worker_id=worker_id).first()
    if has_orders:
        worker.status = "offline"
        worker.name = f"[已删除] {worker.name}" if not worker.name.startswith("[已删除]") else worker.name
        db.session.commit()
        return jsonify({"message": "该员工有历史订单，已下架处理"}), 200

    db.session.delete(worker)
    db.session.commit()
    return jsonify({"message": "删除成功"}), 200


@bp.route("/api/admin/agent-templates", methods=["GET"])
def admin_list_agent_templates():
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    templates = AgentTemplate.query.order_by(AgentTemplate.id.desc()).all()
    return jsonify({"agent_templates": [t.to_dict() for t in templates]}), 200


@bp.route("/api/admin/service-plans", methods=["GET"])
def admin_list_service_plans():
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    worker_id = request.args.get("worker_id", type=int)
    query = ServicePlan.query
    if worker_id:
        query = query.filter_by(worker_id=worker_id)
    plans = query.order_by(ServicePlan.id.desc()).all()
    return jsonify({"service_plans": [p.to_dict() for p in plans]}), 200


@bp.route("/api/admin/service-plans", methods=["POST"])
def admin_create_service_plan():
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    slug = (data.get("slug") or "").strip()
    name = (data.get("name") or "").strip()
    price = data.get("price")

    if not worker_id or not slug or not name or price is None:
        return jsonify({"error": "worker_id、slug、name、price 为必填"}), 400

    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "数字员工不存在"}), 404

    existing = ServicePlan.query.filter_by(worker_id=worker_id, slug=slug).first()
    if existing:
        return jsonify({"error": "该套餐 slug 已存在"}), 409

    plan = ServicePlan(
        worker_id=worker_id,
        slug=slug,
        name=name,
        description=(data.get("description") or "").strip(),
        billing_cycle=(data.get("billing_cycle") or "monthly").strip() or "monthly",
        price=price,
        currency=(data.get("currency") or "CNY").strip() or "CNY",
        included_conversations=data.get("included_conversations", 500),
        max_handoffs=data.get("max_handoffs", 50),
        channel_limit=data.get("channel_limit", 1),
        seat_limit=data.get("seat_limit", 1),
        default_duration_hours=data.get("default_duration_hours", 720),
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(plan)
    db.session.commit()
    return jsonify({"message": "套餐创建成功", "service_plan": plan.to_dict()}), 201


@bp.route("/api/admin/service-plans/<int:plan_id>", methods=["PUT"])
def admin_update_service_plan(plan_id):
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    plan = ServicePlan.query.get(plan_id)
    if not plan:
        return jsonify({"error": "套餐不存在"}), 404

    data = request.get_json(silent=True) or {}
    for field in ["name", "description", "billing_cycle", "currency"]:
        if field in data:
            setattr(plan, field, (data.get(field) or "").strip())
    for field in ["included_conversations", "max_handoffs", "channel_limit",
                  "seat_limit", "default_duration_hours"]:
        if field in data:
            setattr(plan, field, int(data[field]))
    if "price" in data:
        plan.price = data["price"]
    if "is_active" in data:
        plan.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify({"message": "套餐更新成功", "service_plan": plan.to_dict()}), 200


@bp.route("/api/admin/deployments", methods=["GET"])
def admin_list_deployments():
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    status = request.args.get("status", type=str)
    query = Deployment.query
    if status:
        query = query.filter_by(status=status)
    deployments = query.order_by(Deployment.created_at.desc()).all()
    return jsonify({"deployments": [d.to_dict() for d in deployments]}), 200


@bp.route("/api/admin/audit-logs", methods=["GET"])
def admin_list_audit_logs():
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    deployment_id = request.args.get("deployment_id", type=int)
    action_type = request.args.get("action_type", type=str)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)

    query = AuditLog.query
    if deployment_id:
        query = query.filter_by(deployment_id=deployment_id)
    if action_type:
        query = query.filter_by(action_type=action_type)

    pagination = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return jsonify({
        "audit_logs": [log.to_dict() for log in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/admin/orders", methods=["GET"])
def admin_list_orders():
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)
    status = request.args.get("status", type=str)
    keyword = request.args.get("keyword", "", type=str).strip()

    query = Order.query
    if status:
        query = query.filter_by(status=status)
    if keyword:
        like_kw = f"%{keyword}%"
        query = query.filter(db.or_(
            Order.order_no.like(like_kw),
            Order.remark.like(like_kw),
        ))
    query = query.order_by(Order.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    orders = []
    for o in pagination.items:
        d = o.to_dict()
        d["username"] = o.user.username if o.user else None
        orders.append(d)

    return jsonify({
        "orders": orders,
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/admin/orders/<int:order_id>/status", methods=["PUT"])
def admin_update_order_status(order_id):
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in ORDER_STATUSES:
        return jsonify({"error": f"无效状态，可选: {', '.join(ORDER_STATUSES)}"}), 400

    allowed = ORDER_TRANSITIONS.get(order.status, [])
    if new_status not in allowed:
        return jsonify({
            "error": f"状态流转不允许: {order.status} → {new_status}，"
                     f"当前状态仅可转为: {', '.join(allowed) if allowed else '无(终态)'}",
        }), 400

    now = datetime.datetime.utcnow()
    order.status = new_status
    ts_map = {
        "paid": "paid_at", "active": "activated_at",
        "completed": "completed_at", "cancelled": "cancelled_at",
        "refunded": "refunded_at",
    }
    if new_status in ts_map:
        setattr(order, ts_map[new_status], now)

    status_labels = {
        "paid": "已支付", "active": "服务中", "completed": "已完成",
        "cancelled": "已取消", "refunded": "已退款",
    }
    label = status_labels.get(new_status, new_status)
    send_message(order.user_id, f"订单状态变更: {label}",
                 f"订单 {order.order_no} 状态已更新为「{label}」",
                 "order", order.id)
    db.session.commit()
    return jsonify({"message": "状态已更新", "order": order.to_dict()}), 200
