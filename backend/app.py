"""虾虾工厂 — Flask 应用入口

本文件仅负责：
1. 创建 Flask app 实例
2. 初始化扩展 (db, limiter, CORS)
3. 注册蓝图 (routes/*)
4. 设置中间件 (安全头, 日志, 异常处理)

业务逻辑已拆分至:
- models.py        — 数据模型
- extensions.py    — Flask 扩展实例
- utils/auth.py    — JWT / 认证
- utils/helpers.py — 通用工具
- services/        — 业务服务
- routes/          — 路由蓝图
"""
import os
import datetime

from sqlalchemy import inspect, text

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bcrypt
import jwt
from sqlalchemy import inspect

from extensions import db, limiter
from utils.helpers import setup_logging, send_alert

# ===== 日志 =====
logger = setup_logging()

# ===== Flask 应用 =====
app = Flask(__name__)
CORS(app)

DB_USER = os.environ.get("DB_USER", "xiaxia")
DB_PASS = os.environ.get("DB_PASS", "xiaxia_secret_2026")
DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "xiaxia_factory")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ===== 初始化扩展 =====
db.init_app(app)
limiter.init_app(app)

# ===== 中间件 =====


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    duration = ""
    if hasattr(g, "request_start"):
        duration = f" {(datetime.datetime.utcnow() - g.request_start).total_seconds()*1000:.0f}ms"
    logger.info(f"{request.method} {request.path} → {response.status_code}{duration}")
    return response


@app.before_request
def before_request_hook():
    g.request_start = datetime.datetime.utcnow()


# ===== 异常处理 =====


@app.errorhandler(500)
def handle_500(e):
    logger.error(f"Internal Server Error: {e}", exc_info=True)
    send_alert("500 Internal Server Error", f"{request.method} {request.path}\n{e}")
    return jsonify({"error": "服务器内部错误"}), 500


@app.errorhandler(429)
def handle_429(e):
    return jsonify({"error": "请求过于频繁，请稍后再试"}), 429


# ===== 数据模型 =====


def ensure_order_schema():
    """Ensure incremental schema changes exist for deployments reusing an older database."""
    inspector = inspect(db.engine)
    if "orders" not in inspector.get_table_names():
        return

    order_columns = {column["name"] for column in inspector.get_columns("orders")}
    if "activated_at" in order_columns:
        return

    alter_sql = "ALTER TABLE orders ADD COLUMN activated_at DATETIME NULL"
    if db.engine.dialect.name == "mysql":
        alter_sql += " AFTER paid_at"

    with db.engine.begin() as conn:
        conn.execute(db.text(alter_sql))
    logger.info("Applied startup schema migration: added orders.activated_at")


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


def ensure_order_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table("orders"):
        return

    column_names = {column["name"] for column in inspector.get_columns("orders")}
    if "activated_at" in column_names:
        return

    dialect_name = db.engine.dialect.name
    if dialect_name == "mysql":
        alter_sql = "ALTER TABLE orders ADD COLUMN activated_at DATETIME NULL AFTER paid_at"
    else:
        alter_sql = "ALTER TABLE orders ADD COLUMN activated_at DATETIME"

    with db.engine.begin() as connection:
        connection.execute(text(alter_sql))

    logger.info("Added missing orders.activated_at column")


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
    send_message(user.id, "服务已开始",
                 f"订单 {order.order_no} 的服务已开始",
                 "order", order.id)
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


app.register_blueprint(auth_bp)
app.register_blueprint(catalog_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(system_bp)

# ===== 向后兼容：让测试可以 import app 后访问模型和工具 =====
from models import (  # noqa: E402, F401
    User, Category, Worker, Order, Payment, Review, Message, Favorite,
    ROLES, ORDER_STATUSES, ORDER_TRANSITIONS,
)
from utils.auth import (  # noqa: E402, F401
    create_token, verify_token, get_current_user, require_admin,
)
from utils.helpers import (  # noqa: E402, F401
    generate_order_no, generate_payment_no, EMAIL_RE, JsonFormatter,
)
from services.messages import send_message  # noqa: E402, F401

# ===== 建表 =====
with app.app_context():
    db.create_all()
    ensure_order_schema()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
