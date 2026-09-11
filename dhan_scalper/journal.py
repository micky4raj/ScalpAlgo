"""SQLite trade lifecycle journal and real-time performance analytics."""

from __future__ import annotations

import math
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .cost_calculator import CostBreakdown
from .execution_engine import ExecutionEvent


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    gross_pnl: float
    total_costs: float
    net_pnl: float


class TradeJournal:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(
            self.database_path, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    def log_tick(
        self,
        *,
        timestamp: datetime,
        security_id: str,
        ltp: float,
        volume: int,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO ticks(timestamp, security_id, ltp, volume) VALUES (?, ?, ?, ?)",
                (timestamp.isoformat(), security_id, ltp, volume),
            )

    def log_execution(self, event: ExecutionEvent) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO executions(
                    order_id, timestamp, status, security_id, side, quantity,
                    requested_price, fill_price, latency_us, slippage, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.order_id,
                    event.timestamp.isoformat(),
                    event.status.value,
                    event.request.security_id,
                    event.request.side.value,
                    event.request.quantity,
                    event.request.price,
                    event.fill_price,
                    event.latency_us,
                    event.slippage,
                    event.message,
                ),
            )

    def log_trade(
        self,
        *,
        opened_at: datetime,
        closed_at: datetime,
        security_id: str,
        quantity: int,
        buy_price: float,
        sell_price: float,
        costs: CostBreakdown,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO trades(
                    opened_at, closed_at, security_id, quantity, buy_price,
                    sell_price, gross_pnl, total_costs, net_pnl
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    opened_at.isoformat(),
                    closed_at.isoformat(),
                    security_id,
                    quantity,
                    buy_price,
                    sell_price,
                    costs.gross_pnl,
                    costs.total_cost,
                    costs.net_pnl,
                ),
            )

    def performance(self) -> PerformanceReport:
        with self._lock:
            rows = self._connection.execute(
                "SELECT gross_pnl, total_costs, net_pnl FROM trades ORDER BY closed_at"
            ).fetchall()
        returns = [float(row["net_pnl"]) for row in rows]
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        gross_pnl = sum(float(row["gross_pnl"]) for row in rows)
        total_costs = sum(float(row["total_costs"]) for row in rows)
        net_pnl = sum(returns)
        profit_factor = (
            sum(wins) / abs(sum(losses)) if losses else float("inf") if wins else 0.0
        )
        peak = 0.0
        equity = 0.0
        max_drawdown = 0.0
        for value in returns:
            equity += value
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        sharpe = _sharpe(returns)
        return PerformanceReport(
            trades=len(returns),
            wins=len(wins),
            losses=len(losses),
            win_rate=len(wins) / len(returns) if returns else 0.0,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            gross_pnl=gross_pnl,
            total_costs=total_costs,
            net_pnl=net_pnl,
        )

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ticks(
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    security_id TEXT NOT NULL,
                    ltp REAL NOT NULL,
                    volume INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executions(
                    id INTEGER PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    security_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    requested_price REAL NOT NULL,
                    fill_price REAL,
                    latency_us INTEGER NOT NULL,
                    slippage REAL NOT NULL,
                    message TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trades(
                    id INTEGER PRIMARY KEY,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT NOT NULL,
                    security_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    buy_price REAL NOT NULL,
                    sell_price REAL NOT NULL,
                    gross_pnl REAL NOT NULL,
                    total_costs REAL NOT NULL,
                    net_pnl REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ticks_timestamp ON ticks(timestamp);
                CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON trades(closed_at);
                """
            )


def _sharpe(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    deviation = math.sqrt(variance)
    return (mean / deviation) * math.sqrt(len(values)) if deviation else 0.0