"""LLM Provider 抽象层。"""
import json
import os
import time
import urllib.error
import urllib.request

from services.agents.support_responder import generate_support_response


DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
SUPPORTED_PROVIDERS = ("rules", "dashscope")


def _env(key, default=""):
    return (os.environ.get(key) or default).strip()


def normalize_provider_name(provider_name=None):
    provider = str(provider_name or "").strip().lower()
    if provider in ("dashscope", "qwen", "qwen-max"):
        return "dashscope"
    return "rules"


def get_default_provider_name():
    provider = _env("AGENT_PROVIDER")
    if provider:
        return normalize_provider_name(provider)
    if is_dashscope_configured():
        return "dashscope"
    return "rules"


def get_default_provider_model(provider_name=None):
    provider_name = normalize_provider_name(provider_name or get_default_provider_name())
    if provider_name == "dashscope":
        return _env("DASHSCOPE_MODEL", "qwen-max")
    return ""


def get_provider_defaults(provider_name=None):
    provider_name = normalize_provider_name(provider_name or get_default_provider_name())
    defaults = {
        "provider": provider_name,
        "provider_model": "",
        "provider_temperature": 0.2,
        "provider_top_p": 0.8,
        "provider_max_tokens": 800,
        "provider_timeout_seconds": 30,
        "provider_retry_attempts": 1,
    }
    if provider_name == "dashscope":
        defaults.update({
            "provider_model": get_default_provider_model(provider_name),
            "provider_temperature": float(_env("DASHSCOPE_TEMPERATURE", "0.2")),
            "provider_top_p": float(_env("DASHSCOPE_TOP_P", "0.8")),
            "provider_max_tokens": int(_env("DASHSCOPE_MAX_TOKENS", "800")),
            "provider_timeout_seconds": int(_env("DASHSCOPE_TIMEOUT_SECONDS", "30")),
            "provider_retry_attempts": int(_env("DASHSCOPE_RETRY_ATTEMPTS", "1")),
        })
    return defaults


def is_dashscope_configured():
    return bool(_env("DASHSCOPE_API_KEY"))


def get_provider_capabilities():
    default_provider = get_default_provider_name()
    return {
        "default_provider": default_provider,
        "default_model": get_default_provider_model(default_provider),
        "dashscope_enabled": is_dashscope_configured(),
        "provider_defaults": get_provider_defaults(default_provider),
        "supported_providers": [
            {
                "name": "rules",
                "label": "rules",
                "configured": True,
                "models": [],
            },
            {
                "name": "dashscope",
                "label": "DashScope",
                "configured": is_dashscope_configured(),
                "models": [get_default_provider_model("dashscope") or "qwen-max"],
            },
        ],
    }


def _get_int_config(deployment_config, key, default_value, minimum=0):
    raw = deployment_config.get(key, default_value)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default_value
    return max(minimum, value)


def _get_float_config(deployment_config, key, default_value, minimum=0.0, maximum=2.0):
    raw = deployment_config.get(key, default_value)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default_value
    return max(minimum, min(maximum, value))


def _extract_message_text(content):
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in ("text", "output_text"):
                parts.append(str(item.get("text") or "").strip())
            elif isinstance(item, str):
                parts.append(item.strip())
        return "\n".join(part for part in parts if part)
    return ""


class RulesSupportProvider:
    name = "rules"

    def generate(self, system_prompt, user_message, snippets, deployment_config):
        response = generate_support_response(user_message, snippets, deployment_config)
        response["provider"] = self.name
        response["provider_meta"] = {
            "model": "rules",
            "latency_ms": 0,
            "usage": {},
            "status": "ok",
            "fallback_used": False,
        }
        return response


