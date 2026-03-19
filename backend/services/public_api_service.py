"""公开 API 访问控制与限流服务。"""
import datetime
import ipaddress
from collections import defaultdict, deque
from urllib.parse import urlparse

from flask import current_app

from extensions import db
from models import Deployment, UsageRecord


_RATE_LIMIT_BUCKETS = defaultdict(deque)


def normalize_origin_value(value):
    raw = str(value or "").strip()
    if not raw:
        return None

    if "://" not in raw:
        raw = f"https://{raw}"

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return None
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        if hostname != "localhost" and "." not in hostname:
            return None
    return f"{parsed.scheme}://{parsed.netloc.lower()}"


def normalize_allowed_origins(value):
    items = value
    if isinstance(value, str):
        items = value.replace("\n", ",").split(",")
    if not isinstance(items, list):
        return []

    normalized = []
    seen = set()
    for item in items:
        origin = normalize_origin_value(item)
        if not origin or origin in seen:
            continue
        seen.add(origin)
        normalized.append(origin)
    return normalized


def find_invalid_allowed_origins(value):
    items = value
    if isinstance(value, str):
        items = value.replace("\n", ",").split(",")
    if not isinstance(items, list):
        return []

    invalid_items = []
    for item in items:
        raw = str(item or "").strip()
        if not raw:
            continue
        if not normalize_origin_value(raw):
            invalid_items.append(raw)
    return invalid_items


def _extract_origin_from_url(url):
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc.lower()}"


def get_request_ip(request_obj):
    return (
        request_obj.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request_obj.remote_addr
        or ""
    )


def build_public_request_context(request_obj):
    origin = normalize_origin_value(request_obj.headers.get("Origin"))
    referer = (request_obj.headers.get("Referer") or "").strip()
    referer_origin = _extract_origin_from_url(referer)
    user_agent = (request_obj.headers.get("User-Agent") or "").strip()
    sec_fetch_site = (request_obj.headers.get("Sec-Fetch-Site") or "").strip().lower()
    browser_originated = bool(origin or referer or sec_fetch_site not in ("", "none"))

    return {
        "origin": origin,
        "referer": referer,
        "referer_origin": referer_origin,
        "user_agent": user_agent,
        "ip_address": get_request_ip(request_obj),
        "sec_fetch_site": sec_fetch_site,
        "browser_originated": browser_originated,
    }


def evaluate_public_access(deployment, deployment_config, access_context):
    allowed_origins = normalize_allowed_origins(deployment_config.get("allowed_origins"))
    public_access_enabled = bool(deployment_config.get("public_access_enabled", True))
    candidate_origin = access_context["origin"] or access_context["referer_origin"]

    base_details = {
        "allowed_origins": allowed_origins,
        "origin": access_context["origin"],
        "referer_origin": access_context["referer_origin"],
        "referer": access_context["referer"],
        "browser_originated": access_context["browser_originated"],
        "user_agent": access_context["user_agent"],
        "ip_address": access_context["ip_address"],
    }

    if not deployment:
        return {
            "allowed": False,
            "status_code": 404,
            "error": "公开聊天入口不存在",
            "reason": "token_not_found",
            "details": base_details,
        }

    if deployment.status in ("pending_setup", "pending_review", "expired"):
        return {
            "allowed": False,
            "status_code": 404,
            "error": "公开聊天入口不存在",
            "reason": "deployment_not_public",
            "details": base_details,
        }

    if deployment.status == "suspended":
        return {
            "allowed": False,
            "status_code": 403,
            "error": "机器人已暂停公开访问",
            "reason": "deployment_suspended",
            "details": base_details,
        }

    if deployment.status != "active":
        return {
            "allowed": False,
            "status_code": 403,
            "error": "机器人尚未发布上线",
            "reason": "deployment_not_active",
            "details": base_details,
        }

    if not public_access_enabled:
        return {
            "allowed": False,
            "status_code": 403,
            "error": "公开 Token 已停用，请在控制台重新启用",
            "reason": "public_token_disabled",
            "details": base_details,
        }

    if access_context["browser_originated"]:
        if access_context["referer"] and not access_context["referer_origin"]:
            return {
                "allowed": False,
                "status_code": 403,
                "error": "浏览器来源校验失败，请检查页面来源域名",
                "reason": "invalid_referer",
                "details": base_details,
            }

        if access_context["origin"] and access_context["referer_origin"] and access_context["origin"] != access_context["referer_origin"]:
            return {
                "allowed": False,
                "status_code": 403,
                "error": "浏览器来源校验失败，请检查页面来源域名",
                "reason": "referer_origin_mismatch",
                "details": base_details,
            }

        if not allowed_origins:
            return {
                "allowed": False,
                "status_code": 403,
                "error": "当前部署尚未配置允许访问的浏览器域名",
                "reason": "allowed_origins_not_configured",
                "details": base_details,
            }

        if not candidate_origin:
            return {
                "allowed": False,
                "status_code": 403,
                "error": "浏览器来源缺失，无法调用公开 API",
                "reason": "missing_browser_origin",
                "details": base_details,
            }

        if candidate_origin not in allowed_origins:
            return {
                "allowed": False,
                "status_code": 403,
                "error": "当前浏览器域名未被授权访问该公开 API",
                "reason": "origin_not_allowed",
                "details": base_details,
            }

        if access_context["referer_origin"] and access_context["referer_origin"] not in allowed_origins:
            return {
                "allowed": False,
                "status_code": 403,
                "error": "当前浏览器域名未被授权访问该公开 API",
                "reason": "referer_not_allowed",
                "details": base_details,
            }

    return {
        "allowed": True,
        "status_code": 200,
        "reason": "allowed",
        "details": base_details,
    }


