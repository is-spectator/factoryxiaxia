"""转人工工单服务。"""

from extensions import db
from models import HandoffTicket
from services.messages import send_message
from utils.helpers import generate_ticket_no


def create_handoff_ticket(deployment, session, reason, summary="", request_source="system"):
    existing = HandoffTicket.query.filter(
        HandoffTicket.session_id == session.id,
        HandoffTicket.status.in_(["open", "in_progress"]),
    ).order_by(HandoffTicket.id.desc()).first()
    if existing:
        return existing, False

    ticket = HandoffTicket(
        deployment_id=deployment.id,
        session_id=session.id,
        user_id=deployment.user_id,
        ticket_no=generate_ticket_no(),
        status="open",
        reason=reason,
        summary=summary,
        request_source=request_source,
    )
    session.needs_handoff = True
    session.status = "handoff_requested"
    session.handoff_reason = reason
    db.session.add(ticket)

    send_message(
        deployment.user_id,
        "有新的转人工请求",
        f"机器人「{deployment.deployment_name}」收到转人工请求，工单号 {ticket.ticket_no}。",
        "system",
        deployment.order_id,
    )
    return ticket, True
