from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AdapterEnvelope(BaseModel):
    data_as_of: str
    source: str = "marketflux-live"
    payload: Dict[str, Any] = Field(default_factory=dict)


class RegimeInputsPayload(BaseModel):
    data_as_of: str
    source_timestamps: Dict[str, Optional[str]] = Field(default_factory=dict)
    vix: Optional[float] = None
    sp500_change_percent: Optional[float] = None
    nasdaq_change_percent: Optional[float] = None
    tlt_change_percent: Optional[float] = None
    unemployment_rate: Optional[float] = None
    ten_two_spread: Optional[float] = None
    bonds_stable: bool = True
    growth_data_positive: bool = False
    warnings: List[str] = Field(default_factory=list)


class Citation(BaseModel):
    label: str
    source: str
    url: Optional[str] = None
    timestamp: Optional[str] = None
    note: Optional[str] = None


class ResearchSignal(BaseModel):
    signal_type: str
    asset_scope: str
    severity: str
    title: str
    summary: str
    tickers: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    freshness: str
    citations: List[Citation] = Field(default_factory=list)


class MacroRegimeView(BaseModel):
    regime: str
    confidence: int
    summary: str
    regime_inputs: Dict[str, Any] = Field(default_factory=dict)
    sector_implications: List[Dict[str, Any]] = Field(default_factory=list)
    key_indicators: List[Dict[str, Any]] = Field(default_factory=list)
    cross_asset_view: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class TickerWorkspace(BaseModel):
    ticker: str
    as_of: str
    snapshot: Dict[str, Any]
    technicals: Dict[str, Any]
    macro_context: Dict[str, Any]
    filings: Dict[str, Any]
    transcripts: Dict[str, Any]
    insider: Dict[str, Any]
    thesis: Dict[str, Any]
    news: List[Dict[str, Any]] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    model_lane: Dict[str, Any] = Field(default_factory=dict)


class DailyBrief(BaseModel):
    id: str
    date: str
    generated_at: str
    macro_regime: Dict[str, Any]
    top_signals: List[ResearchSignal] = Field(default_factory=list)
    watchlist_updates: List[Dict[str, Any]] = Field(default_factory=list)
    top_movers: Dict[str, Any] = Field(default_factory=dict)
    citations: List[Citation] = Field(default_factory=list)
    methodology: Dict[str, Any] = Field(default_factory=dict)


class PortfolioDiagnostics(BaseModel):
    as_of: str
    total_value: float
    concentration_risk: str
    macro_sensitivity: str
    sector_exposure: List[Dict[str, Any]] = Field(default_factory=list)
    holdings: List[Dict[str, Any]] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)


class WatchlistBoard(BaseModel):
    as_of: str
    watchlist_id: str
    items: List[Dict[str, Any]] = Field(default_factory=list)
    saved_theses: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)


class ThesisCreate(BaseModel):
    ticker: str
    thesis_text: str
    stance: str
    confidence: int = Field(ge=0, le=100)
    catalysts: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class MiroFishScenarioCreate(BaseModel):
    project_name: str
    simulation_requirement: str
    seed_materials: List[str] = Field(default_factory=list)
    additional_context: Optional[str] = None
    enable_twitter: bool = False
    enable_reddit: bool = False


class MiroFishReportStatusRequest(BaseModel):
    simulation_id: Optional[str] = None
    task_id: Optional[str] = None


class StrategyTerminalRequest(BaseModel):
    prompt: str
    tickers: List[str] = Field(default_factory=list)
    mode: str = "swing"
    risk_profile: str = "balanced"
    capital_base: float = 100000.0
    allow_short: bool = True
