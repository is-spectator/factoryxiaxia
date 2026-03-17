"""站内消息服务"""
from extensions import db
from models import Message


def send_message(user_id, title, content="", msg_type="system", related_order_id=None):
    """创建站内消息"""
    msg = Message(
        user_id=user_id,
        title=title,
        content=content,
        msg_type=msg_type,
        related_order_id=related_order_id,
    )
    db.session.add(msg)
    return msg
