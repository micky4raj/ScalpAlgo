"""Async orchestrator and safe paper-mode demonstration."""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone

try:
    import uvloop
except ImportError:  # pragma: no cover - optional performance dependency
    uvloop = None

from .config import EngineConfig, ExecutionMode
from .cost_calculator import CostCalculator
from .dhan_client import DhanClient
from .execution_engine import (
    ExecutionController,
    LiveDhanExecutionController,
    OrderRequest,
    PaperExecutionController,
    OrderStatus,
    RiskGate,
)
from .journal import TradeJournal
from .scalp_strategy import (
    ScalpingStrategy,
    SignalAction,
    Side,
    Tick,
)

logger = logging.getLogger(__name__)


async def run_paper_demo(config: EngineConfig) -> None:
    """Run a deterministic paper loop to validate the whole pipeline."""
    journal = TradeJournal(config.journal.database_path)
    costs = CostCalculator(config.costs)
    strategy = ScalpingStrategy(config.strategy, config.instrument_type)
    executor = PaperExecutionController()
    risk_gate = RiskGate(
        max_daily_loss=config.risk.max_daily_loss,
        max_drawdown=config.risk.max_drawdown,
    )
    base = datetime.now(timezone.utc).replace(microsecond=0)
    price = 100.0
    try:
        for index in range(180):
            timestamp = base + timedelta(seconds=index)
            price += 0.10 + math.sin(index / 7) * 0.15
            tick = Tick(
                timestamp=timestamp,
                security_id="DEMO-NIFTY-OPT",
                ltp=max(price, 1.0),
                volume=100 + (index % 9) * 20,
            )
            journal.log_tick(
                timestamp=tick.timestamp,
                security_id=tick.security_id,
                ltp=tick.ltp,
                volume=tick.volume,
            ) if config.journal.tick_logging_enabled else None
            executor.on_tick(tick)
            signal = strategy.on_tick(tick)
            if (
                signal.action is SignalAction.ENTER_LONG
                and risk_gate.allows_entry(journal.performance())
            ):
                request = OrderRequest(
                    tick.security_id,
                    Side.BUY,
                    config.risk.quantity,
                    tick.ltp,
                )
                event = await executor.submit(request)
                journal.log_execution(event)
                if event.status.value == "TRADED" and event.fill_price is not None:
                    strategy.register_entry(signal, config.risk.quantity)
                    entry_price = event.fill_price
                    while strategy.position is not None and index < 179:
                        index += 1
                        exit_tick = Tick(
                            base + timedelta(seconds=index),
                            tick.security_id,
                            entry_price + min(13.0, index * 0.5),
                            tick.volume,
                        )
                        exit_signal = strategy.on_tick(exit_tick)
                        if exit_signal.action is SignalAction.EXIT:
                            executor.on_tick(exit_tick)
                            exit_request = OrderRequest(
                                exit_tick.security_id,
                                Side.SELL,
                                config.risk.quantity,
                                exit_tick.ltp,
                            )
                            exit_event = await executor.submit(exit_request)
                            journal.log_execution(exit_event)
                            if (
                                exit_event.status is OrderStatus.TRADED
                                and exit_event.fill_price is not None
                            ):
                                breakdown = costs.calculate(
                                    buy_price=entry_price,
                                    sell_price=exit_event.fill_price,
                                    quantity=config.risk.quantity,
                                    instrument_type=config.instrument_type,
                                )
                                position = strategy.register_exit()
                                if position is not None:
                                    journal.log_trade(
                                        opened_at=position.opened_at,
                                        closed_at=exit_event.timestamp,
                                        security_id=exit_tick.security_id,
                                        quantity=position.quantity,
                                        buy_price=entry_price,
                                        sell_price=exit_event.fill_price,
                                        costs=breakdown,
                                    )
                            break
        report = journal.performance()
        logger.info(
            "Paper report: trades=%d win_rate=%.1f%% net_pnl=%.2f max_drawdown=%.2f",
            report.trades,
            report.win_rate * 100,
            report.net_pnl,
            report.max_drawdown,
        )
    finally:
        journal.close()


