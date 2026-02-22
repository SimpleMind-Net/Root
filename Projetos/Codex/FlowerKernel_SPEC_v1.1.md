# SPEC — OLS Trend + Flower v5 | Live Screening System
**Version**: 1.1
**Status**: CONFIRMED — all decisions resolved including 5 new proposals
**Target environment**: Google Colab (CPU runtime, Python 3.10+)
**Operating mode**: LIVE — batch-pipelined, incremental-cached, periodic 4H execution
**Language**: Python / NumPy-first; pandas only at I/O + cache boundary

---

## REVISION LOG vs. v1.0

| § | Change | Decision | Rationale summary |
|---|--------|----------|-------------------|
| §0 | Added decisions C8–C12 | Confirmed | 5 new proposals all adopted (with modifications noted) |
| §1 | Removed `FLOWER_USE_HMA`, `FLOWER_HMA_MUL` | C8 | HMA eliminated per user; quad-EMA only |
| §1 | Replaced `KERNEL_*` params with `LINREG_*` | C9 | OLS replaces Gaussian kernel entirely (see §A) |
| §1 | Added `TREND_PREFILTER_*` params | C9+C10 | Enables early discard before expensive features |
| §1 | Added `CACHE_*` params and `DRIVE_*` params | C11 | Google Drive incremental cache |
| §1 | Added `FETCH_BATCH_SIZE` | C10 | Batch-pipeline fetch architecture |
| §2 | Layer map updated: new Layer 0.5 (cache), new Phase 1 / Phase 2 execution model | C10+C11 | Pipeline separation |
| §5.2 | Gaussian kernel computation → OLS linear regression | C9 | See §A for full analysis |
| §5.3 | HMA branch removed from Flower — quad-EMA only | C8 | Simplified, no conditional path |
| §5.1 | Parallelization redesigned: ThreadPool fetch → inline OLS filter → loky features | C10 | Pipeline overlap |
| New §A | Analysis: OLS vs Gaussian Kernel (why OLS wins) | — | Required decision record |
| New §B | Google Drive cache architecture | C11 | Required for incremental fetch |

---

## SECTION A — DECISION ANALYSIS: OLS LINEAR REGRESSION vs. GAUSSIAN KERNEL

*This section documents the reasoning behind replacing the Gaussian kernel with OLS linear regression. It is a permanent record, not implementation code.*

### A.1 What each method measures

| Property | Gaussian Kernel | OLS Linear Regression |
|----------|-----------------|-----------------------|
| **Measurement type** | Local smoothed estimate → local derivative | Global best-fit trend over full window |
| **Output for direction** | `kernel_slope` = derivative at last bar | `beta` = single slope coefficient for all N bars |
| **Complexity** | O(N²) — weight matrix computation | O(N) — closed-form via covariance |
| **For N=250 bars** | 250×250 float32 = 250KB + matmul | 5 scalar operations |
| **Threshold interpretability** | Dimensioned in price/bar, scale-dependent | `beta_pct = beta / mean(P)` is scale-free (% per bar) |
| **Trend quality metric** | None inherent | R² = fraction of variance explained by linear trend |
| **Lag behavior** | Controllable via bandwidth — local-weighted, minimal lag at last bar | No lag concept — fits all bars equally; recent vs. old bars have equal weight |
| **Noise sensitivity at edge** | Sparse kernel support at ends — mitigated by `kernel_valid` flag | Not an issue — OLS distributes error globally |

### A.2 What "equivalent slope" would mean for the kernel

If one wanted to keep the kernel and compute a single slope metric comparable to OLS beta, the only defensible option is:

$$\text{kernel\_slope\_mean} = \frac{\hat{P}_{N-1} - \hat{P}_0}{N-1}$$

This is literally the linear slope between the first and last kernel estimates — which approximates what OLS computes directly, but with added computation cost of the kernel itself. There is no meaningful gain.

Alternatively: the kernel derivative at the last bar (`kernel_est[-1] - kernel_est[-2]`) measures **instantaneous velocity**, not **trend direction**. A ticker that briefly turned upward after a long downtrend would have high instantaneous velocity but a negative OLS slope. For pre-filtering ("is this an uptrending asset?"), instantaneous velocity is the wrong metric. OLS global slope is correct.

### A.3 Conclusion

**The Gaussian kernel is replaced by OLS linear regression.** Reasons, in order of importance:

1. **OLS serves the use case better.** Pre-filtering requires a global trend measure over the full window, not a local derivative. OLS provides this directly.

2. **Critical performance gain in the batch pipeline.** OLS computation (~1µs per ticker) can be done inline within the fetch thread immediately after data arrives — no separate process needed. Kernel computation (~5ms per ticker for N=250) cannot be done inline without introducing latency into the fetch pipeline.

3. **R² as a new signal quality gate.** OLS provides R² at zero additional cost. A ticker with beta_pct > threshold but R² < 0.25 is one with an erratic, noisy upward drift — exactly the kind that should be excluded. The kernel offers no equivalent quality measure without additional computation.

4. **Normalized slope enables meaningful cross-ticker thresholds.** `beta_pct = beta / mean(P) × 100` is in `% per 4H bar` units, making a single `LINREG_SLOPE_THRESHOLD` applicable to both a $5 ADR and a $400 stock. The raw price-unit slope of the kernel requires per-ticker threshold calibration or post-hoc normalization.

5. **Code simplification.** The kernel's `kernel_valid` edge correction, `KERNEL_SOURCE` selection, `KERNEL_BANDWIDTH`, `KERNEL_SLOPE_SMOOTH`, and `KERNEL_SLOPE_THRESH` parameters all disappear. The CONFIG section shrinks by 5 parameters, replaced by 4 cleaner ones.

**One capability lost**: the kernel's local smoothing was visually appealing for detecting recent trend changes earlier than OLS (whose slope reacts more slowly to new bars due to equal weighting). For the signal use case in Layer 4, the Flower oscillator's own `UP > DOWN` flag handles this role. The kernel/OLS is only needed for the pre-filter phase.

