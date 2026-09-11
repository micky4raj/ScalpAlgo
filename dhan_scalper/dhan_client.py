"""Async DhanHQ v2 adapter.

The adapter keeps transport concerns separate from strategy and execution.
Optional third-party packages are imported only when LIVE mode is used:
``aiohttp`` for REST and ``websockets`` for the feed.
"""

from __future__ import annotations

import json
import logging
import struct
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .config import DhanConfig
from .scalp_strategy import Tick

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OrderResponse:
    order_id: str
    status: str
    raw: dict[str, Any]


class DhanClient:
    """Small async wrapper around DhanHQ order and market-data endpoints."""

    def __init__(self, config: DhanConfig) -> None:
        self.config = config
        self._session: Any | None = None

    async def __aenter__(self) -> "DhanClient":
        try:
            import aiohttp
        except ImportError as exc:
            raise RuntimeError(
                "Install live dependencies with: pip install -e '.[live]'"
            ) from exc
        self._session = aiohttp.ClientSession(
            headers={
                "access-token": self.config.access_token,
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=10),
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def place_order(self, payload: dict[str, Any]) -> OrderResponse:
        if self._session is None:
            raise RuntimeError("DhanClient must be used as an async context manager")
        async with self._session.post(
            f"{self.config.rest_base_url}/orders", json=payload
        ) as response:
            body = await response.json(content_type=None)
            if response.status >= 400:
                raise RuntimeError(f"Dhan order rejected ({response.status}): {body}")
            order_id = str(body.get("orderId", ""))
            if not order_id:
                raise RuntimeError(f"Dhan response did not include orderId: {body}")
            return OrderResponse(order_id, str(body.get("orderStatus", "PENDING")), body)

    async def get_order(self, order_id: str) -> OrderResponse:
        if self._session is None:
            raise RuntimeError("DhanClient must be used as an async context manager")
        async with self._session.get(
            f"{self.config.rest_base_url}/orders/{order_id}"
        ) as response:
            body = await response.json(content_type=None)
            if response.status >= 400:
                raise RuntimeError(f"Dhan order lookup failed ({response.status}): {body}")
            return OrderResponse(order_id, str(body.get("orderStatus", "UNKNOWN")), body)

    async def cancel_order(self, order_id: str) -> OrderResponse:
        if self._session is None:
            raise RuntimeError("DhanClient must be used as an async context manager")
        async with self._session.delete(
            f"{self.config.rest_base_url}/orders/{order_id}"
        ) as response:
            body = await response.json(content_type=None)
            if response.status >= 400:
                raise RuntimeError(f"Dhan cancellation failed ({response.status}): {body}")
            return OrderResponse(order_id, str(body.get("orderStatus", "CANCELLED")), body)

    async def stream_ticks(
        self,
        *,
        subscriptions: list[tuple[str, str]],
    ) -> AsyncIterator[Tick]:
        """Yield decoded ticker packets from Dhan's binary websocket feed.

        The Dhan v2 request is JSON; the response is a compact binary packet.
        The feed is kept as a generator so reconnect/backoff remains the
        caller's responsibility.
        """
        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError(
                "Install live dependencies with: pip install -e '.[live]'"
            ) from exc
        headers = {
            "access-token": self.config.access_token,
            "client-id": self.config.client_id,
            "version": self.config.api_version,
        }
        async with websockets.connect(
            self.config.websocket_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
        ) as socket:
            for offset in range(0, len(subscriptions), 100):
                batch = subscriptions[offset : offset + 100]
                await socket.send(json.dumps(_subscription_payload(batch)))
            async for message in socket:
                if isinstance(message, bytes):
                    tick = _decode_ticker_packet(message)
                    if tick is not None:
                        yield tick


def _subscription_payload(
    subscriptions: list[tuple[str, str]],
) -> dict[str, object]:
    """Build the documented Dhan v2 ticker subscription JSON payload."""
    if not subscriptions:
        raise ValueError("At least one Dhan subscription is required")
    instruments = [
        {"ExchangeSegment": segment, "SecurityId": security_id}
        for segment, security_id in subscriptions
    ]
    return {
        "RequestCode": 15,
        "InstrumentCount": len(instruments),
        "InstrumentList": instruments,
    }


def _decode_ticker_packet(packet: bytes) -> Tick | None:
    """Decode Dhan's 8-byte response header plus 8-byte ticker payload."""
    if len(packet) < 16:
        return None
    try:
        response_code, message_length, _segment, security_id_number = (
            struct.unpack_from("<BHBI", packet)
        )
        if response_code != 2 or message_length > len(packet):
            return None
        ltp = struct.unpack_from("<f", packet, 8)[0]
        if ltp <= 0:
            return None
        last_trade_epoch = struct.unpack_from("<I", packet, 12)[0]
        return Tick(
            timestamp=datetime.fromtimestamp(
                last_trade_epoch, tz=timezone.utc
            ),
            security_id=str(security_id_number),
            ltp=float(ltp),
            volume=0,
        )
    except struct.error:
        return None