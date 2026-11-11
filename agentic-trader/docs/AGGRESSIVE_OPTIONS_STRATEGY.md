# Aggressive Options Strategy: Research Summary and Playbook

Date: 2026-11-11. Data: Yahoo Finance daily bars, VXN (Nasdaq-100 implied vol), ^IRX (3-month
T-bill), 1999-2026. Reproduce with the commands at the end. Not investment advice.

## Bottom line

1. **The only aggressive approach that held up is leveraged trend-following:** be long QQQ with
   leverage while SPY is above its 200-day SMA, and be in cash when it is below.
2. **Options version (recommended if you want options): LEAPS-style QQQ calls about 15% in the
   money with about 270 days to expiry, rolled at 60 days left.** Results by premium share:

   | Premium | Exposure | 2001-2026 CAGR | Max drawdown | Sharpe |
   |---:|---:|---:|---:|---:|
   | 30% of the account | ~1.1-1.4x | +10.4% | 38% | 0.63 |
   | 50% of the account | ~1.8-2.3x | +15.6% | 55% | 0.64 |

   Both were positive in every sub-period, including 2001-2010, and in all 81 neighbouring
   parameter sets. QQQ buy & hold earned +10.2% a year with a 69% drawdown.
3. **It does not beat the ETF version.** 2x QQQ (QLD) with the same rule earned +16.4% / 50% /
   0.66, or 16.4% / 45% / 0.66 with a 2% band around the SMA. The option's time value costs
   about as much as the ETF's financing and decay. Options cap the loss per position at the
   premium; they do not add return.
4. **Short-dated "lottery" option strategies did not work** once priced with real implied vol:
   ATM breakout calls (+0.4%/yr), put credit spreads (+2-5%/yr), dip calls on panic days
   (+2.7%/yr, and they lost in 2001-2010), plus the put hedges and score-switching tested
   earlier.
5. Expect drawdowns of **38-55%**, years like 2022 (-30% / -46%), and a weak 2021-2026
   (+5-6%/yr). If that is too much, use the 30% version, or allocate a smaller share of
   your money to this account.

## What was tested

All option strategies trade **QQQ only**, so there is no stock picking and no survivorship. They
are priced off the actual VXN, the actual T-bill rate (one-day lag) and a 0.7% dividend yield,
with a strike-based volatility skew, a mean-reverting implied-vol term structure and bid-ask
costs. Windows: **2001-2010** (dot-com bust and 2008, a stress test), **2011-2021** (out of sample
for every idea in this project) and **2021-2026** (where most ideas came from).

| Code | Strategy |
|---|---|
| S1 | ATM 35-DTE call on a 20-day breakout above the 50-day SMA, only while SPY > 50-day SMA; 5% of equity per trade |
| S2 | ATM 45-DTE call when the market score is below 30 (panic); 5% per trade |
| S3a/b | ~15% ITM 120-DTE call held while SPY > 200-day SMA, rolled at 30 DTE; 30% / 50% of equity in premium |
| **S3c/d** | **Same with ~270-DTE calls rolled at 60 DTE (LEAPS-style); 30% / 50%** |
| S4 | 5%-OTM, 5%-wide 35-DTE put credit spread sold while SPY > 200-day SMA; 10% or 25% max loss per trade |
| Benchmarks | QQQ buy & hold; 2x / 3x QQQ (synthetic, calibrated to QLD/TQQQ) held while SPY > 200-day SMA |

**Base pricing:** skew +0.75 vol points per 1% below spot and -0.25 per 1% above, quoted for
30-day options and scaled by sqrt(30/days). The 30-day VXN mean-reverts toward 24% at kappa 3/yr
for other expiries. Half bid-ask is 0.5% per leg. Full tables:
[`aggressive_research_results.md`](aggressive_research_results.md) and
[`trend_variants_results.md`](trend_variants_results.md).

## Results (CAGR % / max drawdown % / Sharpe)

