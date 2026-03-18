"""订单、支付、评价、收藏、消息路由"""
import datetime
from flask import Blueprint, request, jsonify
from extensions import db
from models import (Order, Worker, Payment, Review, Message,
                    Favorite, ServicePlan, ORDER_TRANSITIONS)
from utils.auth import get_current_user, require_admin
from utils.helpers import generate_order_no, generate_payment_no
from services.messages import send_message

bp = Blueprint("orders", __name__)


# ===== 订单 =====

@bp.route("/api/orders", methods=["POST"])
def create_order():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供JSON数据"}), 400

    worker_id = data.get("worker_id")
    duration_hours = data.get("duration_hours")
    service_plan_id = data.get("service_plan_id")
    remark = (data.get("remark") or "").strip()

    if not worker_id:
        return jsonify({"error": "请选择员工"}), 400

    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "数字员工不存在"}), 404
    if worker.status == "offline":
        return jsonify({"error": "该数字员工当前不可用"}), 400

    service_plan = None
    order_type = "rental"
    if service_plan_id or worker.worker_type == "agent_service":
        if not service_plan_id:
            return jsonify({"error": "该机器人需选择服务套餐"}), 400
        service_plan = ServicePlan.query.filter_by(
            id=service_plan_id, worker_id=worker.id, is_active=True
        ).first()
        if not service_plan:
            return jsonify({"error": "服务套餐不存在或已下架"}), 400
        duration_hours = service_plan.default_duration_hours
        total_amount = float(service_plan.price)
        order_type = "agent_deployment"
    else:
        if duration_hours is None:
            return jsonify({"error": "请选择租赁时长"}), 400
        try:
            duration_hours = int(duration_hours)
        except (ValueError, TypeError):
            return jsonify({"error": "租赁时长必须为数字"}), 400
        if duration_hours < 1 or duration_hours > 8760:
            return jsonify({"error": "租赁时长应在1-8760小时之间"}), 400
        total_amount = round(float(worker.hourly_rate) * duration_hours, 2)

    order = Order(
        order_no=generate_order_no(),
        user_id=user.id,
        worker_id=worker.id,
        service_plan_id=service_plan.id if service_plan else None,
        duration_hours=duration_hours,
        total_amount=total_amount,
        order_type=order_type,
        status="pending",
        remark=remark,
    )
    db.session.add(order)
    worker.total_orders += 1
    db.session.commit()

    return jsonify({"message": "下单成功", "order": order.to_dict()}), 201


@bp.route("/api/orders", methods=["GET"])
def get_my_orders():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    per_page = min(per_page, 50)
    status = request.args.get("status", type=str)

    query = Order.query.filter_by(user_id=user.id)
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(Order.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "orders": [o.to_dict() for o in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/orders/<int:order_id>", methods=["GET"])
def get_order_detail(order_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "无权查看此订单"}), 403

    return jsonify({"order": order.to_dict()}), 200


@bp.route("/api/orders/<int:order_id>/cancel", methods=["POST"])
def cancel_order(order_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "无权操作此订单"}), 403
    if "cancelled" not in ORDER_TRANSITIONS.get(order.status, []):
        return jsonify({"error": "当前状态无法取消"}), 400

    order.status = "cancelled"
    order.cancelled_at = datetime.datetime.utcnow()
    send_message(user.id, "订单已取消",
                 f"订单 {order.order_no} 已取消",
                 "order", order.id)
    db.session.commit()

    return jsonify({"message": "订单已取消", "order": order.to_dict()}), 200


