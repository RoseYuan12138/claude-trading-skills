#!/usr/bin/env python3
"""$10k -> $100k agentic options account: today's candidates and a rolling-start backtest.

Rule family (two-index LEAPS trend calls, see docs/AGGRESSIVE_OPTIONS_STRATEGY.md): hold one
call position on the underlying while SPY and QQQ both close above their 200-day SMAs, ~270
days to expiry, roll at 60 days left, cash otherwise. The account stops trading ("goal") the
first day equity reaches $100k and stops ("ruin") the first day it is below $3k.

Prices are Black-Scholes model prices, not real quotes: QQQ off VXN (VIX x 1.86 before
2001) with the repo's skew and term structure; TQQQ / SOXL / IWM off realised vol x a premium.
TQQQ and SOXL use real bars from 2010 and a synthetic 3x series (``synthetic_leveraged``)
before that, spliced at the first real bar.

Example:
    python3 agentic-trader/scripts/run_agentic_10k.py --data-dir data/ohlcv \\
        --macro-dir data/macro --adj-dir data/adjusted --out report.md
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.models import Bar  # noqa: E402
from agentic_trader.options import OptionExitRules, OptionRules, Right  # noqa: E402
from agentic_trader.playbook import (  # noqa: E402
    ItmTrendParams,
    _estimate,
    monthly_expiry_on_or_after,
)
from agentic_trader.pricing import bs_delta, bs_price  # noqa: E402
from agentic_trader.sim.data import load_csv_dir  # noqa: E402
from agentic_trader.sim.options_engine import (  # noqa: E402
    OptionSimConfig,
    OptionSimulator,
    expiry_after,
    round_strike,
    strike_step,
)
from agentic_trader.sim.rotation import synthetic_leveraged  # noqa: E402

START_CASH, GOAL, FLOOR = 10_000.0, 100_000.0, 3_000.0
LADDER = (0.85, 0.90, 0.95, 1.00)  # deepest ITM first; ATM is the last resort


class LadderSimulator(OptionSimulator):
    """Buys the deepest-ITM strike on ``ladder`` of which at least one contract fits the
    premium budget. A small account cannot afford one 15%-ITM QQQ LEAPS (~$14k on
    2026-11-11), so it steps toward the money, which raises leverage per dollar."""

    def __init__(self, *a, ladder: tuple[float, ...] = LADDER, **kw):
        super().__init__(*a, **kw)
        self.ladder = ladder

    def _build_order(self, s, d, equity, right, note, close, atr, risk_pct=None):
        base = self.cfg
        try:
            for m in self.ladder:
                self.cfg = replace(base, strike_moneyness=m)
                order = super()._build_order(s, d, equity, right, note, close, atr, risk_pct)
                if order is not None:
                    return order
            return None
        finally:
            self.cfg = base


def goal_or_ruin(
    curve: list[tuple[date, float]], goal: float = GOAL, floor: float = FLOOR
) -> tuple[list[tuple[date, float]], str, date | None]:
    """Truncate an equity curve at the first close >= goal ("goal") or < floor ("ruin").

    After either event the account stops trading, so equity is frozen at that value."""
    for i, (d, e) in enumerate(curve):
        if e >= goal or e < floor:
            frozen = list(curve[: i + 1]) + [(x, e) for x, _ in curve[i + 1 :]]
            return frozen, "goal" if e >= goal else "ruin", d
    return list(curve), "open", None


def curve_stats(curve: list[tuple[date, float]]) -> dict[str, float]:
    eq = [e for _, e in curve]
    peak, dd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e)
        dd = max(dd, 1 - e / peak)
    years = max((curve[-1][0] - curve[0][0]).days / 365.25, 1e-9)
    return {"cagr": ((max(eq[-1], 1e-9) / eq[0]) ** (1 / years) - 1) * 100, "dd": dd * 100}


def realised_vol(bars: list[Bar], window: int = 60) -> float:
    c = [b.close for b in bars[-window - 1 :]]
    r = [math.log(b / a) for a, b in zip(c, c[1:])]
    return statistics.stdev(r) * math.sqrt(252)


def splice_synthetic(real: list[Bar], base: list[Bar], leverage: float, irx: dict) -> list[Bar]:
    """Synthetic L x ``base`` before the first real bar, scaled to meet it, then real bars."""
    first = real[0].date
    syn = synthetic_leveraged([b for b in base if b.date <= first], leverage, irx)
    if not syn or syn[-1].date != first:
        raise ValueError("base series must contain the first real date")
    k = real[0].close / syn[-1].close
    pre = [Bar(b.date, b.close * k, b.close * k, b.close * k, b.close * k, 0) for b in syn[:-1]]
    return pre + list(real)


# ----------------------------------------------------------------- today's candidates


def candidates(data, vxn_today, vix_today, irx_today, as_of, equity, budget_pct):
    """Model-priced call candidates for today. Returns a list of dicts."""
    out = []
    rate = irx_today / 100
    p = ItmTrendParams()
    q = data["QQQ"][-1].close
    expiry = monthly_expiry_on_or_after(expiry_after(as_of, 270))
    for m in (0.85, 0.90, 0.95, 1.00, 1.05):
        k = round_strike(q * m, strike_step(q))
        px, delta = _estimate(q, k, expiry, as_of, vxn_today / 100, rate, p)
        out.append(
            _row("QQQ", q, k, expiry, px, delta, equity, budget_pct, rate, as_of, "VXN term+skew")
        )
    others = {
        "TQQQ": 1.1 * realised_vol(data["TQQQ"]),
        "SOXL": 1.1 * realised_vol(data["SOXL"]),
        "IWM": vix_today / 100 * 1.3,
    }
    for sym, iv in others.items():
        s = data[sym][-1].close
        for m in (0.85, 1.00):
            k = round_strike(s * m, strike_step(s))
            t = (expiry - as_of).days / 365
            px = bs_price(s, k, t, rate, iv, Right.CALL, 0.0)
            delta = bs_delta(s, k, t, rate, iv, Right.CALL)
            out.append(
                _row(sym, s, k, expiry, px, delta, equity, budget_pct, rate, as_of, f"IV {iv:.0%}")
            )
    return out


def _row(sym, spot, k, expiry, px, delta, equity, budget_pct, rate, as_of, iv_note):
    ask = px * 1.005  # half bid-ask of 0.5%
    n = math.floor(equity * budget_pct / 100 / (ask * 100))
    return {
        "sym": sym,
        "spot": spot,
        "strike": k,
        "expiry": expiry,
        "dte": (expiry - as_of).days,
        "price": px,
        "contract": px * 100,
        "n": n,
        "delta": delta,
        "breakeven": k + px,
        "be_pct": (k + px) / spot * 100 - 100,
        "exposure": delta * spot * 100 * n / equity,
        "notional_1": delta * spot * 100 / equity,
        "iv": iv_note,
    }


# ----------------------------------------------------------------- backtest


def run_rule(
    data, sym, vxn, irx, start, end, premium_pct, moneyness, dte=270, roll=60, cash=START_CASH
):
    """Two-index LEAPS trend calls on ``sym``; returns the raw equity curve and trades."""
    qqq_priced = sym == "QQQ"
    d = {s: [b for b in data[s] if b.date <= end] for s in {"QQQ", "SPY", sym}}
    cfg = OptionSimConfig(
        initial_cash=cash,
        start_date=start,
        untradable=tuple(s for s in d if s != sym),
        hedge_symbols=(sym,),
        risk_per_trade_pct=premium_pct,
        div_yield=0.007 if qqq_priced else 0.0,
        half_spread_pct=0.5 if qqq_priced else 1.0,
        min_half_spread=0.01,
        put_skew_per_pct=0.75,
        call_skew_per_pct=-0.25,
        iv_term_mean=0.24 if qqq_priced else None,
        iv_premium=1.1,
        hv_window=60,
        iv_floor=0.15,
        signal_mode="index_trend",
        regime_symbol="SPY",
        regime_also=("QQQ",),
        regime_sma=200,
        exit_on_regime_bear=True,
        strike_moneyness=moneyness[0] if isinstance(moneyness, tuple) else moneyness,
        target_dte=dte,
    )
    rules = OptionRules(
        max_loss_per_trade_pct=premium_pct + 0.01,
        max_total_risk_pct=premium_pct + 0.01,
        max_contracts=10**9,
        max_dte=400,
        daily_loss_limit_pct=100.0,
    )
    exits = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=roll)
    kw = dict(iv_overrides=vxn if qqq_priced else None, rates_pct=irx)
    if isinstance(moneyness, tuple):
        res = LadderSimulator(d, rules, exits, cfg, ladder=moneyness, **kw).run()
    else:
        res = OptionSimulator(d, rules, exits, cfg, **kw).run()
    return res.equity_curve, res


def rolling(
    data, sym, vxn, irx, end, premium_pct, moneyness, years=range(2000, 2022), today_px=None
):
    """One run per start year. With ``today_px`` the account is scaled so that it is as
    small relative to one contract as $10k is today: cash = $10k x price at start /
    today_px, and the goal and floor scale with it. Option prices scale with the underlying,
    so this replays today's "can only afford one ATM-ish contract" problem in every year."""
    rows = []
    for y in years:
        start = date(y, 1, 3)
        scale = 1.0
        if today_px:
            first = next(b.close for b in data[sym] if b.date >= start)
            scale = first / today_px
        raw, res = run_rule(
            data, sym, vxn, irx, start, end, premium_pct, moneyness, cash=START_CASH * scale
        )
        curve, outcome, when = goal_or_ruin(raw, GOAL * scale, FLOOR * scale)
        tail = [e for _, e in raw[-504:]]
        if outcome == "open" and len(tail) == 504 and max(tail) - min(tail) < 1e-6 * tail[0]:
            outcome = "stuck"  # no trade for 2 years: one contract no longer fits the budget
        to_stop = curve if when is None else [(d, e) for d, e in curve if d <= when]
        s_full = curve_stats(raw)
        s_stop = curve_stats(to_stop)
        rows.append(
            {
                "start": y,
                "outcome": outcome,
                "when": when,
                "years": ((when - raw[0][0]).days / 365.25) if when else None,
                "cagr_raw": s_full["cagr"],
                "dd_raw": s_full["dd"],
                "dd_to_stop": s_stop["dd"],
                "final": curve[-1][1] / scale,
                "trades": len(res.trades),
            }
        )
    return rows