---

## SECTION B — GOOGLE DRIVE CACHE ARCHITECTURE

### B.1 Problem Statement

| Constraint | Impact |
|------------|--------|
| yfinance 1min data: max 7–8 days lookback | Fresh fetch on each run loses historical depth |
| yfinance 4H data: unlimited lookback but slow for large N | Re-fetching 250+ bars per ticker per cycle is wasteful |
| Colab kernel resets: in-memory data lost between sessions | Every restart = full re-fetch from scratch |
| Fetch is I/O bound: ~150–300ms per ticker per interval | 100 tickers × 2 intervals = 30–60s fetch time per cycle |

### B.2 Cache Benefits

1. **Incremental 4H fetch**: instead of 250 bars (~100ms/ticker), fetch only new bars since last run (~30ms/ticker). At 4H intervals, there is typically 1 new bar per cycle. Speedup: ~3×.

2. **1min history accumulation**: after 4 weeks of cached runs, you have 20+ days of 1min data instead of the yfinance 7-day hard limit. This materially improves Hurst and skew estimation quality over time.

3. **Session persistence**: cache survives Colab kernel restarts, RAM upgrades, and VM preemptions. The system resumes from the last cached state with zero re-fetch cost beyond the new bars.

4. **Automatic pruning**: cache never grows unbounded — only the window required by the largest parameter is kept.

### B.3 Cache Directory Structure

```
DRIVE_CACHE_DIR/                           (default: /content/drive/MyDrive/flower_cache/)
├── _meta.json                             # global metadata dict: {ticker: {interval: last_utc}}
├── _config_hash.txt                       # SHA256 of CONFIG — if changed, full re-fetch triggered
├── PBR_4h.parquet                         # 4H OHLCV for PBR, float32/64 dtypes preserved
├── PBR_1m.parquet                         # 1min OHLCV for PBR
├── VALE_4h.parquet
├── VALE_1m.parquet
└── ...
```

**File format**: Parquet (via `pandas.to_parquet` with `engine="fastparquet"` or `engine="pyarrow"`).
- Preserves dtypes (float32, float64, DatetimeIndex with UTC timezone)
- ~5–10× smaller than CSV
- Fast columnar read (only needed columns loaded)
- Supports append via read → concat → write (no in-place append, but fast enough)

### B.4 Max Cache Window Computation (auto-derived from CONFIG)

The pruning cutoff is computed once at startup from CONFIG parameters:

```
MAX_CACHE_BARS_4H = ceil(
    max(LINREG_BARS, OU_CALIB_BARS, HMM_TRAIN_BARS, HURST_WIN_4H, CVD_NORM_WINDOW)
    × CACHE_SAFETY_FACTOR
)
# Example: max(250, 120, 200, 100, 60) = 250 × 1.5 = 375 bars 4H ≈ 62 trading days

MAX_CACHE_BARS_1MIN = ceil(
    max(HURST_WIN_1MIN, SKEW_WINDOW_1MIN, MIN_BARS_1MIN)
    × CACHE_SAFETY_FACTOR
)
# Example: max(500, 500, 200) = 500 × 1.5 = 750 bars 1min ≈ 1.9 trading days
```

`CACHE_SAFETY_FACTOR = 1.5` is CONFIG-adjustable. It provides buffer for weekends, holiday gaps, and minor data losses during merge.

### B.5 Cache Invalidation Rules

| Trigger | Action |
|---------|--------|
| CONFIG changed (detected via SHA256 hash diff) | Full re-fetch for all tickers; rebuild cache |
| Ticker added to `TICKERS` | Full re-fetch for new ticker only |
| Ticker removed from `TICKERS` | Corresponding parquet files are **not** deleted automatically (user must manually clean); they are simply ignored |
| Parquet file corrupted (read exception) | Delete file, full re-fetch for that ticker; emit WARNING |
| Cache file timestamp > `CACHE_MAX_AGE_DAYS` stale | Full re-fetch; treat as cold start |
| `FORCE_FULL_FETCH = True` in CONFIG | Override all cache; full re-fetch for all tickers |

### B.6 Incremental Merge Algorithm

```
load_or_fetch(ticker, interval, max_bars):

    cache_file = DRIVE_CACHE_DIR / f"{ticker}_{interval}.parquet"

    ── Cold start (no cache) ──────────────────────────────────────────
    if not cache_file.exists():
        period = bars_to_yfinance_period(max_bars, interval)
        df = yf.download(ticker, period=period, interval=interval,
                          repair=True, auto_adjust=True, prepost=False)
        df = qc_clean(df)                   # type enforcement + forward-fill
        df = df.iloc[-max_bars:]            # prune to max window
        df.to_parquet(cache_file)
        update_meta(ticker, interval, df.index[-1])
        return df

    ── Incremental fetch ──────────────────────────────────────────────
    cached = pd.read_parquet(cache_file)
    last_ts = cached.index[-1]              # UTC timestamp of last cached bar

    # Fetch only new data since last cached bar
    # Use start= for 4H (unlimited lookback); for 1min use period="2d" (yfinance constraint)
    if interval == "1m":
        new = yf.download(ticker, period="2d", interval="1m",
                           repair=True, auto_adjust=True, prepost=False)
    else:
        new = yf.download(ticker, start=last_ts, interval=interval,
                           repair=True, auto_adjust=True, prepost=False)

    if new is not None and len(new) > 0:
        # Merge: concat + dedup by timestamp (keep latest version of any bar)
        combined = pd.concat([cached, new])
        combined = combined[~combined.index.duplicated(keep='last')]
        combined = combined.sort_index()
    else:
        combined = cached                   # no new data (e.g., market closed)

    # Prune: keep only max_bars most recent bars
    combined = combined.iloc[-max_bars:]

    # Persist updated cache
    combined.to_parquet(cache_file)
    update_meta(ticker, interval, combined.index[-1])

    return combined
```

