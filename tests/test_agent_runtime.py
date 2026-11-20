from app.agents.rules import get_rulebook
from app.agents.runtime import AgentRuntime, Tool, ToolRegistry


def registry():
    tools = ToolRegistry()
    tools.register(Tool(
        name="normalize_crop_name",
        description="Normalise a crop name",
        handler=lambda args: {"ok": True, "crop_name": args["crop_name"].strip().lower()},
    ))
    tools.register(Tool(
        name="publish_listing",
        description="Publish a listing",
        handler=lambda args: {"ok": True, "published": True},
        consequential=True,
    ))
    return tools


def test_rulebooks_cover_all_seven_agents():
    expected = {
        "orchestrator", "farmer", "buyer_matching", "market_intelligence",
        "logistics", "storage", "trust_transaction",
    }
    assert expected == {
        get_rulebook(name).name for name in expected
    }


def test_agent_executes_allowlisted_tool_and_records_loop():
    runtime = AgentRuntime(registry())
    trace = runtime.execute("farmer", [{
        "tool": "normalize_crop_name", "arguments": {"crop_name": " Maize "}
    }])
    assert trace.status == "completed"
    assert [event["event"] for event in trace.events] == [
        "plan_created", "plan_step", "tool_call_started",
        "tool_result_observed", "step_checked", "workflow_completed",
    ]


def test_agent_cannot_call_tool_outside_its_rulebook():
    trace = AgentRuntime(registry()).execute("farmer", [{
        "tool": "publish_listing", "arguments": {"listing_id": 10}
    }])
    assert trace.status == "failed"
    assert "not authorised" in trace.events[-1]["error"]


def test_consequential_tool_requires_approval_even_if_allowlisted():
    tools = ToolRegistry()
    tools.register(Tool(
        name="publish_listing", description="Publish", handler=lambda _: {"ok": True},
        consequential=True,
    ))
    # Add the tool to a dedicated test rulebook without weakening production rules.
    from app.agents import rules
    original = rules.RULEBOOKS["farmer"]
    rules.RULEBOOKS["farmer"] = type(original)(
        name=original.name, purpose=original.purpose,
        allowed_tools=frozenset({"publish_listing"}),
        prohibited_actions=original.prohibited_actions,
        requires_human_approval=frozenset({"publish_listing"}),
    )
    try:
        runtime = AgentRuntime(tools)
        pending = runtime.execute("farmer", [{"tool": "publish_listing"}])
        assert pending.status == "awaiting_human_approval"
        approved = runtime.execute(
            "farmer", [{"tool": "publish_listing"}],
            approved_actions=frozenset({"publish_listing"}),
        )
        assert approved.status == "completed"
    finally:
        rules.RULEBOOKS["farmer"] = original


def test_tool_failure_fails_closed():
    tools = ToolRegistry()
    tools.register(Tool(
        name="normalize_crop_name", description="Fail",
        handler=lambda _: {"ok": False, "error": "source unavailable"},
    ))
    trace = AgentRuntime(tools).execute("farmer", [{"tool": "normalize_crop_name"}])
    assert trace.status == "failed"
    assert trace.events[-1]["passed"] is False
