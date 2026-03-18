"""用量统计服务"""
import datetime
from extensions import db
from models import UsageRecord, ConversationSession, ConversationMessage, HandoffTicket


def record_session_usage(deployment_id):
    """记录一次会话到每日用量"""
    today = datetime.date.today()
    record = UsageRecord.query.filter_by(
        deployment_id=deployment_id, record_date=today
    ).first()

    if not record:
        record = UsageRecord(deployment_id=deployment_id, record_date=today)
        db.session.add(record)

    record.session_count += 1
    return record


def record_message_usage(deployment_id):
    """记录一条消息到每日用量"""
    today = datetime.date.today()
    record = UsageRecord.query.filter_by(
        deployment_id=deployment_id, record_date=today
    ).first()

    if not record:
        record = UsageRecord(deployment_id=deployment_id, record_date=today)
        db.session.add(record)

    record.message_count += 1
    return record


def record_handoff_usage(deployment_id):
    """记录一次转人工到每日用量"""
    today = datetime.date.today()
    record = UsageRecord.query.filter_by(
        deployment_id=deployment_id, record_date=today
    ).first()

    if not record:
        record = UsageRecord(deployment_id=deployment_id, record_date=today)
        db.session.add(record)

    record.handoff_count += 1
    return record


def get_deployment_metrics(deployment_id, days=30):
    """获取部署实例的统计指标"""
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    records = UsageRecord.query.filter(
        UsageRecord.deployment_id == deployment_id,
        UsageRecord.record_date >= cutoff,
    ).order_by(UsageRecord.record_date).all()

    total_sessions = sum(r.session_count for r in records)
    total_messages = sum(r.message_count for r in records)
    total_handoffs = sum(r.handoff_count for r in records)
    total_resolved = sum(r.resolved_count for r in records)

    # 计算解决率和转人工率
    resolution_rate = (total_resolved / total_sessions * 100) if total_sessions > 0 else 0
    handoff_rate = (total_handoffs / total_sessions * 100) if total_sessions > 0 else 0

    # 满意度
    sat_records = [r for r in records if r.avg_satisfaction is not None]
    avg_satisfaction = (
        sum(float(r.avg_satisfaction) for r in sat_records) / len(sat_records)
        if sat_records else None
    )

    return {
        "period_days": days,
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_handoffs": total_handoffs,
        "total_resolved": total_resolved,
        "resolution_rate": round(resolution_rate, 1),
        "handoff_rate": round(handoff_rate, 1),
        "avg_satisfaction": round(avg_satisfaction, 2) if avg_satisfaction else None,
        "daily": [r.to_dict() for r in records],
    }
