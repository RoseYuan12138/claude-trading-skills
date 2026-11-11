# Aggressive Options Strategy: Research Summary and Playbook

Date: 2026-11-11. Data: Yahoo Finance daily bars, VXN (Nasdaq-100 implied vol), ^IRX (3-month
T-bill), 1999-2026. Reproduce with the commands at the end. Not investment advice.

## Bottom line

1. **The only aggressive approach that held up is leveraged trend-following:** be long QQQ with
   leverage while SPY is above its 200-day SMA, and be in cash when it is below.
2. Options can implement it: a **~15% in-the-money QQQ call with ~120 days to expiry**, rolled at
   30 days left. That gives about 1.4x QQQ exposure with 30% of the account in premium, or about
   2.3x with 50%. It earned **+10.9% a year (30%) / +15.8% (50%)** over 2001-2026, against +10.2% for
   QQQ buy & hold, and it was positive in all three sub-periods, including 2001-2010.
3. **It does not beat the ETF version.** 2x QQQ (QLD) with the same 200-day rule earned +16.4% a
   year with a smaller drawdown (50% vs 65%). Under realistic skew, the call's time value costs
   about as much as the ETF's financing and decay, or more. The option version caps the loss per
   position at the premium; it does not add return.
4. **Short-dated "lottery" option strategies did not work** once priced with real implied vol:
   ATM breakout calls (~0%/yr), put credit spreads (+1.7 to 3.8%/yr), dip calls on panic days
   (+2.2%/yr, and they lost in 2001-2010), and every put-based hedge tested earlier.
5. Expect drawdowns of **40-65%**, years like 2022 (-33% / -50%), and a weak 2021-2026 (+4.4%/yr).
   If that is not acceptable, use the 30% premium version or a smaller account share.

## What was tested

All option strategies trade **QQQ only**, so there is no stock picking and no survivorship. They
are priced off the actual VXN, the actual T-bill rate and a 0.7% dividend yield, with a
strike-based volatility skew and bid-ask costs. Windows: **2001-2010** (dot-com bust and 2008,
a stress test), **2011-2021** (out of sample for every idea in this project) and **2021-2026**
(where most ideas came from).

| Code | Strategy |
|---|---|
| S1 | ATM 35-DTE call on a 20-day breakout above the 50-day SMA, only while SPY > 50-day SMA; 5% of equity per trade |
| S2 | ATM 45-DTE call when the market score is below 30 (panic); 5% per trade |
| S3 | ~15% ITM ~120-DTE call held while SPY > 200-day SMA, rolled at 30 DTE; 30% (S3a) or 50% (S3b) of equity in premium |
| S4 | 5%-OTM, 5%-wide 35-DTE put credit spread sold while SPY > 200-day SMA; 10% or 25% max loss per trade |
| Benchmarks | QQQ buy & hold; 2x / 3x QQQ (synthetic, calibrated to QLD/TQQQ) held while SPY > 200-day SMA |

S1/S2 exits: -50% premium stop, trailing stop after +50%, close at 5 DTE. S4 exits: take profit at
50% of the credit, stop at a loss of 2x the credit, close at 7 DTE or when SPY < 200-day SMA.

## Results (CAGR % / max drawdown % / Sharpe)

Base pricing: skew +0.75 vol points per 1% below spot (30-day basis, scaled by sqrt(30/days)),
0.5% half bid-ask per leg. Full tables: [`aggressive_research_results.md`](aggressive_research_results.md).

| Strategy | 2001-2010 | 2011-2021 | 2021-2026 | **2001-2026** |
|---|---|---|---|---|
| QQQ buy & hold | -1.4 / 69 / 0.10 | +21.0 / 29 / 1.07 | +12.4 / 35 / 0.62 | +10.2 / 69 / 0.52 |
| **2x QQQ while SPY > 200d** | +5.3 / 50 / 0.33 | +30.0 / 35 / 1.03 | +11.4 / 44 / 0.49 | **+16.4 / 50 / 0.66** |
| 3x QQQ while SPY > 200d | +4.8 / 68 / 0.32 | +42.7 / 48 / 1.02 | +10.8 / 60 / 0.46 | +20.7 / 68 / 0.65 |
| **S3a ITM trend calls, 30%** | +6.0 / 44 / 0.41 | +19.0 / 30 / 0.89 | +4.4 / 40 / 0.30 | **+10.9 / 44 / 0.59** |
| **S3b ITM trend calls, 50%** | +7.7 / 65 / 0.40 | +30.4 / 45 / 0.91 | +4.4 / 58 / 0.31 | **+15.8 / 65 / 0.60** |
| S1 breakout calls | -0.8 / 24 | +1.3 / 20 | +3.1 / 13 | +0.8 / 24 / 0.13 |
| S2 dip calls | -0.9 / 40 | +4.6 / 13 | +3.3 / 18 | +2.2 / 40 / 0.31 |
| S4a put credit, 10% | +0.8 / 11 | +3.3 / 10 | +0.6 / 9 | +1.7 / 11 / 0.32 |
| S4b put credit, 25% | +1.5 / 25 | +7.8 / 25 | +0.9 / 21 | +3.8 / 25 / 0.33 |

### Robustness of S3

