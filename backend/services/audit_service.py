"""审计日志服务。"""
import json

from flask import has_request_context, request

from extensions import db
from models import AuditLog


def record_audit(action_type, resource_type, resource_id, summary="", actor_user_id=None,
                 deployment_id=None, details=None, ip_address=None):
    if ip_address is None and has_request_context():
        ip_address = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr
            or ""
        )

    log = AuditLog(
        actor_user_id=actor_user_id,
        deployment_id=deployment_id,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=str(resource_id),
        summary=summary,
        details_json=json.dumps(details or {}, ensure_ascii=False),
        ip_address=ip_address or "",
    )
    db.session.add(log)
    return log
