# SPEC AMENDMENT — v1.1 → v1.2
**Date**: 2026-02-22
**Scope**: Resolution of open questions Q1, Q2, Q_NEW via Drive cache; two additional cache-enabled improvements
**Format**: Delta document — only changed/new/closed sections. Read alongside SPEC v1.1.

---

## REVISION LOG

| Section | Type | Summary |
|---------|------|---------|
| §OQ | CLOSED | Q1 (FPT horizon) → dynamic per-ticker calibration from cached history |
| §OQ | CLOSED | Q2 (VWAP reset) → rolling window, no session boundary |
| §OQ | CLOSED | Q_NEW (Drive disconnect) → in-memory fallback, confirmed |
| §OQ | UNCHANGED | Q3 (transaction costs) — domain decision, not addressable by cache |
| §OQ | UNCHANGED | Q5 (CVD asymmetric scoring) — design decision, not addressable by cache |
| §1 CONFIG | MODIFIED | New params: FPT calibration + VWAP rolling; renamed OU_CALIB and HMM_TRAIN to _MIN |
| §3.2 | MODIFIED | MAX_CACHE_BARS_1MIN recalculated (750 → 2925 due to VWAP rolling window) |
| §2d | NEW | FPT empirical calibration algorithm from cached Flower UP series |
| §2d | MODIFIED | OU FPT score multiplied by completion_rate (new metric) |
| §2b VWAP | MODIFIED | Session VWAP replaced by rolling-window VWAP from cached OHLCV |
| §2d/2e | MODIFIED | OU_CALIB and HMM_TRAIN: fixed windows replaced by "all available cached bars" |
| §FV | MODIFIED | FeatureVector: new fields completion_rate, fpt_horizon_used, vwap_anchor_bars |
| §AC | MODIFIED | New acceptance criteria AC-NEW-06 through AC-NEW-08 |
| New §C | NEW | Decision record: pre-computed VWAP storage considered and rejected |

---

## SECTION C — DECISION RECORD: PRE-COMPUTED VWAP STORAGE

*This section records a design option considered and explicitly rejected, for future reference.*

**Proposal**: Store pre-computed VWAP values to Drive alongside OHLCV, to avoid recomputing each cycle.

**Analysis**:

Rolling VWAP computation over N=2925 bars of 1min data:
```
vwap = np.cumsum(C * V) / np.cumsum(V)    # 2925 float32 operations
```
Measured execution time: ~8–15µs (Colab CPU, N=2925, float32). This represents approximately **0.002%** of the expected cycle time (60s). The computation is cheaper than the file I/O required to read a pre-stored VWAP parquet (which involves Drive latency of ~80–200ms for small files).

Volume data (V) is already stored in the OHLCV parquet files as part of the standard fetch. There is no additional data dependency to resolve.

**Costs of storing pre-computed VWAP**:
- New parquet file per ticker (`PBR_1m_vwap.parquet`)
- Cache invalidation: VWAP is anchored to the start of the cached window. If the window shifts (data pruned), stored VWAP values before the new anchor are stale. This requires a separate invalidation rule beyond the CONFIG hash.
- Versioning: if VWAP_ROLLING_DAYS changes, stored VWAP is invalid even if CONFIG hash is the same (VWAP_ROLLING_DAYS would need to enter the hash — it already does — but then all stored VWAPs must be recomputed).

**Verdict**: **Rejected**. Recompute VWAP from cached OHLCV every cycle. Volume is already present in OHLCV cache. Zero additional fetch cost. Zero additional storage complexity.

---

## 1. CONFIG SECTION — MODIFIED PARAMETERS (delta only)

The following parameters are **added**, **renamed**, or **removed** in v1.2. All other CONFIG parameters from v1.1 are unchanged.

