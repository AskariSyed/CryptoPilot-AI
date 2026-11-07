"""
CryptoPilot AI - Database & Relational Persistence Package.
"""

from cryptopilot.database.analytics import (
    PerformanceAnalyticsService,
    PerformanceReport,
)
from cryptopilot.database.connection import (
    DatabaseManager,
    get_db_manager,
    get_session,
    reset_db_manager,
)
from cryptopilot.database.models import (
    AgentDecisionModel,
    Base,
    DepositModel,
    ExchangeModel,
    MarketCandleModel,
    MarketSnapshotModel,
    OrderModel,
    PortfolioModel,
    PositionModel,
    RiskEventModel,
    TradeModel,
    TradingPairModel,
)
from cryptopilot.database.repository import (
    CandleRepository,
    DecisionRepository,
    OrderRepository,
    PortfolioRepository,
    PositionRepository,
    RiskEventRepository,
)
from cryptopilot.database.transactions import (
    atomic_transaction,
    record_agent_decision,
    record_deposit_and_update_balance,
    record_fill_and_update_portfolio,
    record_risk_event,
)

__all__ = [
    "AgentDecisionModel",
    "Base",
    "CandleRepository",
    "DatabaseManager",
    "DecisionRepository",
    "DepositModel",
    "ExchangeModel",
    "MarketCandleModel",
    "MarketSnapshotModel",
    "OrderModel",
    "OrderRepository",
    "PerformanceAnalyticsService",
    "PerformanceReport",
    "PortfolioModel",
    "PortfolioRepository",
    "PositionModel",
    "PositionRepository",
    "RiskEventModel",
    "RiskEventRepository",
    "TradeModel",
    "TradingPairModel",
    "atomic_transaction",
    "get_db_manager",
    "get_session",
    "record_agent_decision",
    "record_deposit_and_update_balance",
    "record_fill_and_update_portfolio",
    "record_risk_event",
    "reset_db_manager",
]