**Critical note on 1min incremental fetch**: yfinance enforces a hard 7-day lookback for 1min data regardless of `start=`. The incremental fetch using `period="2d"` works as long as the cache is less than 7 days stale. Since the system runs every 4H, the cache will always be fresh. If the Colab session is abandoned for >7 days, the 1min cache becomes a "cold start" for new bars but **existing cached history is preserved** — the merge simply appends the fresh 2-day window to the existing history.

---

## 1. CONFIG SECTION (v1.1 — user-editable zone)

```python
# ═══════════════════════════════════════════════════════════════
#  USER CONFIG — edit only this section
# ═══════════════════════════════════════════════════════════════

# ── 1. Asset Universe ────────────────────────────────────────────────────────
TICKERS: list[str] = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA",
    "PBR",      "VALE",     "ITUB",     "BBD",
    "A1LB34.SA", "ALB",
]

# ── 2. B3 ↔ US Parity Map ───────────────────────────────────────────────────
# Format: { 'TICKER_B3': ('TICKER_US', None) }
# PARITY_FACTOR (the None) is computed at runtime — never hardcode it.
PARITY: dict[str, tuple[str, None]] = {
    "PETR4.SA":  ("PBR",  None),
    "VALE3.SA":  ("VALE", None),
    "ITUB4.SA":  ("ITUB", None),
    "BBDC4.SA":  ("BBD",  None),
    "A1LB34.SA": ("ALB",  None),
}

# ── 3. FX Source ─────────────────────────────────────────────────────────────
FX_TICKER: str = "BRL=X"

# ── 4. Trend Pre-Filter (OLS Linear Regression on 4H) ───────────────────────
# Phase 1 filter: tickers not meeting BOTH thresholds are discarded before
# any expensive feature computation (Hurst, OU, HMM, CVD, etc.)
#
# LINREG_BARS: window length for OLS fit (bars of 4H data)
#   250 bars × 4H = ~62 trading days ≈ 3 months
#   Increase for smoother (slower) trend detection; decrease for responsiveness.
LINREG_BARS             : int   = 250

# LINREG_SLOPE_THRESHOLD: minimum normalized slope to pass filter
#   Units: % of mean(close) per 4H bar
#   Example: 0.02 means price must be rising ≥ 0.02% per 4H bar on the OLS fit
#            ≈ 0.12%/day ≈ 0.6%/week ≈ 2.4%/month (compounded)
#   Set to 0.0 to disable slope filter (only R² filters)
LINREG_SLOPE_THRESHOLD  : float = 0.02

# LINREG_R2_THRESHOLD: minimum R² for the OLS fit to pass filter
#   R² < 0.25 → noisy, erratic — high slope may be artifact of a single spike
#   R² > 0.50 → clean, consistent trend
#   Set to 0.0 to disable R² filter (only slope filters)
LINREG_R2_THRESHOLD     : float = 0.25

# LINREG_SOURCE: price series used for regression
LINREG_SOURCE           : str   = "close"   # "close" | "hlc3" | "ohlc4"

# ── 5. Flower Oscillator Parameters (1min) ───────────────────────────────────
# Smoothing: original AFL quad-EMA only — no HMA option
FLOWER_N           : int   = 5       # base EMA period (all 4 EMA passes use this)
FLOWER_OB          : float = 200.0   # overbought threshold
FLOWER_OS          : float = -200.0  # oversold threshold
FLOWER_VOL_SMA     : int   = 20      # volume SMA length for volume filter
FLOWER_VOL_THRESH  : float = 1.2     # volume ≥ SMA × this to confirm buy signal
FLOWER_PIVOT_LEGS  : int   = 5       # bars each side for pivot detection
FLOWER_VWAP_MUL    : float = 1.5     # VWAP band StDev multiplier

# ── 6. Score Weights ─────────────────────────────────────────────────────────
# Note: Linear regression slope / R² are NOT score components — they are
# hard pre-filters. Tickers that pass pre-filtering are scored on these 6 dims.
W_OU_FPT    : float = 0.25   # OU first passage time probability
W_HURST     : float = 0.20   # Hurst dual-scale divergence (H_4H − H_1min)
W_HMM       : float = 0.18   # HMM volatility regime transition probability
W_SKEW      : float = 0.12   # realized return skewness (1min)
W_LIQUIDITY : float = 0.10   # liquidity score (volume + spread)
W_CVD       : float = 0.15   # tick-rule CVD signal (4H)

# ── 7. Data Quality Thresholds ───────────────────────────────────────────────
MAX_NAN_FRACTION   : float = 0.05
MIN_BARS_4H        : int   = 60
MIN_BARS_1MIN      : int   = 200
MIN_VOL_DAILY_USD  : float = 1e6
MAX_SPREAD_PROXY   : float = 0.015
ZERO_VOL_MAX_FRAC  : float = 0.02

# ── 8. OU First Passage Time ─────────────────────────────────────────────────
OU_CALIB_BARS      : int   = 120     # 4H bars for OU parameter estimation
OU_FPT_HORIZON     : int   = 100     # 1min bars for FPT horizon (~1.7H intraday)

# ── 9. Hurst ─────────────────────────────────────────────────────────────────
HURST_METHOD       : str   = "dfa"   # "dfa" | "rs"
HURST_WIN_4H       : int   = 100
HURST_WIN_1MIN     : int   = 500

# ── 10. HMM ──────────────────────────────────────────────────────────────────
HMM_TRAIN_BARS     : int   = 200     # 4H bars for HMM training

# ── 11. CVD (tick-rule, 4H) ──────────────────────────────────────────────────
CVD_WINDOW         : int   = 30      # 4H bars for CVD accumulation
CVD_NORM_WINDOW    : int   = 60      # 4H bars for CVD z-score normalization

# ── 12. Signal Parameters ────────────────────────────────────────────────────
ENTRY_MIN_SCORE    : float = 0.60    # min composite score for entry signal
ENTRY_FLOWER_LEVEL : float = -200.0  # Flower UP ≤ this at entry
REENTRY_COOLDOWN   : int   = 60      # 1min bars cooldown after exit
MAX_HOLD_BARS      : int   = 7200    # 1min bars max hold ≈ 5 trading days

# ── 13. Live Execution ───────────────────────────────────────────────────────
RUN_INTERVAL_HOURS : int   = 4
SCORE_NORM_METHOD  : str   = "rank"  # "rank" | "zscore" | "minmax"
FETCH_BATCH_SIZE   : int   = 10      # tickers per fetch batch (pipeline tuning)
                                     # increase if network is fast; decrease if timeouts occur

# ── 14. Google Drive Cache ───────────────────────────────────────────────────
DRIVE_CACHE_ENABLED : bool  = True
DRIVE_CACHE_DIR     : str   = "/content/drive/MyDrive/flower_cache"
CACHE_SAFETY_FACTOR : float = 1.5    # max_bars kept = max_required × this factor
CACHE_MAX_AGE_DAYS  : int   = 30     # if cache file is older than this → full re-fetch
FORCE_FULL_FETCH    : bool  = False  # True = ignore cache, full re-fetch this cycle only
                                     # (resets to False automatically after one cycle)

# ═══════════════════════════════════════════════════════════════
#  END USER CONFIG
# ═══════════════════════════════════════════════════════════════
```

