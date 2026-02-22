from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import schedule
import yfinance as yf
from hmmlearn.hmm import GaussianHMM
from numba import njit

# ═══════════════════════════════════════════════════════════════
#  USER CONFIG — edit only this section
# ═══════════════════════════════════════════════════════════════
TICKERS: list[str] = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA",
    "PBR", "VALE", "ITUB", "BBD", "A1LB34.SA", "ALB",
]
PARITY: dict[str, tuple[str, None]] = {
    "PETR4.SA": ("PBR", None),
    "VALE3.SA": ("VALE", None),
    "ITUB4.SA": ("ITUB", None),
    "BBDC4.SA": ("BBD", None),
    "A1LB34.SA": ("ALB", None),
}
FX_TICKER: str = "BRL=X"
PARITY_RECOMPUTE_THIS_CYCLE: bool = True

LINREG_BARS: int = 250
LINREG_SLOPE_THRESHOLD: float = 0.02
LINREG_R2_THRESHOLD: float = 0.25
LINREG_SOURCE: str = "close"

FLOWER_N: int = 5
FLOWER_OB: float = 200.0
FLOWER_OS: float = -200.0
FLOWER_VOL_SMA: int = 20
FLOWER_VOL_THRESH: float = 1.2
FLOWER_VWAP_MUL: float = 1.5
VWAP_ROLLING_DAYS: int = 5

W_OU_FPT: float = 0.25
W_HURST: float = 0.20
W_HMM: float = 0.18
W_SKEW: float = 0.12
W_LIQUIDITY: float = 0.10
W_CVD: float = 0.15

MAX_NAN_FRACTION: float = 0.05
MIN_BARS_4H: int = 60
MIN_BARS_1MIN: int = 200
MIN_VOL_DAILY_USD: float = 1e6
MAX_SPREAD_PROXY: float = 0.015
ZERO_VOL_MAX_FRAC: float = 0.02

OU_CALIB_BARS_MIN: int = 120
FPT_MIN_EVENTS: int = 5
FPT_FALLBACK_BARS: int = 100
FPT_MAX_HORIZON_BARS: int = 600
FPT_PERCENTILE: float = 75.0
MIN_COMPLETION_RATE: float = 0.30

HURST_WIN_4H: int = 100
HURST_WIN_1MIN: int = 500
HMM_TRAIN_BARS_MIN: int = 200
CVD_WINDOW: int = 30
CVD_NORM_WINDOW: int = 60
SKEW_WINDOW_1MIN: int = 500

ENTRY_MIN_SCORE: float = 0.60
ENTRY_FLOWER_LEVEL: float = -200.0
REENTRY_COOLDOWN: int = 60
MAX_HOLD_BARS: int = 7200

RUN_INTERVAL_HOURS: int = 4
SCORE_NORM_METHOD: str = "rank"
FETCH_BATCH_SIZE: int = 10

DRIVE_CACHE_ENABLED: bool = True
DRIVE_CACHE_DIR: str = "/content/drive/MyDrive/flower_cache"
CACHE_SAFETY_FACTOR: float = 1.5
CACHE_MAX_AGE_DAYS: int = 30
FORCE_FULL_FETCH: bool = False
# ═══════════════════════════════════════════════════════════════

DTYPE_F32 = np.float32
EPS_F64 = 1e-12
BARS_PER_TRADING_DAY_1MIN = 390
FETCH_MAX_WORKERS_CAP = 8
FETCH_4H_OVERLAP_HOURS = 8


@njit(nogil=True)
def ema_numba(values: np.ndarray, period: int) -> np.ndarray:
    alpha = np.float32(2.0 / (period + 1.0))
    out = np.empty(values.size, dtype=np.float32)
    out[0] = values[0]
    for i in range(1, values.size):
        out[i] = out[i - 1] + alpha * (values[i] - out[i - 1])
    return out


@njit(nogil=True)
def rolling_std_numba(values: np.ndarray, window: int) -> np.ndarray:
    n = values.size
    out = np.empty(n, dtype=np.float32)
    csum = np.empty(n + 1, dtype=np.float64)
    csum2 = np.empty(n + 1, dtype=np.float64)
    csum[0] = 0.0
    csum2[0] = 0.0
    for i in range(n):
        v = float(values[i])
        csum[i + 1] = csum[i] + v
        csum2[i + 1] = csum2[i] + v * v
    for i in range(n):
        left = 0 if i + 1 < window else i + 1 - window
        count = i + 1 - left
        s = csum[i + 1] - csum[left]
        s2 = csum2[i + 1] - csum2[left]
        mean = s / count
        var = max(0.0, s2 / count - mean * mean)
        out[i] = np.float32(math.sqrt(var))
    return out


