#!/usr/bin/env python3
"""Aggressive QQQ option strategies vs leveraged-ETF benchmarks, 2001-2026.

All option strategies trade QQQ only (no stock picking, no survivorship) and are priced
off the actual VXN implied-vol index. Parameters are fixed in this file before running;
the windows are a 2001-2010 stress period (dot-com bust, 2008), 2011-2021 (out of sample
for every idea found in this project) and 2021-2026 (where most ideas came from).

Strategies
  S1 breakout calls  ATM 35-DTE call on 20d breakouts above the 50d SMA while SPY > 50d SMA
  S2 dip calls       ATM 45-DTE call when the market score < 30
  S3 ITM trend calls 15%-ITM 120-DTE call held while SPY > 200d SMA, rolled at 30 DTE
  S4 put credit      5%-OTM, 5%-wide 35-DTE put spread sold while SPY > 200d SMA
  C1 / C2            S3 or S4 (80% of capital) + S2 (20%)
Benchmarks: QQQ buy & hold, 2x QQQ buy & hold, 2x QQQ while SPY > 200d SMA (synthetic,
calibrated to QLD; dividend-adjusted QQQ and ^IRX borrowing cost).

Example:
    python3 agentic-trader/scripts/run_aggressive_research.py --data-dir data/ohlcv \\
        --macro-dir data/macro --adj-dir data/adjusted
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentic_trader.market_score import market_scores  # noqa: E402
from agentic_trader.options import OptionExitRules, OptionRules  # noqa: E402
from agentic_trader.sim.data import ETF_SYMBOLS, load_csv_dir  # noqa: E402
from agentic_trader.sim.options_engine import OptionSimConfig, OptionSimulator  # noqa: E402
from agentic_trader.sim.rotation import rotation_curve, synthetic_leveraged  # noqa: E402

PERIODS = {
    "2000-2026 from the dot-com peak": (date(2000, 1, 3), date(2026, 11, 10)),
    "2001-2010 stress": (date(2001, 2, 1), date(2010, 12, 31)),
    "2011-2021 out of sample": (date(2011, 1, 3), date(2021, 8, 31)),
    "2021-2026 in sample": (date(2021, 9, 1), date(2026, 11, 10)),
    "2001-2026 all": (date(2001, 2, 1), date(2026, 11, 10)),
}

DEBIT_EXITS = OptionExitRules(stop_loss_pct=50, trail_after_pct=50, trail_pct=35, time_stop_dte=5)
TREND_EXITS = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=30)
CREDIT_EXITS = OptionExitRules(
    stop_loss_pct=None,
    trail_after_pct=None,
    credit_take_profit_pct=50,
    credit_stop_multiple=2.0,
    time_stop_dte=7,
)

# name -> (config overrides, exits, risk % per trade)
OPTION_STRATEGIES = {
    "S1 breakout calls (5%/trade)": (
        dict(regime_symbol="SPY", regime_sma=50, allow_puts=False, target_dte=35),
        DEBIT_EXITS,
        5.0,
    ),
    "S2 dip calls, score < 30 (5%/trade)": (
        dict(signal_mode="score_dip", dip_threshold=30.0, target_dte=45),
        DEBIT_EXITS,
        5.0,
    ),
    "S3a ITM trend calls, 30% in premium": (
        dict(
            signal_mode="index_trend",
            regime_symbol="SPY",
            regime_sma=200,
            exit_on_regime_bear=True,
            strike_moneyness=0.85,
            target_dte=120,
        ),
        TREND_EXITS,
        30.0,
    ),
    "S3b ITM trend calls, 50% in premium": (
        dict(
            signal_mode="index_trend",
            regime_symbol="SPY",
            regime_sma=200,
            exit_on_regime_bear=True,
            strike_moneyness=0.85,
            target_dte=120,
        ),
        TREND_EXITS,
        50.0,
    ),
    "S3c LEAPS trend calls, 270d/roll 60, 30%": (
        dict(
            signal_mode="index_trend",
            regime_symbol="SPY",
            regime_sma=200,
            exit_on_regime_bear=True,
            strike_moneyness=0.85,
            target_dte=270,
        ),
        OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=60),
        30.0,
    ),
    "S3d LEAPS trend calls, 270d/roll 60, 50%": (
        dict(
            signal_mode="index_trend",
            regime_symbol="SPY",
            regime_sma=200,
            exit_on_regime_bear=True,
            strike_moneyness=0.85,
            target_dte=270,
        ),
        OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=60),
        50.0,
    ),
    "S3e LEAPS 270d, 30%, SPY and QQQ > 200d": (
        dict(
            signal_mode="index_trend",
            regime_symbol="SPY",
            regime_also=("QQQ",),
            regime_sma=200,
            exit_on_regime_bear=True,
            strike_moneyness=0.85,
            target_dte=270,
        ),
        OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=60),
        30.0,
    ),
    "S3f LEAPS 270d, 50%, SPY and QQQ > 200d": (
        dict(
            signal_mode="index_trend",
            regime_symbol="SPY",
            regime_also=("QQQ",),
            regime_sma=200,
            exit_on_regime_bear=True,
            strike_moneyness=0.85,
            target_dte=270,
        ),
        OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=60),
        50.0,
    ),
    "S4a put credit spreads (10% max loss)": (
        dict(
            signal_mode="put_credit",
            regime_symbol="SPY",
            regime_sma=200,
            exit_on_regime_bear=True,
            credit_otm_pct=5.0,
            credit_width_pct=5.0,
            target_dte=35,
        ),
        CREDIT_EXITS,
        10.0,
    ),
    "S4b put credit spreads (25% max loss)": (
        dict(
            signal_mode="put_credit",
            regime_symbol="SPY",
            regime_sma=200,
            exit_on_regime_bear=True,
            credit_otm_pct=5.0,
            credit_width_pct=5.0,
            target_dte=35,
        ),
        CREDIT_EXITS,
        25.0,
    ),
}
# Pricing scenarios: (put skew, call skew) in vol points per 1% out of the money.
# Skew is by strike (calls and puts at the same strike share IV) and is quoted for
# 30-day options, scaled by sqrt(30 / days) for other expiries.
PRICING = {
    "no skew": (0.0, 0.0),
    "base skew": (0.75, -0.25),
    "steep skew": (1.25, 0.0),
}
# IV term structure (30-day VXN mean-reverting to 24% at kappa 3/yr for other expiries);
# set to None for the flat-term sensitivity row.
TERM_MEAN, TERM_KAPPA = 0.24, 3.0
BASE_PRICING = "base skew"
HALF_SPREAD_PCT = 0.5  # QQQ options: a few cents wide; 0.5% of price per leg, $0.01 minimum
COST_SCENARIOS = (0.5, 1.0, 2.5)

COMBOS = {
    "C1 S3a 80% + S2 20%": ("S3a ITM trend calls, 30% in premium", 0.8),
    "C2 S4a 80% + S2 20%": ("S4a put credit spreads (10% max loss)", 0.8),
}


def stats(curve):
    eq = [e for _, e in curve]
    rets = [b / a - 1 for a, b in zip(eq, eq[1:]) if a > 0]
    sd = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    peak, dd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e)
        dd = max(dd, 1 - e / peak)
    years = len(eq) / 252
    end = max(eq[-1], 1e-12)
    yearly, prev = {}, None
    for d, e in curve:
        yearly.setdefault(d.year, [prev if prev is not None else e, e])
        yearly[d.year][1] = e
        prev = e
    yr = {y: (b / a - 1) * 100 for y, (a, b) in yearly.items()}
    return {
        "cagr": ((end / eq[0]) ** (1 / years) - 1) * 100,
        "dd": dd * 100,
        "sharpe": statistics.mean(rets) / sd * math.sqrt(252) if sd > 0 else 0.0,
        "worst": min(yr.values()),
        "years": yr,
    }


def sweep_s3(option_curve_params, cash):
    """S3 neighbourhood: moneyness x DTE x regime SMA x roll DTE x premium, base pricing."""
    import itertools

    data, scores = option_curve_params["data"], option_curve_params["scores"]
    vxn, irx = option_curve_params["vxn"], option_curve_params["irx"]
    put_skew, call_skew = PRICING[BASE_PRICING]
    results = []
    for m, dte, sma, roll, prem in itertools.product(
        (0.80, 0.85, 0.90), (180, 270, 365), (150, 200, 250), (30, 60, 90), (30.0, 50.0)
    ):
        if roll >= dte - 60:
            continue
        row = []
        for start, end in PERIODS.values():
            d = {s: [b for b in data[s] if b.date <= end] for s in ("QQQ", "SPY")}
            cfg = OptionSimConfig(
                initial_cash=cash,
                start_date=start,
                untradable=("SPY",),
                hedge_symbols=("QQQ",),
                risk_per_trade_pct=prem,
                div_yield=0.007,
                half_spread_pct=HALF_SPREAD_PCT,
                min_half_spread=0.01,
                put_skew_per_pct=put_skew,
                call_skew_per_pct=call_skew,
                iv_term_mean=TERM_MEAN,
                iv_term_kappa=TERM_KAPPA,
                signal_mode="index_trend",
                regime_symbol="SPY",
                regime_also=("QQQ",),
                regime_sma=sma,
                exit_on_regime_bear=True,
                strike_moneyness=m,
                target_dte=dte,
            )
            rules = OptionRules(
                max_loss_per_trade_pct=prem + 0.01,
                max_total_risk_pct=prem + 0.01,
                max_contracts=10**9,
                max_dte=400,
                daily_loss_limit_pct=100.0,
            )
            exits = OptionExitRules(stop_loss_pct=None, trail_after_pct=None, time_stop_dte=roll)
            curve = (
                OptionSimulator(
                    d, rules, exits, cfg, scores=scores, iv_overrides=vxn, rates_pct=irx
                )
                .run()
                .equity_curve
            )
            row.append(stats(curve))
        results.append(((m, dte, sma, roll, prem), row))
    out = [
        "## LEAPS parameter neighbourhood, SPY and QQQ > SMA (base pricing)",
        "",
        "Moneyness 0.80/0.85/0.90 x DTE 180/270/365 x regime SMA 150/200/250 x roll at "
        "30/60/90 DTE, for 30% and 50% of equity in premium.",
        "",
        "| Premium | Window | Combos | CAGR min / median / max % | Median Max DD % | "
        "Median Sharpe | Combos < 0 |",
        "|---:|---|---:|---|---:|---:|---:|",
    ]
    for prem in (30.0, 50.0):
        sub = [r for k, r in results if k[4] == prem]
        for i, pname in enumerate(PERIODS):
            c = [r[i]["cagr"] for r in sub]
            out.append(
                f"| {prem:g}% | {pname} | {len(sub)} | {min(c):+.1f} / {statistics.median(c):+.1f} "
                f"/ {max(c):+.1f} | {statistics.median(r[i]['dd'] for r in sub):.0f} | "
                f"{statistics.median(r[i]['sharpe'] for r in sub):.2f} | "
                f"{sum(x < 0 for x in c)} |"
            )
    out.append("")
    return out


def combine(*curves):
    maps = [dict(c) for c in curves]
    dates = sorted(set.intersection(*(set(m) for m in maps)))
    return [(d, sum(m[d] for m in maps)) for d in dates]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument(
        "--data-dir", type=Path, required=True, help="split-adjusted OHLCV (QQQ, SPY, stocks)"
    )
    p.add_argument("--macro-dir", type=Path, required=True, help="^VIX, ^VXN, HYG (adjusted)")
    p.add_argument(
        "--adj-dir", type=Path, required=True, help="dividend-adjusted QQQ, SPY and ^IRX"
    )
    p.add_argument("--initial-cash", type=float, default=1_000_000.0)
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    p.add_argument("--sweep", action="store_true", help="add the S3 parameter-neighbourhood sweep")
    args = p.parse_args(argv)

    data = load_csv_dir(args.data_dir)
    macro = load_csv_dir(args.macro_dir)
    adj = load_csv_dir(args.adj_dir)
    stocks = sorted(s for s in data if s not in ETF_SYMBOLS)
    scores = {
        d: m.score
        for d, m in market_scores(
            {**{s: data[s] for s in stocks}, "SPY": data["SPY"]},
            "SPY",
            vix=macro.get("^VIX"),
            credit=macro.get("HYG"),
            breadth_symbols=stocks,
        ).items()
    }
    # VXN starts 2001-01-23; before that use VIX x 1.86 (the VXN/VIX ratio in 2001-2003,
    # conservative for 2000: the overall median ratio is 1.21).
    vxn_raw = {b.date: b.close for b in macro["^VXN"]}
    vix_raw = {b.date: b.close for b in macro.get("^VIX", [])}
    vxn = {"QQQ": {**{d: v * 1.86 for d, v in vix_raw.items()}, **vxn_raw}}
    irx = {b.date: b.close for b in adj["^IRX"]}
    two_x = synthetic_leveraged(adj["QQQ"], 2.0, irx, expense_pct=1.43)  # calibrated to QLD
    three_x = synthetic_leveraged(adj["QQQ"], 3.0, irx, expense_pct=2.53)  # calibrated to TQQQ

    def option_curve(
        name, start, end, cash, pricing=BASE_PRICING, half_spread=HALF_SPREAD_PCT, term=True
    ):
        overrides, exits, risk = OPTION_STRATEGIES[name]
        put_skew, call_skew = PRICING[pricing]
        d = {s: [b for b in data[s] if b.date <= end] for s in ("QQQ", "SPY")}
        cfg = OptionSimConfig(
            initial_cash=cash,
            start_date=start,
            untradable=("SPY",),
            hedge_symbols=("QQQ",),
            risk_per_trade_pct=risk,
            div_yield=0.007,
            half_spread_pct=half_spread,
            min_half_spread=0.01,
            put_skew_per_pct=put_skew,
            call_skew_per_pct=call_skew,
            iv_term_mean=TERM_MEAN if term else None,
            iv_term_kappa=TERM_KAPPA,
            **overrides,
        )
        rules = OptionRules(
            max_loss_per_trade_pct=risk + 0.01,
            max_total_risk_pct=risk + 0.01,
            max_contracts=10**9,
            max_dte=400,
            daily_loss_limit_pct=100.0,
        )
        res = OptionSimulator(
            d, rules, exits, cfg, scores=scores, iv_overrides=vxn, rates_pct=irx
        ).run()
        return res.equity_curve, res

    lines = [
        "# Aggressive QQQ Option Strategies, 2001-2026",
        "",
        "All option strategies trade QQQ only and are priced off the actual VXN, the actual "
        "3-month T-bill rate (^IRX) and a 0.7% dividend yield, with a strike-based skew "
        f"('{BASE_PRICING}': +0.75 vol point per 1% below spot, -0.25 per 1% above, for 30-day "
        "options, scaled by sqrt(30/days)), a term structure (30-day VXN mean-reverting to "
        f"{TERM_MEAN:.0%} at kappa {TERM_KAPPA:g}/yr for longer expiries) and a "
        f"{HALF_SPREAD_PCT}% half bid-ask per leg. Later tables vary skew and costs. Strategy "
        "parameters were fixed before the first run; skew, rates, dividends and costs were "
        "corrected afterwards (see the strategy document). "
        "Exits: S1/S2 -50% premium stop, trailing after +50%, 5 DTE; "
        "S3 regime exit (SPY < 200d) and roll at 30 DTE; S4 take profit at 50% of credit, stop "
        "at 2x credit, close at 7 DTE or when SPY < 200d.",
        "",
    ]
    yearly_all = {}
    for pname, (start, end) in PERIODS.items():
        rows = []
        # benchmarks
        qqq = rotation_curve(adj["QQQ"], None, start, end)
        rows.append(("QQQ buy & hold", stats(qqq), "–"))
        rows.append(
            ("2x QQQ buy & hold (QLD-like)", stats(rotation_curve(two_x, None, start, end)), "–")
        )
        lev = rotation_curve(two_x, adj["SPY"], start, end, sma=200)
        rows.append(("2x QQQ while SPY > 200d", stats(lev), "–"))
        lev3 = rotation_curve(three_x, adj["SPY"], start, end, sma=200)
        rows.append(("3x QQQ while SPY > 200d", stats(lev3), "–"))
        both = rotation_curve(two_x, adj["SPY"], start, end, sma=200, regime_also=[adj["QQQ"]])
        rows.append(("2x QQQ while SPY and QQQ > 200d", stats(both), "–"))
        curves = {}
        for name in OPTION_STRATEGIES:
            curve, res = option_curve(name, start, end, args.initial_cash)
            curves[name] = curve
            n = len(res.trades)
            wins = sum(t.pnl > 0 for t in res.trades)
            rows.append((name, stats(curve), f"{n} ({wins / n * 100:.0f}% won)" if n else "0"))
            print(".", end="", file=sys.stderr, flush=True)
        for cname, (base, w) in COMBOS.items():
            a, _ = option_curve(base, start, end, args.initial_cash * w)
            b, _ = option_curve(
                "S2 dip calls, score < 30 (5%/trade)", start, end, args.initial_cash * (1 - w)
            )
            c = combine(a, b)
            curves[cname] = c
            rows.append((cname, stats(c), "–"))
        if pname.endswith("all"):
            yearly_all = {name: s["years"] for name, s, _ in rows}
        lines += [
            f"## {pname} ({start} to {end})",
            "",
            "| Strategy | CAGR % | Max DD % | Sharpe | Worst year % | Trades |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for name, s, trades in rows:
            lines.append(
                f"| {name} | {s['cagr']:+.1f} | {s['dd']:.0f} | {s['sharpe']:.2f} | "
                f"{s['worst']:+.0f} | {trades} |"
            )
        lines.append("")
    print(file=sys.stderr)

    start, end = PERIODS["2001-2026 all"]
    lines += [
        "## Sensitivity to option pricing, 2001-2026 (CAGR % / Max DD % / Sharpe)",
        "",
        "| Strategy | " + " | ".join(PRICING) + " | base skew, flat term structure |",
        "|---|" + "---|" * (len(PRICING) + 1),
    ]
    for name in OPTION_STRATEGIES:
        cells = []
        for pricing in PRICING:
            st = stats(option_curve(name, start, end, args.initial_cash, pricing)[0])
            cells.append(f"{st['cagr']:+.1f} / {st['dd']:.0f} / {st['sharpe']:.2f}")
        st = stats(option_curve(name, start, end, args.initial_cash, term=False)[0])
        cells.append(f"{st['cagr']:+.1f} / {st['dd']:.0f} / {st['sharpe']:.2f}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Sensitivity to bid-ask costs, 2001-2026, base skew (CAGR % / Max DD % / Sharpe)",
        "",
        "| Strategy | " + " | ".join(f"{c}% half spread" for c in COST_SCENARIOS) + " |",
        "|---|" + "---|" * len(COST_SCENARIOS),
    ]
    for name in OPTION_STRATEGIES:
        cells = []
        for cost in COST_SCENARIOS:
            st = stats(option_curve(name, start, end, args.initial_cash, half_spread=cost)[0])
            cells.append(f"{st['cagr']:+.1f} / {st['dd']:.0f} / {st['sharpe']:.2f}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("")

    if args.sweep:
        lines += sweep_s3(
            option_curve_params=dict(data=data, scores=scores, vxn=vxn, irx=irx),
            cash=args.initial_cash,
        )

    years = sorted({y for ys in yearly_all.values() for y in ys})
    lines += ["## Return by year, 2001-2026 (%)", ""]
    lines.append("| Strategy | " + " | ".join(str(y)[2:] for y in years) + " |")
    lines.append("|---|" + "---:|" * len(years))
    for name, ys in yearly_all.items():
        lines.append(f"| {name} | " + " | ".join(f"{ys.get(y, 0):+.0f}" for y in years) + " |")
    lines += [
        "",
        "## Limits",
        "",
        "- VXN is 30-day at-the-money implied vol for the Nasdaq-100; strike skew and term "
        "structure are modelled, not observed. Real chains are needed to confirm the numbers.",
        "- Bid-ask: 0.5% of the option price per leg (min $0.01) by default; the cost table "
        "shows 1% and 2.5%. Fills at the next open after a signal at the close.",
        "- European pricing with a 0.7% dividend yield; no early assignment, no commissions.",
        "- Leveraged-ETF rows are synthetic (daily 2x/3x of dividend-adjusted QQQ minus "
        "borrowing at ^IRX and costs calibrated to QLD/TQQQ since 2010).",
    ]
    md = "\n".join(lines) + "\n"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "aggressive_research.md"
    out.write_text(md)
    print(md)
    print(f"Report: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
