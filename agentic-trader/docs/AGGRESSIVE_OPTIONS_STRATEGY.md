# Aggressive Options Strategy: Research Summary and Playbook

Date: 2026-11-11. Data: Yahoo Finance daily bars, VXN (Nasdaq-100 implied vol), ^IRX (3-month
T-bill), 1999-2026. Reproduce with the commands at the end. Not investment advice.

## Bottom line

1. **The only aggressive approach that held up is leveraged trend-following:** be long QQQ with
   leverage while the trend is up, and be in cash otherwise.
2. **Recommended options version: LEAPS-style QQQ calls about 15% in the money with about 270
   days to expiry, rolled at 60 days left, held only while both SPY and QQQ close above their
   200-day SMAs.**

   | Premium | Exposure | 2001-2026 CAGR | Max DD | Sharpe | From the 2000 peak |
   |---:|---:|---:|---:|---:|---:|
   | 30% of the account (S3e) | ~1.1-1.4x | **+11.2%** | **28%** | 0.68 | +9.0% / 43% DD |
   | 50% of the account (S3f) | ~1.8-2.3x | **+15-17%** | **41%** | 0.71 | +13.3% / 62% DD |

   Both were positive in every window. Across 162 neighbouring parameter sets times 5 windows
   (810 runs), **none lost money**. For comparison, QQQ buy & hold earned +10.2% a year
   (2001-2026) with a 69% drawdown, and 83% from the 2000 peak.
3. **Options only slightly beat the ETF version.** 2x QQQ with the same two-index filter earned
   +15.4% / 44% / 0.65, and with the SPY-only filter +16.4% / 50% / 0.66. The option version's
   main edge is the cap on the loss per position; the return advantage is small and depends on
   the pricing assumptions.
4. **Short-dated "lottery" option strategies did not work** once priced with real implied vol:
   ATM breakout calls (+0.4%/yr), put credit spreads (+2-5%/yr), dip calls on panic days
   (+2.7%/yr, and they lost in 2001-2010), plus the put hedges and score-switching tested
   earlier.
5. Expect drawdowns of **28-62%** (worst when starting at a bubble top) and losing years like
   2022 (-18% / -29%). If that is too much, use the 30% version, or put less of your money in
   this account.
6. **On 2026-11-10 the rule says CASH:** SPY (749.92) is above its 200-day SMA (730.99), but
   QQQ (674.76) is below its own (681.42). The SPY-only version would have said BUY.

## What was tested

All option strategies trade **QQQ only**, so there is no stock picking and no survivorship. They
are priced off the actual VXN, the actual T-bill rate (one-day lag) and a 0.7% dividend yield,
with a strike-based volatility skew, a mean-reverting implied-vol term structure and bid-ask
costs. Windows: **from the 2000 dot-com peak**, **2001-2010** (dot-com bust and 2008, a stress
test), **2011-2021** (out of sample for every idea in this project) and **2021-2026** (where most
ideas came from).

| Code | Strategy |
|---|---|
| S1 | ATM 35-DTE call on a 20-day breakout above the 50-day SMA, only while SPY > 50-day SMA; 5% of equity per trade |
| S2 | ATM 45-DTE call when the market score is below 30 (panic); 5% per trade |
| S3a/b | ~15% ITM 120-DTE call held while SPY > 200-day SMA, rolled at 30 DTE; 30% / 50% of equity in premium |
| S3c/d | Same with ~270-DTE calls rolled at 60 DTE (LEAPS-style); 30% / 50% |
| **S3e/f** | **S3c/d, but only while SPY and QQQ are both above their 200-day SMAs** (recommended) |
| S4 | 5%-OTM, 5%-wide 35-DTE put credit spread sold while SPY > 200-day SMA; 10% or 25% max loss per trade |
| Benchmarks | QQQ buy & hold; 2x / 3x QQQ (synthetic, calibrated to QLD/TQQQ) held while SPY > 200-day SMA |

**Base pricing:** skew +0.75 vol points per 1% below spot and -0.25 per 1% above, quoted for
30-day options and scaled by sqrt(30/days). The 30-day VXN mean-reverts toward 24% at kappa 3/yr
for other expiries. Half bid-ask is 0.5% per leg. Full tables:
[`aggressive_research_results.md`](aggressive_research_results.md) and
[`trend_variants_results.md`](trend_variants_results.md).

## Results (CAGR % / max drawdown % / Sharpe)