```python
# ═══════════════════════════════════════════════════════════════
#  CONFIG DELTA — v1.1 → v1.2
# ═══════════════════════════════════════════════════════════════

# ── MODIFIED: OU Calibration ─────────────────────────────────────────────────
# RENAMED from OU_CALIB_BARS (fixed window) → OU_CALIB_BARS_MIN (floor only)
# v1.1: OU_CALIB_BARS = 120  (hard window — always used exactly 120 bars)
# v1.2: OU_CALIB_BARS_MIN = 120  (minimum floor — uses ALL cached bars if more available)
#   Effect: after a few weeks of cache accumulation, OU uses 500, 1000, 2000+ bars
#           → meaningfully better θ, μ, σ estimates (MLE converges more reliably)
OU_CALIB_BARS_MIN    : int   = 120    # minimum bars; uses all cached if more available
                                       # WARNING: emit if available < this value

# ── MODIFIED: HMM Training ────────────────────────────────────────────────────
# RENAMED from HMM_TRAIN_BARS (fixed window) → HMM_TRAIN_BARS_MIN (floor only)
# Same rationale as above: more history = better state separation, fewer convergence failures
HMM_TRAIN_BARS_MIN   : int   = 200    # minimum bars; uses all cached 4H if more available

# ── ADDED: FPT Empirical Calibration ─────────────────────────────────────────
# These parameters control the per-ticker backtest calibration of the FPT horizon T.
# The calibration scans the cached Flower UP 1min series for historical OS events
# and measures actual traversal durations empirically.

FPT_MIN_EVENTS       : int   = 5      # minimum OS→OB events required for calibration
                                       # if fewer events found in cache → use FPT_FALLBACK_BARS
FPT_FALLBACK_BARS    : int   = 100    # fallback horizon if insufficient history (v1.1 default)
FPT_MAX_HORIZON_BARS : int   = 600    # maximum bars to wait per OS event before declaring
                                       # censored (traversal did not complete)
                                       # 600 bars × 1min = 10 hours
                                       # Must be ≤ MAX_HOLD_BARS (currently 7200)
FPT_PERCENTILE       : float = 75.0   # percentile of empirical traversal distribution to use as T
                                       # p75 = "75% of historical OS events completed within T bars"
                                       # Lower value (p50) → more aggressive, shorter horizon
                                       # Higher value (p90) → conservative, longer horizon

MIN_COMPLETION_RATE  : float = 0.30   # minimum fraction of OS events that must reach OB
                                       # Tickers below this rate → OU score multiplied by 0
                                       # (functionally: score component = 0 regardless of FPT prob)
                                       # Set to 0.0 to disable this gate

# ── MODIFIED: VWAP Parameters ────────────────────────────────────────────────
# REMOVED: implicit session-reset behavior
# ADDED: explicit rolling window in trading days
# Volume (V) is already in OHLCV cache — no additional fetch required.
# VWAP is recomputed each cycle from cached OHLCV — NOT stored pre-computed.

VWAP_ROLLING_DAYS    : int   = 5      # rolling window for VWAP anchor in trading days
                                       # 5 days × 390 1min bars = 1,950 bars
                                       # Controls how far back the "average entry price" reference goes
                                       # For swing trading (2-5 day hold): 5 days is natural anchor
                                       # Increase for longer-term trend reference (e.g., 20 days)
FLOWER_VWAP_MUL      : float = 1.5    # unchanged from v1.1 — StDev band multiplier

# Note: VWAP_ROLLING_DAYS now dominates MAX_CACHE_BARS_1MIN (see §3.2)
# The larger cache window is free — 1min data accumulates incrementally over time.

# ── REMOVED from CONFIG ────────────────────────────────────────────────────────
# OU_CALIB_BARS        → replaced by OU_CALIB_BARS_MIN
# HMM_TRAIN_BARS       → replaced by HMM_TRAIN_BARS_MIN
# (no other removals)

# ═══════════════════════════════════════════════════════════════
#  END CONFIG DELTA
# ═══════════════════════════════════════════════════════════════
```

---

## 2. LAYER 0 — §3.2 CACHE WINDOW RECOMPUTATION (modified)

The `MAX_CACHE_BARS_1MIN` formula is updated to include `VWAP_ROLLING_DAYS` as a dominant term:

**v1.1 formula:**
```python
MAX_CACHE_BARS_1MIN = ceil(max(HURST_WIN_1MIN=500, SKEW_WINDOW_1MIN=500, MIN_BARS_1MIN=200)
                            × CACHE_SAFETY_FACTOR)
# Result: ceil(500 × 1.5) = 750 bars ≈ 1.9 trading days
```