async def run_live(config: EngineConfig) -> None:
    """Start the live adapter only after all safety checks pass."""
    config.validate()
    journal = TradeJournal(config.journal.database_path)
    costs = CostCalculator(config.costs)
    strategy = ScalpingStrategy(config.strategy, config.instrument_type)
    risk_gate = RiskGate(
        max_daily_loss=config.risk.max_daily_loss,
        max_drawdown=config.risk.max_drawdown,
    )
    subscriptions = _parse_subscriptions()
    if not subscriptions:
        journal.close()
        raise ValueError(
            "LIVE mode requires DHAN_SUBSCRIPTIONS, for example "
            "DHAN_SUBSCRIPTIONS=12:12345"
        )
    try:
        async with DhanClient(config.dhan) as client:
            executor: ExecutionController = LiveDhanExecutionController(client)
            logger.warning("LIVE mode enabled for configured subscriptions")
            async for tick in client.stream_ticks(subscriptions=subscriptions):
                if config.journal.tick_logging_enabled:
                    journal.log_tick(
                        timestamp=tick.timestamp,
                        security_id=tick.security_id,
                        ltp=tick.ltp,
                        volume=tick.volume,
                    )
                signal = strategy.on_tick(tick)
                if signal.action is SignalAction.ENTER_LONG and risk_gate.allows_entry(
                    journal.performance()
                ):
                    event = await executor.submit(
                        OrderRequest(
                            security_id=tick.security_id,
                            side=Side.BUY,
                            quantity=config.risk.quantity,
                            price=tick.ltp,
                        )
                    )
                    journal.log_execution(event)
                    if (
                        event.status is OrderStatus.TRADED
                        and event.fill_price is not None
                    ):
                        strategy.register_entry(signal, config.risk.quantity)
                elif signal.action is SignalAction.EXIT and strategy.position is not None:
                    event = await executor.submit(
                        OrderRequest(
                            security_id=tick.security_id,
                            side=Side.SELL,
                            quantity=strategy.position.quantity,
                            price=tick.ltp,
                        )
                    )
                    journal.log_execution(event)
                    if (
                        event.status is OrderStatus.TRADED
                        and event.fill_price is not None
                    ):
                        position = strategy.register_exit()
                        if position is not None:
                            breakdown = costs.calculate(
                                buy_price=position.entry_price,
                                sell_price=event.fill_price,
                                quantity=position.quantity,
                                instrument_type=config.instrument_type,
                            )
                            journal.log_trade(
                                opened_at=position.opened_at,
                                closed_at=event.timestamp,
                                security_id=tick.security_id,
                                quantity=position.quantity,
                                buy_price=position.entry_price,
                                sell_price=event.fill_price,
                                costs=breakdown,
                            )
    finally:
        journal.close()


def _parse_subscriptions() -> list[tuple[str, str]]:
    """Parse ``segment:security_id`` pairs from an environment variable."""
    import os

    raw = os.getenv("DHAN_SUBSCRIPTIONS", "")
    subscriptions: list[tuple[str, str]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            segment, security_id = item.split(":", maxsplit=1)
            if not segment or not security_id.isdigit():
                raise ValueError
            subscriptions.append((segment, security_id))
        except ValueError as exc:
            raise ValueError(
                "DHAN_SUBSCRIPTIONS must contain comma-separated segment:id pairs"
            ) from exc
    return subscriptions


async def main_async() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = EngineConfig.from_env()
    config.validate()
    if config.execution_mode is ExecutionMode.PAPER:
        await run_paper_demo(config)
    else:
        await run_live(config)


def main() -> None:
    if uvloop is not None:
        uvloop.install()
    asyncio.run(main_async())


if __name__ == "__main__":
    main()