---

## 2. SYSTEM ARCHITECTURE (v1.1)

### 2.1 Layer Map

```
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 0 — Config validation & universe resolution                    │
│    - Weight sum validation, type assertions, PARITY consistency       │
│    - Resolve TICKERS → canonical_tickers (frozenset, deduped)         │
│    - Compute PARITY_FACTOR per pair                                   │
│    - Compute MAX_CACHE_BARS_4H and MAX_CACHE_BARS_1MIN from CONFIG    │
│    - Compute and compare CONFIG hash → cache invalidation if changed  │
├──────────────────────────────────────────────────────────────────────┤
│  LAYER 0.5 — Google Drive Cache Manager                               │
│    - Mount Drive (if DRIVE_CACHE_ENABLED)                             │
│    - Initialize cache directory + _meta.json if missing               │
│    - Per ticker: check cache freshness, flag cold-start vs incremental│
├──────────────────────────────────────────────────────────────────────┤
│  LAYER 1 — Two-Phase Data Acquisition & Pre-filter                    │
│                                                                       │
│   PHASE 1 [I/O + lightweight CPU, batched, pipelined]:                │
│    - ThreadPoolExecutor: fetch batches of FETCH_BATCH_SIZE tickers    │
│    - Per ticker as fetch completes:                                   │
│        → Cache merge (load parquet + append new bars + prune + save)  │
│        → QC hard checks (reject immediately if fail)                  │
│        → OLS slope + R² on 4H close  [~1µs, inline on fetch thread]  │
│        → If slope < THRESHOLD or R² < THRESHOLD → DISCARD             │
│        → Else → enqueue for Phase 2                                   │
│                                                                       │
│   PHASE 2 [CPU-bound, joblib loky, only passing tickers]:             │
│    - QC soft checks + type enforcement → float32 arrays               │
│    - Full feature computation (Hurst, OU, HMM, Skew, CVD, Liq)       │
│                                                                       │
├──────────────────────────────────────────────────────────────────────┤
│  LAYER 2 — Feature Computation (Phase 2, per passing ticker)          │
│    2a. OLS slope + R² — already computed in Phase 1, reused here     │
│    2b. Flower oscillator v5 — quad-EMA only (1min)                   │
│    2c. Hurst exponent DFA (4H + 1min)                                 │
│    2d. OU calibration + first passage time (Flower UP series)         │
│    2e. HMM 2-state volatility regime (4H)                            │
│    2f. Realized skewness (1min)                                       │
│    2g. CVD tick-rule (4H)                                             │
│    2h. Liquidity score (4H volume + spread)                           │
├──────────────────────────────────────────────────────────────────────┤
│  LAYER 3 — Composite Score Engine                                     │
│    (unchanged from v1.0)                                             │
├──────────────────────────────────────────────────────────────────────┤
│  LAYER 4 — Signal Logic & Advisory Messages                           │
│    (OLS slope direction replaces kernel_bull flag in entry conditions)│
├──────────────────────────────────────────────────────────────────────┤
│  LAYER 5 — Stress-Test Suite                                          │
│    (unchanged: weight sensitivity + crisis + data degradation)        │
├──────────────────────────────────────────────────────────────────────┤
│  LAYER 6 — Rich Output Renderer                                       │
│    (adds OLS slope/R² per ticker; adds cache status panel)            │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 LIVE Execution Loop (v1.1 — pipeline model)

```
──── Startup (runs once) ────────────────────────────────────────────────────
[L0]   validate_config()                    → FrozenConfig cfg
[L0]   resolve_universe()                   → frozenset canonical_tickers
[L0]   compute_parity_factors()             → updated PARITY dict
[L0]   compute_cache_windows(cfg)           → MAX_CACHE_BARS_4H, MAX_CACHE_BARS_1MIN
[L0.5] init_cache(cfg)                      → mount Drive, create dirs, check config hash

──── Periodic cycle (every RUN_INTERVAL_HOURS) ──────────────────────────────
t0 = now()

[L1 Phase 1]  batch_fetch_and_prefilter(canonical_tickers, cfg)
              ┌─ ThreadPoolExecutor(max_workers = min(FETCH_BATCH_SIZE, 8)) ─┐
              │  For each batch of FETCH_BATCH_SIZE tickers:                  │
              │    futures = {submit(fetch_and_cache, ticker): ticker}         │
              │    for future in as_completed(futures):                        │
              │        df_4H, df_1min = future.result()                        │
              │        if qc_hard_fails(df_4H, df_1min): log_reject(); skip   │
              │        slope, r2 = ols_slope(df_4H.Close, LINREG_BARS)        │
              │        if slope < THRESHOLD or r2 < THRESHOLD:                 │
              │            log_filtered(ticker, slope, r2); skip               │
              │        passing_queue.put((ticker, df_4H, df_1min, slope, r2)) │
              └──────────────────────────────────────────────────────────────┘