@bp.route("/api/orders/<int:order_id>/pay", methods=["POST"])
def pay_order(order_id):
    """模拟支付（开发环境）"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "无权操作此订单"}), 403

    # 幂等性：已支付状态 + 有成功支付记录，直接返回
    if order.status == "paid":
        existing = Payment.query.filter_by(order_id=order.id, status="success").first()
        if existing:
            return jsonify({"message": "已支付", "order": order.to_dict(), "payment": existing.to_dict()}), 200

    if "paid" not in ORDER_TRANSITIONS.get(order.status, []):
        return jsonify({"error": f"当前状态({order.status})无法支付"}), 400

    data = request.get_json(silent=True) or {}
    method = data.get("method", "mock")
    if method not in ("mock", "alipay", "wechat"):
        method = "mock"

    now = datetime.datetime.utcnow()
    payment = Payment(
        payment_no=generate_payment_no(),
        order_id=order.id,
        user_id=user.id,
        amount=order.total_amount,
        method=method,
        status="success",
        paid_at=now,
    )
    order.status = "paid"
    order.paid_at = now

    db.session.add(payment)
    send_message(user.id, "支付成功",
                 f"订单 {order.order_no} 支付成功，金额 ￥{float(order.total_amount):.2f}",
                 "order", order.id)
    db.session.commit()

    return jsonify({
        "message": "支付成功",
        "order": order.to_dict(),
        "payment": payment.to_dict(),
    }), 200


@bp.route("/api/orders/<int:order_id>/activate", methods=["POST"])
def activate_order(order_id):
    """开始服务（paid → active）"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "无权操作此订单"}), 403
    if "active" not in ORDER_TRANSITIONS.get(order.status, []):
        return jsonify({"error": f"当前状态({order.status})无法激活服务"}), 400

    order.status = "active"
    order.activated_at = datetime.datetime.utcnow()
    send_message(user.id, "服务已开始",
                 f"订单 {order.order_no} 的服务已开始",
                 "order", order.id)
    db.session.commit()

    return jsonify({"message": "服务已开始", "order": order.to_dict()}), 200


@bp.route("/api/orders/<int:order_id>/complete", methods=["POST"])
def complete_order(order_id):
    """确认完成（active → completed）"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "无权操作此订单"}), 403
    if "completed" not in ORDER_TRANSITIONS.get(order.status, []):
        return jsonify({"error": f"当前状态({order.status})无法完成"}), 400

    order.status = "completed"
    order.completed_at = datetime.datetime.utcnow()
    send_message(user.id, "服务已完成",
                 f"订单 {order.order_no} 已完成，快去评价吧！",
                 "order", order.id)
    db.session.commit()

    return jsonify({"message": "服务已完成", "order": order.to_dict()}), 200


@bp.route("/api/orders/<int:order_id>/refund", methods=["POST"])
def refund_order(order_id):
    """申请退款（paid/active → refunded）"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "无权操作此订单"}), 403
    if "refunded" not in ORDER_TRANSITIONS.get(order.status, []):
        return jsonify({"error": f"当前状态({order.status})无法退款"}), 400

    now = datetime.datetime.utcnow()
    order.status = "refunded"
    order.refunded_at = now

    payment = Payment.query.filter_by(order_id=order.id, status="success").first()
    if payment:
        payment.status = "refunded"
        payment.refunded_at = now

    send_message(user.id, "退款成功",
                 f"订单 {order.order_no} 已退款，金额 ￥{float(order.total_amount):.2f}",
                 "order", order.id)
    db.session.commit()

    return jsonify({"message": "退款成功", "order": order.to_dict()}), 200


