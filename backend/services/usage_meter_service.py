"""用量记录与统计服务。"""
import json

from sqlalchemy import case, func

from extensions import db
from models import (
    ConversationMessage,
    ConversationSession,
    HandoffTicket,
    KnowledgeBase,
    KnowledgeDocument,
    UsageRecord,
)


def record_usage(deployment_id, metric_type, quantity=1, unit="count", session_id=None, meta=None):
    record = UsageRecord(
        deployment_id=deployment_id,
        session_id=session_id,
        metric_type=metric_type,
        quantity=quantity,
        unit=unit,
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
    )
    db.session.add(record)
    return record


def summarize_deployment_usage(deployment_id):
    raw_metrics = db.session.query(
        UsageRecord.metric_type,
        func.coalesce(func.sum(UsageRecord.quantity), 0),
    ).filter(
        UsageRecord.deployment_id == deployment_id
    ).group_by(UsageRecord.metric_type).all()
    metrics_map = {metric_type: float(total) for metric_type, total in raw_metrics}

    avg_confidence = db.session.query(
        func.avg(ConversationMessage.confidence)
    ).join(
        ConversationSession, ConversationSession.id == ConversationMessage.session_id
    ).filter(
        ConversationSession.deployment_id == deployment_id,
        ConversationMessage.role == "assistant",
    ).scalar()

    document_counts = db.session.query(
        func.count(KnowledgeDocument.id),
        func.sum(case((KnowledgeDocument.status == "published", 1), else_=0)),
    ).join(
        KnowledgeBase, KnowledgeBase.id == KnowledgeDocument.knowledge_base_id
    ).filter(
        KnowledgeBase.deployment_id == deployment_id
    ).first()

    sessions_total = ConversationSession.query.filter_by(deployment_id=deployment_id).count()
    handoff_total = HandoffTicket.query.filter_by(deployment_id=deployment_id).count()
    open_handoff_total = HandoffTicket.query.filter(
        HandoffTicket.deployment_id == deployment_id,
        HandoffTicket.status.in_(["open", "in_progress"]),
    ).count()

    total_documents = int(document_counts[0] or 0) if document_counts else 0
    published_documents = int(document_counts[1] or 0) if document_counts else 0

    return {
        "sessions_total": sessions_total,
        "messages_in": int(metrics_map.get("message_in", 0)),
        "messages_out": int(metrics_map.get("message_out", 0)),
        "knowledge_hits": int(metrics_map.get("knowledge_hit", 0)),
        "handoff_total": handoff_total,
        "open_handoff_total": open_handoff_total,
        "documents_total": total_documents,
        "published_documents_total": published_documents,
        "avg_confidence": round(float(avg_confidence or 0), 3) if avg_confidence is not None else None,
    }
