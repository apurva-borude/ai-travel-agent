"""Thin wrapper around the Cerebras inference API.

Cerebras gives a free tier (1M tokens/day) and an OpenAI-compatible chat API,
so the message / tool-call shapes below look just like OpenAI's.
Docs: https://inference-docs.cerebras.ai/
"""

import os

try:
    from cerebras.cloud.sdk import Cerebras
except ImportError:
    Cerebras = None


DEFAULT_MODEL = "gpt-oss-120b"
# DEFAULT_MODEL = "llama-3.3-70b"   # this one 404'd on my free key, kept for ref


class CerebrasLLM:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.environ.get("CEREBRAS_API_KEY")
        self.model = model or os.environ.get("CEREBRAS_MODEL") or DEFAULT_MODEL
        self._client = None
        if self.api_key and Cerebras is not None:
            # short timeout + few retries so that if we hit the free-tier rate
            # limit we fall back to the rules engine fast instead of hanging.
            self._client = Cerebras(
                api_key=self.api_key,
                timeout=20.0,
                max_retries=0,  # don't sit and retry on a 429, just fall back
            )

    @property
    def available(self) -> bool:
        """True if we can actually talk to Cerebras (key present + sdk installed)."""
        return self._client is not None

    def chat(self, messages, tools=None, tool_choice="auto", temperature=0.2):
        """Single chat completion call. Returns the raw message object so the
        agent can look at .content and .tool_calls itself."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            # gpt-oss is a reasoning model - keep effort low so the demo stays
            # snappy (it's only doing simple policy checks, not hard maths).
            "reasoning_effort": "low",
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message
