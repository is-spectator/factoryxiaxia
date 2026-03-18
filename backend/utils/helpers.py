"""通用工具函数"""
import os
import re
import json
import logging
import datetime
import traceback
import random
import secrets


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    return logging.getLogger("xiaxia")


def send_alert(title, detail=""):
    """发送异常告警到 Webhook（钉钉/飞书/Slack）"""
    if not ALERT_WEBHOOK_URL:
        return
    try:
        import urllib.request
        payload = json.dumps({
            "msgtype": "text",
            "text": {"content": f"[虾虾工厂告警] {title}\n{detail}"}
        }).encode("utf-8")
        req = urllib.request.Request(ALERT_WEBHOOK_URL, data=payload,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        logger = logging.getLogger("xiaxia")
        logger.warning("告警发送失败")


def generate_order_no():
    now = datetime.datetime.utcnow()
    return now.strftime("XF%Y%m%d%H%M%S") + str(random.randint(1000, 9999))


def generate_payment_no():
    now = datetime.datetime.utcnow()
    return now.strftime("PAY%Y%m%d%H%M%S") + str(random.randint(100000, 999999))


def generate_ticket_no():
    now = datetime.datetime.utcnow()
    return now.strftime("HT%Y%m%d%H%M%S") + str(random.randint(1000, 9999))


def generate_public_token(length=18):
    return secrets.token_urlsafe(length)