- **Parameter sweep** (81 combinations each for 30% and 50% premium: moneyness 0.80/0.85/0.90,
  DTE 90/120/180, regime SMA 150/200/250, roll at 20/30/45 DTE). At 30% premium, all 81 were
  positive in every window; 2001-2026 CAGR ranged from +7.7% to +15.9% (median +11.7%). At 50%,
  5 of 81 lost money in 2021-2026; the 2001-2026 median was +16.5%. The chosen parameters ranked
  in the middle, so they were not cherry-picked. The knob that matters is leverage: less in the
  money means more exposure per premium dollar.
- **Skew:** 2001-2026 CAGR was 13.3% / 10.9% / 9.2% (S3a) with no / base / steep skew. Steeper
  skew makes ITM calls dearer: an 85% strike call carries the same implied vol as the 85% put.
- **Costs:** S3a was 10.9% / 9.2% / 4.2% at 0.5% / 1% / 2.5% half bid-ask. QQQ options are very
  liquid (near-the-money spreads of a few cents), so 0.5-1% is realistic. Always use limit orders.

## Playbook for the independent agent account

**Rule (checked once a day after the close):**

| Condition | Action |
|---|---|
| SPY close >= its 200-day SMA, no position | Buy QQQ calls ~15% in the money, first monthly expiry at least 120 days out; premium = 30% of the account (50% for the more aggressive version) |
| Position with more than 30 days left, SPY still above | Hold |
| 30 days or fewer left, SPY still above | Roll: sell, then buy the new 120-day call at the same sizing |
| SPY close < its 200-day SMA | Sell everything the next morning and hold cash (T-bills) |

- **Order type:** limit at or near the mid; never market orders on options.
- **Today's ticket:** `python3 agentic-trader/scripts/strategy_today.py --fetch --equity <account $>`.
  On 2026-11-10 it said **BUY**: SPY 749.92 was above its 200-day SMA of 730.99, so the rule calls
  for QQQ 575C (about 15% ITM) expiring around 2027-03, at an estimated ~$11,900 per contract.
- **Minimum account:** one contract costs about $12,000, so with 30% premium you need roughly
  $40,000 or more to size it sensibly. Below that, the QLD version is more precise: put
  (target exposure / 2) of the account in QLD and the rest in cash.
- **Robinhood:** buying calls needs options Level 2. The live risk gate's default option rules cap
  premium at 2% per trade. This strategy needs a separate rules profile with
  `max_loss_per_trade_pct` around 30-50, and the MCP option-order tool still has to be mapped in
  `config/mcp_tool_map.yaml`.
- **Kill switch:** the strategy has historically lost 40-65% from a peak. Decide the account share
  so that a 65% drawdown on it is survivable; do not add leverage after losses.

**Not recommended** (tested and rejected): ATM breakout calls, put credit spreads, panic-dip calls
as a standalone strategy, single-stock option strategies (no real IV data; the profits disappear at
realistic pricing), put hedges and score-based call/put switching.

## Corrections made during this research

The intermediate numbers reported earlier in the conversation were superseded by these fixes:

1. **Credit-spread exit bug:** closing a losing credit spread was priced at about $0.04, so every
   trade won (Sharpe 2+). After the fix, put credit spreads came out roughly break-even.
2. **Bid-ask on spreads:** charging each deep-ITM leg separately made spreads cost more than their
   width. Spreads are now priced as a package and capped at their width.
3. **Skew by strike:** skew had been applied by option type, which underpriced ITM calls. It is now
   by strike, consistent with put-call parity.
4. **Rates and dividends:** a fixed 4% rate overpriced calls in 2009-2021. The model now uses the
   actual ^IRX rate (one-day lag) and a 0.7% dividend yield.
5. **Costs:** 2.5% bid-ask had been used for everything. It now defaults to 0.5% for QQQ, with 1%
   and 2.5% shown.

## Limits

- No historical option chains: implied vol is VXN plus a modelled skew and term structure. A
  paper-trading period that logs real Robinhood quotes against the model is the next check.
- Daily bars: decisions at the close, fills at the next open; no early assignment or commissions.
- 2x/3x benchmarks are synthetic before 2010 (tracking error vs QLD/TQQQ since 2010: about
  0.1-0.2% a day, calibrated for drift).
- History, especially 2011-2021, favoured leveraged Nasdaq exposure. A long sideways or falling
  market would hurt any version of this strategy, with or without the filter.

## Reproduce

```bash
D=data   # any folder
python3 agentic-trader/scripts/fetch_ohlcv.py --symbols QQQ SPY AAPL MSFT INTC AMZN NVDA AMD GOOGL META TSLA AVGO --start 1999-03-10 --out-dir $D/ohlcv
python3 agentic-trader/scripts/fetch_ohlcv.py --symbols ^VIX ^VXN --start 1999-01-01 --out-dir $D/macro
python3 agentic-trader/scripts/fetch_ohlcv.py --symbols HYG --adjusted --start 2007-04-01 --out-dir $D/macro
python3 agentic-trader/scripts/fetch_ohlcv.py --symbols QQQ SPY --adjusted --start 1999-03-10 --out-dir $D/adjusted
python3 agentic-trader/scripts/fetch_ohlcv.py --symbols ^IRX --start 1999-01-01 --out-dir $D/adjusted
python3 agentic-trader/scripts/run_aggressive_research.py --data-dir $D/ohlcv --macro-dir $D/macro --adj-dir $D/adjusted --sweep
```
