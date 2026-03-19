"""部署相关服务。"""
import datetime
import json

from models import Deployment, KnowledgeBase, KnowledgeDocument
from utils.helpers import generate_public_token


DEFAULT_DEPLOYMENT_CONFIG = {
    "brand_voice": "professional",
    "business_name": "",
    "handoff_message": "这个问题我需要转给人工客服继续确认，请稍等。",
    "pii_masking_enabled": True,
    "handoff_on_pii": False,
    "forbidden_topics": [],
    "sensitive_keywords": [],
    "provider": "rules",
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
    config = dict(DEFAULT_DEPLOYMENT_CONFIG)
    raw_config = raw_config or {}
    if not isinstance(raw_config, dict):
        raw_config = {}

    for field in ["brand_voice", "business_name", "handoff_message", "provider"]:
        if field in raw_config and raw_config.get(field) is not None:
            config[field] = str(raw_config.get(field)).strip()

    for field in ["pii_masking_enabled", "handoff_on_pii"]:
        if field in raw_config:
            config[field] = bool(raw_config.get(field))

    for field in ["forbidden_topics", "sensitive_keywords"]:
        config[field] = normalize_string_list(raw_config.get(field))

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


def get_public_deployment(public_token):
    if not public_token:
        return None
    return Deployment.query.filter_by(public_token=public_token, status="active").first()


def get_primary_knowledge_base(deployment_id):
    return KnowledgeBase.query.filter_by(deployment_id=deployment_id).order_by(KnowledgeBase.id.asc()).first()


def publish_deployment(deployment):
    ensure_public_token(deployment)
    knowledge_bases = KnowledgeBase.query.filter_by(deployment_id=deployment.id).all()
    if not knowledge_bases:
        raise ValueError("请先上传知识库")

    total_documents = 0
    now = datetime.datetime.utcnow()
    for knowledge_base in knowledge_bases:
        documents = KnowledgeDocument.query.filter_by(knowledge_base_id=knowledge_base.id).all()
        if not documents:
            continue

        total_documents += len(documents)
        knowledge_base.status = "active"
        knowledge_base.published_at = now
        for document in documents:
            document.status = "published"

    if total_documents == 0:
        raise ValueError("请至少上传一篇知识文档")

    if deployment.status in ("pending_setup", "pending_review"):
        deployment.status = "active"
    if not deployment.started_at:
        deployment.started_at = now

    return knowledge_bases