class DashScopeQwenProvider:
    name = "dashscope"

    def __init__(self):
        self.api_key = _env("DASHSCOPE_API_KEY")
        self.base_url = _env("DASHSCOPE_BASE_URL", DEFAULT_DASHSCOPE_BASE_URL)
        self.fallback_provider = RulesSupportProvider()

    def _build_messages(self, system_prompt, user_message, snippets, heuristic_response):
        snippets_text = "\n".join(
            f"- {snippet['title']}: {snippet['excerpt']}" for snippet in snippets
        ) or "- 当前没有命中知识片段，请明确说明知识不足并建议转人工。"
        strategy_text = (
            f"风险等级: {heuristic_response['risk_level']}\n"
            f"是否建议转人工: {'是' if heuristic_response['should_handoff'] else '否'}\n"
            f"原因: {heuristic_response['reason']}\n"
            f"规则草稿: {heuristic_response['reply']}"
        )
        user_content = (
            f"客户问题:\n{user_message}\n\n"
            f"知识片段:\n{snippets_text}\n\n"
            f"回复策略:\n{strategy_text}\n\n"
            "请直接输出最终给客户看的中文回复，不要解释思考过程，不要编造知识片段之外的信息。"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    def _request_completion(self, model, messages, deployment_config):
        timeout_seconds = _get_int_config(
            deployment_config,
            "provider_timeout_seconds",
            get_provider_defaults(self.name)["provider_timeout_seconds"],
            minimum=5,
        )
        retry_attempts = _get_int_config(
            deployment_config,
            "provider_retry_attempts",
            get_provider_defaults(self.name)["provider_retry_attempts"],
            minimum=0,
        )
        payload = {
            "model": model,
            "messages": messages,
            "temperature": _get_float_config(
                deployment_config,
                "provider_temperature",
                get_provider_defaults(self.name)["provider_temperature"],
                minimum=0.0,
                maximum=2.0,
            ),
            "top_p": _get_float_config(
                deployment_config,
                "provider_top_p",
                get_provider_defaults(self.name)["provider_top_p"],
                minimum=0.0,
                maximum=1.0,
            ),
            "max_tokens": _get_int_config(
                deployment_config,
                "provider_max_tokens",
                get_provider_defaults(self.name)["provider_max_tokens"],
                minimum=64,
            ),
        }

        last_error = None
        started_at = time.perf_counter()
        for attempt in range(retry_attempts + 1):
            request_obj = urllib.request.Request(
                self.base_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request_obj, timeout=timeout_seconds) as response:
                    body = response.read().decode("utf-8")
                    latency_ms = round((time.perf_counter() - started_at) * 1000, 1)
                    return json.loads(body), latency_ms
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="ignore")
                last_error = RuntimeError(f"DashScope HTTP {exc.code}: {error_body[:240]}")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            if attempt < retry_attempts:
                time.sleep(min(1.5, 0.5 * (attempt + 1)))

        raise RuntimeError(str(last_error or "DashScope 调用失败"))

    def generate(self, system_prompt, user_message, snippets, deployment_config):
        heuristic_response = generate_support_response(user_message, snippets, deployment_config)
        heuristic_response["provider_meta"] = {
            "model": deployment_config.get("provider_model") or get_default_provider_model(self.name),
            "latency_ms": 0,
            "usage": {},
            "status": "fallback",
            "fallback_used": True,
        }

        if not self.api_key:
            fallback = self.fallback_provider.generate(system_prompt, user_message, snippets, deployment_config)
            fallback["provider_meta"].update({
                "requested_provider": self.name,
                "status": "missing_api_key",
                "fallback_used": True,
                "error": "DASHSCOPE_API_KEY 未配置，已回退到 rules provider",
            })
            return fallback

        model = (deployment_config.get("provider_model") or get_default_provider_model(self.name) or "qwen-max").strip()
        messages = self._build_messages(system_prompt, user_message, snippets, heuristic_response)

        try:
            raw_response, latency_ms = self._request_completion(model, messages, deployment_config)
            choices = raw_response.get("choices") or []
            message = choices[0].get("message") if choices else {}
            output_text = _extract_message_text(message.get("content"))
            if not output_text:
                raise RuntimeError("DashScope 返回内容为空")

            heuristic_response["reply"] = output_text
            heuristic_response["provider"] = self.name
            heuristic_response["provider_meta"] = {
                "model": model,
                "latency_ms": latency_ms,
                "usage": raw_response.get("usage") or {},
                "request_id": raw_response.get("id"),
                "status": "ok",
                "fallback_used": False,
            }
            return heuristic_response
        except Exception as exc:  # noqa: BLE001
            fallback = self.fallback_provider.generate(system_prompt, user_message, snippets, deployment_config)
            fallback["provider_meta"].update({
                "requested_provider": self.name,
                "requested_model": model,
                "status": "provider_failed",
                "fallback_used": True,
                "error": str(exc),
            })
            return fallback


def get_chat_provider(provider_name=None):
    provider_name = normalize_provider_name(provider_name or get_default_provider_name())
    if provider_name == "dashscope":
        return DashScopeQwenProvider()
    return RulesSupportProvider()
