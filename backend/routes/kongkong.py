"""空空 OpenClaw 实例管理路由。"""
import os

from flask import Blueprint, jsonify, request

from extensions import db
from models import AuditLog, Deployment, KongKongInstance
from services.audit_service import record_audit
from services.kongkong_provision_service import (
    build_kongkong_launch_payload,
    destroy_kongkong_instance,
    restart_kongkong_instance,
    start_kongkong_instance,
    stop_kongkong_instance,
)
from services.kongkong_runtime_service import get_runtime_mode, is_mock_runtime_record
from services.messages import send_message
from services.deployment_service import user_can_manage_deployment
from utils.auth import get_current_user


bp = Blueprint("kongkong", __name__)


def _load_manageable_instance(instance_id):
    user = get_current_user()
    if not user:
        return None, None, (jsonify({"error": "请先登录"}), 401)

    instance = KongKongInstance.query.get(instance_id)
    if not instance:
        return user, None, (jsonify({"error": "空空实例不存在"}), 404)

    deployment = instance.deployment
    if not deployment or not user_can_manage_deployment(user, deployment):
        return user, None, (jsonify({"error": "无权操作该空空实例"}), 403)
    return user, instance, None


@bp.route("/api/kongkong/instances", methods=["GET"])
def list_kongkong_instances():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录"}), 401

    query = KongKongInstance.query
    if (user.role or "user") not in ("admin", "operator"):
        query = query.filter_by(user_id=user.id)
    deployment_id = request.args.get("deployment_id", type=int)
    if deployment_id:
        query = query.filter_by(deployment_id=deployment_id)
    instances = query.order_by(KongKongInstance.created_at.desc()).all()
    return jsonify({"instances": [instance.to_dict() for instance in instances]}), 200


@bp.route("/api/kongkong/instances/<int:instance_id>", methods=["GET"])
def get_kongkong_instance_detail(instance_id):
    user, instance, error = _load_manageable_instance(instance_id)
    if error:
        return error
    payload = instance.to_dict()
    payload["deployment"] = instance.deployment.to_dict() if instance.deployment else None
    return jsonify({"instance": payload}), 200


def _commit_instance_action(user, instance, action_type, summary, details=None):
    record_audit(
        action_type=action_type,
        resource_type="kongkong_instance",
        resource_id=instance.id,
        actor_user_id=user.id if user else None,
        deployment_id=instance.deployment_id,
        summary=summary,
        details=details or {"status": instance.status},
    )
    db.session.commit()
    return jsonify({"message": summary, "instance": instance.to_dict()}), 200


@bp.route("/api/kongkong/instances/<int:instance_id>/start", methods=["POST"])
def start_instance(instance_id):
    user, instance, error = _load_manageable_instance(instance_id)
    if error:
        return error
    start_kongkong_instance(instance)
    instance.deployment.status = "active"
    return _commit_instance_action(user, instance, "kongkong.started", f"空空实例已启动：{instance.instance_slug}")


@bp.route("/api/kongkong/instances/<int:instance_id>/stop", methods=["POST"])
def stop_instance(instance_id):
    user, instance, error = _load_manageable_instance(instance_id)
    if error:
        return error
    stop_kongkong_instance(instance, suspend=False)
    instance.deployment.status = "suspended"
    return _commit_instance_action(user, instance, "kongkong.stopped", f"空空实例已停止：{instance.instance_slug}")


@bp.route("/api/kongkong/instances/<int:instance_id>/restart", methods=["POST"])
def restart_instance(instance_id):
    user, instance, error = _load_manageable_instance(instance_id)
    if error:
        return error
    restart_kongkong_instance(instance)
    instance.deployment.status = "active"
    return _commit_instance_action(user, instance, "kongkong.restarted", f"空空实例已重启：{instance.instance_slug}")


@bp.route("/api/kongkong/instances/<int:instance_id>/suspend", methods=["POST"])
def suspend_instance(instance_id):
    user, instance, error = _load_manageable_instance(instance_id)
    if error:
        return error
    stop_kongkong_instance(instance, suspend=True)
    instance.deployment.status = "suspended"
    send_message(
        instance.user_id,
        "空空实例已暂停",
        f"实例「{instance.instance_slug}」已暂停，恢复后可继续访问 OpenClaw 工作台。",
        "system",
        instance.deployment.order_id if instance.deployment else None,
    )
    return _commit_instance_action(user, instance, "kongkong.suspended", f"空空实例已暂停：{instance.instance_slug}")


@bp.route("/api/kongkong/instances/<int:instance_id>/destroy", methods=["POST"])
def destroy_instance(instance_id):
    user, instance, error = _load_manageable_instance(instance_id)
    if error:
        return error
    destroy_kongkong_instance(instance)
    if instance.deployment:
        instance.deployment.status = "expired"
    return _commit_instance_action(user, instance, "kongkong.destroyed", f"空空实例已销毁：{instance.instance_slug}")


@bp.route("/api/kongkong/instances/<int:instance_id>/launch-link", methods=["POST"])
def create_launch_link(instance_id):
    user, instance, error = _load_manageable_instance(instance_id)
    if error:
        return error
    if instance.status != "running":
        return jsonify({"error": "空空实例尚未运行，无法生成入口链接"}), 400
    if get_runtime_mode() != "docker" and (os.environ.get("APP_ENV") or "").strip().lower() != "test":
        return jsonify({
            "error": "当前环境仍处于空空 mock 模式，请设置 KONGKONG_RUNTIME_MODE=docker 并重建后端/前端容器后再试",
        }), 409
    if get_runtime_mode() == "docker" and is_mock_runtime_record(instance):
        start_kongkong_instance(instance)

    payload = build_kongkong_launch_payload(instance)
    record_audit(
        action_type="kongkong.launch_link_requested",
        resource_type="kongkong_instance",
        resource_id=instance.id,
        actor_user_id=user.id if user else None,
        deployment_id=instance.deployment_id,
        summary=f"申请空空工作台入口：{instance.instance_slug}",
        details={"entry_url": payload["entry_url"]},
    )
    db.session.commit()
    return jsonify({"launch": payload, "instance": instance.to_dict()}), 200


@bp.route("/api/admin/kongkong/instances", methods=["GET"])
def admin_list_kongkong_instances():
    user = get_current_user()
    if not user or (user.role or "user") not in ("admin", "operator"):
        return jsonify({"error": "无管理员权限"}), 403

    instances = KongKongInstance.query.order_by(KongKongInstance.created_at.desc()).all()
    return jsonify({"instances": [instance.to_dict() for instance in instances]}), 200


@bp.route("/api/admin/kongkong/audit-logs", methods=["GET"])
def admin_list_kongkong_audit_logs():
    user = get_current_user()
    if not user or (user.role or "user") not in ("admin", "operator"):
        return jsonify({"error": "无管理员权限"}), 403

    query = AuditLog.query.filter_by(resource_type="kongkong_instance")
    deployment_id = request.args.get("deployment_id", type=int)
    if deployment_id:
        query = query.filter_by(deployment_id=deployment_id)
    logs = query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return jsonify({"audit_logs": [log.to_dict() for log in logs]}), 200
