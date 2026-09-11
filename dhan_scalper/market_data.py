"""Paper-mode market-data providers with a DhanHQ-to-yfinance fallback."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import EngineConfig, PaperDataSource
from .dhan_client import DhanClient
from .scalp_strategy import Tick

logger = logging.getLogger(__name__)


async def paper_ticks(config: EngineConfig) -> AsyncIterator[Tick]:
    """Yield paper ticks, falling back to yfinance only for paper data.

    A DhanHQ connection failure, missing paper subscription, or feed timeout
    selects yfinance. No order execution path is involved here.
    """
    source = config.paper_feed.source
    if source is PaperDataSource.DEMO:
        async for tick in _demo_ticks():
            yield tick
        return
    if source is PaperDataSource.YFINANCE:
        async for tick in _yfinance_ticks(config):
            yield tick
        return

    subscriptions = _paper_subscriptions()
    if not subscriptions:
        logger.warning(
            "DhanHQ paper feed is not configured; using yfinance fallback"
        )
    elif not config.dhan.client_id or not config.dhan.access_token:
        logger.warning(
            "DhanHQ paper feed credentials are unavailable; using yfinance fallback"
        )
    else:
        try:
            async with DhanClient(config.dhan) as client:
                stream = client.stream_ticks(
                    subscriptions=subscriptions
                ).__aiter__()
                while True:
                    try:
                        tick = await asyncio.wait_for(
                            stream.__anext__(),
                            timeout=config.paper_feed.dhan_tick_timeout_seconds,
                        )
                    except StopAsyncIteration:
                        break
                    yield tick
        except Exception as exc:
            logger.warning(
                "DhanHQ paper feed failed; using yfinance fallback (%s)",
                type(exc).__name__,
            )

    async for tick in _yfinance_ticks(config):
        yield tick


async def _yfinance_ticks(config: EngineConfig) -> AsyncIterator[Tick]:
    rows = await asyncio.to_thread(
        _download_yfinance_rows,
        config.paper_feed.yfinance_symbol,
        config.paper_feed.yfinance_period,
        config.paper_feed.yfinance_interval,
        config.paper_feed.max_yfinance_rows,
    )
    if not rows:
        raise RuntimeError(
            f"yfinance returned no data for {config.paper_feed.yfinance_symbol}"
        )
    logger.info(
        "Using yfinance paper feed: symbol=%s interval=%s rows=%d",
        config.paper_feed.yfinance_symbol,
        config.paper_feed.yfinance_interval,
        len(rows),
    )
    for tick in rows:
        yield tick
        await asyncio.sleep(0)


def _download_yfinance_rows(
    symbol: str,
    period: str,
    interval: str,
    max_rows: int,
) -> list[Tick]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError(
            "Install the paper feed dependency with: pip install -e ."
        ) from exc

    frame = yf.Ticker(symbol).history(
        period=period,
        interval=interval,
        auto_adjust=False,
        actions=False,
    )
    if frame.empty:
        return []
    rows: list[Tick] = []
    for timestamp, row in frame.tail(max_rows).iterrows():
        close = _number(row.get("Close"))
        if close <= 0:
            continue
        volume = int(_number(row.get("Volume")))
        parsed_timestamp = timestamp.to_pydatetime()
        if parsed_timestamp.tzinfo is None:
            parsed_timestamp = parsed_timestamp.replace(tzinfo=timezone.utc)
        else:
            parsed_timestamp = parsed_timestamp.astimezone(timezone.utc)
        rows.append(
            Tick(
                timestamp=parsed_timestamp,
                security_id=symbol,
                ltp=close,
                volume=volume,
            )
        )
    return rows


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _paper_subscriptions() -> list[tuple[str, str]]:
    import os

    raw = os.getenv("DHAN_SUBSCRIPTIONS", "")
    subscriptions: list[tuple[str, str]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        segment, separator, security_id = item.partition(":")
        if separator and segment and security_id.isdigit():
            subscriptions.append((segment, security_id))
    return subscriptions


async def _demo_ticks() -> AsyncIterator[Tick]:
    import math

    base = datetime.now(timezone.utc).replace(microsecond=0)
    price = 100.0
    for index in range(180):
        price += 0.10 + math.sin(index / 7) * 0.15
        yield Tick(
            timestamp=base + timedelta(seconds=index),
            security_id="DEMO-NIFTY-OPT",
            ltp=max(price, 1.0),
            volume=100 + (index % 9) * 20,
        )
        await asyncio.sleep(0)