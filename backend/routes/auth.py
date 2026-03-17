"""用户认证路由：注册、登录、个人信息"""
import os
import bcrypt
from flask import Blueprint, request, jsonify
from extensions import db, limiter
from models import User
from utils.auth import create_token, get_current_user
from utils.helpers import EMAIL_RE

bp = Blueprint("auth", __name__)


@bp.route("/api/register", methods=["POST"])
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


@bp.route("/api/login", methods=["POST"])
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


@bp.route("/api/profile", methods=["GET"])
def profile():
    user = get_current_user()
    if not user:
        return jsonify({"error": "未登录或登录已过期"}), 401
    return jsonify({"user": user.to_dict()}), 200
