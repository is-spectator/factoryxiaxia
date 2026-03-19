"""系统路由：健康检查、API文档"""
import datetime
import os
from flask import Blueprint, jsonify
from extensions import db, limiter
from services.provider_service import get_provider_capabilities

bp = Blueprint("system", __name__)


def get_payment_mode():
    return "manual_review" if (os.environ.get("APP_ENV") or "").strip().lower() == "production" else "mock"


@bp.route("/api/health", methods=["GET"])
@limiter.exempt
def health():
    result = {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
    try:
        db.session.execute(db.text("SELECT 1"))
        result["database"] = "connected"
    except Exception as e:
        result["status"] = "degraded"
        result["database"] = f"error: {e}"
    return jsonify(result), 200 if result["status"] == "ok" else 503


@bp.route("/api/runtime-config", methods=["GET"])
@limiter.exempt
def runtime_config():
    provider_capabilities = get_provider_capabilities()
    return jsonify({
        "payment_mode": get_payment_mode(),
        "app_env": (os.environ.get("APP_ENV") or "development").strip().lower(),
        "provider": provider_capabilities,
    }), 200


@bp.route("/api/docs", methods=["GET"])
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
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            }
        },
        "paths": {
            "/register": {
                "post": {
                    "tags": ["用户"],
                    "summary": "用户注册",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["username", "email", "password", "confirm_password"],
                                    "properties": {
                                        "username": {"type": "string"},
                                        "email": {"type": "string"},
                                        "password": {"type": "string"},
                                        "confirm_password": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"201": {"description": "注册成功"}},
                }
            },
            "/login": {
                "post": {
                    "tags": ["用户"],
                    "summary": "用户登录",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["login_id", "password"],
                                    "properties": {
                                        "login_id": {"type": "string"},
                                        "password": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "登录成功"}},
                }
            },
            "/profile": {
                "get": {
                    "tags": ["用户"],
                    "summary": "获取个人信息",
                    "security": [{"BearerAuth": []}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/categories": {
                "get": {
                    "tags": ["分类"],
                    "summary": "分类列表",
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/workers": {
                "get": {
                    "tags": ["员工"],
                    "summary": "员工列表",
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "per_page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "category_id", "in": "query", "schema": {"type": "integer"}},
                        {"name": "status", "in": "query", "schema": {"type": "string"}},
                        {"name": "keyword", "in": "query", "schema": {"type": "string"}},
                        {"name": "sort_by", "in": "query", "schema": {"type": "string"}},
                    ],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/workers/{id}": {
                "get": {
                    "tags": ["员工"],
                    "summary": "员工详情",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/workers/{id}/reviews": {
                "get": {
                    "tags": ["评价"],
                    "summary": "员工评价列表",
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/orders": {
                "post": {
                    "tags": ["订单"],
                    "summary": "创建订单",
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["worker_id", "duration_hours"],
                                    "properties": {
                                        "worker_id": {"type": "integer"},
                                        "duration_hours": {"type": "integer"},
                                        "remark": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"201": {"description": "下单成功"}},
                },
                "get": {
                    "tags": ["订单"],
                    "summary": "我的订单列表",
                    "security": [{"BearerAuth": []}],
                    "responses": {"200": {"description": "成功"}},
                },
            },
            "/orders/{id}": {
                "get": {
                    "tags": ["订单"],
                    "summary": "订单详情",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/orders/{id}/pay": {
                "post": {
                    "tags": ["支付"],
                    "summary": "开发环境快捷支付",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "支付成功"}},
                }
            },
            "/orders/{id}/payment-review": {
                "post": {
                    "tags": ["支付"],
                    "summary": "提交付款确认",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "提交成功"}},
                }
            },
            "/orders/{id}/activate": {
                "post": {
                    "tags": ["订单"],
                    "summary": "开始服务",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/orders/{id}/complete": {
                "post": {
                    "tags": ["订单"],
                    "summary": "确认完成",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/orders/{id}/refund": {
                "post": {
                    "tags": ["支付"],
                    "summary": "申请退款",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/orders/{id}/cancel": {
                "post": {
                    "tags": ["订单"],
                    "summary": "取消订单",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/orders/{id}/review": {
                "post": {
                    "tags": ["评价"],
                    "summary": "提交评价",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["rating"],
                                    "properties": {
                                        "rating": {"type": "integer", "minimum": 1, "maximum": 5},
                                        "content": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"201": {"description": "评价成功"}},
                }
            },
            "/orders/{id}/payments": {
                "get": {
                    "tags": ["支付"],
                    "summary": "订单支付记录",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/messages": {
                "get": {
                    "tags": ["消息"],
                    "summary": "消息列表",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "is_read", "in": "query", "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/messages/{id}/read": {
                "post": {
                    "tags": ["消息"],
                    "summary": "标记已读",
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/messages/read-all": {
                "post": {
                    "tags": ["消息"],
                    "summary": "全部已读",
                    "security": [{"BearerAuth": []}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/messages/unread-count": {
                "get": {
                    "tags": ["消息"],
                    "summary": "未读数",
                    "security": [{"BearerAuth": []}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/favorites": {
                "get": {
                    "tags": ["收藏"],
                    "summary": "收藏列表",
                    "security": [{"BearerAuth": []}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/favorites/{worker_id}": {
                "post": {
                    "tags": ["收藏"],
                    "summary": "收藏员工",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {"name": "worker_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    ],
                    "responses": {"201": {"description": "成功"}},
                },
                "delete": {
                    "tags": ["收藏"],
                    "summary": "取消收藏",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {"name": "worker_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "成功"}},
                },
            },
            "/favorites/{worker_id}/check": {
                "get": {
                    "tags": ["收藏"],
                    "summary": "检查收藏状态",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {"name": "worker_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/recommendations": {
                "get": {
                    "tags": ["推荐"],
                    "summary": "智能推荐员工",
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/admin/stats": {
                "get": {
                    "tags": ["管理后台"],
                    "summary": "数据统计",
                    "security": [{"BearerAuth": []}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/admin/users": {
                "get": {
                    "tags": ["管理后台"],
                    "summary": "用户列表",
                    "security": [{"BearerAuth": []}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/admin/workers": {
                "get": {
                    "tags": ["管理后台"],
                    "summary": "员工列表",
                    "security": [{"BearerAuth": []}],
                    "responses": {"200": {"description": "成功"}},
                },
                "post": {
                    "tags": ["管理后台"],
                    "summary": "新增员工",
                    "security": [{"BearerAuth": []}],
                    "responses": {"201": {"description": "成功"}},
                },
            },
            "/admin/orders": {
                "get": {
                    "tags": ["管理后台"],
                    "summary": "订单列表",
                    "security": [{"BearerAuth": []}],
                    "responses": {"200": {"description": "成功"}},
                }
            },
            "/health": {
                "get": {
                    "tags": ["系统"],
                    "summary": "健康检查",
                    "responses": {
                        "200": {"description": "正常"},
                        "503": {"description": "异常"},
                    },
                }
            },
        },
    }
    return jsonify(spec), 200
