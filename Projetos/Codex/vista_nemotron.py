# =============================================================================
# @title VISTA Nemotron 3 Nano Omni  —  Multi-Ticker, Bug-Fixed, Optimized
# =============================================================================
'''
# API provider : OpenRouter (free tier)
# Environment  : Google Colab (CPU) + Numba JIT
# =============================================================================
This script implements a multi-timeframe financial forecasting pipeline by integrating high-performance data processing with vision-language model (VLM)
reasoning. It utilizes yfinance to fetch market data and Numba (JIT-compiled functions) for the efficient calculation of Volume Weighted Moving Averages (VWMA)
and log returns. The core logic generates a consolidated visualization of Weekly, Daily, and 15-minute Heikin-Ashi charts overlaid with VWMA lines, which are
then encoded as a base64 payload. This visual context, alongside pre-computed momentum z-scores and price-distance metrics, is dispatched via ThreadPoolExecutor
to the Nemotron-3-Nano model on OpenRouter; the model analyzes the synthetic price series to predict future closing prices, which are finally aggregated using
a median filter to ensure a robust, consensus-driven 5-day forecast.

TASK 1 FIXES APPLIED:
1. Fixed URL typo: "https://openrouter.ai/api/v1/chat/completions " had trailing space → removed
2. Increased max_tokens for reasoning models (Nemotron needs more output tokens for chain-of-thought)
3. Improved _extract_response_text() to handle content=None properly for reasoning models
4. Added sys import for proper exit handling

TASK 2 CHANGES:
- Removed fallback to random-walk in call_vlm() and ensemble_vlm()
- If VLM calls fail, raise explicit error and terminate main() with explanatory message
'''
# ── Colab install (uncomment in Colab) ──────────────────────────────────────
# !pip install -q yfinance pyarrow numba

import os, sys, time, json, base64, re, logging
from statistics import median
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numba
import requests

# ── Colab Secrets support ────────────────────────────────────────────────────
# In Colab, set your OPENROUTER_API_KEY in Secrets and grant access.
# Outside Colab, use the OPENROUTER_API_KEY environment variable.
try:
    from google.colab import userdata
    _GET_API_KEY = lambda: userdata.get("OPENROUTER_API_KEY")
except ImportError:
    _GET_API_KEY = lambda: os.getenv("OPENROUTER_API_KEY")

# ── Configuration ────────────────────────────────────────────────────────────
TICKERS_INPUT  = "MRVL"               # space-separated, edit in-line
VLM_MODEL      = "nemotron"           # "nemotron" | "glm-4.6v" | "glm-5v-turbo"
PERIOD_DAILY   = "2y"
PERIOD_WEEKLY  = "2y"
PERIOD_15M     = "60d"
VWMA_WINDOW    = 20
MOM_PERIOD     = 14
MOM_ZSCORE_WINDOW = 60                # lookback for z-score normalisation
N_ENSEMBLE     = 3                     # parallel VLM calls per ticker
RETRY_MAX      = 3
CHART_BARS     = 100                   # last N bars to show per timeframe
IMAGE_DPI      = 150
TIMEOUT_VLM    = 180                   # seconds (increased for reasoning models)