def summarise(rows):
    goals = [r for r in rows if r["outcome"] == "goal"]
    ruins = [r for r in rows if r["outcome"] == "ruin"]
    stuck = [r for r in rows if r["outcome"] == "stuck"]
    yrs = sorted(r["years"] for r in goals)
    return {
        "starts": len(rows),
        "goal": len(goals),
        "ruin": len(ruins),
        "stuck": len(stuck),
        "median_years": statistics.median(yrs) if yrs else None,
        "goal_10y": sum(r["years"] <= 10 for r in goals),
        "goal_5y": sum(r["years"] <= 5 for r in goals),
        "median_cagr": statistics.median(r["cagr_raw"] for r in rows),
        "median_dd": statistics.median(r["dd_to_stop"] for r in rows),
        "worst_dd": max(r["dd_to_stop"] for r in rows),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--data-dir", type=Path, required=True, help="QQQ SPY TQQQ SOXL IWM csv")
    ap.add_argument("--macro-dir", type=Path, required=True, help="^VXN ^VIX ^IRX csv")
    ap.add_argument("--adj-dir", type=Path, required=True, help="adjusted QQQ and ^SOX csv")
    ap.add_argument("--end", type=date.fromisoformat, default=None)
    ap.add_argument("--equity", type=float, default=START_CASH)
    ap.add_argument("--budget-pct", type=float, default=80.0)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    macro = load_csv_dir(args.macro_dir)
    adj = load_csv_dir(args.adj_dir)
    irx = {b.date: b.close for b in macro["^IRX"]}
    vix = {b.date: b.close for b in macro["^VIX"]}
    vxn_raw = {b.date: b.close for b in macro["^VXN"]}
    vxn = {"QQQ": {**{d: v * 1.86 for d, v in vix.items()}, **vxn_raw}}
    data["TQQQ"] = splice_synthetic(data["TQQQ"], adj["QQQ"], 3.0, irx)
    data["SOXL"] = splice_synthetic(data["SOXL"], adj["^SOX"], 3.0, irx)
    end = args.end or min(data["SPY"][-1].date, data["QQQ"][-1].date)
    lines = []

    # today's candidates
    as_of = end
    vxn_today = next(v for d, v in sorted(vxn_raw.items(), reverse=True) if d <= as_of)
    vix_today = next(v for d, v in sorted(vix.items(), reverse=True) if d <= as_of)
    irx_today = next(v for d, v in sorted(irx.items(), reverse=True) if d <= as_of)
    cut = {s: [b for b in data[s] if b.date <= as_of] for s in ("QQQ", "TQQQ", "SOXL", "IWM")}
    lines.append(
        f"## Candidates on {as_of} (model prices: VXN {vxn_today:.1f}, VIX {vix_today:.1f}, "
        f"T-bill {irx_today:.2f}%; budget {args.budget_pct:.0f}% of ${args.equity:,.0f})\n"
    )
    lines.append(
        "| Call | Spot | Expiry (DTE) | Model $/sh | $/contract | Affordable | Delta | "
        "Breakeven (vs spot) | Exposure if bought | Exposure of 1 contract | IV basis |"
    )
    lines.append("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for c in candidates(cut, vxn_today, vix_today, irx_today, as_of, args.equity, args.budget_pct):
        lines.append(
            f"| {c['sym']} {c['strike']:g}C | {c['spot']:.2f} | {c['expiry']} ({c['dte']}) | "
            f"{c['price']:.2f} | {c['contract']:,.0f} | {c['n']} | {c['delta']:.2f} | "
            f"{c['breakeven']:.2f} ({c['be_pct']:+.1f}%) | {c['exposure']:.1f}x | "
            f"{c['notional_1']:.1f}x | {c['iv']} |"
        )

    # rolling-start backtests
    today_px = data["QQQ"][-1].close
    variants = [
        ("QQQ", 80.0, LADDER, today_px),
        ("QQQ", 95.0, LADDER, today_px),
        ("QQQ", 80.0, 1.00, today_px),
        ("QQQ", 80.0, LADDER),
        ("QQQ", 30.0, 0.85),
        ("QQQ", 50.0, 0.85),
        ("QQQ", 80.0, 0.85),
        ("QQQ", 95.0, 0.85),
        ("QQQ", 80.0, 1.00),
        ("QQQ", 95.0, 1.00),
        ("TQQQ", 80.0, 0.85),
        ("SOXL", 80.0, 0.85),
    ]
    lines.append(
        f"\n## Rolling starts {2000}-{2021} (Jan of each year, $10k, to {end}; goal $100k, "
        f"ruin < $3k)\n"
    )
    lines.append(
        "| Rule | Reached $100k | ...within 5y | ...within 10y | Median years | Ruin | Stuck in cash | "
        "Median CAGR (no stop) | Median max DD | Worst max DD |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    detail = []
    for sym, prem, m, *norm in variants:
        rows = rolling(data, sym, vxn, irx, end, prem, m, today_px=norm[0] if norm else None)
        s = summarise(rows)
        itm = 0 if isinstance(m, tuple) else round((1 - m) * 100)
        name = f"{sym} {itm}% ITM, {prem:.0f}% premium"
        if m == 1.0:
            name = f"{sym} ATM, {prem:.0f}% premium"
        elif isinstance(m, tuple):
            name = f"{sym} ladder 15% ITM -> ATM, {prem:.0f}% premium"
        if norm:
            name += ", sized like $10k today"
        med = f"{s['median_years']:.1f}" if s["median_years"] is not None else "-"
        lines.append(
            f"| {name} | {s['goal']}/{s['starts']} | {s['goal_5y']} | {s['goal_10y']} | {med} | "
            f"{s['ruin']} | {s['stuck']} | {s['median_cagr']:+.1f}% | {s['median_dd']:.0f}% | {s['worst_dd']:.0f}% |"
        )
        detail.append((name, rows))
        print(lines[-1], file=sys.stderr)
    for name, rows in detail:
        lines.append(f"\n### {name}\n")
        lines.append(
            "| Start | Outcome | Date | Years | CAGR to end (no stop) | Max DD to stop | "
            "Final (in today's $) | Trades |"
        )
        lines.append("|---:|---|---|---:|---:|---:|---:|---:|")
        for r in rows:
            yrs = f"{r['years']:.1f}" if r["years"] is not None else "-"
            lines.append(
                f"| {r['start']} | {r['outcome']} | {r['when'] or '-'} | {yrs} | "
                f"{r['cagr_raw']:+.1f}% | {r['dd_to_stop']:.0f}% | ${r['final']:,.0f} | {r['trades']} |"
            )
    text = "\n".join(lines) + "\n"
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
