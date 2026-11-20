"""Optional LLM brain adapter.

The deterministic application remains usable without a model provider. When configured,
this adapter asks an OpenAI-compatible chat-completions endpoint for a structured plan.
Model output is untrusted and must pass AgentRuntime policy checks before any tool runs.
"""
import json
from typing import Any

import httpx


class BrainNotConfigured(RuntimeError):
    pass


class OpenAICompatibleBrain:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: float = 20.0):
        if not base_url or not api_key or not model:
            raise BrainNotConfigured("Configure AI_BASE_URL, AI_API_KEY and AI_MODEL")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def create_plan(
        self, *, agent_name: str, instructions: str, task: str, tools: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": (
                    f"You are the {agent_name} agent. {instructions} "
                    "Return JSON only in the form {\"steps\":[{\"tool\":\"name\",\"arguments\":{}}]}. "
                    "Never claim a tool ran. Only propose tools listed in the supplied tool catalogue."
                )},
                {"role": "user", "content": json.dumps({"task": task, "tools": tools})},
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        decoded = json.loads(content)
        steps = decoded.get("steps")
        if not isinstance(steps, list) or any(not isinstance(item, dict) for item in steps):
            raise ValueError("Model returned an invalid plan")
        return steps
