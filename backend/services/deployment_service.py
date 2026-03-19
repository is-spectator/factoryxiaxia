"""部署相关服务。"""
import datetime
import json

from models import Deployment, KnowledgeBase, KnowledgeDocument
from services.knowledge_quality_service import (
    build_knowledge_summary,
    collect_publishable_knowledge_bases,
)
from services.provider_service import (
    get_default_provider_model,
    get_default_provider_name,
    get_provider_defaults,
    normalize_provider_name,
)
from services.public_api_service import (
    find_invalid_allowed_origins,
    normalize_allowed_origins,
)
from utils.helpers import generate_public_token


def get_default_deployment_config():
    provider_defaults = get_provider_defaults(get_default_provider_name())
    return {
        "brand_voice": "professional",
        "business_name": "",
        "handoff_message": "这个问题我需要转给人工客服继续确认，请稍等。",
        "pii_masking_enabled": True,
        "handoff_on_pii": False,
        "forbidden_topics": [],
        "sensitive_keywords": [],
        "provider": provider_defaults["provider"],
        "provider_model": provider_defaults["provider_model"] or get_default_provider_model(provider_defaults["provider"]),
        "provider_temperature": provider_defaults["provider_temperature"],
        "provider_top_p": provider_defaults["provider_top_p"],
        "provider_max_tokens": provider_defaults["provider_max_tokens"],
        "provider_timeout_seconds": provider_defaults["provider_timeout_seconds"],
        "provider_retry_attempts": provider_defaults["provider_retry_attempts"],
        "allowed_origins": [],
        "public_access_enabled": True,
    }


def user_can_manage_deployment(user, deployment):
    if not user or not deployment:
        return False
    if deployment.user_id == user.id:
        return True
    return (user.role or "user") in ("admin", "operator")


def get_manageable_deployment(user, deployment_id):
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return None
    if not user_can_manage_deployment(user, deployment):
        return None
    return deployment


def normalize_string_list(value):
    if not value:
        return []
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",")]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_deployment_config(raw_config, deployment=None):
    config = get_default_deployment_config()
    raw_config = raw_config or {}
    if not isinstance(raw_config, dict):
        raw_config = {}

    for field in ["brand_voice", "business_name", "handoff_message", "provider", "provider_model"]:
        if field in raw_config and raw_config.get(field) is not None:
            config[field] = str(raw_config.get(field)).strip()

    config["provider"] = normalize_provider_name(config.get("provider"))
    provider_defaults = get_provider_defaults(config["provider"])
    if not config.get("provider_model"):
        config["provider_model"] = provider_defaults["provider_model"] or get_default_provider_model(config["provider"])

    for field in ["pii_masking_enabled", "handoff_on_pii"]:
        if field in raw_config:
            config[field] = bool(raw_config.get(field))

    for field in ["forbidden_topics", "sensitive_keywords"]:
        config[field] = normalize_string_list(raw_config.get(field))

    config["allowed_origins"] = normalize_allowed_origins(raw_config.get("allowed_origins"))

    if "public_access_enabled" in raw_config:
        config["public_access_enabled"] = bool(raw_config.get("public_access_enabled"))

    for field, minimum in [
        ("provider_max_tokens", 64),
        ("provider_timeout_seconds", 5),
        ("provider_retry_attempts", 0),
    ]:
        if field in raw_config:
            try:
                config[field] = max(minimum, int(raw_config.get(field)))
            except (TypeError, ValueError):
                pass

    for field, bounds in [
        ("provider_temperature", (0.0, 2.0)),
        ("provider_top_p", (0.0, 1.0)),
    ]:
        if field in raw_config:
            try:
                value = float(raw_config.get(field))
                config[field] = max(bounds[0], min(bounds[1], value))
            except (TypeError, ValueError):
                pass

    for field in [
        "provider_temperature",
        "provider_top_p",
        "provider_max_tokens",
        "provider_timeout_seconds",
        "provider_retry_attempts",
    ]:
        if config.get(field) in (None, "", []):
            config[field] = provider_defaults[field]

    if deployment and not config["business_name"]:
        config["business_name"] = deployment.deployment_name

    return config


def load_deployment_config(deployment):
    try:
        parsed = json.loads(deployment.config_json or "{}")
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    return normalize_deployment_config(parsed, deployment=deployment)


def dump_deployment_config(config, deployment=None):
    return json.dumps(normalize_deployment_config(config, deployment=deployment), ensure_ascii=False)


def ensure_public_token(deployment):
    if deployment.public_token:
        return deployment.public_token

    token = generate_public_token()
    while Deployment.query.filter_by(public_token=token).first():
        token = generate_public_token()
    deployment.public_token = token
    return token


def rotate_public_token(deployment):
    deployment.public_token = None
    return ensure_public_token(deployment)


def find_public_deployment(public_token):
    if not public_token:
        return None
    return Deployment.query.filter_by(public_token=public_token).first()


def get_public_deployment(public_token):
    if not public_token:
        return None
    return Deployment.query.filter_by(public_token=public_token, status="active").first()


def validate_deployment_config(config):
    invalid_origins = find_invalid_allowed_origins((config or {}).get("allowed_origins"))
    if invalid_origins:
        joined = "、".join(invalid_origins)
        return f"以下来源域名格式无效，请填写完整的 http(s):// 域名：{joined}"
    provider = normalize_provider_name((config or {}).get("provider") or get_default_provider_name())
    if provider not in ("rules", "dashscope"):
        return "暂不支持该 provider，请选择 rules 或 dashscope"
    return None


def get_primary_knowledge_base(deployment_id):
    return KnowledgeBase.query.filter_by(deployment_id=deployment_id).order_by(KnowledgeBase.id.asc()).first()


def publish_deployment(deployment):
    ensure_public_token(deployment)
    knowledge_bases = collect_publishable_knowledge_bases(deployment.id)
    now = datetime.datetime.utcnow()
    for knowledge_base in knowledge_bases:
        documents = KnowledgeDocument.query.filter_by(knowledge_base_id=knowledge_base.id).all()
        knowledge_base.status = "active"
        knowledge_base.published_at = now
        for document in documents:
            document.status = "published"

    if deployment.status in ("pending_setup", "pending_review"):
        deployment.status = "active"
    if not deployment.started_at:
        deployment.started_at = now
    summary, version = build_knowledge_summary(knowledge_bases)
    deployment.knowledge_version = version
    deployment.knowledge_last_published_at = now
    deployment.knowledge_summary_json = json.dumps(summary, ensure_ascii=False)

    return knowledge_bases
