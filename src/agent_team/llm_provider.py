"""LLM Provider 抽象层 — 统一 Anthropic 和 OpenAI 接口。

工具 schema 内部使用 Anthropic 格式（name/description/input_schema），
Provider 负责在调用 OpenAI 时转换格式。

用法:
    provider = AnthropicProvider()          # 默认，需 ANTHROPIC_API_KEY
    provider = OpenAIProvider()             # 需 OPENAI_API_KEY
    provider = OpenAIProvider(model="gpt-4o")

    response = await provider.create_message(
        model="claude-sonnet-4-6",
        system_prompt="You are...",
        messages=[{"role": "user", "content": "Hello"}],
        tools=[{"name": "read_file", "description": "...", "input_schema": {...}}],
        max_tokens=4096,
    )
    # response.content, response.stop_reason, response.usage 统一格式
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Unified response types ──────────────────────────────────────────

@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class LLMResponse:
    """与 provider 无关的 LLM 响应。"""
    content: list            # TextBlock(str) or ToolUseBlock
    stop_reason: str         # "end_turn" or "tool_use"
    usage: TokenUsage


# ── Provider base ────────────────────────────────────────────────────

class LLMProvider(ABC):
    """LLM 供应商的抽象基类。"""

    # 可重试的错误关键词
    _RETRYABLE_ERRORS = ("rate", "limit", "throttl", "429", "too many", "overloaded", "capacity", "timeout")

    async def create_message(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        extra_body: Optional[dict] = None,
    ) -> LLMResponse:
        """带重试的 create_message，处理限流和临时错误。最多重试 3 次。"""
        last_error = None
        for attempt in range(3):
            try:
                return await self._create_message_impl(
                    model, system_prompt, messages, tools, max_tokens, extra_body
                )
            except Exception as exc:
                last_error = exc
                err_str = str(exc).lower()
                is_retryable = any(kw in err_str for kw in self._RETRYABLE_ERRORS)
                if is_retryable and attempt < 2:
                    wait = (attempt + 1) * 3  # 3s, 6s, then give up
                    logger.warning(
                        f"LLM call failed (retryable, attempt {attempt+1}/3): {exc}. "
                        f"Waiting {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        raise last_error  # type: ignore

    @abstractmethod
    async def _create_message_impl(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        extra_body: Optional[dict] = None,
    ) -> LLMResponse:
        """子类实现具体调用逻辑"""
        ...


# ── Base provider (共享 __init__ / _get_client / semaphore) ─────────

class _BaseProvider(LLMProvider):
    """Provider 基类：封装 API key 解析、懒惰客户端创建、并发信号量。"""

    _api_key_env: str = ""
    _base_url_env: str = ""
    _default_model: str = ""
    _client_module: str = ""       # e.g. "anthropic"
    _client_class: str = ""        # e.g. "AsyncAnthropic"
    _api_key_error: str = ""       # e.g. "ANTHROPIC_API_KEY not set"

    def __init__(self, api_key: str = "", model: str = "",
                 base_url: str = "", max_concurrent: int | None = None):
        self.api_key = api_key or os.environ.get(self._api_key_env, "")
        if not self.api_key:
            raise RuntimeError(self._api_key_error)
        self.base_url = base_url or os.environ.get(self._base_url_env, "")
        self.default_model = model or self._default_model
        self._client = None
        self._semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else None

    def _get_client(self):
        if self._client is None:
            mod = __import__(self._client_module)
            cls = getattr(mod, self._client_class)
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = cls(**kwargs)
        return self._client

    async def _create_message_impl(
        self,
        model: str = "",
        system_prompt: str = "",
        messages: list[dict] | None = None,
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        extra_body: dict | None = None,
    ) -> LLMResponse:
        if self._semaphore:
            async with self._semaphore:
                return await self._do_create_message(model, system_prompt, messages, tools, max_tokens, extra_body)
        return await self._do_create_message(model, system_prompt, messages, tools, max_tokens, extra_body)


# ── Anthropic provider ───────────────────────────────────────────────

class AnthropicProvider(_BaseProvider):
    """Anthropic Claude API。

    需要环境变量 ANTHROPIC_API_KEY。
    可通过 ANTHROPIC_BASE_URL 或 base_url 参数指定自定义端点。
    max_concurrent: 最大并发请求数（None=不限制，设为 1-2 可避免低 QPS API 限流）
    """

    _api_key_env = "ANTHROPIC_API_KEY"
    _base_url_env = "ANTHROPIC_BASE_URL"
    _default_model = "claude-sonnet-4-6"
    _client_module = "anthropic"
    _client_class = "AsyncAnthropic"
    _api_key_error = "ANTHROPIC_API_KEY not set"

    async def _do_create_message(self, model, system_prompt, messages, tools, max_tokens, extra_body):
        client = self._get_client()
        kwargs = {
            "model": model or self.default_model,
            "system": system_prompt,
            "messages": messages or [],
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if extra_body:
            kwargs["extra_body"] = extra_body
        resp = await client.messages.create(**kwargs)
        return self._to_unified(resp)

    @staticmethod
    def _to_unified(resp) -> LLMResponse:
        content = []
        for block in resp.content:
            if block.type == "tool_use":
                content.append(ToolUseBlock(id=block.id, name=block.name, input=block.input))
            else:
                content.append(getattr(block, 'text', str(block)))

        stop = "tool_use" if resp.stop_reason == "tool_use" else "end_turn"

        return LLMResponse(
            content=content,
            stop_reason=stop,
            usage=TokenUsage(
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
            ),
        )


# ── OpenAI provider ──────────────────────────────────────────────────

class OpenAIProvider(_BaseProvider):
    """OpenAI 兼容 API（GPT-4o, GPT-4.1, Qwen, DeepSeek 等）。

    需要环境变量 OPENAI_API_KEY。
    通过 OPENAI_BASE_URL 或 base_url 参数指定自定义端点。
    max_concurrent: 最大并发请求数（None=不限制，设为 1-2 可避免低 QPS API 限流）
    """

    _api_key_env = "OPENAI_API_KEY"
    _base_url_env = "OPENAI_BASE_URL"
    _default_model = "gpt-4o"
    _client_module = "openai"
    _client_class = "AsyncOpenAI"
    _api_key_error = "OPENAI_API_KEY not set"

    async def _do_create_message(self, model, system_prompt, messages, tools, max_tokens, extra_body):
        client = self._get_client()

        # 构建 OpenAI 格式的消息列表
        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

        openai_messages.extend(self._convert_messages(messages or []))

        # 转换工具格式
        openai_tools = None
        if tools:
            openai_tools = [self._convert_tool_schema(t) for t in tools]

        effective_model = model or self.default_model

        # Qwen3 系列默认关掉 thinking——但部分模型/API版本不支持此参数
        # 仅对明确以 "qwen3-" 开头的模型启用（qwen3.6-max-preview 不走此逻辑）
        merged_extra = dict(extra_body) if extra_body else {}
        if effective_model.lower().startswith("qwen3-") and "enable_thinking" not in merged_extra:
            merged_extra["enable_thinking"] = False

        kwargs = {
            "model": effective_model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools
        if merged_extra:
            kwargs["extra_body"] = merged_extra

        logger.debug(f"OpenAI request: model={effective_model}, extra_body={merged_extra}")
        try:
            resp = await client.chat.completions.create(**kwargs)
            return self._to_unified(resp)
        except Exception as exc:
            # 记录完整的错误信息，包括请求体
            body_summary = {
                "model": effective_model,
                "message_count": len(openai_messages),
                "has_tools": openai_tools is not None,
                "extra_body": merged_extra,
            }
            logger.error(
                f"OpenAI API error: {exc}\n"
                f"  Request summary: {body_summary}\n"
                f"  System prompt length: {len(system_prompt)} chars\n"
                f"  Last message length: {len(str(openai_messages[-1].get('content',''))) if openai_messages else 0} chars"
            )
            raise

    @staticmethod
    def _convert_messages(messages: list[dict]) -> list[dict]:
        """将 Anthropic 风格的消息列表转换为 OpenAI 格式。"""
        result = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # 纯文本消息
            if isinstance(content, str):
                result.append({"role": role, "content": content})
                continue

            # 列表内容
            if isinstance(content, list):
                if role == "assistant":
                    text_parts = []
                    tool_calls = []
                    for block in content:
                        if OpenAIProvider._is_tool_use(block):
                            tool_calls.append({
                                "id": block.id,
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": json.dumps(block.input),
                                },
                            })
                        elif isinstance(block, str):
                            text_parts.append(block)
                        elif hasattr(block, 'text'):
                            text_parts.append(block.text)

                    r = {"role": "assistant"}
                    r["content"] = "\n".join(text_parts) if text_parts else None
                    if tool_calls:
                        r["tool_calls"] = tool_calls
                    result.append(r)

                elif role == "user":
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            result.append({
                                "role": "tool",
                                "tool_call_id": block["tool_use_id"],
                                "content": block["content"],
                            })

            else:
                result.append({"role": role, "content": str(content)})
        return result

    @staticmethod
    def _is_tool_use(block) -> bool:
        """检查 block 是否是工具调用（兼容 Anthropic SDK 和 ToolUseBlock）。"""
        if isinstance(block, ToolUseBlock):
            return True
        if hasattr(block, 'type') and getattr(block, 'type') == 'tool_use':
            return True
        return False

    @staticmethod
    def _convert_tool_schema(schema: dict) -> dict:
        """将 Anthropic 工具 schema 转换为 OpenAI 格式。"""
        return {
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema.get("description", ""),
                "parameters": schema.get("input_schema", {"type": "object", "properties": {}}),
            },
        }

    @staticmethod
    def _to_unified(resp) -> LLMResponse:
        choice = resp.choices[0]
        content = []
        stop = "end_turn"

        if choice.message.content:
            content.append(choice.message.content)

        if choice.message.tool_calls:
            stop = "tool_use"
            for tc in choice.message.tool_calls:
                raw_args = tc.function.arguments or ""
                try:
                    args = json.loads(raw_args) if raw_args.strip() else {}
                except json.JSONDecodeError:
                    logger.warning(
                        f"OpenAI tool call JSON parse failed for {tc.function.name}: "
                        f"raw={raw_args[:300]}"
                    )
                    args = {}
                content.append(ToolUseBlock(
                    id=tc.id,
                    name=tc.function.name,
                    input=args,
                ))

        if choice.finish_reason == "tool_calls":
            stop = "tool_use"

        return LLMResponse(
            content=content,
            stop_reason=stop,
            usage=TokenUsage(
                input_tokens=resp.usage.prompt_tokens,
                output_tokens=resp.usage.completion_tokens,
            ),
        )


# ── Factory ──────────────────────────────────────────────────────────

def create_provider(provider_type: str = "", model: str = "",
                    api_key: str = "", base_url: str = "") -> LLMProvider:
    """根据类型创建 Provider。

    Args:
        provider_type: "anthropic" 或 "openai"（默认从 AGENT_TEAM_PROVIDER 环境变量读取）
        model: 覆盖默认模型
        api_key: 覆盖 API key
        base_url: 自定义 API 端点（如 Qwen: https://dashscope.aliyuncs.com/compatible-mode/v1）
    """
    ptype = provider_type or os.environ.get("AGENT_TEAM_PROVIDER", "anthropic")

    if ptype == "openai":
        return OpenAIProvider(api_key=api_key, model=model or "gpt-4o",
                             base_url=base_url)
    else:
        return AnthropicProvider(api_key=api_key, model=model or "claude-sonnet-4-6",
                                base_url=base_url)