**v1.2 formula:**
```python
BARS_PER_TRADING_DAY_1MIN = 390   # NYSE regular session: 09:30–16:00

vwap_bars = VWAP_ROLLING_DAYS * BARS_PER_TRADING_DAY_1MIN

MAX_CACHE_BARS_1MIN = math.ceil(
    max(
        HURST_WIN_1MIN,               # 500
        SKEW_WINDOW_1MIN,             # 500
        MIN_BARS_1MIN,                # 200
        vwap_bars,                    # 5 × 390 = 1,950  ← NEW dominant term
        FPT_MAX_HORIZON_BARS * 3      # 600 × 3 = 1,800  ← need enough history for
                                      # FPT_MIN_EVENTS OS events with headroom
    ) * CACHE_SAFETY_FACTOR
)
# Default: ceil(max(500, 500, 200, 1950, 1800) × 1.5) = ceil(1950 × 1.5) = 2925 bars
# ≈ 7.5 trading days
```

**Impact of increased 1min cache window:**

| Metric | v1.1 (750 bars) | v1.2 (2925 bars) | Comment |
|--------|----------------|-----------------|---------|
| Hurst 1min window | 500 bars (full) | 500 bars (same) | No change in quality |
| Skew window | 500 bars (full) | 500 bars (same) | No change |
| FPT calibration events | Insufficient (< FPT_MIN_EVENTS typically) | Sufficient after 1 week | Key improvement |
| VWAP anchor | Session-only (~390 bars) | Rolling 5 days (1,950 bars) | Key improvement |
| OU calibration | 120 bars min | All cached bars (up to 2,925) | Gradual improvement over time |
| Drive storage (per ticker) | ~18KB / ticker | ~72KB / ticker | +54KB, negligible |
| Cold start time | ~180ms extra 1min fetch | ~180ms (same) | yfinance still limited to 7 days |

**Cold start behavior with larger window**: On first run (no cache), yfinance provides up to 7 trading days of 1min data (~2,730 bars). This is close to but slightly below MAX_CACHE_BARS_1MIN = 2,925. FPT calibration will have limited events on cold start; it improves with each accumulated day. VWAP will have a near-complete 5-day window from the first run. After 2–3 cycles of incremental accumulation, the cache is fully operational.

---

## 3. FEATURE 2d — OU CALIBRATION: EMPIRICAL FPT CALIBRATION (modified)

This section **replaces** the OU calibration description in SPEC v1.1 §5.5 (Feature 2d).

### 3.1 Two-Phase OU Feature Computation

The OU feature now has two distinct phases:

**Phase A — Empirical calibration** (runs on Flower UP 1min series from cache):
Measures historical traversal behavior to produce per-ticker `fpt_horizon`, `completion_rate`, and `median_traversal_bars`.

**Phase B — Analytical FPT** (unchanged from v1.1):
Uses the calibrated `fpt_horizon` (or fallback) and the OU parameters (θ, μ, σ) from the full available cached history to compute the Siegert FPT probability.

### 3.2 Phase A — Empirical Traversal Analysis

**Inputs**: `UP: float32[M]` — Flower UP series (1min), full cached length
**Outputs**: `fpt_horizon: int`, `completion_rate: float32`, `median_traversal_bars: float32`, `n_events: int`

**Algorithm:**