| Strategy | From 2000 peak | 2001-2010 | 2011-2021 | 2021-2026 | **2001-2026** |
|---|---|---|---|---|---|
| QQQ buy & hold | +8.3 / 83 | -1.4 / 69 | +21.0 / 29 | +12.4 / 35 | +10.2 / 69 / 0.52 |
| 2x QQQ while SPY > 200d | +10.2 / 86 | +5.3 / 50 | +30.0 / 35 | +11.4 / 44 | +16.4 / 50 / 0.66 |
| 2x QQQ while SPY and QQQ > 200d | +10.3 / 78 | +6.7 / 44 | +25.3 / 35 | +12.2 / 40 | +15.4 / 44 / 0.65 |
| 3x QQQ while SPY > 200d | +10.0 / 96 | +4.8 / 68 | +42.7 / 48 | +10.8 / 60 | +20.7 / 68 / 0.65 |
| S3c LEAPS 30%, SPY filter | +8.2 / 50 | +4.9 / 38 | +18.4 / 25 | +5.1 / 34 | +10.4 / 38 / 0.63 |
| S3d LEAPS 50%, SPY filter | +11.6 / 72 | +6.9 / 55 | +29.2 / 38 | +6.2 / 51 | +15.6 / 55 / 0.64 |
| **S3e LEAPS 30%, SPY and QQQ** | +9.0 / 43 | +7.2 / 28 | +15.7 / 26 | +8.5 / 24 | **+11.2 / 28 / 0.68** |
| **S3f LEAPS 50%, SPY and QQQ** | +13.3 / 62 | +11.1 / 41 | +24.7 / 40 | +12.6 / 38 | **+17.2 / 41 / 0.71** |
| S3b ITM calls 120d, 50% | – | +6.6 / 66 | +27.3 / 46 | +2.9 / 59 | +14.0 / 66 / 0.55 |
| S1 breakout calls | – | -0.8 / 24 | +0.4 / 22 | +2.9 / 14 | +0.4 / 24 / 0.09 |
| S2 dip calls | – | -0.4 / 40 | +4.8 / 13 | +4.3 / 16 | +2.7 / 40 / 0.35 |
| S4a put credit, 10% | – | +0.3 / 11 | +4.1 / 10 | +1.8 / 8 | +2.1 / 11 / 0.39 |

Before VXN existed (2000), QQQ options are priced at VIX x 1.86, the 2001-2003 VXN/VIX ratio.
That is conservative: the overall median ratio is 1.21.

### Refinements tested (fixed in advance, with the term structure on)

| Variant | 2001-2026 |
|---|---|
| V1: SMA band +/-2% (fewer whipsaws), options 30% / 50% | 10.3 / 43 / 0.56 and 14.6 / 63 / 0.56 (small gain vs 120d base) |
| V2: size by target vol / VXN, options | 8.8-10.6 / 52-64 / 0.48: **worse**. It buys less right after selloffs, when trends restart |
| **V3: LEAPS 270d, roll at 60** | **10.4 / 38 / 0.63 and 15.6 / 55 / 0.64: better than 120d on all metrics** |
| V1+V2+V3 | 9.2-11.3 / 45-56 / 0.52: worse than V3 alone |
| ETF V5: 2x with the 2% band | 16.4 / 45 / 0.66: same return as plain 2x, smaller drawdown |
| ETF V4: 0-3x scaled to 25% target vol | 11.4 / 27-35 / 0.71: best Sharpe, much lower return |
| **Two-index filter (SPY and QQQ > 200d)**, LEAPS 30% / 50% | **11.2 / 28 / 0.68 and 17.2 / 41 / 0.71** |

The two-index filter was added **after** a stress test showed the SPY-only filter failed at the
dot-com top. SPY stayed above its 200-day SMA until autumn 2000 while QQQ crashed from March, and
the 50% version lost 54% in 2000. Because the idea was not pre-registered, it was checked across
the whole neighbourhood. It beat the SPY-only filter on Sharpe in 152 of 162 parameter sets
(2001-2026) and in all 162 for 2001-2010, but in only 14 of 162 for 2011-2021: the stricter filter
is invested less, which costs return in strong bull markets. Its main benefit is a smaller
drawdown: the median max drawdown fell from 46% to 39%.

### Robustness of the recommended version (LEAPS + two-index filter)

