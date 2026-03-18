"""Support Responder 的轻量执行逻辑。

首版先用规则 + 知识片段拼装回复，后续可以替换成真实 LLM。
"""

HANDOFF_KEYWORDS = {
    "人工", "人工客服", "投诉", "退款", "退货", "赔偿", "法律", "律师",
    "隐私", "合同", "human", "refund", "complaint",
}
SENSITIVE_KEYWORDS = {
    "赔偿", "法律", "律师", "隐私", "退款", "退货", "合同",
}


def _contains_keyword(message, keywords):
    lowered = (message or "").lower()
    for keyword in keywords:
        if keyword.lower() in lowered:
            return True
    return False


def _voice_prefix(brand_voice):
    voice = (brand_voice or "professional").strip().lower()
    if voice in ("warm", "friendly"):
        return "我先根据当前知识库帮你整理一下："
    if voice in ("concise", "brief"):
        return "结论如下："
    return "根据当前知识库，我可以先确认这些信息："


def generate_support_response(user_message, snippets, deployment_config=None):
    deployment_config = deployment_config or {}
    explicit_handoff = _contains_keyword(user_message, HANDOFF_KEYWORDS)
    sensitive = _contains_keyword(user_message, SENSITIVE_KEYWORDS)
    top_score = snippets[0]["score"] if snippets else 0

    confidence = 0.28
    if snippets:
        confidence = min(0.96, 0.42 + min(top_score, 5) * 0.08 + max(0, len(snippets) - 1) * 0.05)

    if sensitive:
        confidence = min(confidence, 0.42)
    if explicit_handoff:
        confidence = min(confidence, 0.35)

    if not snippets:
        return {
            "reply": (
                "这个问题我暂时没有足够的知识库依据来直接答复。"
                "为了避免误导，我已经建议转人工继续处理。"
            ),
            "confidence": round(confidence, 3),
            "risk_level": "medium",
            "should_handoff": True,
            "reason": "knowledge_not_found",
            "sources": [],
        }

    lead = _voice_prefix(deployment_config.get("brand_voice"))
    snippets_text = "；".join(
        f"{snippet['title']}：{snippet['excerpt']}" for snippet in snippets[:2]
    )
    closing = "如果你愿意，我可以继续帮你细化到下一步处理动作。"
    should_handoff = False
    reason = "answered_from_knowledge"
    risk_level = "low"

    if sensitive or explicit_handoff:
        should_handoff = True
        reason = "sensitive_or_manual_handoff"
        risk_level = "high" if sensitive else "medium"
        closing = "这个问题更适合交给人工客服继续确认，我已经建议转人工。"
    elif confidence < 0.6:
        should_handoff = True
        reason = "low_confidence"
        risk_level = "medium"
        closing = "当前命中信息还不够充分，建议转人工做进一步确认。"

    return {
        "reply": f"{lead}{snippets_text}。{closing}",
        "confidence": round(confidence, 3),
        "risk_level": risk_level,
        "should_handoff": should_handoff,
        "reason": reason,
        "sources": [
            {
                "document_id": snippet["document_id"],
                "title": snippet["title"],
                "source_name": snippet["source_name"],
            }
            for snippet in snippets
        ],
    }
