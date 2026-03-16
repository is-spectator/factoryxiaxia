import os
import datetime
import re

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import jwt

app = Flask(__name__)
CORS(app)

DB_USER = os.environ.get("DB_USER", "xiaxia")
DB_PASS = os.environ.get("DB_PASS", "xiaxia_secret_2026")
DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "xiaxia_factory")
JWT_SECRET = os.environ.get("JWT_SECRET", "xiaxia-jwt-secret-key-2026")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ===== 数据模型 =====

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ===== 工具函数 =====

def create_token(user):
    payload = {
        "user_id": user.id,
        "username": user.username,
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
    return User.query.get(payload["user_id"])


def generate_order_no():
    now = datetime.datetime.utcnow()
    import random
    return now.strftime("XF%Y%m%d%H%M%S") + str(random.randint(1000, 9999))


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


# ===== 用户 API =====

@app.route("/api/register", methods=["POST"])
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

    duration_hours = int(duration_hours)
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
    if order.status not in ("pending",):
        return jsonify({"error": "当前状态无法取消"}), 400

    order.status = "cancelled"
    db.session.commit()

    return jsonify({"message": "订单已取消", "order": order.to_dict()}), 200


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