[L1 Phase 2]  passing_data = collect(passing_queue)
              → convert dfs to float32 arrays, run QC soft checks

[L2]          features = Parallel(n_jobs=-1, backend="loky")(
                  delayed(compute_all_features)(ticker, arr_4H, arr_1min, slope, r2, cfg)
                  for ticker, arr_4H, arr_1min, slope, r2 in passing_data
              )                             → list[FeatureVector]

[L3]          scores = compute_scores(features, cfg)
                                            → list[ScoredTicker]

[L4]          signals = evaluate_signals(scores, state_cache)
                                            → list[SignalResult]

[L6]          render_output(signals, parity, cache_stats)

[L5]          run_stress_tests(features, scores, cfg)    # non-blocking thread

log(f"Cycle: {now()-t0:.1f}s | Fetched: {T} | Filtered: {T-P} | Scored: {P}")
```

### 2.3 Pipeline Overlap Analysis

**Why ThreadPoolExecutor for fetching + inline OLS works:**

```
Time axis →

Fetch batch 1 [T1..T10]  ███████████████
  As each ticker completes: ols_slope()  ← ~1µs, negligible

Fetch batch 2 [T11..T20]         ███████████████
  ols_slope() for batch 1 results:          ██  ← overlaps with batch 2 fetch

...

All batches done.
Passing tickers queued.
Loky full feature computation:                                ███████████████
```

The key insight: `ols_slope()` is O(N) with N=250, executing in ~1µs. It is computed **inline on the fetch thread** as each ticker's data arrives, consuming zero time relative to the ~150–300ms fetch latency per ticker. No separate process or queue coordination is needed for the OLS step. The only process-level parallelism is in Phase 2 (full features), which runs on the already-filtered, already-fetched data.

**Early discard benefit estimation (empirical projection):**

Assuming 50% of tickers fail the slope/R² pre-filter (conservative for a diverse universe in a mixed market):
- Phase 2 (full features) runs on 50% of tickers
- Features computation saved: Hurst O(N log N) + OU O(N) + HMM O(N²×states) + CVD O(N)
- Estimated Phase 2 time reduction: ~45–55%
- Increases further if LINREG_SLOPE_THRESHOLD is raised (more aggressive pre-filtering)

In a bull market (most tickers trending), the pre-filter may pass 80–90% of tickers → smaller benefit. In a correction (most tickers trending down), it may pass only 10–20% → enormous benefit. The filter is most valuable when the universe is large and the market environment makes most tickers unsuitable.

---

## 3. LAYER 0 — CONFIG VALIDATION (v1.1 additions)

### 3.1 Additions to Config Validation

```
# New in v1.1:
assert LINREG_BARS >= 20                    # minimum meaningful regression window
assert 0.0 <= LINREG_SLOPE_THRESHOLD        # must be non-negative (buy-only strategy)
assert 0.0 <= LINREG_R2_THRESHOLD <= 1.0
assert LINREG_SOURCE in {"close", "hlc3", "ohlc4"}
assert FETCH_BATCH_SIZE >= 1
assert CACHE_SAFETY_FACTOR >= 1.0           # must keep at least as many bars as required
assert CACHE_MAX_AGE_DAYS >= 1

# Remove in v1.1:
# KERNEL_SOURCE, KERNEL_BANDWIDTH, KERNEL_SLOPE_SMOOTH, KERNEL_SLOPE_THRESH
# (kernel params deleted from CONFIG entirely)
```

### 3.2 Cache Window Computation (run once at startup)

```python
MAX_CACHE_BARS_4H = math.ceil(
    max(
        LINREG_BARS,        # dominant at 250
        OU_CALIB_BARS,      # 120
        HMM_TRAIN_BARS,     # 200
        HURST_WIN_4H,       # 100
        CVD_NORM_WINDOW     # 60
    ) * CACHE_SAFETY_FACTOR
)
# Default: ceil(250 × 1.5) = 375 bars 4H ≈ 62 trading days

MAX_CACHE_BARS_1MIN = math.ceil(
    max(
        HURST_WIN_1MIN,     # 500
        SKEW_WINDOW_1MIN,   # 500
        MIN_BARS_1MIN       # 200
    ) * CACHE_SAFETY_FACTOR
)
# Default: ceil(500 × 1.5) = 750 bars 1min ≈ 1.9 trading days
```

These values are computed once and passed through `FrozenConfig`. No computation function may use a hardcoded window size.

### 3.3 CONFIG Hash for Cache Invalidation

```python
import hashlib, json

def config_hash(cfg: FrozenConfig) -> str:
    # Serialize only parameters that affect data requirements or computation
    # (not output params like SCORE_NORM_METHOD or DRIVE_CACHE_DIR)
    relevant = {k: v for k, v in vars(cfg).items()
                if k not in {"DRIVE_CACHE_DIR", "CACHE_MAX_AGE_DAYS",
                             "FORCE_FULL_FETCH", "SCORE_NORM_METHOD",
                             "RUN_INTERVAL_HOURS", "FETCH_BATCH_SIZE"}}
    return hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()[:16]
```

If the stored hash differs from the current hash at startup, emit:
```
⚠ CONFIG CHANGED — Cache invalidated. Full re-fetch will be performed this cycle.
   Previous hash: {old_hash}  Current hash: {new_hash}
   Affected: all tickers × all intervals