# ── Available VLM models (all free on OpenRouter) ────────────────────────────
VLM_MODELS = {
    "nemotron": {
        "id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "reasoning": True,
        "max_tokens": 1024,              # Increased for reasoning output
    },
    "glm-4.6v": {
        "id": "z-ai/glm-4.6v:free",
        "reasoning": False,
        "max_tokens": 256,
    },
    "glm-5v-turbo": {
        "id": "z-ai/glm-5v-turbo:free",
        "reasoning": True,
        "max_tokens": 1024,
    },
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("VISTA")

# ── PROMPT template ──────────────────────────────────────────────────────────
PROMPT = """Three Heikin-Ashi candlestick charts, each with a VWMA overlay line.
[LEFT] = WEEKLY | [CENTER] = DAILY | [RIGHT] = 15-MIN
Ignore any text labels, colored markers, or ticker identifiers on the charts.

Data (pre-computed — use directly, do not derive additional statistics):
Last close: {close}
5-day log returns: [{r1}, {r2}, {r3}, {r4}, {r5}]
Price vs VWMA distance: {dist}%
Momentum z-score: {z}

Treat as a synthetic price series. Do not use prior knowledge of any company, sector, or market event.

Heikin-Ashi signals: consecutive same-color candles = active trend; shrinking bodies with long wicks on both sides = exhaustion zone; first opposite-color candle = potential reversal.

For each timeframe (weekly, then daily, then 15-min), classify the trend as increasing, decreasing, stabilizing, or fluctuating. Assess cross-timeframe alignment. Identify visual support/resistance levels and momentum state. Cross-check against the data: log return direction vs. visual trend, VWMA distance suggesting continuation or mean reversion, z-score indicating normal or extreme momentum.

Predict the next 5 daily closing prices.
Output ONLY a JSON array — no other text:
[d1, d2, d3, d4, d5]"""


# =============================================================================
# Numba JIT functions
# =============================================================================

@numba.jit(nopython=True, nogil=True, cache=False)
def _vwma_core(close, volume, window):
    """Volume-Weighted Moving Average — rolling, O(n)."""
    n = close.shape[0]
    out = np.empty(n, dtype=np.float32)
    for i in range(n):
        out[i] = np.nan
    csum = np.float32(0.0)
    vsum = np.float32(0.0)
    for i in range(n):
        csum += close[i] * volume[i]
        vsum += volume[i]
        if i >= window:
            csum -= close[i - window] * volume[i - window]
            vsum -= volume[i - window]
        if i >= window - 1 and vsum != 0.0:
            out[i] = csum / vsum
    return out


@numba.jit(nopython=True, nogil=True, cache=False)
def _log_returns_last_n(close, n):
    """Last n daily *log* returns as fractions (not %)."""
    out = np.empty(n, dtype=np.float32)
    s = close.shape[0] - n
    for i in range(n):
        out[i] = np.log(close[s + i] / close[s + i - 1])
    return out


@numba.jit(nopython=True, nogil=True, cache=False)
def _rolling_momentum(close, period, out_len):
    """Compute the last `out_len` momentum values (close[i] - close[i-period])."""
    out = np.empty(out_len, dtype=np.float32)
    start = close.shape[0] - out_len
    for i in range(out_len):
        out[i] = close[start + i] - close[start + i - period]
    return out


# =============================================================================
# Data helpers
# =============================================================================

def to_f32_1d(s) -> np.ndarray:
    """Flatten any DataFrame / Series to contiguous float32 1-D array."""
    arr = np.ascontiguousarray(np.ravel(s.to_numpy(dtype=np.float32)))
    return arr


def download_ticker(ticker: str, interval: str, period: str) -> pd.DataFrame:
    """Download with retries; validate the interval matches the data.

    Uses auto_adjust=True and repair=False to avoid yfinance
    KeyError('Stock Splits') bug present in some versions.
    """
    for attempt in range(RETRY_MAX):
        try:
            df = yf.download(
                ticker,
                interval=interval,
                period=period,
                threads=True,
                progress=False,
                auto_adjust=True,
            )
            if df.empty:
                raise ValueError(f"Empty dataframe returned for {ticker} {interval}")
            df = validate_and_fix_interval(df, interval, ticker)
            return df
        except Exception as exc:
            log.warning("Download attempt %d/%d failed for %s %s: %s",
                        attempt + 1, RETRY_MAX, ticker, interval, exc)
            time.sleep(1 * (2 ** attempt))
    raise RuntimeError(f"Download failed after {RETRY_MAX} retries: {ticker} {interval}")


def validate_and_fix_interval(df: pd.DataFrame, interval: str,
                               ticker: str) -> pd.DataFrame:
    """Ensure the data actually matches the requested interval.

    yfinance sometimes silently returns daily data when intraday fails.
    We detect this by checking the median time-delta between consecutive bars.
    Compares total_seconds() to avoid Timedelta type issues.
    """
    if interval in ("1wk", "1d"):
        return df  # daily and weekly are reliable

    # Expected timedelta in seconds for intraday intervals
    expected_sec = {"15m": 15 * 60, "5m": 5 * 60, "1h": 3600}
    if interval not in expected_sec:
        return df

    # Compute median delta in seconds (skip NaNs / gaps from weekends)
    deltas = pd.Series(df.index).diff().dropna()
    median_sec = deltas.median().total_seconds()

    # If median delta is much larger than expected, data is wrong
    if median_sec > expected_sec[interval] * 10:
        log.warning("Interval mismatch for %s %s: median_delta=%.0fs, expected=%ds. "
                     "Retrying with group_by='ticker'...",
                     ticker, interval, median_sec, expected_sec[interval])
        # Retry with explicit group_by to force correct interval
        df2 = yf.download(
            ticker,
            interval=interval,
            period="60d",
            threads=False,
            progress=False,
            auto_adjust=True,
            repair=False,
            group_by="ticker",
        )
        if not df2.empty:
            # Extract the ticker sub-frame if MultiIndex
            if isinstance(df2.columns, pd.MultiIndex):
                df2 = df2[ticker]
            deltas2 = pd.Series(df2.index).diff().dropna()
            median_sec2 = deltas2.median().total_seconds()
            if median_sec2 <= expected_sec[interval] * 10:
                log.info("Retry succeeded for %s %s", ticker, interval)
                return df2
        # If retry also fails, raise — do NOT silently use daily data
        raise ValueError(
            f"Could not obtain valid {interval} data for {ticker}. "
            f"Last bar spacing: {median_sec}s"
        )
    return df


def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Convert standard OHLC to Heikin-Ashi OHLC.

    HA_Close = (O + H + L + C) / 4
    HA_Open  = (prev_HA_Open + prev_HA_Close) / 2  (first = (O+C)/2)
    HA_High  = max(H, HA_Open, HA_Close)
    HA_Low   = min(L, HA_Open, HA_Close)
    """
    o = df["Open"].to_numpy(dtype=np.float64).ravel()
    h = df["High"].to_numpy(dtype=np.float64).ravel()
    l = df["Low"].to_numpy(dtype=np.float64).ravel()
    c = df["Close"].to_numpy(dtype=np.float64).ravel()
    n = len(c)

    ha_c = (o + h + l + c) / 4.0
    ha_o = np.empty(n, dtype=np.float64)
    ha_o[0] = (o[0] + c[0]) / 2.0
    for i in range(1, n):
        ha_o[i] = (ha_o[i - 1] + ha_c[i - 1]) / 2.0
    ha_h = np.maximum(h, np.maximum(ha_o, ha_c))
    ha_l = np.minimum(l, np.minimum(ha_o, ha_c))

    out = pd.DataFrame(index=df.index)
    out["Open"]  = ha_o.astype(np.float32)
    out["High"]  = ha_h.astype(np.float32)
    out["Low"]   = ha_l.astype(np.float32)
    out["Close"] = ha_c.astype(np.float32)
    return out


# =============================================================================
# Chart generation — 3 separate images, dark background
# =============================================================================

def _plot_single_ha(df_ha, vwma_line, path, dpi=IMAGE_DPI):
    """Plot one Heikin-Ashi chart with VWMA overlay on dark background.

    Uses batched LineCollection + PatchCollection instead of per-candle
    draw calls — ~3-5x faster for 100-bar charts.
    """
    from matplotlib.collections import LineCollection, PatchCollection
    from matplotlib.patches import Rectangle

    o = df_ha["Open"].to_numpy(dtype=np.float32).ravel()
    h = df_ha["High"].to_numpy(dtype=np.float32).ravel()
    l = df_ha["Low"].to_numpy(dtype=np.float32).ravel()
    c = df_ha["Close"].to_numpy(dtype=np.float32).ravel()
    n = len(c)
    x = np.arange(n, dtype=np.float32)
    vv = np.asarray(vwma_line, dtype=np.float32).ravel()

    fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi, facecolor="#0d1117")
    ax.set_facecolor("#0d1117")

    # ── Batch wicks as LineCollection ─────────────────────────────────
    wick_segs = [[(x[j], l[j]), (x[j], h[j])] for j in range(n)]
    wick_col = LineCollection(wick_segs, colors="#8b949e", linewidths=0.5)
    ax.add_collection(wick_col)

    # ── Batch bodies as PatchCollection ───────────────────────────────
    rects, colors = [], []
    for j in range(n):
        lower = float(min(o[j], c[j]))
        height = float(abs(c[j] - o[j]))
        if height < 1e-6:
            height = 0.1  # doji
        rects.append(Rectangle((x[j] - 0.3, lower), 0.6, height))
        colors.append("#3fb950" if c[j] >= o[j] else "#f85149")
    body_col = PatchCollection(rects, facecolors=colors, edgecolors=colors,
                               linewidths=0)
    ax.add_collection(body_col)

    # ── VWMA line ─────────────────────────────────────────────────────
    ax.plot(x, vv, color="#58a6ff", linewidth=1.2, alpha=0.85)

    ax.set_xlim(-1, n)
    ax.set_ylim(float(np.nanmin(l)) * 0.995, float(np.nanmax(h)) * 1.005)
    ax.set_axis_off()
    fig.savefig(path, bbox_inches="tight", pad_inches=0,
                facecolor=fig.get_facecolor())
    plt.close(fig)


def generate_chart_images(weekly, daily, intraday,
                          vw_w, vw_d, vw_i, ticker_tag) -> list:
    """Generate 3 separate Heikin-Ashi + VWMA chart PNGs.
    Returns list of file paths [weekly.png, daily.png, intraday.png].
    """
    # Take last CHART_BARS rows
    w  = weekly.tail(CHART_BARS)
    d  = daily.tail(CHART_BARS)
    i_ = intraday.tail(CHART_BARS)

    # Convert to Heikin-Ashi
    w_ha = heikin_ashi(w)
    d_ha = heikin_ashi(d)
    i_ha = heikin_ashi(i_)

    paths = []
    for label, df_ha, vw in [("wk", w_ha, vw_w[-CHART_BARS:]),
                              ("dy", d_ha, vw_d[-CHART_BARS:]),
                              ("15", i_ha, vw_i[-CHART_BARS:])]:
        p = f"/tmp/vista_{ticker_tag}_{label}.png"
        _plot_single_ha(df_ha, vw, p)
        paths.append(p)
    return paths


# =============================================================================
# Metrics computation
# =============================================================================

def compute_metrics(dc, dv):
    """Return dict of all metrics needed for the PROMPT.

    All metrics are daily-centric (consistent with the prompt's intent).
    Parameters: dc=daily close, dv=daily volume (float32 arrays).

    Returns: close, r1..r5, dist, z
    """
    # ── VWMA (daily) ──
    vw_d = _vwma_core(dc, dv, VWMA_WINDOW)

    # ── 5-day log returns (fractional) ──
    r5 = _log_returns_last_n(dc, 5)

    # ── Price vs VWMA distance (daily close vs daily VWMA) ──
    dist = (dc[-1] / vw_d[-1] - 1.0) * 100.0

    # ── Momentum z-score ──
    # Build a rolling momentum series and normalise
    lookback = min(MOM_ZSCORE_WINDOW, len(dc) - MOM_PERIOD)
    if lookback < 2:
        z = 0.0
    else:
        mom_series = _rolling_momentum(dc, MOM_PERIOD, lookback)
        mu = np.mean(mom_series)
        sigma = np.std(mom_series)
        z = (mom_series[-1] - mu) / sigma if sigma > 1e-8 else 0.0

    return {
        "close": float(dc[-1]),
        "r1": round(float(r5[0]), 4),
        "r2": round(float(r5[1]), 4),
        "r3": round(float(r5[2]), 4),
        "r4": round(float(r5[3]), 4),
        "r5": round(float(r5[4]), 4),
        "dist": round(float(dist), 2),
        "z": round(float(z), 2),
    }


# =============================================================================
# VLM call
# =============================================================================

def parse_vlm_array(text: str) -> list:
    """Robustly extract a JSON array of 5 floats from VLM response.

    Handles: None content, markdown fences, surrounding prose,
    nested brackets, reasoning_content fallback, etc.
    """
    if text is None:
        raise ValueError("VLM returned None content")

    if not isinstance(text, str):
        text = str(text)

    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Try every bracket-delimited substring
    for m in re.finditer(r"\[[^\]]*\]", text):
        try:
            arr = json.loads(m.group())
            if isinstance(arr, list) and len(arr) == 5:
                return [float(x) for x in arr]
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    # Fallback: try the whole text as JSON
    try:
        arr = json.loads(text)
        if isinstance(arr, list) and len(arr) == 5:
            return [float(x) for x in arr]
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    raise ValueError(f"No valid 5-element JSON array found in VLM response: {text[:300]}")


def _extract_response_text(resp_json: dict) -> str:
    """Extract the model's text response from an OpenRouter API response.

    Handles reasoning models that may return content=None with the answer
    in a different field. Tries multiple field names for maximum compatibility.
    """
    msg = resp_json.get("choices", [{}])[0].get("message", {})

    # Primary: standard content field
    content = msg.get("content")
    if content is not None:
        return content

    # Fallback for reasoning models: try various field names
    for key in ("reasoning_content", "reasoning", "thinking"):
        val = msg.get(key)
        if val is not None:
            log.info("VLM content was None, extracted from message.%s", key)
            return val

    # Last resort: log the full response structure for debugging
    log.warning("VLM returned no usable content. Response keys: %s",
                list(msg.keys()))
    log.debug("Full response: %s", json.dumps(resp_json, indent=2)[:500])
    return None


def call_vlm(img_paths: list, metrics: dict,
             api_key=None, model_key=None) -> list:
    """Send prompt + 3 images to VLM via OpenRouter.
    Returns list of 5 predicted prices.
    
    TASK 2: No fallback to random-walk. Raises exception on failure.
    """
    if api_key is None:
        api_key = _GET_API_KEY()
    if not api_key:
        # TASK 2: Raise error instead of fallback
        raise RuntimeError(
            "CRITICAL: No OPENROUTER_API_KEY found. "
            "Set OPENROUTER_API_KEY environment variable or Colab Secret. "
            "Cannot proceed without API key."
        )

    # Select model configuration
    if model_key is None:
        model_key = VLM_MODEL
    mcfg = VLM_MODELS.get(model_key)
    if mcfg is None:
        raise ValueError(f"Unknown model key '{model_key}'. "
                         f"Available: {list(VLM_MODELS.keys())}")

    # Build the prompt text with all fields properly filled
    prompt_text = PROMPT.format(
        close=metrics["close"],
        r1=metrics["r1"],
        r2=metrics["r2"],
        r3=metrics["r3"],
        r4=metrics["r4"],
        r5=metrics["r5"],
        dist=metrics["dist"],
        z=metrics["z"],
    )

    # Build content: text + 3 images
    content = [{"type": "text", "text": prompt_text}]
    for p in img_paths:
        b64 = base64.b64encode(open(p, "rb").read()).decode()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"}
        })

    body = {
        "model": mcfg["id"],
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.7,
        "max_tokens": mcfg["max_tokens"],
    }
    # Only add reasoning param for models that support it
    if mcfg.get("reasoning"):
        body["reasoning"] = {"enabled": True, "max_tokens": 4096}

    hdr = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "VISTA",
    }

    # TASK 1 FIX: Removed trailing space from URL
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=hdr,
        json=body,
        timeout=TIMEOUT_VLM,
    )
    r.raise_for_status()
    resp_json = r.json()

    # Extract response text, handling reasoning models that return content=None
    raw = _extract_response_text(resp_json)
    return parse_vlm_array(raw)


def ensemble_vlm(img_paths: list, metrics: dict, n: int = N_ENSEMBLE) -> list:
    """Call VLM n times in parallel, return median consensus.
    
    TASK 2: No fallback to naive forecast. Raises exception if all calls fail.
    """
    api_key = _GET_API_KEY()
    results = []
    errors = []
    
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(call_vlm, img_paths, metrics, api_key, VLM_MODEL)
                   for _ in range(n)]
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception as exc:
                errors.append(str(exc))
                log.warning("VLM call failed: %s", exc)
    
    if not results:
        # TASK 2: Raise error instead of fallback
        error_summary = "; ".join(errors[:3])  # Show first 3 errors
        raise RuntimeError(
            f"CRITICAL: All {n} VLM calls failed. "
            f"Errors: {error_summary}. "
            "Check API key, model availability, and network connectivity. "
            "Cannot proceed without valid VLM response."
        )
    
    med = [round(median([r[i] for r in results]), 2) for i in range(5)]
    return med


# =============================================================================
# Per-ticker pipeline
# =============================================================================

def process_ticker(ticker: str) -> dict:
    """Full pipeline for one ticker: download → compute → chart → VLM → forecast."""
    log.info("▶ Processing %s", ticker)
    t0 = time.perf_counter()

    # ── 1. Download 3 timeframes in parallel ──────────────────────────────
    with ThreadPoolExecutor(max_workers=3) as pool:
        fw = pool.submit(download_ticker, ticker, "1wk", PERIOD_WEEKLY)
        fd = pool.submit(download_ticker, ticker, "1d", PERIOD_DAILY)
        fi = pool.submit(download_ticker, ticker, "15m", PERIOD_15M)
        weekly  = fw.result()
        daily   = fd.result()
        intraday = fi.result()

    # ── 2. Extract close & volume arrays ──────────────────────────────────
    wc, wv = to_f32_1d(weekly["Close"]),  to_f32_1d(weekly["Volume"])
    dc, dv = to_f32_1d(daily["Close"]),   to_f32_1d(daily["Volume"])
    ic, iv = to_f32_1d(intraday["Close"]), to_f32_1d(intraday["Volume"])

    # ── 3. Compute VWMA lines ────────────────────────────────────────────
    vw_w = _vwma_core(wc, wv, VWMA_WINDOW)
    vw_d = _vwma_core(dc, dv, VWMA_WINDOW)
    vw_i = _vwma_core(ic, iv, VWMA_WINDOW)

    # ── 4. Compute metrics ───────────────────────────────────────────────
    metrics = compute_metrics(dc, dv)
    log.info("  %s metrics: close=%.2f  dist=%.2f%%  z=%.2f",
             ticker, metrics["close"], metrics["dist"], metrics["z"])

    # ── 5. Generate 3 chart images ───────────────────────────────────────
    img_paths = generate_chart_images(weekly, daily, intraday,
                                      vw_w, vw_d, vw_i, ticker)

    # ── 6. Ensemble VLM calls ────────────────────────────────────────────
    forecast = ensemble_vlm(img_paths, metrics, N_ENSEMBLE)

    elapsed = time.perf_counter() - t0
    log.info("  %s forecast: %s  (%.1fs)", ticker, forecast, elapsed)

    return {"ticker": ticker, "forecast": forecast}


# =============================================================================
# Output formatting
# =============================================================================

def _fmt_num(v) -> str:
    """Format float with comma as decimal separator, no thousand separator."""
    if v is None:
        return "N/A"
    # f-string with no grouping, then swap . → ,
    return f"{v:.2f}".replace(".", ",")


def format_results_table(results: list) -> str:
    """Format results as a table with comma decimal separator."""
    cols = ["Ticker", "D+1", "D+2", "D+3", "D+4", "D+5"]
    rows = []
    for r in sorted(results, key=lambda x: x["ticker"]):
        f = r["forecast"]
        cells = [r["ticker"]] + [_fmt_num(v) for v in f]
        rows.append("  ".join(f"{c:>10}" for c in cells))

    header = "  ".join(f"{c:>10}" for c in cols)
    sep = "  ".join("\u2500" * 10 for _ in cols)
    return "\n".join([header, sep] + rows)


# =============================================================================
# Main
# =============================================================================

def main():
    tickers = TICKERS_INPUT.strip().split()
    if not tickers:
        print("No tickers provided. Set TICKERS_INPUT at the top of the script.")
        return

    model_info = VLM_MODELS.get(VLM_MODEL, {})
    log.info("VISTA VLM — model: %s (%s) — tickers: %s",
             VLM_MODEL, model_info.get("id", "?"), tickers)

    # Process tickers in parallel (each independent to prevent anchoring)
    results = []
    critical_error = None
    
    with ThreadPoolExecutor(max_workers=min(len(tickers), 4)) as pool:
        futures = {pool.submit(process_ticker, t): t for t in tickers}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                ticker = futures[fut]
                log.error("Failed for %s: %s", ticker, exc)
                # TASK 2: Store critical error and stop processing
                critical_error = exc
                break  # Stop processing further tickers on critical error

    # TASK 2: If critical error occurred, output error message and exit
    if critical_error is not None:
        print("\n" + "="*70)
        print("EXECUTION TERMINATED DUE TO CRITICAL ERROR")
        print("="*70)
        print(f"Error: {critical_error}")
        print("="*70)
        print("The script cannot continue without valid VLM responses.")
        print("Please check:")
        print("  1. OPENROUTER_API_KEY is set correctly")
        print("  2. Network connectivity to openrouter.ai")
        print("  3. Model availability on OpenRouter")
        print("="*70)
        sys.exit(1)

    if not results:
        print("\nNo results obtained. Exiting.")
        sys.exit(1)

    print(f"\nModel: {model_info.get('id', VLM_MODEL)}")
    print(format_results_table(results))

    # Also output as CSV-friendly
    print("\n--- CSV ---")
    for r in sorted(results, key=lambda x: x["ticker"]):
        f = r["forecast"]
        vals = ";".join(
            f"{v:.2f}".replace(".", ",") if v is not None else "N/A"
            for v in f
        )
        print(f"{r['ticker']};{vals}")


if __name__ == "__main__":
    main()
