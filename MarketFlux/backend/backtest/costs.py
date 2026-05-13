"""Transaction cost models.

The engine asks the cost model for an *effective* fill price and a per-trade
commission. Slippage is applied as a price adjustment so PnL is computed
naturally; commission is deducted from cash separately.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    """Simple combined cost model.

    ``commission_per_share`` and ``commission_min`` apply per fill.
    ``slippage_bps`` widens the fill price against the trader (paid on entry and
    exit). ``commission_pct`` is an alternative percentage-of-notional fee.
    """

    commission_per_share: float = 0.0
    commission_min: float = 0.0
    commission_pct: float = 0.0
    slippage_bps: float = 5.0  # 5 bps = 0.05%

    def fill_price(self, ref_price: float, side: str) -> float:
        """Apply slippage. ``side`` is 'buy' or 'sell'."""
        adj = ref_price * (self.slippage_bps / 10_000.0)
        if side == "buy":
            return ref_price + adj
        if side == "sell":
            return max(0.0, ref_price - adj)
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")

    def commission(self, shares: float, fill_price: float) -> float:
        if shares <= 0:
            return 0.0
        per_share = self.commission_per_share * shares
        pct = self.commission_pct * shares * fill_price
        return max(self.commission_min, per_share + pct)


DEFAULT_COSTS = CostModel(
    commission_per_share=0.0,
    commission_min=0.0,
    commission_pct=0.0005,  # 5 bps notional, similar to mid-tier broker
    slippage_bps=5.0,
)


def cost_model_from_dict(data: dict | None) -> CostModel:
    if not data:
        return DEFAULT_COSTS
    return CostModel(
        commission_per_share=float(data.get("commission_per_share", 0.0)),
        commission_min=float(data.get("commission_min", 0.0)),
        commission_pct=float(data.get("commission_pct", 0.0)),
        slippage_bps=float(data.get("slippage_bps", DEFAULT_COSTS.slippage_bps)),
    )
