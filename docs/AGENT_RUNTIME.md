# HarvestLink AI — Four-pillar agent runtime

This implementation turns the Championship lesson's four-part agent model into an enforceable engineering contract.

## 1. Brain

`app.agents.brain.OpenAICompatibleBrain` is an optional OpenAI-compatible chat-completions adapter. It produces a proposed JSON tool plan. It is deliberately not enabled unless `AI_BASE_URL`, `AI_API_KEY` and `AI_MODEL` are configured. The application must remain functional without these values. Provider output is untrusted.

## 2. Hands

`ToolRegistry` contains explicitly registered Python tools. Tool handlers must return dictionaries. A model cannot create or register tools at runtime. The initial registry contains safe crop-name normalisation and agent-capability discovery examples; business-data tools should be added by wrapping existing authorised service functions, not by exposing raw database access.

## 3. Rulebook

`rules.py` defines each of the seven agents' purpose, tool allowlist, prohibited actions and human-approval boundaries. The runtime enforces the tool allowlist independently of model instructions. Unknown agents and tools fail closed.

## 4. Work habit

`AgentRuntime.execute` records a structured execution trace for plan creation, steps, tool calls, observed results, checks, approval requests and failures. It follows plan → act → observe → check → complete/escalate. The trace is returned to the caller and can be persisted by the calling workflow.

## Safety properties

- Model output is a proposal, never permission.
- Only registered tools can run.
- Each agent can invoke only its allowlisted tools.
- Consequential tools require an explicit approval token in the caller's approved-actions set.
- Tool errors and invalid results fail closed.
- No tool in the starter registry sends messages, publishes listings, books logistics or moves money.

## Configuration

Optional environment variables:

- `AI_BASE_URL`: OpenAI-compatible API base URL.
- `AI_API_KEY`: provider API key; keep it in deployment secrets, never commit it.
- `AI_MODEL`: model identifier.

Do not put secrets in GitHub source files, screenshots or chat messages.

## Current scope and honest limitations

This is a guarded runtime foundation, not yet a fully autonomous production multi-agent system. The LLM adapter is optional and not wired to live marketplace tools or WhatsApp. The starter tool registry deliberately exposes only safe examples. Next implementation steps are to wrap existing marketplace, farmer and logistics service functions with user-scoped tools, persist execution traces in the existing workflow/agent-task records, add authenticated agent-run endpoints, and run provider-backed evaluation tests after credentials are configured.