| Strategy | 2001-2010 | 2011-2021 | 2021-2026 | **2001-2026** |
|---|---|---|---|---|
| QQQ buy & hold | -1.4 / 69 / 0.10 | +21.0 / 29 / 1.07 | +12.4 / 35 / 0.62 | +10.2 / 69 / 0.52 |
| **2x QQQ while SPY > 200d** | +5.3 / 50 / 0.33 | +30.0 / 35 / 1.03 | +11.4 / 44 / 0.49 | **+16.4 / 50 / 0.66** |
| 3x QQQ while SPY > 200d | +4.8 / 68 / 0.32 | +42.7 / 48 / 1.02 | +10.8 / 60 / 0.46 | +20.7 / 68 / 0.65 |
| S3a ITM calls 120d, 30% | +5.4 / 46 / 0.37 | +17.4 / 31 / 0.82 | +3.8 / 41 / 0.28 | +9.9 / 46 / 0.54 |
| S3b ITM calls 120d, 50% | +6.6 / 66 / 0.36 | +27.3 / 46 / 0.84 | +2.9 / 59 / 0.27 | +14.0 / 66 / 0.55 |
| **S3c LEAPS calls 270d, 30%** | +4.9 / 38 / 0.37 | +18.4 / 25 / 0.98 | +5.1 / 34 / 0.34 | **+10.4 / 38 / 0.63** |
| **S3d LEAPS calls 270d, 50%** | +6.9 / 55 / 0.39 | +29.2 / 38 / 0.99 | +6.2 / 51 / 0.35 | **+15.6 / 55 / 0.64** |
| S1 breakout calls | -0.8 / 24 | +0.4 / 22 | +2.9 / 14 | +0.4 / 24 / 0.09 |
| S2 dip calls | -0.4 / 40 | +4.8 / 13 | +4.3 / 16 | +2.7 / 40 / 0.35 |
| S4a put credit, 10% | +0.3 / 11 | +4.1 / 10 | +1.8 / 8 | +2.1 / 11 / 0.39 |

### Refinements tested (fixed in advance, with the term structure on)

| Variant | 2001-2026 |
|---|---|
| V1: SMA band +/-2% (fewer whipsaws), options 30% / 50% | 10.3 / 43 / 0.56 and 14.6 / 63 / 0.56 (small gain vs 120d base) |
| V2: size by target vol / VXN, options | 8.8-10.6 / 52-64 / 0.48: **worse**. It buys less right after selloffs, when trends restart |
| **V3: LEAPS 270d, roll at 60** | **10.4 / 38 / 0.63 and 15.6 / 55 / 0.64: better than 120d on all metrics** |
| V1+V2+V3 | 9.2-11.3 / 45-56 / 0.52: worse than V3 alone |
| ETF V5: 2x with the 2% band | 16.4 / 45 / 0.66: same return as plain 2x, smaller drawdown |
| ETF V4: 0-3x scaled to 25% target vol | 11.4 / 27-35 / 0.71: best Sharpe, much lower return |

### Robustness of the LEAPS version

- **Parameter sweep** (81 sets each at 30% and 50% premium: moneyness 0.80/0.85/0.90, DTE
  180/270/365, regime SMA 150/200/250, roll at 30/60/90 DTE). **All 162 were positive in every
  window.** 2001-2026 CAGR at 30%: +7.5% to +13.2% (median +9.8%); at 50%: +11.2% to +19.0% (median
  +14.6%). Longer expiries lower drawdowns, and the roll point barely matters.
- **Skew:** 2001-2026 CAGR for S3d was 18.5% / 15.6% / 14.0% with no / base / steep skew, and 19.6%
  with a flat term structure. ITM calls carry the IV of the same-strike puts.
- **Costs:** S3d was 15.6% / 13.4% / 7.3% at 0.5% / 1% / 2.5% half bid-ask. QQQ options are very
  liquid, so 0.5-1% is realistic for limit orders near the mid. Wide fills would destroy it.

## Playbook for the independent agent account

**Rule (checked once a day after the close):**

| Condition | Action |
|---|---|
| SPY close >= its 200-day SMA, no position | Buy QQQ calls about 15% in the money, first monthly expiry at least 270 days out; premium = 30% of the account (50% for the more aggressive version) |
| More than 60 days left, SPY still above | Hold |
| 60 days or fewer left, SPY still above | Roll: sell, then buy a new ~270-day call at the same sizing |
| SPY close < its 200-day SMA | Sell everything the next morning and hold cash (T-bills) |

- **Order type:** limit at or near the mid; never market orders on options.
- **Today's ticket:** `python3 agentic-trader/scripts/strategy_today.py --fetch --equity <account $>`.
  On 2026-11-10 it said **BUY**: SPY 749.92 was above its 200-day SMA of 730.99. For a $200,000
  account: 4 x QQQ 575C around 2027-08, at an estimated ~$13,600 each (27% of the account),
  about 1.1x exposure. The ETF equivalent is ~$109,000 in QLD, the rest in cash.
- **Minimum account:** one contract costs about $13,600, so with 30% premium you need about
  $45,000 or more to size it sensibly. Below that, the QLD version is more precise: put
  (target exposure / 2) of the account in QLD and the rest in cash.
- **Robinhood:** buying calls needs options Level 2. The live risk gate's default option rules cap
  premium at 2% per trade. This strategy needs its own rules profile with
  `max_loss_per_trade_pct` around 30-50, and the MCP option-order tool still has to be mapped in
  `config/mcp_tool_map.yaml`.
- **Kill switch:** the strategy has historically lost 38-55% from a peak. Size the account so a
  55% drawdown on it is survivable; do not add leverage after losses.

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
