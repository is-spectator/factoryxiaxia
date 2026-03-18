"""聊天安全与脱敏规则。"""
import re


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")


def apply_pii_masking(text):
    findings = []
    masked = text or ""

    if EMAIL_RE.search(masked):
        masked = EMAIL_RE.sub("[masked-email]", masked)
        findings.append("email")
    if PHONE_RE.search(masked):
        masked = PHONE_RE.sub("[masked-phone]", masked)
        findings.append("phone")

    return masked, findings


def _find_matches(text, keywords):
    lowered = (text or "").lower()
    return [keyword for keyword in keywords if keyword and keyword.lower() in lowered]


def inspect_inbound_message(message, deployment_config):
    deployment_config = deployment_config or {}
    pii_enabled = deployment_config.get("pii_masking_enabled", True)
    masked_message, pii_findings = apply_pii_masking(message) if pii_enabled else ((message or ""), [])

    forbidden_topics = deployment_config.get("forbidden_topics") or []
    sensitive_keywords = deployment_config.get("sensitive_keywords") or []
    forbidden_matches = _find_matches(masked_message, forbidden_topics)
    sensitive_matches = _find_matches(masked_message, sensitive_keywords)

    blocked = bool(forbidden_matches)
    should_handoff = bool(forbidden_matches or sensitive_matches)
    if pii_findings and deployment_config.get("handoff_on_pii"):
        should_handoff = True

    risk_level = "low"
    if forbidden_matches or sensitive_matches:
        risk_level = "high"
    elif pii_findings:
        risk_level = "medium"

    refusal_message = None
    reason = None
    if forbidden_matches:
        reason = "forbidden_topic"
        refusal_message = (
            "这个问题超出了当前机器人可直接处理的范围。"
            "为了避免误导，我已经建议转人工继续确认。"
        )
    elif sensitive_matches:
        reason = "sensitive_keyword"

    return {
        "masked_message": masked_message,
        "pii_findings": pii_findings,
        "forbidden_matches": forbidden_matches,
        "sensitive_matches": sensitive_matches,
        "blocked": blocked,
        "should_handoff": should_handoff,
        "risk_level": risk_level,
        "reason": reason,
        "refusal_message": refusal_message,
    }


def sanitize_outbound_message(message, deployment_config):
    if deployment_config.get("pii_masking_enabled", True):
        masked_message, _ = apply_pii_masking(message)
        return masked_message
    return message