@bp.route("/api/orders/<int:order_id>/payments", methods=["GET"])
def get_order_payments(order_id):
    """查看订单的支付记录"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "无权查看"}), 403

    payments = Payment.query.filter_by(order_id=order.id).order_by(Payment.created_at.desc()).all()
    return jsonify({"payments": [p.to_dict() for p in payments]}), 200


@bp.route("/api/orders/cancel-expired", methods=["POST"])
def cancel_expired_orders():
    """定时任务：取消超时未支付订单（创建超过30分钟仍为pending）"""
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=30)
    expired = Order.query.filter(
        Order.status == "pending",
        Order.created_at < cutoff,
    ).all()

    count = 0
    for order in expired:
        order.status = "cancelled"
        order.cancelled_at = datetime.datetime.utcnow()
        send_message(order.user_id, "订单已超时取消",
                     f"订单 {order.order_no} 因超时未支付已自动取消",
                     "order", order.id)
        count += 1

    db.session.commit()
    return jsonify({"message": f"已取消 {count} 个超时订单", "cancelled_count": count}), 200


# ===== 评价 =====

@bp.route("/api/orders/<int:order_id>/review", methods=["POST"])
def create_review(order_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "无权评价此订单"}), 403
    if order.status != "completed":
        return jsonify({"error": "只能评价已完成的订单"}), 400

    existing = Review.query.filter_by(order_id=order.id).first()
    if existing:
        return jsonify({"error": "该订单已评价"}), 400

    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    content = (data.get("content") or "").strip()

    if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({"error": "评分为1-5的整数"}), 400

    review = Review(
        order_id=order.id,
        user_id=user.id,
        worker_id=order.worker_id,
        rating=rating,
        content=content,
    )
    db.session.add(review)

    worker = Worker.query.get(order.worker_id)
    worker_name = worker.name if worker else "员工"
    if worker:
        avg = db.session.query(db.func.avg(Review.rating)).filter_by(worker_id=worker.id).scalar()
        if avg is not None:
            worker.rating = round(float(avg), 1)

    send_message(user.id, "评价已提交",
                 f"您对「{worker_name}」的评价已提交，感谢反馈！",
                 "order", order.id)
    db.session.commit()

    return jsonify({"message": "评价成功", "review": review.to_dict()}), 201


# ===== 站内消息 =====

@bp.route("/api/messages", methods=["GET"])
def get_messages():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 50)
    is_read = request.args.get("is_read", type=str)

    query = Message.query.filter_by(user_id=user.id)
    if is_read == "true":
        query = query.filter_by(is_read=True)
    elif is_read == "false":
        query = query.filter_by(is_read=False)
    query = query.order_by(Message.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    unread_count = Message.query.filter_by(user_id=user.id, is_read=False).count()

    return jsonify({
        "messages": [m.to_dict() for m in pagination.items],
        "total": pagination.total,
        "unread_count": unread_count,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/messages/<int:msg_id>/read", methods=["POST"])
def mark_message_read(msg_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    msg = Message.query.get(msg_id)
    if not msg or msg.user_id != user.id:
        return jsonify({"error": "消息不存在"}), 404

    msg.is_read = True
    db.session.commit()
    return jsonify({"message": "已读"}), 200


@bp.route("/api/messages/read-all", methods=["POST"])
def mark_all_read():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    Message.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"message": "全部已读"}), 200


@bp.route("/api/messages/unread-count", methods=["GET"])
def unread_count():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    count = Message.query.filter_by(user_id=user.id, is_read=False).count()
    return jsonify({"unread_count": count}), 200


# ===== 收藏 =====

@bp.route("/api/favorites", methods=["GET"])
def get_favorites():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    favs = Favorite.query.filter_by(user_id=user.id).order_by(Favorite.created_at.desc()).all()
    return jsonify({"favorites": [f.to_dict() for f in favs]}), 200


@bp.route("/api/favorites/<int:worker_id>", methods=["POST"])
def add_favorite(worker_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "员工不存在"}), 404

    existing = Favorite.query.filter_by(user_id=user.id, worker_id=worker_id).first()
    if existing:
        return jsonify({"message": "已收藏", "favorite": existing.to_dict()}), 200

    fav = Favorite(user_id=user.id, worker_id=worker_id)
    db.session.add(fav)
    db.session.commit()
    return jsonify({"message": "收藏成功", "favorite": fav.to_dict()}), 201


@bp.route("/api/favorites/<int:worker_id>", methods=["DELETE"])
def remove_favorite(worker_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    fav = Favorite.query.filter_by(user_id=user.id, worker_id=worker_id).first()
    if not fav:
        return jsonify({"error": "未收藏"}), 404

    db.session.delete(fav)
    db.session.commit()
    return jsonify({"message": "已取消收藏"}), 200


@bp.route("/api/favorites/<int:worker_id>/check", methods=["GET"])
def check_favorite(worker_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    exists = Favorite.query.filter_by(user_id=user.id, worker_id=worker_id).first() is not None
    return jsonify({"is_favorited": exists}), 200
