"""Phase 14 integration and edge-case coverage for the paper-trading pipeline."""

from datetime import UTC, datetime, timedelta

from cryptopilot.agent.arbiter import DecisionArbiter
from cryptopilot.agent.models import ArbitrationInput, MarketRegime, SignalWeights
from cryptopilot.data.models import Candle
from cryptopilot.data.validator import CandleValidator
from cryptopilot.execution.broker import PaperBroker
from cryptopilot.features.pipeline import FeaturePipeline
from cryptopilot.portfolio.manager import PortfolioManager
from cryptopilot.risk.manager import RiskManager
from cryptopilot.risk.models import SizedOrderProposal
from cryptopilot.strategies.base import SignalType, StrategySignal


def _candles(count: int = 240) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=start + timedelta(hours=index),
            open=100.0 + index * 0.1,
            high=101.0 + index * 0.1,
            low=99.0 + index * 0.1,
            close=100.5 + index * 0.1,
            volume=100.0,
        )
        for index in range(count)
    ]


def test_data_feature_strategy_input_path_has_no_lookahead() -> None:
    candles = _candles()
    result = CandleValidator.validate_series(candles, "1h", require_closed=True)
    assert result.is_valid

    import pandas as pd

    frame = pd.DataFrame([c.model_dump() for c in result.validated_candles])
    features = FeaturePipeline().transform(frame)
    assert len(features) == len(frame) - FeaturePipeline.MAX_WARMUP_BARS
    assert features.index.max() == frame.index.max()


def test_decision_risk_and_paper_execution_pipeline() -> None:
    signal = StrategySignal(
        strategy_id="integration",
        symbol="BTC/USDT",
        signal=SignalType.BUY,
        confidence=0.9,
        entry_price=100.0,
        suggested_stop_loss=95.0,
        suggested_take_profit=110.0,
        rationale="Synthetic confirmed trend",
        invalidation_condition="Close below stop",
        timestamp=datetime.now(UTC),
    )
    decision = DecisionArbiter(
        weights=SignalWeights(weight_technical=1.0, weight_ml=0.0, weight_sentiment=0.0)
    ).synthesize_decision(
        ArbitrationInput(
            symbol="BTC/USDT",
            current_price=100.0,
            strategy_signals=[signal],
            market_regime=MarketRegime.TRENDING_BULL,
        )
    )
    risk = RiskManager().evaluate_and_size(decision, PortfolioManager(initial_capital=30.0))
    assert risk.is_approved
    assert risk.proposal is not None

    broker = PaperBroker()
    bracket = broker.submit_bracket(risk.proposal, reference_price=100.0)
    assert bracket.is_active
    assert broker.get_portfolio().positions["BTC/USDT"].quantity > 0


def test_gap_down_stop_loss_closes_position_without_live_network() -> None:
    broker = PaperBroker()
    broker.submit_bracket(
        SizedOrderProposal(
            symbol="BTC/USDT",
            action=SignalType.BUY,
            quantity=0.05,
            notional_value=5.0,
            entry_price=100.0,
            stop_loss_price=95.0,
            take_profit_price=110.0,
            risk_budget_dollars=0.30,
            risk_budget_pct=0.01,
            allocation_pct=5.0 / 30.0,
            estimated_fees=0.01,
            rationale="Synthetic stop-loss stress case",
            timestamp=datetime.now(UTC),
        ),
        account_id="small_account_01",
        reference_price=100.0,
    )
    broker.process_candle(
        Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=datetime.now(UTC),
            open=80.0,
            high=82.0,
            low=70.0,
            close=75.0,
            volume=1000.0,
        )
    )
    assert "BTC/USDT" not in broker.get_portfolio().positions
