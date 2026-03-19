"""空空实例创建与编排服务。"""
import datetime
import json

from extensions import db
from models import KongKongInstance
from services.deployment_service import dump_deployment_config, load_deployment_config
from services.kongkong_runtime_service import (
    build_launch_payload,
    generate_gateway_token,
    provision_instance_runtime,
    restart_instance_runtime,
    slugify_instance_name,
    start_instance_runtime,
    stop_instance_runtime,
    destroy_instance_runtime,
)
from services.provider_service import get_default_provider_model


def _build_default_runtime_meta():
    return {
        "created_by": "xiaxia_factory",
        "product": "kongkong",
    }


def ensure_kongkong_defaults(deployment):
    config = load_deployment_config(deployment)
    changed = False
    if config.get("provider") != "dashscope":
        config["provider"] = "dashscope"
        changed = True
    model = (config.get("provider_model") or "").strip()
    if not model:
        config["provider_model"] = get_default_provider_model("dashscope") or "qwen-max"
        changed = True
    if changed:
        deployment.config_json = dump_deployment_config(config, deployment=deployment)
    return config


def get_or_create_kongkong_instance(deployment):
    instance = KongKongInstance.query.filter_by(deployment_id=deployment.id).first()
    if instance:
        return instance

    config = ensure_kongkong_defaults(deployment)
    service_plan = deployment.service_plan
    instance = KongKongInstance(
        deployment_id=deployment.id,
        user_id=deployment.user_id,
        organization_id=deployment.organization_id,
        worker_id=deployment.worker_id,
        service_plan_id=deployment.service_plan_id,
        status="provisioning",
        container_name="",
        container_id="",
        instance_slug=slugify_instance_name(deployment.deployment_name, deployment.id),
        entry_url="",
        gateway_token=generate_gateway_token(),
        model_provider=config.get("provider") or "dashscope",
        model_name=config.get("provider_model") or "qwen-max",
        cpu_limit=getattr(service_plan, "cpu_limit", 1.0) or 1.0,
        memory_limit_mb=getattr(service_plan, "memory_limit_mb", 2048) or 2048,
        storage_limit_gb=getattr(service_plan, "storage_limit_gb", 10) or 10,
        expires_at=deployment.expires_at,
        runtime_meta_json=json.dumps(_build_default_runtime_meta(), ensure_ascii=False),
    )
    db.session.add(instance)
    db.session.flush()
    return instance


def provision_kongkong_instance(deployment):
    instance = get_or_create_kongkong_instance(deployment)
    try:
        provision_instance_runtime(instance)
        deployment.status = "active"
        deployment.started_at = deployment.started_at or datetime.datetime.utcnow()
        return instance
    except Exception as exc:  # noqa: BLE001
        instance.status = "error"
        instance.error_message = str(exc)
        deployment.status = "pending_review"
        return instance


def restart_kongkong_instance(instance):
    restart_instance_runtime(instance)
    instance.error_message = ""
    return instance


def start_kongkong_instance(instance):
    start_instance_runtime(instance)
    instance.error_message = ""
    return instance


def stop_kongkong_instance(instance, suspend=False):
    stop_instance_runtime(instance, suspend=suspend)
    return instance


def destroy_kongkong_instance(instance):
    destroy_instance_runtime(instance)
    return instance


def build_kongkong_launch_payload(instance):
    return build_launch_payload(instance)
