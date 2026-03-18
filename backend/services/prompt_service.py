"""Prompt 模板渲染服务。"""


def render_support_prompt(template, deployment, deployment_config, snippets, policy):
    tools = template.to_dict().get("default_tools", []) if template else []
    tools_text = ", ".join(tools) if tools else "knowledge_base, handoff, conversation_log"
    forbidden_text = ", ".join(policy.get("forbidden_topics") or []) or "无"
    sensitive_text = ", ".join(policy.get("sensitive_keywords") or []) or "无"
    knowledge_text = "\n".join(
        f"- {snippet['title']}: {snippet['excerpt']}" for snippet in snippets
    ) or "- 当前没有命中知识片段，必须保守回答并考虑转人工。"

    base_template = (
        template.prompt_template
        if template and template.prompt_template
        else (
            "你是企业专属数字客服员工，必须严格基于知识库回答。"
            "不确定时要明确说明，并优先转人工。"
        )
    )

    return (
        f"{base_template}\n\n"
        f"企业名称: {deployment_config.get('business_name') or deployment.deployment_name}\n"
        f"品牌语气: {deployment_config.get('brand_voice') or 'professional'}\n"
        f"可用工具: {tools_text}\n"
        f"禁答主题: {forbidden_text}\n"
        f"高风险关键词: {sensitive_text}\n"
        f"当前部署: {deployment.deployment_name}\n"
        f"知识片段:\n{knowledge_text}\n"
        "输出要求:\n"
        "1. 回答必须基于知识片段，不得编造。\n"
        "2. 遇到高风险、知识不足、禁答主题时，优先转人工。\n"
        "3. 回答应简洁、克制、以解决问题为中心。"
    )
