"""Transparent brokerage, tax, and net P&L calculations."""

from __future__ import annotations

from dataclasses import dataclass

from .config import CostConfig, InstrumentType


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    buy_turnover: float
    sell_turnover: float
    total_turnover: float
    brokerage: float
    stt: float
    exchange_charges: float
    sebi_charges: float
    stamp_duty: float
    gst: float
    total_cost: float
    gross_pnl: float
    net_pnl: float


class CostCalculator:
    """Calculates costs for a complete buy-then-sell round trip."""

    def __init__(self, config: CostConfig) -> None:
        self.config = config

    def calculate(
        self,
        *,
        buy_price: float,
        sell_price: float,
        quantity: int,
        instrument_type: InstrumentType,
    ) -> CostBreakdown:
        if buy_price < 0 or sell_price < 0:
            raise ValueError("Prices cannot be negative")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        buy_turnover = buy_price * quantity
        sell_turnover = sell_price * quantity
        total_turnover = buy_turnover + sell_turnover
        brokerage = min(
            self.config.brokerage_flat,
            buy_turnover * self.config.brokerage_rate,
        ) + min(
            self.config.brokerage_flat,
            sell_turnover * self.config.brokerage_rate,
        )
        stt_rate = (
            self.config.option_stt_sell_rate
            if instrument_type is InstrumentType.OPTION
            else self.config.futures_stt_sell_rate
        )
        stt = sell_turnover * stt_rate
        exchange_charges = total_turnover * self.config.exchange_turnover_rate
        sebi_charges = total_turnover * self.config.sebi_turnover_rate
        stamp_duty = buy_turnover * self.config.stamp_duty_buy_rate
        gst = (brokerage + exchange_charges) * self.config.gst_rate
        total_cost = (
            brokerage
            + stt
            + exchange_charges
            + sebi_charges
            + stamp_duty
            + gst
        )
        gross_pnl = (sell_price - buy_price) * quantity
        return CostBreakdown(
            buy_turnover=buy_turnover,
            sell_turnover=sell_turnover,
            total_turnover=total_turnover,
            brokerage=brokerage,
            stt=stt,
            exchange_charges=exchange_charges,
            sebi_charges=sebi_charges,
            stamp_duty=stamp_duty,
            gst=gst,
            total_cost=total_cost,
            gross_pnl=gross_pnl,
            net_pnl=gross_pnl - total_cost,
        )