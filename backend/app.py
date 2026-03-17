import os
import datetime
import re
import logging
import json
import traceback

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bcrypt
import jwt

# ===== 结构化日志 =====


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("xiaxia")

# ===== Flask 应用 =====

app = Flask(__name__)
CORS(app)

DB_USER = os.environ.get("DB_USER", "xiaxia")
DB_PASS = os.environ.get("DB_PASS", "xiaxia_secret_2026")
DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "xiaxia_factory")
JWT_SECRET = os.environ.get("JWT_SECRET", "xiaxia-jwt-secret-key-2026")
ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ===== 限流 =====

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[os.environ.get("RATE_LIMIT_DEFAULT", "60/minute")],
    storage_uri="memory://",
)

# ===== 安全响应头 + 请求日志 =====


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # 请求日志
    duration = ""
    if hasattr(g, "request_start"):
        duration = f" {(datetime.datetime.utcnow() - g.request_start).total_seconds()*1000:.0f}ms"
    logger.info(f"{request.method} {request.path} → {response.status_code}{duration}")
    return response


@app.before_request
def before_request_hook():
    g.request_start = datetime.datetime.utcnow()

# ===== 全局异常处理 + 告警 =====


def send_alert(title, detail=""):
    """发送异常告警到 Webhook（钉钉/飞书/Slack）"""
    if not ALERT_WEBHOOK_URL:
        return
    try:
        import urllib.request
        payload = json.dumps({
            "msgtype": "text",
            "text": {"content": f"[虾虾工厂告警] {title}\n{detail}"}
        }).encode("utf-8")
        req = urllib.request.Request(ALERT_WEBHOOK_URL, data=payload,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        logger.warning("告警发送失败")


@app.errorhandler(500)
def handle_500(e):
    logger.error(f"Internal Server Error: {e}", exc_info=True)
    send_alert("500 Internal Server Error", f"{request.method} {request.path}\n{e}")
    return jsonify({"error": "服务器内部错误"}), 500


@app.errorhandler(429)
def handle_429(e):
    return jsonify({"error": "请求过于频繁，请稍后再试"}), 429


# ===== 数据模型 =====

ROLES = ["user", "operator", "admin"]


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
    billing_unit = db.Column(db.String(20), default="时薪")  # 时薪/月租/按件计费
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
            "status": self.status,
            "rating": float(self.rating) if self.rating else 5.0,
            "total_orders": self.total_orders,
        }


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


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_no = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    duration_hours = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default="pending")
    remark = db.Column(db.Text, default="")
    paid_at = db.Column(db.DateTime, nullable=True)
    activated_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    refunded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

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


# ===== 工具函数 =====

def create_token(user):
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role or "user",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        return None
    user = User.query.get(payload["user_id"])
    if user and not user.is_active:
        return None
    return user


def require_admin():
    """返回当前用户（如果是 admin/operator），否则返回 None"""
    user = get_current_user()
    if not user:
        return None
    if (user.role or "user") not in ("admin", "operator"):
        return None
    return user


def generate_order_no():
    now = datetime.datetime.utcnow()
    import random
    return now.strftime("XF%Y%m%d%H%M%S") + str(random.randint(1000, 9999))


def generate_payment_no():
    now = datetime.datetime.utcnow()
    import random
    return now.strftime("PAY%Y%m%d%H%M%S") + str(random.randint(100000, 999999))


def send_message(user_id, title, content="", msg_type="system", related_order_id=None):
    """创建站内消息"""
    msg = Message(
        user_id=user_id,
        title=title,
        content=content,
        msg_type=msg_type,
        related_order_id=related_order_id,
    )
    db.session.add(msg)
    return msg


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


# ===== 用户 API =====

