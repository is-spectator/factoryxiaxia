"""LLM Provider 抽象层。

首版默认走 rules provider，后续可以扩展 OpenAI / self-hosted provider。
"""
import os

from services.agents.support_responder import generate_support_response


class RulesSupportProvider:
    name = "rules"

    def generate(self, system_prompt, user_message, snippets, deployment_config):
        response = generate_support_response(user_message, snippets, deployment_config)
        response["provider"] = self.name
        response["system_prompt"] = system_prompt
        return response


def get_chat_provider(provider_name=None):
    provider_name = (provider_name or os.environ.get("AGENT_PROVIDER", "rules")).strip().lower()
    if provider_name in ("", "rules", "mock", "local"):
        return RulesSupportProvider()
    return RulesSupportProvider()
