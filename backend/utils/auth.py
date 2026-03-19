"""认证工具：JWT 生成/验证、获取当前用户"""
import os
import datetime
import jwt
from flask import request
from models import User

JWT_SECRET = (os.environ.get("JWT_SECRET") or "").strip()


def create_token(user):
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET 未配置")
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role or "user",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token):
    if not JWT_SECRET:
        return None
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