```
Then delete all parquet files and rebuild. Do **not** silently use stale cached data with different parameters.

---

## 4. LAYER 0.5 — GOOGLE DRIVE CACHE MANAGER (new)

### 4.1 Drive Mount and Initialization

```python
def init_cache(cfg: FrozenConfig) -> CacheState:
    if not cfg.DRIVE_CACHE_ENABLED:
        return CacheState(enabled=False)

    # Mount Google Drive (idempotent — no-op if already mounted)
    from google.colab import drive
    drive.mount("/content/drive", force_remount=False)

    cache_dir = Path(cfg.DRIVE_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Config hash check
    hash_file = cache_dir / "_config_hash.txt"
    current_hash = config_hash(cfg)
    if hash_file.exists():
        stored_hash = hash_file.read_text().strip()
        if stored_hash != current_hash and not cfg.FORCE_FULL_FETCH:
            emit_warning("CONFIG_CHANGED", old=stored_hash, new=current_hash)
            # Delete all parquet files
            for f in cache_dir.glob("*.parquet"):
                f.unlink()
    hash_file.write_text(current_hash)

    # Load or create metadata
    meta_file = cache_dir / "_meta.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
    else:
        meta = {}

    return CacheState(enabled=True, cache_dir=cache_dir, meta=meta)
```

### 4.2 Per-Ticker Fetch with Cache

```python
def fetch_and_cache(
    ticker    : str,
    interval  : str,          # "4h" | "1m"
    max_bars  : int,
    cfg       : FrozenConfig,
    state     : CacheState
) -> pd.DataFrame:

    if not state.enabled or cfg.FORCE_FULL_FETCH:
        return _cold_fetch(ticker, interval, max_bars)

    cache_file = state.cache_dir / f"{ticker}_{interval.replace(' ','')}.parquet"

    # ── Cold start ─────────────────────────────────────────────────
    if not cache_file.exists():
        df = _cold_fetch(ticker, interval, max_bars)
        _save_cache(df, cache_file, state, ticker, interval)
        return df

    # ── Staleness check ────────────────────────────────────────────
    file_age_days = (datetime.utcnow() - datetime.utcfromtimestamp(
                      cache_file.stat().st_mtime)).total_seconds() / 86400
    if file_age_days > cfg.CACHE_MAX_AGE_DAYS:
        emit_warning(f"{ticker}: cache {file_age_days:.0f} days old — full re-fetch")
        df = _cold_fetch(ticker, interval, max_bars)
        _save_cache(df, cache_file, state, ticker, interval)
        return df

    # ── Incremental fetch ──────────────────────────────────────────
    try:
        cached = pd.read_parquet(cache_file)
    except Exception as e:
        emit_warning(f"{ticker}: cache read error ({e}) — full re-fetch")
        cache_file.unlink(missing_ok=True)
        df = _cold_fetch(ticker, interval, max_bars)
        _save_cache(df, cache_file, state, ticker, interval)
        return df

    last_ts = cached.index[-1]

    if interval == "1m":
        # yfinance 1min max lookback = 7 days; period="2d" reliably overlaps with last cached bar
        new_data = yf.download(ticker, period="2d", interval="1m",
                                repair=True, auto_adjust=True, prepost=False, progress=False)
    else:
        new_data = yf.download(ticker, start=last_ts - timedelta(hours=8),
                                interval=interval,
                                repair=True, auto_adjust=True, prepost=False, progress=False)
        # Note: start offset of -8H ensures the last cached bar is re-fetched
        # (handles potential partial-bar issue on the last 4H candle)

    if new_data is not None and len(new_data) > 0:
        combined = pd.concat([cached, new_data])
        combined = combined[~combined.index.duplicated(keep='last')]
        combined = combined.sort_index()
    else:
        combined = cached

    # Prune: retain only max_bars most recent bars
    if len(combined) > max_bars:
        combined = combined.iloc[-max_bars:]

    _save_cache(combined, cache_file, state, ticker, interval)
    return combined
```

### 4.3 Cache Status Metrics (for Rich output)

After each cycle, report per-ticker cache state:

```
{ticker}: 4H cache {n_bars_4H} bars (fresh {age_4H_hours:.0f}H)
          1m cache {n_bars_1m} bars  (fresh {age_1m_minutes:.0f}min)
          fetch mode: INCREMENTAL | COLD | FORCED
```

Summary line in panel footer:
```
Cache: {n_cached}/{n_total} tickers loaded from Drive | Saved {fetch_time_saved:.1f}s vs full re-fetch
```

`fetch_time_saved` estimate: `(n_cached_4H × 0.10s) + (n_cached_1min × 0.18s)` (empirical per-request baseline).

---

## 5. LAYER 1 — PHASE 1: BATCH FETCH & OLS PRE-FILTER

### 5.1 OLS Slope Computation (inline, O(N))

This function runs on the fetch thread immediately after data arrives. It must be fast enough to not meaningfully delay the next fetch result from being processed — target < 0.5ms.

**Inputs**: `C: float32[N]` (close prices, 4H, last `LINREG_BARS` bars)
**Outputs**: `slope_pct: float32`, `r2: float32`

**Equations:**

Centered time axis (reduces numerical conditioning issues):

$$t_i = i - \frac{N-1}{2}, \quad i = 0, 1, \ldots, N-1$$

OLS slope (closed-form, no matrix inversion):

$$\hat{\beta} = \frac{\sum_{i=0}^{N-1} t_i (P_i - \bar{P})}{\sum_{i=0}^{N-1} t_i^2}$$

Normalized slope (scale-free, comparable across tickers):

$$\hat{\beta}_{\%} = \frac{\hat{\beta}}{\bar{P}} \times 100 \quad \text{(\% of mean price per 4H bar)}$$

Coefficient of determination:

$$R^2 = 1 - \frac{\text{SS}_\text{res}}{\text{SS}_\text{tot}}, \quad \text{SS}_\text{res} = \sum(P_i - \hat{P}_i)^2, \quad \text{SS}_\text{tot} = \sum(P_i - \bar{P})^2$$

where $\hat{P}_i = \bar{P} + \hat{\beta}(t_i)$.

**Note:** $R^2 = r_{Pearson}^2$ for simple linear regression — can be computed as `np.corrcoef(t, P)[0,1]**2`, which is equivalent and slightly more numerically robust for near-constant series.

**Vectorized implementation:**

```python
def ols_slope(C_4H: np.ndarray, n_bars: int) -> tuple[np.float32, np.float32]:
    P = C_4H[-n_bars:].astype(np.float64)        # float64 for OLS stability
    N = len(P)
    if N < 10:
        return np.float32(0.0), np.float32(0.0)  # insufficient data → fails threshold

    t     = np.arange(N, dtype=np.float64) - (N - 1) / 2.0
    P_bar = P.mean()
    t_sum_sq = (t * t).sum()

    if t_sum_sq < 1e-12 or P_bar < 1e-10:        # degenerate case guard
        return np.float32(0.0), np.float32(0.0)

    beta    = (t * (P - P_bar)).sum() / t_sum_sq
    beta_pct = float(beta / P_bar * 100.0)

    # R² via Pearson r (numerically robust for near-flat series)
    r = float(np.corrcoef(t, P)[0, 1])
    r2 = float(r * r)

    return np.float32(beta_pct), np.float32(r2)
```

**Pre-filter decision:**

```python
def passes_trend_filter(slope_pct: float, r2: float, cfg: FrozenConfig) -> bool:
    return (slope_pct >= cfg.LINREG_SLOPE_THRESHOLD and
            r2        >= cfg.LINREG_R2_THRESHOLD)
```

Discarded tickers are logged with slope and R² values — important for user calibration of thresholds.

---

## 6. LAYER 2 — FEATURE 2a: OLS REPLACES KERNEL (updated)

In v1.1, the OLS slope and R² computed in Phase 1 are **passed directly** to the feature vector — they are not recomputed. The `compute_all_features()` function receives `slope_pct` and `r2` as pre-computed inputs.

The `trend_bull` flag (previously `kernel_bull`) is:

$$\text{trend\_bull} = \begin{cases} 1 & \text{if } \hat{\beta}_\% > \text{LINREG\_SLOPE\_THRESHOLD} \text{ AND } R^2 > \text{LINREG\_R2\_THRESHOLD} \\ 0 & \text{otherwise} \end{cases}$$

Since all Phase 2 tickers already passed the pre-filter, `trend_bull` will always be `1` for them. The flag is retained in the FeatureVector for completeness (monitoring its evolution across cycles) and for the signal entry condition check in Layer 4.

**Memory impact of removing the kernel:**

| Resource | v1.0 (kernel) | v1.1 (OLS) | Saving |
|----------|--------------|-----------|--------|
| N×N weight matrix | 375×375×4B = 563KB/ticker | 0 | 563KB/ticker |
| Matrix multiply (float64) | O(N²) | O(N) | ~140,000 ops → ~375 ops |
| WMA helper | required | not required | removed |
| Edge validity array | required | not required | removed |
| Additional CONFIG params | 4 | 0 | simplified |

At 50 tickers per worker: ~28MB saved in working memory. Peak RAM drops from ~50MB to ~22MB per worker.

---

## 7. LAYER 2 — FEATURE 2b: FLOWER OSCILLATOR v5 (simplified — quad-EMA only)

**Removed from v1.0**: `FLOWER_USE_HMA` flag, `FLOWER_HMA_MUL` parameter, `hma()` function, `wma()` helper (no longer needed anywhere in the codebase with kernel and HMA both removed).

**Full Flower computation (quad-EMA, no branches):**

```
ys1  = (H + L + 2.0*C) / 4.0                     float32[M]
rk3  = ema(ys1, N)                                float32[M]   ← 1st EMA pass (normalization baseline)
rk4  = rolling_std(ys1, N) + ε                   float32[M]
rk5  = (ys1 - rk3) × 200.0 / rk4                float32[M]   ← normalized deviation ×200

rk6  = ema(rk5, N)                                float32[M]   ← 2nd EMA pass
UP   = ema(rk6, N)                                float32[M]   ← 3rd EMA pass (triple-smooth)
DOWN = ema(UP,  N)                                float32[M]   ← 4th EMA pass (quad-smooth)

flower_bull = (UP > DOWN).astype(int8)
```

All other aspects of Feature 2b (volume filter, buy/sell crossover detection, VWAP normalization, pivot detection) are **unchanged from v1.0 §5.3**.

**Lag note (documented for user)**: With N=5 and quad-EMA, the effective group delay is approximately 2N = 10 bars. On 1min charts, this is ~10 minutes. This is an accepted trade-off per the user's preference for the original algorithm's behavior, confirmed after live testing.

---

## 8. LAYER 4 — SIGNAL LOGIC (updated for OLS)

### 8.1 Entry Condition Update

`kernel_bull` is replaced by `trend_bull` (OLS-based). The entry condition table from v1.0 §7.1 is updated:

| # | Condition | Expression |
|---|-----------|-----------|
| E1 | OLS trend bullish | `fv.trend_bull == 1` (slope_pct > threshold AND R² > threshold) |
| ~~E2~~ | ~~Kernel edge valid~~ | **Removed** — OLS has no edge validity concept |
| E3 | Flower at OS | `fv.flower_up <= ENTRY_FLOWER_LEVEL` |
| E4 | Volume confirmed | `fv.vol_pass == 1` |
| E5 | Score threshold | `composite_score >= ENTRY_MIN_SCORE` |
| E6 | Not in cooldown | `bars_since_last_exit >= REENTRY_COOLDOWN` |

Entry now requires **5 conditions** (vs. 6 in v1.0 — one removed by eliminating `kernel_valid`).

### 8.2 Exit Condition Update

`EXIT_B: kernel_4H.bull turns 0` → `EXIT_B: trend_bull turns 0 (slope_pct drops below LINREG_SLOPE_THRESHOLD OR R² drops below LINREG_R2_THRESHOLD on next 4H cycle)`

Since OLS slope is recomputed every 4H cycle, EXIT_B triggers naturally when the regime changes. The 4H cycle is the resolution of this exit — not 1min-granular. This is a slight coarsening vs. the kernel's instantaneous derivative, but acceptable given OLS computes a more stable directional signal.

---

## 9. LAYER 6 — RICH OUTPUT (v1.1 additions)

### 9.1 New Panel Sections

**Pre-filter summary panel** (new, shown at top of each cycle):
```
┌─ TREND PRE-FILTER (OLS, {LINREG_BARS} bars 4H) ─────────────────────────┐
│ Slope threshold: ≥ {LINREG_SLOPE_THRESHOLD:.3f}%/bar  │  R² threshold: ≥ {LINREG_R2_THRESHOLD:.2f}  │
│ Passed: {P}/{T} tickers ({P/T:.0%})  │  Discarded: {T-P}                  │
│                                                                           │
│ TOP SLOPES (passed):                                                      │
│   PBR:  +0.041%/bar  R²=0.73  ✓                                          │
│   VALE: +0.029%/bar  R²=0.51  ✓                                          │
│                                                                           │
│ DISCARDED (slope or R² below threshold):                                  │
│   BRFS: +0.008%/bar  R²=0.12  ✗  (slope too low + weak trend quality)    │
│   SUZB: -0.003%/bar  R²=0.04  ✗  (bearish slope)                         │
└───────────────────────────────────────────────────────────────────────────┘
```

**Cache status panel** (new, shown at bottom):
```
┌─ CACHE STATUS ────────────────────────────────────────────────────────────┐
│ Drive: mounted ✓  │  Cache dir: /content/drive/MyDrive/flower_cache       │
│ Config hash: a3f7c12b (unchanged ✓)                                       │
│ Tickers: 74 cached  │  0 cold start  │  Est. time saved: 38.2s            │
│ 4H bars range: 280–375 bars  │  1min bars range: 512–750 bars             │
│ Oldest cache: ITUB_4h (12.3H)  │  Next prune triggered: never (within max)│
└───────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Per-Ticker Display Update

Replace kernel slope line with OLS metrics:

```
│ ⚡ PBR   [0.83]  ENTRY SIGNAL — All conditions met.                       │
│           OLS trend: BULL ▲  slope: +0.041%/bar  R²=0.73  (250 bars 4H)  │   ← replaces kernel line
│           Flower UP: -213.4  OVERSOLD  │  vol_pass: ✓                     │
│           CVD z: -1.83  │  HMM: low-vol P(expand)=0.71                    │
│           H_4H: 0.64  H_1m: 0.41  │  FPT prob: 0.79                       │
│           Cache: 4H=343bars(2.1H)  1m=750bars(18min)  [INCREMENTAL]       │  ← new cache line
```

---

## 10. UPDATED LIBRARY DEPENDENCIES

```
# Tier 1 — pre-installed on Colab
numpy  >= 1.24
scipy  >= 1.10       # lfilter (EMA), skew, erfc (FPT), rankdata
pandas >= 2.0        # cache I/O (parquet r/w), ffill in CVD, DatetimeIndex

# Tier 2 — pip install required
yfinance  >= 0.2.40
hmmlearn  >= 0.3.0
joblib    >= 1.3
rich      >= 13.0
schedule  >= 1.2
fastparquet >= 2023.10   # or pyarrow >= 14.0 — parquet engine for cache
                          # fastparquet preferred: lower Colab memory footprint

# google.colab — pre-installed in Colab, not pip-installable
from google.colab import drive
```

**Removed from v1.0**: No new removals. `WMA` helper function is removed from the codebase (no longer used — kernel gone, HMA gone).

---

## 11. UPDATED MEMORY ESTIMATE

| Resource | v1.0 | v1.1 | Change |
|----------|------|------|--------|
| Kernel matrix (per ticker) | 563KB | 0 | −563KB |
| HMA working arrays (per ticker) | ~50KB | 0 | −50KB |
| Parquet cache (per ticker, Drive) | 0 | ~15–40KB | +cloud storage |
| Peak worker RAM (50 tickers) | ~50MB | ~22MB | −56% |
| Phase 2 ticker count (typical) | 100% of universe | ~50% of universe | −50% compute |

---

## 12. UPDATED ACCEPTANCE CRITERIA

*Changes from v1.0 AC table:*

| ID | Change | New criterion |
|----|--------|---------------|
| AC-02 | Unchanged | Spearman ρ > 0.85 under weight perturbation |
| AC-03 | Unchanged | TIER-1 drops ≥ 10% in crisis windows |
| AC-NEW-01 | New | Pre-filter discards ≥ 80% of bearish tickers during crash windows (Axis B) |
| AC-NEW-02 | New | Incremental fetch saves ≥ 60% of cold-fetch time after first cycle |
| AC-NEW-03 | New | Cache merge produces no duplicate timestamps and preserves monotonic index |
| AC-NEW-04 | New | CONFIG hash change correctly triggers full re-fetch (no stale data used) |
| AC-NEW-05 | New | OLS slope computation < 0.5ms per ticker (profiled on Colab CPU) |
| AC-06 | Updated | Full pipeline runtime ≤ 60s on Colab (down from 120s due to cache + pre-filter) |

---

## 13. OPEN QUESTIONS (updated — 4 remaining from v1.0, 1 new)

| Q# | Question | Assumed default | Impact |
|----|----------|----------------|--------|
| Q1 | OU FPT horizon: 100 bars 1min realistic? | 100 (empirical calibration needed) | High — affects FPT probability values |
| Q2 | VWAP reset: daily session or rolling? | Daily session reset | Affects VWAP continuity for 4H/swing |
| Q3 | Backtest transaction cost assumption | 0.10% round-trip | Critical for AC evaluation |
| Q5 | CVD asymmetric scoring accepted? | YES | W_CVD weight interpretation |
| Q_NEW | After sustained Drive disconnect: fallback to in-memory only or halt? | In-memory only (no Drive save), emit WARNING, continue | Determines resilience vs. data-integrity trade-off |