@app.route("/api/register", methods=["POST"])
@limiter.limit(os.environ.get("RATE_LIMIT_AUTH", "10/minute"))
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供JSON数据"}), 400

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not username or not email or not password:
        return jsonify({"error": "用户名、邮箱和密码为必填项"}), 400
    if len(username) < 2 or len(username) > 80:
        return jsonify({"error": "用户名长度应在2-80个字符之间"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "邮箱格式不正确"}), 400
    if len(password) < 8:
        return jsonify({"error": "密码至少需要8位"}), 400
    if password != confirm_password:
        return jsonify({"error": "两次密码输入不一致"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "用户名已被注册"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "邮箱已被注册"}), 409

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(username=username, email=email, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()

    token = create_token(user)
    return jsonify({"message": "注册成功", "token": token, "user": user.to_dict()}), 201


@app.route("/api/login", methods=["POST"])
@limiter.limit(os.environ.get("RATE_LIMIT_AUTH", "10/minute"))
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供JSON数据"}), 400

    login_id = (data.get("login_id") or "").strip()
    password = data.get("password") or ""

    if not login_id or not password:
        return jsonify({"error": "请输入用户名/邮箱和密码"}), 400

    user = User.query.filter(
        (User.username == login_id) | (User.email == login_id)
    ).first()

    if not user or not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        return jsonify({"error": "用户名/邮箱或密码错误"}), 401

    if not user.is_active:
        return jsonify({"error": "账号已被禁用，请联系管理员"}), 403

    token = create_token(user)
    return jsonify({"message": "登录成功", "token": token, "user": user.to_dict()}), 200


@app.route("/api/profile", methods=["GET"])
def profile():
    user = get_current_user()
    if not user:
        return jsonify({"error": "未登录或登录已过期"}), 401
    return jsonify({"user": user.to_dict()}), 200


# ===== 分类 API =====

@app.route("/api/categories", methods=["GET"])
def get_categories():
    cats = Category.query.order_by(Category.sort_order).all()
    return jsonify({"categories": [c.to_dict() for c in cats]}), 200


# ===== 数字员工 API =====

@app.route("/api/workers", methods=["GET"])
def get_workers():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 12, type=int)
    per_page = min(per_page, 50)

    category_id = request.args.get("category_id", type=int)
    status = request.args.get("status", type=str)
    keyword = request.args.get("keyword", "", type=str).strip()
    sort_by = request.args.get("sort_by", "total_orders", type=str)

    query = Worker.query

    if category_id:
        query = query.filter(Worker.category_id == category_id)
    if status:
        query = query.filter(Worker.status == status)
    if keyword:
        like_kw = f"%{keyword}%"
        query = query.filter(
            db.or_(
                Worker.name.like(like_kw),
                Worker.skills.like(like_kw),
                Worker.description.like(like_kw),
            )
        )

    if sort_by == "price_asc":
        query = query.order_by(Worker.hourly_rate.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Worker.hourly_rate.desc())
    elif sort_by == "rating":
        query = query.order_by(Worker.rating.desc())
    elif sort_by == "level":
        query = query.order_by(Worker.level.desc())
    else:
        query = query.order_by(Worker.total_orders.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "workers": [w.to_brief_dict() for w in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@app.route("/api/workers/<int:worker_id>", methods=["GET"])
def get_worker_detail(worker_id):
    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "数字员工不存在"}), 404
    return jsonify({"worker": worker.to_dict()}), 200


# ===== 订单 API =====

@app.route("/api/orders", methods=["POST"])
def create_order():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供JSON数据"}), 400

    worker_id = data.get("worker_id")
    duration_hours = data.get("duration_hours")
    remark = (data.get("remark") or "").strip()

    if not worker_id or not duration_hours:
        return jsonify({"error": "请选择员工和租赁时长"}), 400

    try:
        duration_hours = int(duration_hours)
    except (ValueError, TypeError):
        return jsonify({"error": "租赁时长必须为数字"}), 400
    if duration_hours < 1 or duration_hours > 8760:
        return jsonify({"error": "租赁时长应在1-8760小时之间"}), 400

    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "数字员工不存在"}), 404
    if worker.status == "offline":
        return jsonify({"error": "该数字员工当前不可用"}), 400

    total_amount = round(float(worker.hourly_rate) * duration_hours, 2)

    order = Order(
        order_no=generate_order_no(),
        user_id=user.id,
        worker_id=worker.id,
        duration_hours=duration_hours,
        total_amount=total_amount,
        status="pending",
        remark=remark,
    )
    db.session.add(order)
    worker.total_orders += 1
    db.session.commit()

    return jsonify({"message": "下单成功", "order": order.to_dict()}), 201


@app.route("/api/orders", methods=["GET"])
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


@app.route("/api/orders/<int:order_id>", methods=["GET"])
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


@app.route("/api/orders/<int:order_id>/cancel", methods=["POST"])
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


@app.route("/api/orders/<int:order_id>/pay", methods=["POST"])
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


@app.route("/api/orders/<int:order_id>/activate", methods=["POST"])
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
    db.session.commit()

    return jsonify({"message": "服务已开始", "order": order.to_dict()}), 200


@app.route("/api/orders/<int:order_id>/complete", methods=["POST"])
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