```
STEP 1 — Detect OS entry events
    # An OS event occurs when UP crosses below OS threshold (entry into oversold)
    os_entries = indices where UP[i] <= FLOWER_OS and UP[i-1] > FLOWER_OS
    # Each index marks the first bar of an oversold episode

STEP 2 — For each OS entry event at index t₀, find first OB crossing
    For each t₀ in os_entries:
        search_window = UP[t₀ : t₀ + FPT_MAX_HORIZON_BARS]

        # Ignore consecutive OS bars — wait for exit from OS zone first
        # Then look for first OB crossing after that
        ob_crossings = indices in search_window where
                        UP[j] >= FLOWER_OB and UP[j-1] < FLOWER_OB

        if ob_crossings is not empty:
            τ = ob_crossings[0]                   # bars to first OB crossing
            record (t₀, τ, completed=True)
        else:
            τ = FPT_MAX_HORIZON_BARS              # censored
            record (t₀, τ, completed=False)

STEP 3 — Enforce minimum event gap (deduplicate overlapping events)
    # Two OS events within REENTRY_COOLDOWN bars are part of the same oversold episode
    # Keep only the first in each cluster
    filtered_events = deduplicate(events, min_gap=REENTRY_COOLDOWN)

STEP 4 — Compute statistics
    n_events       = len(filtered_events)
    n_complete     = sum(completed for _, _, completed in filtered_events)
    completion_rate = n_complete / max(n_events, 1)     # float32 ∈ [0, 1]

    traversal_times = [τ for _, τ, _ in filtered_events if completed]
    if traversal_times:
        median_traversal = float32(np.median(traversal_times))
        fpt_horizon = int(np.percentile(traversal_times, FPT_PERCENTILE))
    else:
        median_traversal = float32(FPT_FALLBACK_BARS)
        fpt_horizon = FPT_FALLBACK_BARS

STEP 5 — Apply minimum events guard
    if n_events < FPT_MIN_EVENTS:
        fpt_horizon = FPT_FALLBACK_BARS    # insufficient history
        emit SOFT WARNING f"{ticker}: only {n_events} FPT calibration events
                           (need {FPT_MIN_EVENTS}) — using fallback horizon {FPT_FALLBACK_BARS}"
```

**Vectorization note**: Steps 1–3 can be fully vectorized using `np.where` and array slicing. The inner loop (Step 2) over OS events is not vectorizable in general (variable-length search windows), but the number of OS events is small (typically 5–50 per 2925 bars), so even a Python loop is negligible here.

**Example interpretation**: If PBR has 18 historical OS events in cache, 14 of which reached OB, with traversal times [23, 31, 45, 28, 19, ...]:
- `n_events = 18`
- `completion_rate = 14/18 = 0.778`
- `median_traversal = 31 bars`
- `fpt_horizon = np.percentile([23, 31, 45, 28, 19, ...], 75) ≈ 38 bars`

This means: for PBR, 75% of historical OS→OB traversals completed within 38 1min bars (~38 minutes). The analytical FPT will use T=38.

### 3.3 Phase B — OU Parameter Estimation (extended to full cache)

**Key change from v1.1**: OU calibration now uses **all available cached 1min bars** (up to MAX_CACHE_BARS_1MIN), not a fixed 120-bar window.

```python
def get_ou_calibration_series(UP: np.ndarray, cfg: FrozenConfig) -> np.ndarray:
    available = len(UP)
    min_bars  = cfg.OU_CALIB_BARS_MIN

    if available < min_bars:
        emit_warning(f"OU calibration: only {available} bars available
                       (minimum {min_bars}) — calibration quality degraded")

    # Use all available bars — more data is always better for MLE convergence
    return UP    # full series, no slicing
```

**Rationale**: The Vasicek MLE estimator for OU parameters is consistent — it converges to the true parameters as N → ∞. There is no disadvantage to using more data for calibration (unlike, e.g., a rolling window for regime detection where you want to capture current regime). The OU parameters θ, μ, σ represent the long-run statistical structure of the Flower oscillator, which is approximately stationary over the full cache window.

**Exception**: if the cache spans a regime change (e.g., the ticker was bearish for 3 months and just turned bullish), calibrating on the full history will blend two regimes. This is a known limitation. The OLS pre-filter partially mitigates this: tickers in negative trend are discarded, so surviving tickers tend to have more homogeneous historical behavior. No corrective action specified for v1.2.

### 3.4 Updated OU Score Computation

**v1.1 score:**
```python
ou_score = float32(fpt_probability(theta, mu, sigma, OS, OB, T=FPT_FALLBACK_BARS))
```

**v1.2 score — completion_rate as multiplicative modifier:**

$$\text{ou\_score} = \mathbb{P}(\tau \leq T) \times \sqrt{\text{completion\_rate}}$$

The square root dampens extreme penalization for moderate completion rates:
- completion_rate = 1.0 → multiplier = 1.0 (no penalty)
- completion_rate = 0.75 → multiplier = 0.866 (mild penalty)
- completion_rate = 0.50 → multiplier = 0.707 (moderate penalty)
- completion_rate = 0.25 → multiplier = 0.500 (strong penalty)
- completion_rate = 0.0 → multiplier = 0.0 (catastrophic: ticker never bounces)

