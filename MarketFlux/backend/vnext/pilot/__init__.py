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
- reflection: nightly journal + thesis drift detector + leaderboard ranking.
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
    get_personality_by_slug,
    list_personalities,
    upsert_personality,
    delete_personality,
    set_paused,
    set_visibility,
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
from .reflection import (
    JOURNAL_COLLECTION,
    DRIFT_COLLECTION,
    generate_journal_entry,
    list_journal_entries,
    detect_thesis_drift,
    list_drift_flags,
    compute_leaderboard,
    run_nightly_reflection,
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
    "get_personality_by_slug",
    "list_personalities",
    "upsert_personality",
    "delete_personality",
    "set_paused",
    "set_visibility",
    "apply_user_override",
    "TradeProposal",
    "ProposalStatus",
    "create_proposal",
    "get_proposal",
    "list_proposals",
    "update_proposal_status",
    "expire_overdue_proposals",
    "JOURNAL_COLLECTION",
    "DRIFT_COLLECTION",
    "generate_journal_entry",
    "list_journal_entries",
    "detect_thesis_drift",
    "list_drift_flags",
    "compute_leaderboard",
    "run_nightly_reflection",
]