@app.route("/api/orders/<int:order_id>/refund", methods=["POST"])
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

    # 标记支付记录为已退款
    payment = Payment.query.filter_by(order_id=order.id, status="success").first()
    if payment:
        payment.status = "refunded"
        payment.refunded_at = now

    send_message(user.id, "退款成功",
                 f"订单 {order.order_no} 已退款，金额 ￥{float(order.total_amount):.2f}",
                 "order", order.id)
    db.session.commit()

    return jsonify({"message": "退款成功", "order": order.to_dict()}), 200


@app.route("/api/orders/<int:order_id>/payments", methods=["GET"])
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


@app.route("/api/orders/cancel-expired", methods=["POST"])
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


# ===== 评价 API =====

@app.route("/api/orders/<int:order_id>/review", methods=["POST"])
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

    # 更新员工平均评分
    worker = Worker.query.get(order.worker_id)
    if worker:
        avg = db.session.query(db.func.avg(Review.rating)).filter_by(worker_id=worker.id).scalar()
        if avg is not None:
            worker.rating = round(float(avg), 1)

    db.session.commit()

    return jsonify({"message": "评价成功", "review": review.to_dict()}), 201


@app.route("/api/workers/<int:worker_id>/reviews", methods=["GET"])
def get_worker_reviews(worker_id):
    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "员工不存在"}), 404

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    per_page = min(per_page, 50)

    query = Review.query.filter_by(worker_id=worker_id).order_by(Review.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "reviews": [r.to_dict() for r in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


# ===== 站内消息 API =====

@app.route("/api/messages", methods=["GET"])
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


@app.route("/api/messages/<int:msg_id>/read", methods=["POST"])
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


@app.route("/api/messages/read-all", methods=["POST"])
def mark_all_read():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    Message.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"message": "全部已读"}), 200


@app.route("/api/messages/unread-count", methods=["GET"])
def unread_count():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    count = Message.query.filter_by(user_id=user.id, is_read=False).count()
    return jsonify({"unread_count": count}), 200


# ===== 收藏 API =====

@app.route("/api/favorites", methods=["GET"])
def get_favorites():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    favs = Favorite.query.filter_by(user_id=user.id).order_by(Favorite.created_at.desc()).all()
    return jsonify({"favorites": [f.to_dict() for f in favs]}), 200


@app.route("/api/favorites/<int:worker_id>", methods=["POST"])
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


@app.route("/api/favorites/<int:worker_id>", methods=["DELETE"])
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


@app.route("/api/favorites/<int:worker_id>/check", methods=["GET"])
def check_favorite(worker_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    exists = Favorite.query.filter_by(user_id=user.id, worker_id=worker_id).first() is not None
    return jsonify({"is_favorited": exists}), 200


# ===== 推荐 API =====

@app.route("/api/recommendations", methods=["GET"])
def get_recommendations():
    """基于用户历史订单推荐相似分类员工"""
    user = get_current_user()
    limit = request.args.get("limit", 6, type=int)
    limit = min(limit, 20)

    if user:
        # 获取用户历史订单涉及的分类
        ordered_cats = db.session.query(Worker.category_id).join(
            Order, Order.worker_id == Worker.id
        ).filter(Order.user_id == user.id).distinct().all()
        cat_ids = [c[0] for c in ordered_cats]

        # 获取用户已经下过单的员工ID
        ordered_worker_ids = db.session.query(Order.worker_id).filter(
            Order.user_id == user.id
        ).distinct().all()
        exclude_ids = [w[0] for w in ordered_worker_ids]

        if cat_ids:
            # 推荐同分类、未使用过的员工
            query = Worker.query.filter(
                Worker.category_id.in_(cat_ids),
                Worker.status != "offline",
            )
            if exclude_ids:
                query = query.filter(~Worker.id.in_(exclude_ids))
            recs = query.order_by(Worker.rating.desc(), Worker.total_orders.desc()).limit(limit).all()

            # 不足则补充热门员工
            if len(recs) < limit:
                existing_ids = [w.id for w in recs] + exclude_ids
                extra = Worker.query.filter(
                    Worker.status != "offline",
                    ~Worker.id.in_(existing_ids) if existing_ids else True,
                ).order_by(Worker.total_orders.desc()).limit(limit - len(recs)).all()
                recs.extend(extra)

            return jsonify({"recommendations": [w.to_brief_dict() for w in recs], "strategy": "personalized"}), 200

    # 未登录或无历史 → 热门推荐
    hot = Worker.query.filter(Worker.status != "offline").order_by(
        Worker.total_orders.desc(), Worker.rating.desc()
    ).limit(limit).all()
    return jsonify({"recommendations": [w.to_brief_dict() for w in hot], "strategy": "popular"}), 200


# ===== 管理后台 API =====

@app.route("/api/admin/stats", methods=["GET"])
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

    # 最近7天订单趋势
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

    # 分类订单占比
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


@app.route("/api/admin/users", methods=["GET"])
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


@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
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


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
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

    # 有关联订单的用户不能物理删除，改为禁用
    order_count = Order.query.filter_by(user_id=user_id).count()
    if order_count > 0:
        user.is_active = False
        user.username = f"_deleted_{user.id}_{user.username}"
        db.session.commit()
        return jsonify({"message": "用户已禁用（存在关联订单，无法物理删除）"}), 200

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "删除成功"}), 200