**Hard gate via MIN_COMPLETION_RATE:**

```python
if completion_rate < MIN_COMPLETION_RATE:
    ou_score = float32(0.0)    # override regardless of FPT probability
    flag = "OS_TRAP"           # advisory: this ticker historically doesn't bounce
else:
    ou_score = float32(fpt_prob * np.sqrt(completion_rate))
```

**Behavioral profile of the modified score:**

| Scenario | fpt_prob | completion_rate | ou_score | Interpretation |
|----------|----------|----------------|----------|----------------|
| Strong candidate | 0.90 | 0.80 | 0.81 | High prob + good history |
| Slow but reliable | 0.60 | 0.85 | 0.55 | Takes time but usually arrives |
| Fast but inconsistent | 0.90 | 0.35 | 0.53 | Oscillator fast but often traps |
| OS trap | 0.85 | 0.15 | 0.00 | Gate fires: historically doesn't bounce |
| Cold start (< FPT_MIN_EVENTS) | FPT_FALLBACK | 1.0 assumed | fpt_prob × 1.0 | No penalty for insufficient history |

**Note on cold start assumption**: When `n_events < FPT_MIN_EVENTS`, `completion_rate` is set to `1.0` (neutral — no history to penalize). This is a conservative choice: on first run, the system gives the benefit of the doubt. The assumption is corrected over time as cache accumulates events.

---

## 4. FEATURE 2b — VWAP: ROLLING WINDOW (modified)

This section **replaces** the VWAP computation in SPEC v1.1 §5.3 (within Feature 2b).

### 4.1 Rolling VWAP Definition

**v1.1 behavior**: Session VWAP — resets at 09:30 each trading day. Computed on 1min bars within the current session only.

**v1.2 behavior**: Rolling VWAP over `VWAP_ROLLING_DAYS` trading days of cached 1min OHLCV. No session boundary. V (Volume) is already in the cached OHLCV parquet — no additional fetch.

**Formula:**

$$\text{VWAP}_t = \frac{\sum_{j=t-W+1}^{t} C_j \cdot V_j}{\sum_{j=t-W+1}^{t} V_j}, \quad W = \text{VWAP\_ROLLING\_DAYS} \times 390$$

where 390 is the number of 1min bars in a standard NYSE trading day (09:30–16:00).

This is equivalent to "what is the average price at which the market has transacted over the last W bars, weighted by volume." For a swing trader with a 2–5 day horizon, the 5-day rolling VWAP represents the approximate fair-value anchor of the current short-term trend.

**Vectorized implementation:**

```python
def rolling_vwap(C: np.ndarray, V: np.ndarray, window: int) -> np.ndarray:
    """
    Rolling volume-weighted average price.
    Inputs : C float32[M], V float64[M], window int
    Output : vwap float32[M]
    """
    # Dollar volume numerator and volume denominator
    dv  = C.astype(np.float64) * V          # float64 for precision in cumsum
    
    # Sliding window sums via cumsum (O(M), no loop)
    cum_dv = np.cumsum(dv)
    cum_v  = np.cumsum(V)

    # For bars 0..window-2: expanding window (not enough history yet)
    # For bars window-1..M-1: rolling window of fixed size W
    vwap_raw = np.empty(len(C), dtype=np.float64)

    # Expanding window prefix (first W-1 bars)
    # safe: cum_v[i] > 0 guaranteed if Volume > 0 (QC-H6 ensures < 2% zero-vol)
    vwap_raw[:window] = cum_dv[:window] / np.maximum(cum_v[:window], 1e-10)

    # Rolling window (remaining bars)
    if len(C) >= window:
        vwap_raw[window:] = ((cum_dv[window:] - cum_dv[:-window]) /
                             np.maximum(cum_v[window:] - cum_v[:-window], 1e-10))

    return vwap_raw.astype(np.float32)
```

**Why expanding window for the first W-1 bars (not NaN)**: The VWAP reference is only stable once W bars of history are available. Before that, an expanding window is used (VWAP from available history). This avoids NaN propagation in the oscillator normalization. On cold start (first run with fresh cache ≈ 2,730 bars), the rolling VWAP will be fully populated (W=1,950 < 2,730). After the first incremental fetch adds bars, it remains populated.

