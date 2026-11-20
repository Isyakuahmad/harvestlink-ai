"""Guarded plan/act/observe/check runtime for HarvestLink agents.

Tools are explicitly registered by application code. A model may suggest a tool name,
but the rulebook and runtime decide whether it can execute.
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import uuid4

from app.agents.rules import get_rulebook


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    consequential: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def describe(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]


@dataclass
class ExecutionTrace:
    run_id: str
    agent: str
    status: str
    events: list[dict[str, Any]]

    def record(self, event: str, **details: Any) -> None:
        self.events.append({
            "event": event,
            "timestamp": datetime.now(UTC).isoformat(),
            **details,
        })


class AgentRuntime:
    """Execute one proposed tool action with policy checks and observable checks."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(
        self,
        agent_name: str,
        plan: list[dict[str, Any]],
        *,
        approved_actions: frozenset[str] = frozenset(),
    ) -> ExecutionTrace:
        rulebook = get_rulebook(agent_name)
        trace = ExecutionTrace(str(uuid4()), agent_name, "running", [])
        trace.record("plan_created", steps=len(plan))

        for index, step in enumerate(plan):
            tool_name = str(step.get("tool", ""))
            trace.record("plan_step", index=index, tool=tool_name)
            try:
                tool = self.registry.get(tool_name)
                if tool_name not in rulebook.allowed_tools:
                    raise PermissionError(f"{agent_name} is not authorised to use {tool_name}")
                if tool.consequential and tool_name not in approved_actions:
                    trace.record("approval_required", tool=tool_name)
                    trace.status = "awaiting_human_approval"
                    return trace

                trace.record("tool_call_started", tool=tool_name)
                result = tool.handler(dict(step.get("arguments") or {}))
                if not isinstance(result, dict):
                    raise TypeError("Tool handlers must return a dictionary")
                trace.record("tool_result_observed", tool=tool_name, result=result)
                if result.get("ok") is False:
                    raise RuntimeError(str(result.get("error", "Tool reported failure")))
                trace.record("step_checked", tool=tool_name, passed=True)
            except Exception as exc:
                trace.record("step_checked", tool=tool_name, passed=False, error=str(exc))
                trace.status = "failed"
                return trace

        trace.status = "completed"
        trace.record("workflow_completed")
        return trace


def normalize_crop_name(arguments: dict[str, Any]) -> dict[str, Any]:
    crop = str(arguments.get("crop_name", "")).strip().lower()
    if not crop:
        return {"ok": False, "error": "crop_name is required"}
    aliases = {"corn": "maize", "paddy rice": "rice"}
    return {"ok": True, "crop_name": aliases.get(crop, crop)}


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(Tool(
        name="normalize_crop_name",
        description="Normalise a supplied crop name; does not look up or invent market data.",
        handler=normalize_crop_name,
    ))
    registry.register(Tool(
        name="get_agent_capabilities",
        description="List configured HarvestLink specialist agent names.",
        handler=lambda _: {"ok": True, "agents": [
            "farmer", "buyer_matching", "market_intelligence", "logistics",
            "storage", "trust_transaction",
        ]},
    ))
    return registry
