"""Tick-to-signal Nifty scalping strategy with hard risk exits."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from .config import InstrumentType, StrategyConfig


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class SignalAction(StrEnum):
    ENTER_LONG = "ENTER_LONG"
    ENTER_SHORT = "ENTER_SHORT"
    EXIT = "EXIT"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class Tick:
    timestamp: datetime
    security_id: str
    ltp: float
    volume: int
    bid: float | None = None
    ask: float | None = None


@dataclass(frozen=True, slots=True)
class Candle:
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True, slots=True)
class Signal:
    action: SignalAction
    timestamp: datetime
    price: float
    confidence: float
    reason: str
    stop_loss: float | None = None
    target: float | None = None


@dataclass(slots=True)
class PositionState:
    side: Side
    entry_price: float
    quantity: int
    opened_at: datetime
    stop_loss: float
    target: float
    highest_price: float
    lowest_price: float


def _ema(previous: float | None, price: float, period: int) -> float:
    if previous is None:
        return price
    alpha = 2.0 / (period + 1)
    return (price * alpha) + (previous * (1 - alpha))


class ScalpingStrategy:
    """Maintains indicators in memory and emits deterministic signals."""

    def __init__(
        self, config: StrategyConfig, instrument_type: InstrumentType
    ) -> None:
        self.config = config
        self.instrument_type = instrument_type
        self._ticks: deque[Tick] = deque(maxlen=10_000)
        self._candles: deque[Candle] = deque(
            maxlen=max(config.slow_ema_period + 10, config.atr_period + 10)
        )
        self._volumes: deque[int] = deque(
            maxlen=config.volume_spike_lookback
        )
        self._current_candle: Candle | None = None
        self._fast_ema: float | None = None
        self._slow_ema: float | None = None
        self._cumulative_turnover = 0.0
        self._cumulative_volume = 0
        self.position: PositionState | None = None

    def on_tick(self, tick: Tick) -> Signal:
        if tick.ltp <= 0:
            raise ValueError("Tick LTP must be positive")
        self._ticks.append(tick)
        closed = self._update_candle(tick)
        self._update_trailing_state(tick)

        exit_signal = self._risk_exit(tick)
        if exit_signal is not None:
            return exit_signal
        if not closed or self.position is not None:
            return Signal(
                SignalAction.HOLD,
                tick.timestamp,
                tick.ltp,
                0.0,
                "position managed or candle not closed",
            )
        if len(self._candles) < self.config.slow_ema_period:
            return Signal(
                SignalAction.HOLD,
                tick.timestamp,
                tick.ltp,
                0.0,
                "warming up indicators",
            )

        vwap = self._vwap()
        atr = self._atr()
        volume_ratio = self._volume_ratio()
        fast = self._fast_ema or tick.ltp
        slow = self._slow_ema or tick.ltp
        trend_score = 0.5 if fast > slow else 0.0
        vwap_score = 0.3 if tick.ltp > vwap else 0.0
        volume_score = 0.2 if volume_ratio >= self.config.volume_spike_multiplier else 0.0
        confidence = trend_score + vwap_score + volume_score
        if confidence < self.config.minimum_signal_confidence:
            return Signal(
                SignalAction.HOLD,
                tick.timestamp,
                tick.ltp,
                confidence,
                "filters not aligned",
            )

        target_points = (
            self.config.option_target_points
            if self.instrument_type is InstrumentType.OPTION
            else self.config.index_target_points
        )
        stop = max(self.config.stop_loss_points, atr * self.config.trailing_atr_multiplier)
        return Signal(
            SignalAction.ENTER_LONG,
            tick.timestamp,
            tick.ltp,
            confidence,
            f"EMA/VWAP/volume aligned; volume ratio={volume_ratio:.2f}",
            stop_loss=tick.ltp - stop,
            target=tick.ltp + target_points,
        )

    def register_entry(self, signal: Signal, quantity: int) -> None:
        if signal.action not in {
            SignalAction.ENTER_LONG,
            SignalAction.ENTER_SHORT,
        }:
            raise ValueError("Only entry signals can create a position")
        if signal.stop_loss is None or signal.target is None:
            raise ValueError("Entry signal must include stop and target")
        side = (
            Side.BUY
            if signal.action is SignalAction.ENTER_LONG
            else Side.SELL
        )
        self.position = PositionState(
            side=side,
            entry_price=signal.price,
            quantity=quantity,
            opened_at=signal.timestamp,
            stop_loss=signal.stop_loss,
            target=signal.target,
            highest_price=signal.price,
            lowest_price=signal.price,
        )

    def register_exit(self) -> PositionState | None:
        position = self.position
        self.position = None
        return position

    def _update_candle(self, tick: Tick) -> bool:
        bucket_seconds = self.config.candle_seconds
        epoch = tick.timestamp.timestamp()
        start = datetime.fromtimestamp(
            math.floor(epoch / bucket_seconds) * bucket_seconds,
            tz=timezone.utc,
        )
        end = start + timedelta(seconds=bucket_seconds)
        candle = self._current_candle
        if candle is None:
            self._current_candle = Candle(
                start, end, tick.ltp, tick.ltp, tick.ltp, tick.ltp, tick.volume
            )
            return False
        if start == candle.start:
            self._current_candle = Candle(
                candle.start,
                candle.end,
                candle.open,
                max(candle.high, tick.ltp),
                min(candle.low, tick.ltp),
                tick.ltp,
                candle.volume + tick.volume,
            )
            return False
        self._candles.append(candle)
        self._volumes.append(candle.volume)
        self._fast_ema = _ema(self._fast_ema, candle.close, self.config.fast_ema_period)
        self._slow_ema = _ema(self._slow_ema, candle.close, self.config.slow_ema_period)
        self._cumulative_turnover += candle.close * candle.volume
        self._cumulative_volume += candle.volume
        self._current_candle = Candle(
            start, end, tick.ltp, tick.ltp, tick.ltp, tick.ltp, tick.volume
        )
        return True

    def _vwap(self) -> float:
        if not self._cumulative_volume:
            return self._candles[-1].close
        return self._cumulative_turnover / self._cumulative_volume

    def _atr(self) -> float:
        if len(self._candles) < 2:
            return self.config.stop_loss_points
        values = []
        candles = list(self._candles)[-self.config.atr_period :]
        for previous, current in zip(candles, candles[1:]):
            values.append(
                max(
                    current.high - current.low,
                    abs(current.high - previous.close),
                    abs(current.low - previous.close),
                )
            )
        return sum(values) / len(values) if values else self.config.stop_loss_points

    def _volume_ratio(self) -> float:
        if not self._volumes:
            return 0.0
        average = sum(self._volumes) / len(self._volumes)
        return self._volumes[-1] / average if average else 0.0

    def _update_trailing_state(self, tick: Tick) -> None:
        if self.position is None:
            return
        position = self.position
        position.highest_price = max(position.highest_price, tick.ltp)
        position.lowest_price = min(position.lowest_price, tick.ltp)
        trailing_distance = self._atr() * self.config.trailing_atr_multiplier
        if position.side is Side.BUY:
            position.stop_loss = max(
                position.stop_loss,
                position.highest_price - trailing_distance,
            )

    def _risk_exit(self, tick: Tick) -> Signal | None:
        position = self.position
        if position is None:
            return None
        held_seconds = (tick.timestamp - position.opened_at).total_seconds()
        if position.side is Side.BUY and tick.ltp <= position.stop_loss:
            return Signal(
                SignalAction.EXIT,
                tick.timestamp,
                tick.ltp,
                1.0,
                "hard or trailing stop loss",
            )
        if position.side is Side.BUY and tick.ltp >= position.target:
            return Signal(
                SignalAction.EXIT,
                tick.timestamp,
                tick.ltp,
                1.0,
                "profit target reached",
            )
        if held_seconds >= self.config.max_hold_seconds:
            return Signal(
                SignalAction.EXIT,
                tick.timestamp,
                tick.ltp,
                1.0,
                "maximum holding time reached",
            )
        return None