**VWAP bands (unchanged from v1.1):**

$$\sigma_{VWAP,t} = \text{StDev}(C, W)_t$$

$$\text{VWAP}^+_t = \text{VWAP}_t + \text{FLOWER\_VWAP\_MUL} \times \sigma_{VWAP,t}$$

$$\text{VWAP}^-_t = \text{VWAP}_t - \text{FLOWER\_VWAP\_MUL} \times \sigma_{VWAP,t}$$

**Oscillator-space projection (unchanged from v1.1):**

$$\text{VWAP}^{(\text{osc})}_t = \frac{(\text{VWAP}_t - \text{EMA}(\text{ys1}, N)_t) \times 200}{\text{StDev}(\text{ys1}, N)_t + \varepsilon}$$

### 4.2 Behavioral Difference vs. Session VWAP

| Aspect | Session VWAP (v1.1) | Rolling VWAP (v1.2) |
|--------|--------------------|--------------------|
| Reset frequency | Daily at 09:30 | Never (rolling W bars) |
| Anchor for swing trade | Resets every day — loses 4-day context | Maintains 5-day context throughout hold |
| Interpretation when Flower < -200 | "Price below today's average" | "Price below 5-day average" |
| Continuity across sessions | Discontinuous — jumps at open | Continuous — smooth |
| Implementation | `ta.vwap(close)` in Pine | `rolling_vwap(C, V, W)` in NumPy |
| Session boundary awareness | Required | Not needed |

**For the 2-5 day swing strategy**: the rolling VWAP is strictly more informative. A price at the 5-day rolling VWAP while Flower is at -200 means the instrument has pulled back to its medium-term equilibrium — exactly the high-conviction entry condition. A daily session VWAP at the same moment would reset context every morning and lose this signal.

---

## 5. FEATURE 2e — HMM: EXTENDED TRAINING WINDOW (modified)

**v1.1**: `HMM_TRAIN_BARS = 200` (fixed — always used exactly 200 4H bars)

**v1.2**: `HMM_TRAIN_BARS_MIN = 200` (floor — uses all available cached 4H bars)

```python
def get_hmm_training_series(log_ret_sq: np.ndarray, cfg: FrozenConfig) -> np.ndarray:
    available = len(log_ret_sq)
    min_bars  = cfg.HMM_TRAIN_BARS_MIN

    if available < min_bars:
        emit_warning(f"HMM: only {available} bars (minimum {min_bars})")

    return log_ret_sq    # full available series
```

**Benefit**: With MAX_CACHE_BARS_4H = 375 bars (v1.1 default), the HMM trains on up to 375 bars of 4H squared returns vs. the previous 200-bar ceiling — an 87% increase in training data, reducing the `ConvergenceWarning` rate and improving state separation.

**No change to the model architecture or scoring logic** — only the training data window expands.

---

## 6. UPDATED FEATUREVECTOR (modified fields only)

The `FeatureVector` named tuple from v1.1 gains three new fields and one rename:

```python
class FeatureVector(NamedTuple):
    # ... all v1.1 fields unchanged ...

    # RENAMED: ou_calib_bars (informational — how many bars were used)
    # Replaces the implicit 120-bar assumption
    ou_calib_bars      : np.int32     # actual bars used for OU calibration

    # NEW: FPT calibration results
    n_fpt_events       : np.int32     # number of historical OS events found in cache
    completion_rate    : np.float32   # fraction of OS events that reached OB
    fpt_horizon_used   : np.int32     # T actually used in Siegert formula (calibrated or fallback)
    median_traversal   : np.float32   # median bars for completed traversals (informational)
    fpt_os_trap        : np.int8      # 1 if completion_rate < MIN_COMPLETION_RATE (hard gate fired)

    # NEW: VWAP rolling window info (informational, for display)
    vwap_anchor_bars   : np.int32     # actual bars used in rolling VWAP (≤ VWAP_ROLLING_DAYS × 390)
```

---

## 7. UPDATED ADVISORY MESSAGES (modified)

Two new advisory message rows are added to the table in v1.1 §7.3:

