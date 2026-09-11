"""Typed configuration for the trading engine.

All values are environment-driven so credentials and live-trading decisions
never need to be committed to source control. Tax rates are configurable
because broker and government rate cards can change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ExecutionMode(StrEnum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class InstrumentType(StrEnum):
    OPTION = "OPTION"
    FUTURE = "FUTURE"


class PaperDataSource(StrEnum):
    DHAN = "DHAN"
    YFINANCE = "YFINANCE"
    DEMO = "DEMO"


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


@dataclass(frozen=True, slots=True)
class DhanConfig:
    """Credentials and API endpoints for DhanHQ.

    The access token is intentionally read only at runtime. Do not log this
    object or serialize it.
    """

    client_id: str = ""
    access_token: str = ""
    rest_base_url: str = "https://api.dhan.co/v2"
    websocket_url: str = "wss://api-feed.dhan.co"
    api_version: str = "2"

    @classmethod
    def from_env(cls) -> "DhanConfig":
        return cls(
            client_id=os.getenv("DHAN_CLIENT_ID", ""),
            access_token=os.getenv("DHAN_ACCESS_TOKEN", ""),
            rest_base_url=os.getenv(
                "DHAN_REST_BASE_URL", "https://api.dhan.co/v2"
            ),
            websocket_url=os.getenv(
                "DHAN_WEBSOCKET_URL", "wss://api-feed.dhan.co"
            ),
            api_version=os.getenv("DHAN_API_VERSION", "2"),
        )

    def validate_for_live(self) -> None:
        missing = [
            name
            for name, value in (
                ("DHAN_CLIENT_ID", self.client_id),
                ("DHAN_ACCESS_TOKEN", self.access_token),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "Live execution requires secure environment secrets: "
                + ", ".join(missing)
            )


@dataclass(frozen=True, slots=True)
class CostConfig:
    """Brokerage and statutory charges as decimal rates.

    Defaults match the rates specified in the supplied brief. Exchange, SEBI,
    and stamp rates should be verified against the current rate card before
    enabling LIVE mode; they are intentionally overrideable by environment.
    """

    brokerage_flat: float = 20.0
    brokerage_rate: float = 0.0003
    option_stt_sell_rate: float = 0.000625
    futures_stt_sell_rate: float = 0.000125
    exchange_turnover_rate: float = 0.0000297
    sebi_turnover_rate: float = 0.000001
    stamp_duty_buy_rate: float = 0.00003
    gst_rate: float = 0.18

    @classmethod
    def from_env(cls) -> "CostConfig":
        return cls(
            brokerage_flat=_env_float("BROKERAGE_FLAT", 20.0),
            brokerage_rate=_env_float("BROKERAGE_RATE", 0.0003),
            option_stt_sell_rate=_env_float(
                "OPTION_STT_SELL_RATE", 0.000625
            ),
            futures_stt_sell_rate=_env_float(
                "FUTURES_STT_SELL_RATE", 0.000125
            ),
            exchange_turnover_rate=_env_float(
                "EXCHANGE_TURNOVER_RATE", 0.0000297
            ),
            sebi_turnover_rate=_env_float(
                "SEBI_TURNOVER_RATE", 0.000001
            ),
            stamp_duty_buy_rate=_env_float(
                "STAMP_DUTY_BUY_RATE", 0.00003
            ),
            gst_rate=_env_float("GST_RATE", 0.18),
        )


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    candle_seconds: float = 5.0
    fast_ema_period: int = 5
    slow_ema_period: int = 13
    atr_period: int = 14
    volume_spike_lookback: int = 20
    volume_spike_multiplier: float = 1.5
    minimum_signal_confidence: float = 0.70
    option_target_points: float = 12.0
    index_target_points: float = 25.0
    stop_loss_points: float = 8.0
    trailing_atr_multiplier: float = 1.2
    max_hold_seconds: float = 180.0

    @classmethod
    def from_env(cls) -> "StrategyConfig":
        return cls(
            candle_seconds=_env_float("CANDLE_SECONDS", 5.0),
            fast_ema_period=_env_int("FAST_EMA_PERIOD", 5),
            slow_ema_period=_env_int("SLOW_EMA_PERIOD", 13),
            atr_period=_env_int("ATR_PERIOD", 14),
            volume_spike_lookback=_env_int(
                "VOLUME_SPIKE_LOOKBACK", 20
            ),
            volume_spike_multiplier=_env_float(
                "VOLUME_SPIKE_MULTIPLIER", 1.5
            ),
            minimum_signal_confidence=_env_float(
                "MINIMUM_SIGNAL_CONFIDENCE", 0.70
            ),
            option_target_points=_env_float(
                "OPTION_TARGET_POINTS", 12.0
            ),
            index_target_points=_env_float(
                "INDEX_TARGET_POINTS", 25.0
            ),
            stop_loss_points=_env_float(
                "STOP_LOSS_POINTS", 8.0
            ),
            trailing_atr_multiplier=_env_float(
                "TRAILING_ATR_MULTIPLIER", 1.2
            ),
            max_hold_seconds=_env_float(
                "MAX_HOLD_SECONDS", 180.0
            ),
        )


@dataclass(frozen=True, slots=True)
class RiskConfig:
    max_daily_loss: float = 5_000.0
    max_drawdown: float = 7_500.0
    max_open_positions: int = 1
    quantity: int = 50
    cooldown_seconds: float = 10.0
    live_confirmation: str = ""

    @classmethod
    def from_env(cls) -> "RiskConfig":
        return cls(
            max_daily_loss=_env_float("MAX_DAILY_LOSS", 5_000.0),
            max_drawdown=_env_float("MAX_DRAWDOWN", 7_500.0),
            max_open_positions=_env_int(
                "MAX_OPEN_POSITIONS", 1
            ),
            quantity=_env_int("ORDER_QUANTITY", 50),
            cooldown_seconds=_env_float(
                "COOLDOWN_SECONDS", 10.0
            ),
            live_confirmation=os.getenv("LIVE_TRADING_CONFIRMATION", ""),
        )


@dataclass(frozen=True, slots=True)
class JournalConfig:
    database_path: Path = Path("data/trading_journal.sqlite3")
    tick_logging_enabled: bool = False

    @classmethod
    def from_env(cls) -> "JournalConfig":
        return cls(
            database_path=Path(
                os.getenv("JOURNAL_DATABASE_PATH", "data/trading_journal.sqlite3")
            ),
            tick_logging_enabled=os.getenv(
                "LOG_EVERY_TICK", "false"
            ).lower()
            in {"1", "true", "yes"},
        )


@dataclass(frozen=True, slots=True)
class PaperFeedConfig:
    source: PaperDataSource = PaperDataSource.DHAN
    yfinance_symbol: str = "^NSEI"
    yfinance_period: str = "1d"
    yfinance_interval: str = "1m"
    dhan_tick_timeout_seconds: float = 15.0
    max_yfinance_rows: int = 390

    @classmethod
    def from_env(cls) -> "PaperFeedConfig":
        source = os.getenv("PAPER_DATA_SOURCE", "DHAN").upper()
        try:
            paper_source = PaperDataSource(source)
        except ValueError as exc:
            raise ValueError(
                "PAPER_DATA_SOURCE must be DHAN, YFINANCE, or DEMO"
            ) from exc
        return cls(
            source=paper_source,
            yfinance_symbol=os.getenv("YFINANCE_SYMBOL", "^NSEI"),
            yfinance_period=os.getenv("YFINANCE_PERIOD", "1d"),
            yfinance_interval=os.getenv("YFINANCE_INTERVAL", "1m"),
            dhan_tick_timeout_seconds=_env_float(
                "DHAN_TICK_TIMEOUT_SECONDS", 15.0
            ),
            max_yfinance_rows=_env_int("MAX_YFINANCE_ROWS", 390),
        )


@dataclass(frozen=True, slots=True)
class EngineConfig:
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    instrument_type: InstrumentType = InstrumentType.OPTION
    dhan: DhanConfig = DhanConfig()
    costs: CostConfig = CostConfig()
    strategy: StrategyConfig = StrategyConfig()
    risk: RiskConfig = RiskConfig()
    journal: JournalConfig = JournalConfig()
    paper_feed: PaperFeedConfig = PaperFeedConfig()

    @classmethod
    def from_env(cls) -> "EngineConfig":
        mode = os.getenv("EXECUTION_MODE", ExecutionMode.PAPER.value).upper()
        instrument = os.getenv(
            "INSTRUMENT_TYPE", InstrumentType.OPTION.value
        ).upper()
        try:
            execution_mode = ExecutionMode(mode)
            instrument_type = InstrumentType(instrument)
        except ValueError as exc:
            raise ValueError(
                "EXECUTION_MODE must be PAPER or LIVE and INSTRUMENT_TYPE "
                "must be OPTION or FUTURE"
            ) from exc
        return cls(
            execution_mode=execution_mode,
            instrument_type=instrument_type,
            dhan=DhanConfig.from_env(),
            costs=CostConfig.from_env(),
            strategy=StrategyConfig.from_env(),
            risk=RiskConfig.from_env(),
            journal=JournalConfig.from_env(),
            paper_feed=PaperFeedConfig.from_env(),
        )

    def validate(self) -> None:
        if self.risk.quantity <= 0:
            raise ValueError("ORDER_QUANTITY must be positive")
        if self.paper_feed.max_yfinance_rows <= 0:
            raise ValueError("MAX_YFINANCE_ROWS must be positive")
        if self.strategy.fast_ema_period >= self.strategy.slow_ema_period:
            raise ValueError("FAST_EMA_PERIOD must be less than SLOW_EMA_PERIOD")
        if self.execution_mode is ExecutionMode.LIVE:
            self.dhan.validate_for_live()
            if self.risk.live_confirmation != "I_UNDERSTAND_LIVE_RISK":
                raise ValueError(
                    "LIVE mode requires "
                    "LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK"
                )