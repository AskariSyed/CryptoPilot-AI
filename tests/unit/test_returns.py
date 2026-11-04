"""
Unit tests for cryptopilot.indicators.returns.
Covers: Simple returns and Log returns.
"""

import math

import numpy as np
import pandas as pd
import pytest

from cryptopilot.indicators.base import InvalidInputError
from cryptopilot.indicators.returns import (
    LogReturns,
    PriceReturns,
    calculate_log_returns,
    calculate_returns,
)


class TestReturns:
    def test_calculate_returns(self) -> None:
        prices = pd.Series([100.0, 110.0, 99.0])
        ret1 = calculate_returns(prices, periods=1)

        assert np.isnan(ret1.iloc[0])
        assert ret1.iloc[1] == pytest.approx(0.10)  # +10%
        assert ret1.iloc[2] == pytest.approx(-0.10)  # -10% from 110 to 99

    def test_calculate_returns_multi_period(self) -> None:
        prices = pd.Series([100.0, 105.0, 110.0, 120.0])
        ret2 = calculate_returns(prices, periods=2)

        assert np.isnan(ret2.iloc[0])
        assert np.isnan(ret2.iloc[1])
        assert ret2.iloc[2] == pytest.approx(0.10)  # 110 / 100 - 1

    def test_calculate_returns_invalid_and_empty(self) -> None:
        empty = pd.Series([], dtype=np.float64)
        assert calculate_returns(empty, 1).empty

        prices = pd.Series([10.0, 20.0])
        with pytest.raises(ValueError):
            calculate_returns(prices, 0)

    def test_calculate_log_returns(self) -> None:
        prices = pd.Series([100.0, 105.0])
        log_ret = calculate_log_returns(prices, periods=1)

        assert np.isnan(log_ret.iloc[0])
        expected = math.log(105.0 / 100.0)
        assert log_ret.iloc[1] == pytest.approx(expected)

    def test_calculate_log_returns_invalid_and_empty(self) -> None:
        empty = pd.Series([], dtype=np.float64)
        assert calculate_log_returns(empty, 1).empty

        prices = pd.Series([10.0, 20.0])
        with pytest.raises(ValueError):
            calculate_log_returns(prices, 0)

    def test_classes_dataframe_integration(self) -> None:
        df = pd.DataFrame({"close": [100.0, 105.0, 110.0]})

        pr = PriceReturns(periods=1)
        res_pr = pr.calculate(df)
        assert res_pr.name == "RET_1"
        assert res_pr.iloc[1] == pytest.approx(0.05)

        lr = LogReturns(periods=1)
        res_lr = lr.calculate(df)
        assert res_lr.name == "LOG_RET_1"
        assert res_lr.iloc[1] == pytest.approx(math.log(1.05))

    def test_classes_invalid_input(self) -> None:
        df_bad = pd.DataFrame({"dummy": [1.0]})
        with pytest.raises(InvalidInputError):
            PriceReturns().calculate(df_bad)
        with pytest.raises(InvalidInputError):
            LogReturns().calculate(df_bad)