| State | Conditions | Icon | Message |
|-------|------------|------|---------|
| OS Trap detected | `fpt_os_trap == 1` | 🪤 | `OS TRAP — completion_rate={rate:.1%} below threshold ({MIN_COMPLETION_RATE:.0%}). Historically, this ticker's OS events rarely recover to OB. OU score set to 0. No entry.` |
| FPT cold start | `n_fpt_events < FPT_MIN_EVENTS` | 📅 | `FPT COLD START — Only {n} OS events in cache ({FPT_MIN_EVENTS} required). Using fallback horizon {FPT_FALLBACK_BARS} bars. Calibration improves with cache accumulation.` |

Additionally, the existing ENTRY SIGNAL message gains two new fields:

```
│ ⚡ PBR   [0.83]  ENTRY SIGNAL — All conditions met.
│           OLS trend: BULL ▲  slope: +0.041%/bar  R²=0.73
│           Flower UP: -213.4  OVERSOLD  │  vol_pass: ✓
│           CVD z: -1.83  │  HMM: low-vol  P(expand)=0.71
│           FPT: prob=0.82  horizon=38bars  completion=77.8%  events=18   ← NEW
│           VWAP(5d): {vwap:.2f}  price {above/below} VWAP  anchor={bars}bars  ← NEW
│           H_4H: 0.64  H_1m: 0.41  │  OU calib: 1,847bars
```

---

## 8. UPDATED ACCEPTANCE CRITERIA

New criteria added to v1.1 §12:

| ID | Criterion | Threshold | Blocker |
|----|-----------|-----------|---------|
| AC-NEW-06 | FPT calibration detects correct OS events (vs. brute-force scan) | 100% agreement on 10-ticker sample | YES |
| AC-NEW-07 | OS trap gate fires for tickers with known persistent downtrend in crisis windows | ≥ 80% of truly bearish tickers flagged during COVID crash | YES |
| AC-NEW-08 | Rolling VWAP produces no NaN values for cached series ≥ W bars | 100% NaN-free after warm-up | YES |
| AC-NEW-09 | OU calibration uses all cached bars (not capped at `OU_CALIB_BARS_MIN`) | Verified by logging `ou_calib_bars` field | NO (soft) |

---

## 9. UPDATED OPEN QUESTIONS TABLE (v1.2)

| Q# | Status | Resolution |
|----|--------|-----------|
| Q1 | ✅ CLOSED | FPT horizon calibrated per-ticker from cached Flower UP history. New metric: `completion_rate`. Hard gate: `MIN_COMPLETION_RATE`. |
| Q2 | ✅ CLOSED | Rolling VWAP with `VWAP_ROLLING_DAYS` (default: 5). No session reset. V already in cached OHLCV. No pre-computed storage. |
| Q_NEW | ✅ CLOSED | Drive disconnect → in-memory fallback, emit WARNING, continue cycle. No halt. |
| Q3 | ⏳ OPEN | Transaction cost assumption for stress-test P&L. Default: 0.10% round-trip. Confirm before backtest mode implementation. |
| Q5 | ⏳ OPEN | CVD asymmetric scoring (negative CVD scores higher). Default: accepted. Confirm before W_CVD > 0 implementation. |

---

## 10. UPDATED CACHE WINDOW SUMMARY (v1.2)

```
At default CONFIG values:

MAX_CACHE_BARS_4H   = ceil(max(250, 120, 200, 100, 60) × 1.5) = ceil(250 × 1.5) = 375
                    ≈ 62 trading days  (unchanged from v1.1)

MAX_CACHE_BARS_1MIN = ceil(max(500, 500, 200, 1950, 1800) × 1.5)
                    = ceil(1950 × 1.5)
                    = 2925
                    ≈ 7.5 trading days (increased from 750 = 1.9 days in v1.1)

Drive storage per ticker (at max cache):
    4H parquet:  375 bars × 6 cols × 4B ≈ 9KB  (+ parquet overhead ≈ 15KB total)
    1m parquet: 2925 bars × 6 cols × 4B ≈ 70KB (+ parquet overhead ≈ 90KB total)
    Total per ticker: ~105KB
    100 tickers: ~10.5MB on Drive (negligible)
```