@app.route("/api/admin/workers", methods=["GET"])
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

    query = Worker.query
    if keyword:
        like_kw = f"%{keyword}%"
        query = query.filter(db.or_(Worker.name.like(like_kw), Worker.skills.like(like_kw)))
    if category_id:
        query = query.filter_by(category_id=category_id)
    if status:
        query = query.filter_by(status=status)
    query = query.order_by(Worker.id.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "workers": [w.to_dict() for w in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@app.route("/api/admin/workers", methods=["POST"])
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
    )
    db.session.add(worker)
    db.session.commit()
    return jsonify({"message": "创建成功", "worker": worker.to_dict()}), 201


@app.route("/api/admin/workers/<int:worker_id>", methods=["PUT"])
def admin_update_worker(worker_id):
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "数字员工不存在"}), 404

    data = request.get_json(silent=True) or {}
    for field in ["name", "avatar_icon", "avatar_gradient_from", "avatar_gradient_to",
                  "skills", "description", "billing_unit", "status"]:
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


@app.route("/api/admin/workers/<int:worker_id>", methods=["DELETE"])
def admin_delete_worker(worker_id):
    admin = require_admin()
    if not admin:
        return jsonify({"error": "无管理员权限"}), 403

    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "数字员工不存在"}), 404

    # 有关联订单时软删除（下架），否则物理删除
    has_orders = Order.query.filter_by(worker_id=worker_id).first()
    if has_orders:
        worker.status = "offline"
        worker.name = f"[已删除] {worker.name}" if not worker.name.startswith("[已删除]") else worker.name
        db.session.commit()
        return jsonify({"message": "该员工有历史订单，已下架处理"}), 200

    db.session.delete(worker)
    db.session.commit()
    return jsonify({"message": "删除成功"}), 200


@app.route("/api/admin/orders", methods=["GET"])
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


@app.route("/api/admin/orders/<int:order_id>/status", methods=["PUT"])
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
    db.session.commit()
    return jsonify({"message": "状态已更新", "order": order.to_dict()}), 200


