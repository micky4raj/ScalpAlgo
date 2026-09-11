"""Paper and live execution controllers with identical order semantics."""

from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from .dhan_client import DhanClient, OrderResponse
from .scalp_strategy import Side, Tick


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    TRADED = "TRADED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class OrderRequest:
    security_id: str
    side: Side
    quantity: int
    price: float
    exchange_segment: str = "NSE_FNO"
    product_type: str = "INTRADAY"
    order_type: str = "LIMIT"


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    order_id: str
    status: OrderStatus
    timestamp: datetime
    request: OrderRequest
    fill_price: float | None
    latency_us: int
    slippage: float
    message: str = ""


class ExecutionController(ABC):
    @abstractmethod
    async def submit(
        self, request: OrderRequest, *, on_event: Any | None = None
    ) -> ExecutionEvent:
        raise NotImplementedError


class RiskGate:
    """Hard circuit breaker checked before every new entry."""

    def __init__(self, *, max_daily_loss: float, max_drawdown: float) -> None:
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown

    def allows_entry(self, report: PerformanceReport) -> bool:
        return (
            report.net_pnl > -self.max_daily_loss
            and report.max_drawdown < self.max_drawdown
        )


class PaperExecutionController(ExecutionController):
    """Tick-matched simulator with configurable slippage and queue delay."""

    def __init__(
        self,
        *,
        slippage_rate: float = 0.00075,
        queue_delay_ms: int = 25,
        random_seed: int = 7,
    ) -> None:
        self.slippage_rate = slippage_rate
        self.queue_delay_ms = queue_delay_ms
        self._random = random.Random(random_seed)
        self._sequence = 0
        self._latest_tick: Tick | None = None

    def on_tick(self, tick: Tick) -> None:
        self._latest_tick = tick

    async def submit(
        self, request: OrderRequest, *, on_event: Any | None = None
    ) -> ExecutionEvent:
        started = time.perf_counter_ns()
        self._sequence += 1
        order_id = f"PAPER-{self._sequence:08d}"
        await asyncio.sleep(self.queue_delay_ms / 1000)
        reference = self._latest_tick.ltp if self._latest_tick else request.price
        if reference <= 0 or request.quantity <= 0:
            event = ExecutionEvent(
                order_id,
                OrderStatus.REJECTED,
                datetime.now(timezone.utc),
                request,
                None,
                _elapsed_us(started),
                0.0,
                "invalid market reference or quantity",
            )
        else:
            direction = 1 if request.side is Side.BUY else -1
            slippage = reference * self.slippage_rate * (
                0.8 + self._random.random() * 0.4
            )
            fill_price = reference + (direction * slippage)
            event = ExecutionEvent(
                order_id,
                OrderStatus.TRADED,
                datetime.now(timezone.utc),
                request,
                fill_price,
                _elapsed_us(started),
                fill_price - reference,
                "paper fill",
            )
        if on_event is not None:
            result = on_event(event)
            if asyncio.iscoroutine(result):
                await result
        return event


class LiveDhanExecutionController(ExecutionController):
    """Routes orders to DhanHQ and does not silently simulate failures."""

    def __init__(self, client: DhanClient) -> None:
        self.client = client

    async def submit(
        self, request: OrderRequest, *, on_event: Any | None = None
    ) -> ExecutionEvent:
        started = time.perf_counter_ns()
        payload = {
            "dhanClientId": self.client.config.client_id,
            "transactionType": request.side.value,
            "exchangeSegment": request.exchange_segment,
            "productType": request.product_type,
            "orderType": request.order_type,
            "validity": "DAY",
            "securityId": request.security_id,
            "quantity": request.quantity,
            "price": request.price,
            "triggerPrice": 0,
            "disclosedQuantity": 0,
            "afterMarketOrder": False,
        }
        try:
            response: OrderResponse = await self.client.place_order(payload)
            status = _map_status(response.status)
            event = ExecutionEvent(
                response.order_id,
                status,
                datetime.now(timezone.utc),
                request,
                None,
                _elapsed_us(started),
                0.0,
                "DhanHQ acknowledgement; fill price follows order updates",
            )
        except Exception as exc:
            event = ExecutionEvent(
                f"LIVE-FAILED-{time.time_ns()}",
                OrderStatus.REJECTED,
                datetime.now(timezone.utc),
                request,
                None,
                _elapsed_us(started),
                0.0,
                str(exc),
            )
        if on_event is not None:
            result = on_event(event)
            if asyncio.iscoroutine(result):
                await result
        return event


def _elapsed_us(started_ns: int) -> int:
    return (time.perf_counter_ns() - started_ns) // 1_000


def _map_status(status: str) -> OrderStatus:
    normalized = status.upper()
    for candidate in OrderStatus:
        if candidate.value in normalized:
            return candidate
    return OrderStatus.PENDING