- **Parameter sweep** (81 sets each at 30% and 50% premium: moneyness 0.80/0.85/0.90, DTE
  180/270/365, SMA 150/200/250, roll at 30/60/90 DTE), over 5 windows including from the 2000
  peak: **no run lost money.** 2001-2026 CAGR at 30%: +7.5% to +14.0% (median +10.1%, median
  drawdown 32%); at 50%: +11.4% to +20.7% (median +15.1%, median drawdown 47%).
- **Skew:** S3f 2001-2026 CAGR was 19.7% / 17.2% / 15.8% with no / base / steep skew, and 21.1%
  with a flat term structure.
- **Costs:** S3f was 17.2% / 15.0% / 8.7% at 0.5% / 1% / 2.5% half bid-ask. Limit orders near the
  mid are essential.
- **Another index:** the same LEAPS rule on SPY (priced off VIX, SPY filter) earned +7.8% / 31% DD
  (30%) and +11.8% / 46% DD (50%), against SPY buy & hold at +8.7% / 55% DD. So the effect is not
  QQQ-only, but it is weaker on SPY.

## Playbook for the independent agent account

**Rule (checked once a day after the close):**

| Condition | Action |
|---|---|
| SPY **and** QQQ close above their 200-day SMAs, no position | Buy QQQ calls about 15% in the money, first monthly expiry at least 270 days out; premium = 30% of the account (50% for the more aggressive version) |
| More than 60 days left, both still above | Hold |
| 60 days or fewer left, both still above | Roll: sell, then buy a new ~270-day call at the same sizing |
| SPY **or** QQQ closes below its 200-day SMA | Sell everything the next morning and hold cash (T-bills) |

- **Order type:** limit at or near the mid; never market orders on options.
- **Today's ticket:** `python3 agentic-trader/scripts/strategy_today.py --fetch --equity <account $>`.
  On 2026-11-10 it said **CASH**: SPY 749.92 was above its 200-day SMA (730.99), but QQQ 674.76
  was below its own (681.42). When both are above, a $200,000 account at today's prices would buy
  about 4 x QQQ 575C expiring around 2027-08, at an estimated ~$13,600 each (27% of the account),
  for about 1.1x exposure.
- **Minimum account:** one contract costs about $13,600, so with 30% premium you need about
  $45,000 or more to size it sensibly. Below that, the QLD version is more precise: put
  (target exposure / 2) of the account in QLD and the rest in cash.
- **Robinhood:** buying calls needs options Level 2. The live risk gate's default option rules cap
  premium at 2% per trade. This strategy needs its own rules profile with
  `max_loss_per_trade_pct` around 30-50, and the MCP option-order tool still has to be mapped in
  `config/mcp_tool_map.yaml`.
- **Kill switch:** the strategy has historically lost 28-62% from a peak. Size the account so a
  60% drawdown on it is survivable; do not add leverage after losses.

**Not recommended** (tested and rejected): ATM breakout calls, put credit spreads, panic-dip calls
as a standalone strategy, volatility-targeted option sizing, single-stock option strategies (no
real IV data; the profits disappear at realistic pricing), put hedges and score-based
call/put switching.

## Corrections made during this research

The intermediate numbers reported earlier in the conversation were superseded by these fixes:

1. **Credit-spread exit bug:** closing a losing credit spread was priced at about $0.04, so every
   trade won (Sharpe 2+). After the fix, put credit spreads came out at a few percent a year.
2. **Bid-ask on spreads:** charging each deep-ITM leg separately made spreads cost more than their
   width. Spreads are now priced as a package and capped at their width.
3. **Skew by strike:** skew had been applied by option type, which underpriced ITM calls. It is now
   by strike, consistent with put-call parity.
4. **Rates and dividends:** a fixed 4% rate overpriced calls in 2009-2021. The model now uses the
   actual ^IRX rate (one-day lag) and a 0.7% dividend yield.
5. **Costs:** 2.5% bid-ask had been used for everything. It now defaults to 0.5% for QQQ, with 1%
   and 2.5% shown.
6. **Term structure:** pricing every expiry at 30-day VXN made LEAPS too cheap in calm markets.
   Longer expiries now mean-revert toward a 24% long-run IV, which cut the LEAPS result from 19.6%
   to 15.6% a year (S3d).

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
python3 agentic-trader/scripts/run_trend_variants.py --data-dir $D/ohlcv --macro-dir $D/macro --adj-dir $D/adjusted --iv-term-mean 0.24
```