@njit(nogil=True)
def flower_oscillator_numba(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> tuple[np.ndarray, np.ndarray]:
    ys1 = (high + low + close + close) * np.float32(0.25)
    rk3 = ema_numba(ys1, period)
    rk4 = rolling_std_numba(ys1, period)
    rk5 = np.empty(close.size, dtype=np.float32)
    for i in range(close.size):
        rk5[i] = (ys1[i] - rk3[i]) * np.float32(200.0) / (rk4[i] + np.float32(1e-8))
    rk6 = ema_numba(rk5, period)
    up = ema_numba(rk6, period)
    down = ema_numba(up, period)
    return up, down


@njit(nogil=True)
def rolling_vwap_numba(close: np.ndarray, volume: np.ndarray, window: int) -> np.ndarray:
    n = close.size
    out = np.empty(n, dtype=np.float32)
    dv = np.empty(n, dtype=np.float64)
    cum_dv = np.empty(n + 1, dtype=np.float64)
    cum_v = np.empty(n + 1, dtype=np.float64)
    cum_dv[0] = 0.0
    cum_v[0] = 0.0
    for i in range(n):
        dv[i] = float(close[i]) * float(volume[i])
        cum_dv[i + 1] = cum_dv[i] + dv[i]
        cum_v[i + 1] = cum_v[i] + float(volume[i])
    for i in range(n):
        left = 0 if i + 1 < window else i + 1 - window
        num = cum_dv[i + 1] - cum_dv[left]
        den = cum_v[i + 1] - cum_v[left]
        out[i] = np.float32(num / (den + EPS_F64))
    return out


def config_dict() -> dict[str, Any]:
    return {k: v for k, v in globals().items() if k.isupper() and not k.startswith("DTYPE") and not k.startswith("EPS")}


def validate_config() -> None:
    assert LINREG_BARS >= 20
    assert LINREG_SLOPE_THRESHOLD >= 0.0
    assert 0.0 <= LINREG_R2_THRESHOLD <= 1.0
    assert LINREG_SOURCE in {"close", "hlc3", "ohlc4"}
    assert FETCH_BATCH_SIZE >= 1
    assert CACHE_SAFETY_FACTOR >= 1.0
    assert CACHE_MAX_AGE_DAYS >= 1
    assert FPT_MAX_HORIZON_BARS <= MAX_HOLD_BARS


def compute_cache_windows() -> tuple[int, int]:
    max_4h = math.ceil(max(LINREG_BARS, OU_CALIB_BARS_MIN, HMM_TRAIN_BARS_MIN, HURST_WIN_4H, CVD_NORM_WINDOW) * CACHE_SAFETY_FACTOR)
    vwap_bars = VWAP_ROLLING_DAYS * BARS_PER_TRADING_DAY_1MIN
    max_1m = math.ceil(max(HURST_WIN_1MIN, SKEW_WINDOW_1MIN, MIN_BARS_1MIN, vwap_bars, FPT_MAX_HORIZON_BARS * 3) * CACHE_SAFETY_FACTOR)
    return max_4h, max_1m


def cfg_hash(cfg: dict[str, Any]) -> str:
    excluded = {"DRIVE_CACHE_DIR", "CACHE_MAX_AGE_DAYS", "FORCE_FULL_FETCH", "SCORE_NORM_METHOD", "RUN_INTERVAL_HOURS", "FETCH_BATCH_SIZE", "PARITY_RECOMPUTE_THIS_CYCLE"}
    relevant = {k: v for k, v in cfg.items() if k not in excluded}
    payload = json.dumps(relevant, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def init_cache(cfg: dict[str, Any]) -> dict[str, Any]:
    if DRIVE_CACHE_ENABLED:
        from google.colab import drive
        drive.mount("/content/drive", force_remount=False)
    cache_dir = Path(DRIVE_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    hash_file = cache_dir / "_config_hash.txt"
    current_hash = cfg_hash(cfg)
    if hash_file.exists() and hash_file.read_text().strip() != current_hash and not FORCE_FULL_FETCH:
        for file in cache_dir.glob("*.parquet"):
            file.unlink(missing_ok=True)
    hash_file.write_text(current_hash)
    meta_file = cache_dir / "_meta.json"
    parity_file = cache_dir / "_parity.json"
    meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    parity_cache = json.loads(parity_file.read_text()) if parity_file.exists() else {}
    return {"dir": cache_dir, "meta": meta, "meta_file": meta_file, "parity_file": parity_file, "parity_cache": parity_cache}


def save_cache_state(state: dict[str, Any]) -> None:
    state["meta_file"].write_text(json.dumps(state["meta"], sort_keys=True))
    state["parity_file"].write_text(json.dumps(state["parity_cache"], sort_keys=True))


def fetch_raw(ticker: str, interval: str, period: str | None, start: datetime | None) -> pd.DataFrame:
    kwargs = {"interval": interval, "repair": True, "auto_adjust": True, "prepost": False, "progress": False}
    if period is not None:
        kwargs["period"] = period
    if start is not None:
        kwargs["start"] = start
    df = yf.download(ticker, **kwargs)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    if len(df) == 0:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    return df[["Open", "High", "Low", "Close", "Volume"]].copy()


def ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return df.sort_index()


def fetch_and_cache_interval(ticker: str, interval: str, max_bars: int, state: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    cache_file = state["dir"] / f"{ticker}_{interval}.parquet"
    if FORCE_FULL_FETCH or not cache_file.exists():
        period = "8d" if interval == "1m" else "2y"
        fresh = ensure_utc_index(fetch_raw(ticker, interval, period, None)).iloc[-max_bars:]
        fresh.to_parquet(cache_file)
        state["meta"][f"{ticker}:{interval}"] = fresh.index[-1].isoformat() if len(fresh) else ""
        return fresh, "FORCED" if FORCE_FULL_FETCH else "COLD"
    age_days = (time.time() - cache_file.stat().st_mtime) / 86400.0
    if age_days > CACHE_MAX_AGE_DAYS:
        fresh = ensure_utc_index(fetch_raw(ticker, interval, "8d" if interval == "1m" else "2y", None)).iloc[-max_bars:]
        fresh.to_parquet(cache_file)
        state["meta"][f"{ticker}:{interval}"] = fresh.index[-1].isoformat() if len(fresh) else ""
        return fresh, "STALE"
    cached = ensure_utc_index(pd.read_parquet(cache_file))
    start = None if interval == "1m" else cached.index[-1].to_pydatetime() - timedelta(hours=FETCH_4H_OVERLAP_HOURS)
    period = "2d" if interval == "1m" else None
    new = ensure_utc_index(fetch_raw(ticker, interval, period, start))
    combined = pd.concat([cached, new]) if len(new) else cached
    combined = combined[~combined.index.duplicated(keep="last")].sort_index().iloc[-max_bars:]
    combined.to_parquet(cache_file)
    state["meta"][f"{ticker}:{interval}"] = combined.index[-1].isoformat() if len(combined) else ""
    return combined, "INCREMENTAL"


def select_source(df: pd.DataFrame) -> np.ndarray:
    close = df["Close"].to_numpy(dtype=np.float64)
    if LINREG_SOURCE == "close":
        return close
    if LINREG_SOURCE == "hlc3":
        return ((df["High"].to_numpy(dtype=np.float64) + df["Low"].to_numpy(dtype=np.float64) + close) / 3.0)
    return ((df["Open"].to_numpy(dtype=np.float64) + df["High"].to_numpy(dtype=np.float64) + df["Low"].to_numpy(dtype=np.float64) + close) / 4.0)


def ols_slope_r2_percent(prices: np.ndarray) -> tuple[float, float]:
    p = prices[-LINREG_BARS:].astype(np.float64, copy=False)
    n = p.size
    if n < 10:
        return 0.0, 0.0
    t = np.arange(n, dtype=np.float64) - (n - 1) / 2.0
    p_mean = float(p.mean())
    t_ss = float((t * t).sum())
    if t_ss < EPS_F64 or p_mean < EPS_F64:
        return 0.0, 0.0
    beta = float((t * (p - p_mean)).sum() / t_ss)
    slope_pct = (beta / p_mean) * 100.0
    r = float(np.corrcoef(t, p)[0, 1])
    return slope_pct, r * r


def qc_hard(df4h: pd.DataFrame, df1m: pd.DataFrame) -> tuple[bool, str]:
    if len(df4h) < MIN_BARS_4H or len(df1m) < MIN_BARS_1MIN:
        return False, "insufficient-bars"
    nan_frac = max(float(df4h.isna().mean().mean()), float(df1m.isna().mean().mean()))
    if nan_frac > MAX_NAN_FRACTION:
        return False, "nan-fraction"
    zero_vol = float((df1m["Volume"] <= 0).mean())
    if zero_vol > ZERO_VOL_MAX_FRAC:
        return False, "zero-vol"
    if not df4h.index.is_monotonic_increasing or not df1m.index.is_monotonic_increasing:
        return False, "index-order"
    return True, "ok"


def compute_parity_factors(state: dict[str, Any]) -> dict[str, float]:
    cached = state["parity_cache"]
    if not PARITY_RECOMPUTE_THIS_CYCLE and cached:
        return {k: float(v) for k, v in cached.items()}
    fx = float(fetch_raw(FX_TICKER, "1d", "5d", None)["Close"].iloc[-1])
    factors: dict[str, float] = {}
    for b3, (us, _) in PARITY.items():
        b3_px = float(fetch_raw(b3, "1d", "5d", None)["Close"].iloc[-1])
        us_px = float(fetch_raw(us, "1d", "5d", None)["Close"].iloc[-1])
        factors[b3] = (b3_px / us_px) / fx if us_px > 0 else 1.0
    state["parity_cache"] = factors
    return factors


def skewness(values: np.ndarray) -> float:
    v = values.astype(np.float64)
    m = float(v.mean())
    s = float(v.std())
    if s < EPS_F64:
        return 0.0
    z = (v - m) / s
    return float((z * z * z).mean())


def hurst_rs(values: np.ndarray) -> float:
    v = values.astype(np.float64)
    m = float(v.mean())
    d = np.cumsum(v - m)
    r = float(d.max() - d.min())
    s = float(v.std())
    if s < EPS_F64 or len(v) < 20:
        return 0.5
    return max(0.0, min(1.0, math.log((r / s) + EPS_F64) / math.log(len(v))))


def cvd_score(close: np.ndarray, volume: np.ndarray) -> float:
    d = np.sign(np.diff(close, prepend=close[0]))
    cvd = np.cumsum(d * volume)
    tail = cvd[-CVD_NORM_WINDOW:]
    return float((tail[-1] - tail.mean()) / (tail.std() + EPS_F64))


def fpt_calibration(up: np.ndarray) -> tuple[int, float, int, float, int]:
    os_entries = np.where((up[1:] <= FLOWER_OS) & (up[:-1] > FLOWER_OS))[0] + 1
    if len(os_entries) == 0:
        return FPT_FALLBACK_BARS, 1.0, 0, float(FPT_FALLBACK_BARS), 0
    filtered = [int(os_entries[0])]
    for idx in os_entries[1:]:
        if idx - filtered[-1] >= REENTRY_COOLDOWN:
            filtered.append(int(idx))
    times: list[int] = []
    complete = 0
    for start in filtered:
        end = min(up.size, start + FPT_MAX_HORIZON_BARS)
        segment = up[start:end]
        hits = np.where((segment[1:] >= FLOWER_OB) & (segment[:-1] < FLOWER_OB))[0]
        if hits.size:
            complete += 1
            times.append(int(hits[0] + 1))
    n_events = len(filtered)
    completion = complete / max(1, n_events)
    if n_events < FPT_MIN_EVENTS or not times:
        return FPT_FALLBACK_BARS, 1.0, n_events, float(FPT_FALLBACK_BARS), 0
    horizon = int(np.percentile(np.array(times, dtype=np.float64), FPT_PERCENTILE))
    median = float(np.median(np.array(times, dtype=np.float64)))
    trap = 1 if completion < MIN_COMPLETION_RATE else 0
    return horizon, completion, n_events, median, trap


def ou_score_from_up(up: np.ndarray, horizon: int, completion: float, trap: int) -> float:
    x = up.astype(np.float64)
    dx = np.diff(x)
    x1 = x[:-1]
    denom = float((x1 * x1).sum()) + EPS_F64
    phi = float((x1 * x[1:]).sum() / denom)
    phi = min(max(phi, 1e-4), 0.9999)
    sigma = float(np.std(dx - (phi - 1.0) * x1)) + EPS_F64
    z = abs(FLOWER_OB - FLOWER_OS) / (sigma * math.sqrt(max(1, horizon)))
    fpt_prob = float(math.erfc(z / math.sqrt(2.0)))
    if trap:
        return 0.0
    return fpt_prob * math.sqrt(max(0.0, completion))


def hmm_expand_prob(close_4h: np.ndarray) -> float:
    ret2 = np.diff(np.log(close_4h.astype(np.float64) + EPS_F64)) ** 2
    x = ret2.reshape(-1, 1)
    if x.shape[0] < HMM_TRAIN_BARS_MIN:
        return 0.5
    model = GaussianHMM(n_components=2, covariance_type="diag", n_iter=100)
    model.fit(x)
    state = model.predict(x)[-1]
    trans = model.transmat_[state]
    other = 1 - state
    return float(trans[other])


def liquidity_score(df4h: pd.DataFrame) -> float:
    close = df4h["Close"].to_numpy(dtype=np.float64)
    volume = df4h["Volume"].to_numpy(dtype=np.float64)
    dollar_vol = float(np.mean(close[-20:] * volume[-20:]))
    spread = float(np.mean((df4h["High"] - df4h["Low"]) / (df4h["Close"] + EPS_F64)))
    vol_term = min(1.0, dollar_vol / MIN_VOL_DAILY_USD)
    spread_term = max(0.0, 1.0 - spread / MAX_SPREAD_PROXY)
    return 0.5 * (vol_term + spread_term)


def normalize_scores(values: np.ndarray) -> np.ndarray:
    if SCORE_NORM_METHOD == "zscore":
        return (values - values.mean()) / (values.std() + EPS_F64)
    if SCORE_NORM_METHOD == "minmax":
        return (values - values.min()) / (values.max() - values.min() + EPS_F64)
    order = values.argsort().argsort()
    return order.astype(np.float64) / max(1, len(values) - 1)


def compute_ticker_features(ticker: str, df4h: pd.DataFrame, df1m: pd.DataFrame, slope_pct: float, r2: float) -> dict[str, Any]:
    close4h = df4h["Close"].to_numpy(dtype=np.float32)
    high1m = df1m["High"].to_numpy(dtype=np.float32)
    low1m = df1m["Low"].to_numpy(dtype=np.float32)
    close1m = df1m["Close"].to_numpy(dtype=np.float32)
    vol1m = df1m["Volume"].to_numpy(dtype=np.float32)
    up, down = flower_oscillator_numba(high1m, low1m, close1m, FLOWER_N)
    vwap_window = VWAP_ROLLING_DAYS * BARS_PER_TRADING_DAY_1MIN
    vwap = rolling_vwap_numba(close1m, vol1m, vwap_window)
    fpt_horizon, completion, n_events, median, trap = fpt_calibration(up)
    return {
        "ticker": ticker,
        "slope_pct": slope_pct,
        "r2": r2,
        "trend_bull": int(slope_pct >= LINREG_SLOPE_THRESHOLD and r2 >= LINREG_R2_THRESHOLD),
        "flower_up": float(up[-1]),
        "flower_down": float(down[-1]),
        "vwap_last": float(vwap[-1]),
        "price_last": float(close1m[-1]),
        "ou_score": ou_score_from_up(up, fpt_horizon, completion, trap),
        "hurst_div": hurst_rs(close4h[-HURST_WIN_4H:]) - hurst_rs(close1m[-HURST_WIN_1MIN:]),
        "hmm_expand": hmm_expand_prob(close4h),
        "skew": skewness(np.diff(np.log(close1m[-SKEW_WINDOW_1MIN:] + np.float32(EPS_F64)))),
        "cvd": cvd_score(close4h[-CVD_WINDOW:], df4h["Volume"].to_numpy(dtype=np.float64)[-CVD_WINDOW:]),
        "liq": liquidity_score(df4h),
        "n_fpt_events": n_events,
        "completion_rate": completion,
        "fpt_horizon_used": fpt_horizon,
        "median_traversal": median,
        "fpt_os_trap": trap,
        "ou_calib_bars": int(len(up)),
        "vwap_anchor_bars": min(vwap_window, len(close1m)),
    }


def run_cycle() -> None:
    start = time.time()
    validate_config()
    cfg = config_dict()
    state = init_cache(cfg)
    parity = compute_parity_factors(state)
    max_4h, max_1m = compute_cache_windows()
    passed: list[tuple[str, pd.DataFrame, pd.DataFrame, float, float, str, str]] = []
    fetch_workers = min(FETCH_BATCH_SIZE, FETCH_MAX_WORKERS_CAP)
    with ThreadPoolExecutor(max_workers=fetch_workers) as pool:
        futures = {}
        for ticker in TICKERS:
            futures[pool.submit(fetch_and_cache_interval, ticker, "4h", max_4h, state)] = (ticker, "4h")
            futures[pool.submit(fetch_and_cache_interval, ticker, "1m", max_1m, state)] = (ticker, "1m")
        buffers: dict[str, dict[str, Any]] = {t: {} for t in TICKERS}
        for future in as_completed(futures):
            ticker, interval = futures[future]
            df, mode = future.result()
            buffers[ticker][interval] = (df, mode)
        for ticker in TICKERS:
            df4h, mode4h = buffers[ticker]["4h"]
            df1m, mode1m = buffers[ticker]["1m"]
            ok, reason = qc_hard(df4h, df1m)
            if not ok:
                print(f"FILTER {ticker:<10} reason={reason}")
                continue
            slope_pct, r2 = ols_slope_r2_percent(select_source(df4h))
            if slope_pct < LINREG_SLOPE_THRESHOLD or r2 < LINREG_R2_THRESHOLD:
                print(f"FILTER {ticker:<10} slope={slope_pct:+.4f}% r2={r2:.3f}")
                continue
            passed.append((ticker, df4h, df1m, slope_pct, r2, mode4h, mode1m))
    features: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, os.cpu_count() or 1)) as pool:
        jobs = [pool.submit(compute_ticker_features, t, d4, d1, s, r) for t, d4, d1, s, r, _, _ in passed]
        for j in as_completed(jobs):
            features.append(j.result())
    if not features:
        print("No tickers passed prefilter")
        save_cache_state(state)
        return
    raw = np.array([
        W_OU_FPT * f["ou_score"] + W_HURST * f["hurst_div"] + W_HMM * f["hmm_expand"] +
        W_SKEW * f["skew"] + W_LIQUIDITY * f["liq"] + W_CVD * f["cvd"]
        for f in features
    ], dtype=np.float64)
    scores = normalize_scores(raw)
    print(f"TREND PRE-FILTER passed={len(features)}/{len(TICKERS)}")
    for i, f in enumerate(sorted(features, key=lambda x: x["ticker"])):
        score = float(scores[i])
        entry = (
            f["trend_bull"] == 1 and f["flower_up"] <= ENTRY_FLOWER_LEVEL and score >= ENTRY_MIN_SCORE and f["fpt_os_trap"] == 0
        )
        side = "ENTRY" if entry else "WATCH"
        print(
            f"{side} {f['ticker']:<10} score={score:.3f} slope={f['slope_pct']:+.4f}% r2={f['r2']:.3f} "
            f"UP={f['flower_up']:.1f} VWAP={f['vwap_last']:.2f} completion={f['completion_rate']:.1%} events={f['n_fpt_events']}"
        )
    if parity:
        print("PARITY FACTORS", {k: round(v, 6) for k, v in parity.items()})
    print(f"Cycle time: {time.time() - start:.2f}s")
    save_cache_state(state)


def run_self_test() -> None:
    validate_config()
    max_4h, max_1m = compute_cache_windows()
    assert max_4h >= LINREG_BARS
    assert max_1m >= VWAP_ROLLING_DAYS * BARS_PER_TRADING_DAY_1MIN
    n4 = LINREG_BARS
    n1 = max(3000, VWAP_ROLLING_DAYS * BARS_PER_TRADING_DAY_1MIN + 10)
    x4 = np.linspace(100.0, 120.0, n4, dtype=np.float64)
    slope, r2 = ols_slope_r2_percent(x4)
    assert slope > 0.0 and r2 > 0.9
    c = np.linspace(10.0, 20.0, n1, dtype=np.float32)
    h = c + 0.1
    l = c - 0.1
    v = np.full(n1, 100.0, dtype=np.float32)
    up, down = flower_oscillator_numba(h, l, c, FLOWER_N)
    assert up.size == n1 and down.size == n1
    vwap = rolling_vwap_numba(c, v, VWAP_ROLLING_DAYS * BARS_PER_TRADING_DAY_1MIN)
    assert np.isfinite(vwap).all()
    assert not np.any(np.isnan(vwap[VWAP_ROLLING_DAYS * BARS_PER_TRADING_DAY_1MIN - 1 :]))
    print(f"self-test-ok slope={slope:.6f} r2={r2:.6f} max4h={max_4h} max1m={max_1m}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
        return
    if not args.live:
        run_cycle()
        return
    run_cycle()
    schedule.every(RUN_INTERVAL_HOURS).hours.do(run_cycle)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
