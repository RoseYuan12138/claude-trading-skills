"""Paper "lottery basket": small bets on cheap, far out-of-the-money options.

Entries use the price the user saw (a real quote when available). Before expiry each ticket
is marked with Black-Scholes at the implied vol solved at entry (a model mark, so take-profit
is only an alert to check the real quote). At expiry it settles at intrinsic value from the
underlying's real close, so the final P/L of every held-to-expiry ticket is exact given its
entry price. Rules keep each bet small and forbid averaging down.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .options import MULTIPLIER, Right
from .pricing import bs_price


def implied_vol(price: float, spot: float, strike: float, t: float, rate: float, right) -> float:
    """Bisection on Black-Scholes (no dividends); returns an annual vol."""
    lo, hi = 1e-4, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if bs_price(spot, strike, t, rate, mid, right) < price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


@dataclass(frozen=True)
class BasketRules:
    max_ticket: float = 100.0  # most premium per ticket (1% of the $10k main account)
    take_profit_multiple: float = 3.0  # alert when the model mark reaches this x entry


@dataclass
class LotteryTicket:
    symbol: str
    right: str
    strike: float
    expiry: date
    contracts: int
    entry_price: float
    entry_date: date
    entry_spot: float
    entry_iv: float
    thesis: str = ""
    status: str = "open"  # open / closed / expired
    mark: float = 0.0
    last_spot: float = 0.0
    exit_price: float | None = None
    exit_date: date | None = None

    @property
    def cost(self) -> float:
        return self.entry_price * MULTIPLIER * self.contracts

    @property
    def value(self) -> float:
        px = self.exit_price if self.status != "open" else self.mark
        return (px or 0.0) * MULTIPLIER * self.contracts

    @property
    def pnl(self) -> float:
        return self.value - self.cost

    @property
    def label(self) -> str:
        return f"{self.symbol} {self.expiry} {self.strike:g}{self.right[0].upper()}"


@dataclass
class Basket:
    cash: float
    rules: BasketRules = field(default_factory=BasketRules)
    tickets: list[LotteryTicket] = field(default_factory=list)
    rate: float = 0.04

    @property
    def equity(self) -> float:
        return self.cash + sum(t.value for t in self.tickets if t.status == "open")

    def buy(
        self,
        symbol: str,
        right: Right,
        strike: float,
        expiry: date,
        contracts: int,
        price: float,
        spot: float,
        as_of: date,
        rate: float | None = None,
        thesis: str = "",
    ) -> LotteryTicket:
        cost = price * MULTIPLIER * contracts
        if contracts <= 0 or price <= 0:
            raise ValueError("contracts and price must be positive")
        if cost > self.rules.max_ticket + 1e-9:
            raise ValueError(
                f"ticket costs ${cost:,.0f} > max ticket ${self.rules.max_ticket:,.0f}"
            )
        if cost > self.cash + 1e-9:
            raise ValueError(f"ticket costs ${cost:,.0f} > cash ${self.cash:,.0f}")
        rv = getattr(right, "value", right)
        for t in self.tickets:
            if t.status == "open" and (t.symbol, t.right, t.strike, t.expiry) == (
                symbol,
                rv,
                strike,
                expiry,
            ):
                raise ValueError(f"already hold {t.label}: no averaging down")
        if rate is not None:
            self.rate = rate
        t_years = max((expiry - as_of).days, 1) / 365
        iv = implied_vol(price, spot, strike, t_years, self.rate, rv)
        ticket = LotteryTicket(
            symbol, rv, strike, expiry, contracts, price, as_of, spot, iv, thesis,
            mark=price, last_spot=spot,
        )  # fmt: skip
        self.cash -= cost
        self.tickets.append(ticket)
        return ticket

    def step(self, spots: dict[str, float], as_of: date) -> list[str]:
        """Mark open tickets (model) or settle them at intrinsic on/after expiry.
        Returns take-profit alerts."""
        alerts = []
        for t in self.tickets:
            if t.status != "open" or t.symbol not in spots:
                continue
            s = spots[t.symbol]
            t.last_spot = s
            if as_of >= t.expiry:
                intrinsic = max(s - t.strike, 0.0) if t.right == "call" else max(t.strike - s, 0.0)
                t.status, t.exit_price, t.exit_date, t.mark = "expired", intrinsic, as_of, intrinsic
                self.cash += intrinsic * MULTIPLIER * t.contracts
                continue
            t_years = (t.expiry - as_of).days / 365
            t.mark = bs_price(s, t.strike, t_years, self.rate, t.entry_iv, t.right)
            if t.mark >= t.entry_price * self.rules.take_profit_multiple:
                alerts.append(
                    f"{t.label}: model mark ${t.mark:.2f} >= "
                    f"{self.rules.take_profit_multiple:g}x entry ${t.entry_price:.2f}; check the "
                    "real quote and consider selling (half if you hold 2+)"
                )
        return alerts

    def close(self, index: int, price: float, as_of: date) -> LotteryTicket:
        t = self.tickets[index]
        if t.status != "open":
            raise ValueError(f"{t.label} is already {t.status}")
        t.status, t.exit_price, t.exit_date, t.mark = "closed", price, as_of, price
        self.cash += price * MULTIPLIER * t.contracts
        return t

    def summary(self) -> dict[str, float]:
        done = [t for t in self.tickets if t.status != "open"]
        open_ = [t for t in self.tickets if t.status == "open"]
        return {
            "tickets": len(self.tickets),
            "open": len(open_),
            "closed": len(done),
            "winners": sum(t.pnl > 0 for t in done),
            "spent": sum(t.cost for t in self.tickets),
            "realised_pnl": sum(t.pnl for t in done),
            "open_model_pnl": sum(t.pnl for t in open_),
            "best_multiple": max((t.value / t.cost for t in done), default=0.0),
            "equity": self.equity,
        }

    # ---- persistence ----
    def save(self, path: str | Path) -> None:
        def enc(o):
            if isinstance(o, date):
                return o.isoformat()
            raise TypeError(o)

        data = {
            "cash": self.cash,
            "rate": self.rate,
            "rules": asdict(self.rules),
            "tickets": [asdict(t) for t in self.tickets],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, indent=2, default=enc))

    @classmethod
    def load(cls, path: str | Path) -> Basket:
        raw = json.loads(Path(path).read_text())
        tickets = []
        for t in raw.get("tickets", []):
            t = dict(t)
            for k in ("expiry", "entry_date", "exit_date"):
                t[k] = date.fromisoformat(t[k]) if t.get(k) else None
            tickets.append(LotteryTicket(**t))
        return cls(raw["cash"], BasketRules(**raw.get("rules", {})), tickets, raw.get("rate", 0.04))