@app.route("/api/health", methods=["GET"])
@limiter.exempt
def health():
    result = {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
    # 数据库连通性检查
    try:
        db.session.execute(db.text("SELECT 1"))
        result["database"] = "connected"
    except Exception as e:
        result["status"] = "degraded"
        result["database"] = f"error: {e}"
    return jsonify(result), 200 if result["status"] == "ok" else 503


@app.route("/api/docs", methods=["GET"])
@limiter.exempt
def api_docs():
    """OpenAPI 3.0 规范文档"""
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "虾虾工厂 API",
            "version": "1.0.0",
            "description": "数字员工租赁平台 RESTful API",
        },
        "servers": [{"url": "/api", "description": "API Server"}],
        "components": {
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            }
        },
        "paths": {
            "/register": {"post": {"tags": ["用户"], "summary": "用户注册", "requestBody": {"content": {"application/json": {"schema": {"type": "object", "required": ["username", "email", "password", "confirm_password"], "properties": {"username": {"type": "string"}, "email": {"type": "string"}, "password": {"type": "string"}, "confirm_password": {"type": "string"}}}}}}, "responses": {"201": {"description": "注册成功"}}}},
            "/login": {"post": {"tags": ["用户"], "summary": "用户登录", "requestBody": {"content": {"application/json": {"schema": {"type": "object", "required": ["login_id", "password"], "properties": {"login_id": {"type": "string"}, "password": {"type": "string"}}}}}}, "responses": {"200": {"description": "登录成功"}}}},
            "/profile": {"get": {"tags": ["用户"], "summary": "获取个人信息", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "成功"}}}},
            "/categories": {"get": {"tags": ["分类"], "summary": "分类列表", "responses": {"200": {"description": "成功"}}}},
            "/workers": {"get": {"tags": ["员工"], "summary": "员工列表", "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer"}}, {"name": "per_page", "in": "query", "schema": {"type": "integer"}}, {"name": "category_id", "in": "query", "schema": {"type": "integer"}}, {"name": "status", "in": "query", "schema": {"type": "string"}}, {"name": "keyword", "in": "query", "schema": {"type": "string"}}, {"name": "sort_by", "in": "query", "schema": {"type": "string"}}], "responses": {"200": {"description": "成功"}}}},
            "/workers/{id}": {"get": {"tags": ["员工"], "summary": "员工详情", "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/workers/{id}/reviews": {"get": {"tags": ["评价"], "summary": "员工评价列表", "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/orders": {"post": {"tags": ["订单"], "summary": "创建订单", "security": [{"BearerAuth": []}], "requestBody": {"content": {"application/json": {"schema": {"type": "object", "required": ["worker_id", "duration_hours"], "properties": {"worker_id": {"type": "integer"}, "duration_hours": {"type": "integer"}, "remark": {"type": "string"}}}}}}, "responses": {"201": {"description": "下单成功"}}}, "get": {"tags": ["订单"], "summary": "我的订单列表", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "成功"}}}},
            "/orders/{id}": {"get": {"tags": ["订单"], "summary": "订单详情", "security": [{"BearerAuth": []}], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/orders/{id}/pay": {"post": {"tags": ["支付"], "summary": "模拟支付", "security": [{"BearerAuth": []}], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "支付成功"}}}},
            "/orders/{id}/activate": {"post": {"tags": ["订单"], "summary": "开始服务", "security": [{"BearerAuth": []}], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/orders/{id}/complete": {"post": {"tags": ["订单"], "summary": "确认完成", "security": [{"BearerAuth": []}], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/orders/{id}/refund": {"post": {"tags": ["支付"], "summary": "申请退款", "security": [{"BearerAuth": []}], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/orders/{id}/cancel": {"post": {"tags": ["订单"], "summary": "取消订单", "security": [{"BearerAuth": []}], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/orders/{id}/review": {"post": {"tags": ["评价"], "summary": "提交评价", "security": [{"BearerAuth": []}], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "requestBody": {"content": {"application/json": {"schema": {"type": "object", "required": ["rating"], "properties": {"rating": {"type": "integer", "minimum": 1, "maximum": 5}, "content": {"type": "string"}}}}}}, "responses": {"201": {"description": "评价成功"}}}},
            "/orders/{id}/payments": {"get": {"tags": ["支付"], "summary": "订单支付记录", "security": [{"BearerAuth": []}], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/messages": {"get": {"tags": ["消息"], "summary": "消息列表", "security": [{"BearerAuth": []}], "parameters": [{"name": "is_read", "in": "query", "schema": {"type": "string"}}], "responses": {"200": {"description": "成功"}}}},
            "/messages/{id}/read": {"post": {"tags": ["消息"], "summary": "标记已读", "security": [{"BearerAuth": []}], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/messages/read-all": {"post": {"tags": ["消息"], "summary": "全部已读", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "成功"}}}},
            "/messages/unread-count": {"get": {"tags": ["消息"], "summary": "未读数", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "成功"}}}},
            "/favorites": {"get": {"tags": ["收藏"], "summary": "收藏列表", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "成功"}}}},
            "/favorites/{worker_id}": {"post": {"tags": ["收藏"], "summary": "收藏员工", "security": [{"BearerAuth": []}], "parameters": [{"name": "worker_id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"201": {"description": "成功"}}}, "delete": {"tags": ["收藏"], "summary": "取消收藏", "security": [{"BearerAuth": []}], "parameters": [{"name": "worker_id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/favorites/{worker_id}/check": {"get": {"tags": ["收藏"], "summary": "检查收藏状态", "security": [{"BearerAuth": []}], "parameters": [{"name": "worker_id", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "成功"}}}},
            "/recommendations": {"get": {"tags": ["推荐"], "summary": "智能推荐员工", "responses": {"200": {"description": "成功"}}}},
            "/admin/stats": {"get": {"tags": ["管理后台"], "summary": "数据统计", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "成功"}}}},
            "/admin/users": {"get": {"tags": ["管理后台"], "summary": "用户列表", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "成功"}}}},
            "/admin/workers": {"get": {"tags": ["管理后台"], "summary": "员工列表", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "成功"}}}, "post": {"tags": ["管理后台"], "summary": "新增员工", "security": [{"BearerAuth": []}], "responses": {"201": {"description": "成功"}}}},
            "/admin/orders": {"get": {"tags": ["管理后台"], "summary": "订单列表", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "成功"}}}},
            "/health": {"get": {"tags": ["系统"], "summary": "健康检查", "responses": {"200": {"description": "正常"}, "503": {"description": "异常"}}}},
        }
    }
    return jsonify(spec), 200


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
