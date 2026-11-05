"""
Tests for CryptoPilot AI - Market Regime Classifier.
"""

import pandas as pd
import pytest

from cryptopilot.agent.models import MarketRegime
from cryptopilot.agent.regime import MarketRegimeClassifier


def test_regime_classifier_insufficient_data():
    classifier = MarketRegimeClassifier()

    # None or empty
    assert classifier.classify(None) == MarketRegime.UNKNOWN  # type: ignore
    assert classifier.classify(pd.DataFrame()) == MarketRegime.UNKNOWN

    # Fewer than 10 rows
    df_short = pd.DataFrame({"close": [100.0] * 5})
    assert classifier.classify(df_short) == MarketRegime.UNKNOWN


def test_regime_classifier_high_volatility():
    classifier = MarketRegimeClassifier(high_volatility_atr_ratio=0.035)

    # 15 rows with extreme ATR
    data = {
        "close": [1000.0] * 15,
        "atr_14": [50.0] * 15,  # 50 / 1000 = 5.0% > 3.5%
        "adx_14": [30.0] * 15,
        "ema_20": [1050.0] * 15,
        "ema_50": [1000.0] * 15,
        "macd_12_26_9_hist": [5.0] * 15,
    }
    df = pd.DataFrame(data)
    regime = classifier.classify(df)
    assert regime == MarketRegime.HIGH_VOLATILITY


def test_regime_classifier_trending_bull():
    classifier = MarketRegimeClassifier()

    # Normal ATR (1.5%), strong ADX (32), close > ema_50, ema_20 > ema_50, macd > 0
    data = {
        "close": [2000.0] * 20,
        "atr_14": [20.0] * 20,  # 1%
        "adx_14": [32.0] * 20,  # > 25
        "ema_20": [1980.0] * 20,
        "ema_50": [1900.0] * 20,
        "macd_12_26_9_hist": [12.0] * 20,
    }
    df = pd.DataFrame(data)
    regime = classifier.classify(df)
    assert regime == MarketRegime.TRENDING_BULL


def test_regime_classifier_trending_bear():
    classifier = MarketRegimeClassifier()

    # Normal ATR, strong ADX (28), close < ema_50, ema_20 < ema_50, macd < 0
    data = {
        "close": [1800.0] * 20,
        "atr_14": [20.0] * 20,
        "adx_14": [28.0] * 20,
        "ema_20": [1850.0] * 20,
        "ema_50": [1950.0] * 20,
        "macd_12_26_9_hist": [-8.0] * 20,
    }
    df = pd.DataFrame(data)
    regime = classifier.classify(df)
    assert regime == MarketRegime.TRENDING_BEAR


def test_regime_classifier_ranging():
    classifier = MarketRegimeClassifier()

    # Low ADX (16 <= 20)
    data = {
        "close": [1900.0] * 20,
        "atr_14": [15.0] * 20,
        "adx_14": [16.0] * 20,  # Ranging
        "ema_20": [1905.0] * 20,
        "ema_50": [1895.0] * 20,
        "macd_12_26_9_hist": [1.0] * 20,
    }
    df = pd.DataFrame(data)
    regime = classifier.classify(df)
    assert regime == MarketRegime.RANGING


def test_strategy_multipliers_by_regime():
    classifier = MarketRegimeClassifier()

    m_bull = classifier.get_strategy_multipliers(MarketRegime.TRENDING_BULL)
    assert m_bull["ema_trend"] > 1.0
    assert m_bull["bollinger_reversion"] < 0.5

    m_ranging = classifier.get_strategy_multipliers(MarketRegime.RANGING)
    assert m_ranging["bollinger_reversion"] > 1.2
    assert m_ranging["ema_trend"] < 0.8

    m_vol = classifier.get_strategy_multipliers(MarketRegime.HIGH_VOLATILITY)
    assert m_vol["volatility_momentum"] > 1.2

    m_unk = classifier.get_strategy_multipliers(MarketRegime.UNKNOWN)
    assert m_unk["ema_trend"] == pytest.approx(1.0)