def _consume_rate_limit(bucket_key, limit, window_seconds, now=None):
    if limit is None or int(limit) <= 0:
        return {
            "allowed": True,
            "current": 0,
            "limit": int(limit or 0),
            "window_seconds": window_seconds,
            "retry_after": 0,
        }

    now = now or datetime.datetime.utcnow()
    limit = int(limit)
    bucket = _RATE_LIMIT_BUCKETS[bucket_key]
    cutoff = now - datetime.timedelta(seconds=window_seconds)

    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

    if len(bucket) >= limit:
        retry_after = max(int((bucket[0] + datetime.timedelta(seconds=window_seconds) - now).total_seconds()), 1)
        return {
            "allowed": False,
            "current": len(bucket),
            "limit": limit,
            "window_seconds": window_seconds,
            "retry_after": retry_after,
        }

    bucket.append(now)
    return {
        "allowed": True,
        "current": len(bucket),
        "limit": limit,
        "window_seconds": window_seconds,
        "retry_after": 0,
    }


def get_public_rate_limit_settings():
    return {
        "ip_per_minute": int(current_app.config.get("PUBLIC_CHAT_IP_LIMIT_PER_MINUTE", 30)),
        "deployment_per_minute": int(current_app.config.get("PUBLIC_CHAT_DEPLOYMENT_LIMIT_PER_MINUTE", 120)),
    }


def evaluate_public_rate_limits(deployment, access_context):
    settings = get_public_rate_limit_settings()
    ip_check = _consume_rate_limit(
        ("public_chat_ip", access_context["ip_address"] or "unknown"),
        settings["ip_per_minute"],
        60,
    )
    if not ip_check["allowed"]:
        return {
            "allowed": False,
            "status_code": 429,
            "error": "当前 IP 调用过于频繁，请稍后再试",
            "reason": "ip_rate_limited",
            "details": {
                "limit_scope": "ip",
                "retry_after": ip_check["retry_after"],
                "limit": ip_check["limit"],
                "current": ip_check["current"],
                "ip_address": access_context["ip_address"],
            },
        }

    deployment_check = _consume_rate_limit(
        ("public_chat_deployment", deployment.id),
        settings["deployment_per_minute"],
        60,
    )
    if not deployment_check["allowed"]:
        return {
            "allowed": False,
            "status_code": 429,
            "error": "当前机器人公开 API 调用过于频繁，请稍后再试",
            "reason": "deployment_rate_limited",
            "details": {
                "limit_scope": "deployment",
                "retry_after": deployment_check["retry_after"],
                "limit": deployment_check["limit"],
                "current": deployment_check["current"],
                "deployment_id": deployment.id,
            },
        }

    return {
        "allowed": True,
        "status_code": 200,
        "reason": "allowed",
        "details": {
            "ip_rate_limit": settings["ip_per_minute"],
            "deployment_rate_limit": settings["deployment_per_minute"],
        },
    }


def evaluate_public_quota(deployment):
    plan = deployment.service_plan
    limit = int(plan.included_conversations or 0) if plan else 0
    if limit <= 0:
        return {
            "allowed": True,
            "status_code": 200,
            "reason": "allowed",
            "details": {"quota_limit": limit, "quota_used": 0},
        }

    used = db.session.query(
        db.func.coalesce(db.func.sum(UsageRecord.quantity), 0)
    ).filter(
        UsageRecord.deployment_id == deployment.id,
        UsageRecord.metric_type == "message_in",
    ).scalar()
    used = int(float(used or 0))
    if used >= limit:
        return {
            "allowed": False,
            "status_code": 403,
            "error": "当前套餐会话额度已用尽，请续费或升级套餐",
            "reason": "plan_quota_exhausted",
            "details": {
                "quota_limit": limit,
                "quota_used": used,
                "service_plan_id": deployment.service_plan_id,
            },
        }

    return {
        "allowed": True,
        "status_code": 200,
        "reason": "allowed",
        "details": {
            "quota_limit": limit,
            "quota_used": used,
            "quota_remaining": limit - used,
        },
    }


def reset_public_api_rate_limits():
    _RATE_LIMIT_BUCKETS.clear()
