"""Pilot subpackage: the AI Portfolio Manager experience.

Exposes:
- strategy_dsl: typed JSON spec + deterministic compiler (never let an LLM emit
  executable code; LLMs emit only specs).
- personality: portfolio-manager personalities (Atlas, Sage, Vega) plus a
  Mongo-backed CRUD for user-authored personalities.
- trade_proposals: pending -> approved/rejected/expired -> executed lifecycle
  with full audit log.
- pilot_engine: orchestrator that wires signals, risk, policy, swarm debate,
  NemoClaw sandbox transport, and Alpaca paper execution.
"""

from .strategy_dsl import (
    StrategySpec,
    SpecCompileResult,
    compile_spec,
    DEFAULT_SPEC_SCHEMA_VERSION,
)
from .personality import (
    Personality,
    PersonalityRiskPolicy,
    SEED_PERSONALITIES,
    get_personality,
    list_personalities,
    upsert_personality,
    delete_personality,
    set_paused,
    apply_user_override,
)
from .trade_proposals import (
    TradeProposal,
    ProposalStatus,
    create_proposal,
    get_proposal,
    list_proposals,
    update_proposal_status,
    expire_overdue_proposals,
)

__all__ = [
    "StrategySpec",
    "SpecCompileResult",
    "compile_spec",
    "DEFAULT_SPEC_SCHEMA_VERSION",
    "Personality",
    "PersonalityRiskPolicy",
    "SEED_PERSONALITIES",
    "get_personality",
    "list_personalities",
    "upsert_personality",
    "delete_personality",
    "set_paused",
    "apply_user_override",
    "TradeProposal",
    "ProposalStatus",
    "create_proposal",
    "get_proposal",
    "list_proposals",
    "update_proposal_status",
    "expire_overdue_proposals",
]
