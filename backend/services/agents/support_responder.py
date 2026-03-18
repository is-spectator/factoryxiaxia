"""Support Responder 机器人核心逻辑

基于 agency-agents/support/support-support-responder.md 改造。
负责：
1. 根据知识库检索答案
2. 生成客服回复
3. 输出置信度
4. 决定是否转人工
"""
import json
import re
from models import KnowledgeDocument, ConversationMessage


# 简单关键词匹配 RAG（MVP 阶段，后续替换为向量检索）
def search_knowledge_base(deployment, query, top_k=3):
    """从部署关联的知识库中检索相关文档"""
    kb_list = deployment.knowledge_bases
    if not kb_list:
        return []

    active_kbs = [kb for kb in kb_list if kb.status == "active"]
    if not active_kbs:
        return []

    kb_ids = [kb.id for kb in active_kbs]
    docs = KnowledgeDocument.query.filter(
        KnowledgeDocument.knowledge_base_id.in_(kb_ids),
        KnowledgeDocument.status == "approved",
    ).all()

    if not docs:
        return []

    # 关键词评分
    query_terms = set(query.lower().split())
    scored = []
    for doc in docs:
        text = (doc.title + " " + doc.content).lower()
        score = sum(1 for term in query_terms if term in text)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def build_system_prompt(deployment, knowledge_docs):
    """构建 Support Responder 的 system prompt"""
    config = {}
    if deployment.config_json:
        try:
            config = json.loads(deployment.config_json)
        except (json.JSONDecodeError, TypeError):
            config = {}

    brand_name = config.get("brand_name", "")
    brand_tone = config.get("brand_tone", "专业、友善、高效")
    forbidden_topics = config.get("forbidden_topics", "")
    handoff_keywords = config.get("handoff_keywords", "转人工,找客服,投诉")

    knowledge_context = ""
    if knowledge_docs:
        for doc in knowledge_docs:
            knowledge_context += f"\n### {doc.title}\n{doc.content}\n"

    prompt = f"""你是 {brand_name or deployment.deployment_name} 的智能客服助手。

## 身份与风格
- 语气要求: {brand_tone}
- 你是一个专业的客服代表，始终保持耐心和同理心
- 用简洁清晰的语言回答问题
- 如果不确定答案，诚实告知并建议转人工客服

## 知识库参考
{knowledge_context if knowledge_context else '（暂无知识库内容，请根据通用常识回答）'}

## 禁止话题
{forbidden_topics if forbidden_topics else '无特殊限制'}

## 重要规则
1. 只基于知识库内容回答问题，不要编造信息
2. 如果问题超出知识库范围，回复"抱歉，这个问题我需要转给人工客服为您解答"
3. 不要做出任何承诺（如退款、补偿、折扣）
4. 不要透露内部系统信息或技术细节
5. 如果用户提到以下关键词，建议转人工: {handoff_keywords}

## 输出格式要求
请直接回复用户的问题，保持自然对话风格。"""

    return prompt


def generate_reply(deployment, user_message, session_messages=None):
    """生成机器人回复

    MVP 阶段使用基于关键词匹配的规则引擎。
    后续接入 LLM API 后替换此函数。

    Returns:
        dict: {
            "reply": str,          # 回复内容
            "confidence": float,   # 置信度 0-1
            "should_handoff": bool,# 是否应转人工
            "source_doc_ids": list,# 引用的文档 ID
            "handoff_reason": str, # 转人工原因
        }
    """
    config = {}
    if deployment.config_json:
        try:
            config = json.loads(deployment.config_json)
        except (json.JSONDecodeError, TypeError):
            config = {}

    handoff_keywords = config.get("handoff_keywords", "转人工,找客服,投诉,人工客服")
    handoff_kw_list = [kw.strip() for kw in handoff_keywords.split(",") if kw.strip()]

    # 检查是否触发转人工关键词
    for kw in handoff_kw_list:
        if kw in user_message:
            return {
                "reply": "好的，我这就为您转接人工客服，请稍等。",
                "confidence": 1.0,
                "should_handoff": True,
                "source_doc_ids": [],
                "handoff_reason": f"用户提到关键词: {kw}",
            }

    # 检索知识库
    matched_docs = search_knowledge_base(deployment, user_message)

    if not matched_docs:
        return {
            "reply": "抱歉，关于您的问题我暂时没有找到相关信息。我建议您转接人工客服获得更专业的帮助，请问需要为您转接吗？",
            "confidence": 0.2,
            "should_handoff": False,
            "source_doc_ids": [],
            "handoff_reason": "",
        }

    # 基于匹配到的文档生成回复
    best_doc = matched_docs[0]
    source_ids = [doc.id for doc in matched_docs]

    # 简单启发式回复生成（MVP）
    content = best_doc.content.strip()
    # 如果内容是 FAQ 格式（Q: ... A: ...），提取答案部分
    answer_match = re.search(r'[AaＡ答][：:]\s*(.+)', content, re.DOTALL)
    if answer_match:
        reply_text = answer_match.group(1).strip()
    else:
        # 直接用文档内容，截取前 500 字
        reply_text = content[:500]

    confidence = min(0.9, 0.5 + len(matched_docs) * 0.15)

    return {
        "reply": reply_text,
        "confidence": confidence,
        "should_handoff": confidence < 0.4,
        "source_doc_ids": source_ids,
        "handoff_reason": "置信度过低" if confidence < 0.4 else "",
    }
