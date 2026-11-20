"""Agent rulebooks: responsibilities, tool allowlists and approval boundaries.

These policies are enforced by the runtime; model output is never an authority grant.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRulebook:
    name: str
    purpose: str
    allowed_tools: frozenset[str]
    prohibited_actions: tuple[str, ...]
    requires_human_approval: frozenset[str]


RULEBOOKS: dict[str, AgentRulebook] = {
    "orchestrator": AgentRulebook(
        name="orchestrator",
        purpose="Coordinate specialist agents and report verified workflow outcomes.",
        allowed_tools=frozenset({"get_agent_capabilities"}),
        prohibited_actions=("inventing records", "bypassing role permissions", "claiming unconfirmed success"),
        requires_human_approval=frozenset({"external_contact", "publish_listing", "bind_transaction", "book_logistics", "payment"}),
    ),
    "farmer": AgentRulebook(
        name="farmer",
        purpose="Help farmers structure and review farm and produce information.",
        allowed_tools=frozenset({"normalize_crop_name"}),
        prohibited_actions=("publishing a listing", "sharing private farmer records", "inventing farm evidence"),
        requires_human_approval=frozenset({"publish_listing", "share_farmer_record"}),
    ),
    "buyer_matching": AgentRulebook(
        name="buyer_matching",
        purpose="Explain matches using authorised, persisted marketplace information.",
        allowed_tools=frozenset({"normalize_crop_name"}),
        prohibited_actions=("inventing stock", "inventing prices", "contacting suppliers"),
        requires_human_approval=frozenset({"external_contact", "reserve_inventory"}),
    ),
    "market_intelligence": AgentRulebook(
        name="market_intelligence",
        purpose="Summarise supplied, timestamped market evidence and disclose gaps.",
        allowed_tools=frozenset(),
        prohibited_actions=("fabricating market prices", "presenting estimates as verified facts"),
        requires_human_approval=frozenset({"publish_market_advice"}),
    ),
    "logistics": AgentRulebook(
        name="logistics",
        purpose="Assist with logistics information and quotation comparison.",
        allowed_tools=frozenset(),
        prohibited_actions=("inventing provider capacity or quotes", "booking without approvals"),
        requires_human_approval=frozenset({"book_logistics", "contact_provider"}),
    ),
    "storage": AgentRulebook(
        name="storage",
        purpose="Assist with storage requirements using supplied provider records.",
        allowed_tools=frozenset(),
        prohibited_actions=("inventing warehouse capacity", "claiming an unconfirmed reservation"),
        requires_human_approval=frozenset({"reserve_storage", "contact_provider"}),
    ),
    "trust_transaction": AgentRulebook(
        name="trust_transaction",
        purpose="Apply verification and transaction policy using recorded evidence.",
        allowed_tools=frozenset(),
        prohibited_actions=("self-approving verification", "treating self-reports as independent proof"),
        requires_human_approval=frozenset({"verification_decision", "bind_transaction", "payment", "dispute_resolution"}),
    ),
}


def get_rulebook(agent_name: str) -> AgentRulebook:
    try:
        return RULEBOOKS[agent_name]
    except KeyError as exc:
        raise ValueError(f"Unknown agent: {agent_name}") from exc
