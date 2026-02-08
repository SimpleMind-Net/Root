# @title # First Passage Time Distribution Analysis Screener - yfinance batched - incremental cache - Kernel regression confirmed

from typing import Final
import numpy as np
from numpy import ndarray
import pandas as pd
import yfinance as yf
from datetime import datetime
from tqdm import tqdm
import os
from google.colab import drive
from time import sleep

import logging
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# =============================================================================
# DRIVE MOUNT + INCREMENTAL CACHE
# =============================================================================
drive.mount("/content/drive")
CACHE_PATH: Final[str] = "/content/drive/MyDrive/FPT_Screener/incremental_cache.pkl"


# Cache incremental persistente:
# - Carrega dict {ticker: pd.Series close indexada por datetime}
# - Para cada ticker: tenta fetch incremental desde último timestamp +1h usando yf.Ticker.history
# - Append novas barras
# - Trim: mantém apenas dados >= cutoff (3mo + buffer 10 dias atrás)
# - Fallback full fetch se gap >90 dias ou incremental vazio
# - Salva cache atualizado ao final
# Ganho: runs subsequentes baixam apenas barras novas (segundos típicos)
def load_cache() -> dict[str, pd.Series] | None:
    if os.path.exists(CACHE_PATH):
        cached = pd.read_pickle(CACHE_PATH)
        if isinstance(cached, dict):
            print(f"Incremental cache carregado: {len(cached)} tickers.")
            return cached
    print("Cache não encontrado: fetch completo na primeira execução.")
    return None


def save_cache(data: dict[str, pd.Series]) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    pd.to_pickle(data, CACHE_PATH)
    print(f"Incremental cache salvo: {len(data)} tickers.")


# =============================================================================
# CONFIGURATION
# =============================================================================
CFG: Final[dict] = {
    "interval": "1h",
    "period": "3mo",
    "lookback": 140,
    "ewma_span": 20,
    "student_t_df": 5,
    "n_sims": 1000,
    "max_sim_steps": 1000,
    "upside_pct": 0.09,
    "downside_pct": -0.03,
    "soft_max_days": 4.0,
    "min_quality_score": 0.80,
    "weight_probability": 0.35,
    "weight_time": 0.05,
    "weight_expected_value": 0.20,
    "weight_velocity": 0.20,
    "weight_risk": 0.20,
    "entry_factor": 1.0,
    "cache_buffer_days": 10,
    "max_gap_days": 90,
}

KERNEL_BW: Final[int] = 36
MIN_KERNEL_POINTS: Final[int] = 75
HOURS_PER_BAR: Final[float] = 1.0
USDBRL_TICKER: Final[str] = "USDBRL=X"
FX_FALLBACK: Final[float] = 5.70

UPSIDE_LOG: Final[float] = np.log(1.0 + CFG["upside_pct"])
DOWNSIDE_LOG: Final[float] = np.log(1.0 + CFG["downside_pct"])
T_SCALE: Final[float] = np.sqrt((CFG["student_t_df"] - 2) / CFG["student_t_df"])
LOG2_OVER_SOFT: Final[float] = np.log(2) / CFG["soft_max_days"]

_KERNEL_U: Final[ndarray] = np.arange(1000, dtype=np.float64) / KERNEL_BW
_KERNEL_WEIGHTS: Final[ndarray] = np.where(
    _KERNEL_U < 1.0, (1.0 - _KERNEL_U**3) ** 3, 0.0
)

# =============================================================================
# TICKERS + PARITY
# =============================================================================
TICKERS: Final[tuple[str, ...]] = (
    'A', 'AAL', 'AALR3.SA', 'AAP', 'AAPL', 'AAZQ11.SA', 'ABBV', 'ABCB4.SA', 'ABCP11.SA', 'ABEV',
    'ABNB', 'ABT', 'ACN', 'ACWI11.SA', 'ADBE', 'ADI', 'ADM', 'ADP', 'ADSK', 'AEE',
    # more than 1500 tickers
)

PARITY: Final[dict[str, tuple[str, str, float]]] = {
    'A1AP34.SA': ('AAP', 'NYSE', 16.22),
    'A1CR34.SA': ('AMCR', 'NYSE', 1),
    # other k-v pairs
}

PARITY_REVERSE: Final[dict[str, tuple[str, float]]] = {
    us: (br, float(f)) for br, (us, _, f) in PARITY.items()
}


# =============================================================================
# FORMATTING + DISPLAY
# =============================================================================
def fmt_br(v: float, d: int = 2) -> str:
    s = f"{v:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def bars_display(bars: float) -> str:
    if not np.isfinite(bars):
        return "N/A"
    th = bars * HOURS_PER_BAR
    d, h = int(th // 24), int(th % 24)
    if d == 0:
        return f"{h}h"
    elif h == 0:
        return f"{d}d"
    else:
        return f"{d}d {h}h"


# =============================================================================
# KERNEL REGRESSION
# =============================================================================
def kernel_nw_tricube(prices: ndarray, bw: int = KERNEL_BW) -> ndarray:
    n = len(prices)
    if n == 0:
        return np.array([], dtype=np.float64)
    if bw == KERNEL_BW and n <= len(_KERNEL_WEIGHTS):
        weights = _KERNEL_WEIGHTS[:n]
    else:
        u = np.arange(n, dtype=np.float64) / bw
        weights = np.where(u < 1.0, (1.0 - u**3) ** 3, 0.0)
    idx = np.arange(n)
    lag = idx[:, None] - idx[None, :]
    valid = lag >= 0
    w_mat = np.where(valid, weights[lag], 0.0)
    numerator = w_mat @ prices
    denominator = w_mat.sum(axis=1)
    kernel_est = np.where(denominator > 0, numerator / denominator, prices)
    return kernel_est


def is_kernel_bullish_4h(closes_4h: ndarray) -> bool:
    if len(closes_4h) < MIN_KERNEL_POINTS:
        return False
    prices = closes_4h.astype(np.float64, copy=False)
    kernel = kernel_nw_tricube(prices)
    if (
        len(kernel) < 3
        or not np.all(np.isfinite(kernel[-3:]))
        or kernel[-3] <= 0
        or kernel[-2] <= 0
    ):
        return False
    diff1 = float(kernel[-1]) - float(kernel[-2])
    diff2 = float(kernel[-2]) - float(kernel[-3])
    return diff1 > 0 and diff1 > diff2


# =============================================================================
# DATA FETCHING INCREMENTAL (usando yf.Ticker.history para consistência)
# =============================================================================
def fetch_usdbrl() -> float:
    try:
        df = yf.Ticker(USDBRL_TICKER).history(period="5d", interval="1d")
        if not df.empty and "Close" in df.columns:
            return float(df["Close"].iloc[-1])
    except Exception:
        pass
    return FX_FALLBACK


def fetch_all_data(
    tickers: tuple[str, ...], cached_series: dict[str, pd.Series] | None
) -> dict[str, tuple[pd.Series, float]]:
    results: dict[str, tuple[pd.Series, float]] = {}
    cutoff_date = (
        datetime.now()
        - pd.DateOffset(months=3)
        - pd.Timedelta(days=CFG["cache_buffer_days"])
    )
    failed = 0

    with tqdm(
        total=len(tickers), desc="Atualizando tickers (incremental)", unit="ticker"
    ) as pbar:
        for ticker in tickers:
            cached_close = cached_series.get(ticker) if cached_series else None
            last_ts = (
                cached_close.index[-1]
                if cached_close is not None and len(cached_close) > 0
                else None
            )
            now = pd.Timestamp.now(tz=None)

            force_full = last_ts is None or (now - last_ts).days > CFG["max_gap_days"]

            tk = yf.Ticker(ticker)
            try:
                if force_full:
                    data = tk.history(
                        period=CFG["period"],
                        interval=CFG["interval"],
                        prepost=True,
                        auto_adjust=True,
                    )
                else:
                    start_ts = last_ts + pd.Timedelta(hours=1)
                    data = tk.history(
                        start=start_ts,
                        interval=CFG["interval"],
                        prepost=True,
                        auto_adjust=True,
                    )
            except Exception as e:
                print(f"Erro no fetch de {ticker}: {e}")
                data = pd.DataFrame()

            if data.empty:
                if cached_close is not None and len(cached_close) >= CFG["lookback"]:
                    close_series = cached_close
                else:
                    failed += 1
                    pbar.update(1)
                    continue
            else:
                data.index = data.index.tz_localize(None)
                data.columns = [c.lower() for c in data.columns]
                new_close = data["close"].dropna()

                if cached_close is not None:
                    close_series = pd.concat([cached_close, new_close])
                    close_series = close_series[
                        ~close_series.index.duplicated(keep="last")
                    ]
                else:
                    close_series = new_close

            # Trim antigo
            close_series = close_series[close_series.index >= cutoff_date]

            if len(close_series) >= CFG["lookback"]:
                price = float(close_series.iloc[-1])
                if np.isfinite(price) and price > 0:
                    results[ticker] = (close_series, price)
                else:
                    failed += 1
            else:
                failed += 1
            pbar.update(1)
            sleep(0.05)

    if failed:
        print(f"(Falha ou dados insuficientes em {failed} tickers)")
    return results


# =============================================================================
# VOLATILITY + SIMULATIONS + METRICS
# =============================================================================
def compute_ewma_vol(closes: ndarray, span: int) -> float:
    if len(closes) < 2:
        return 0.0
    lr = np.diff(np.log(closes))
    if len(lr) < span:
        return float(np.std(lr, ddof=0))
    sq = lr * lr
    alpha = 2.0 / (span + 1)
    ewma = sq[0]
    for i in range(1, len(sq)):
        ewma = alpha * sq[i] + (1 - alpha) * ewma
    return float(np.sqrt(ewma)) if ewma > 0 else float(np.std(lr, ddof=0))


def compute_stats(
    closes: ndarray, lookback: int, span: int
) -> tuple[float, float, float]:
    lr = np.diff(np.log(closes[-lookback - 1 :]))
    mu = float(np.mean(lr))
    sigma = compute_ewma_vol(closes, span)
    return mu, sigma, closes[-1] * sigma


def run_fpt_sim(mu: float, sigma: float) -> tuple[float, float]:
    if sigma <= 1e-10:
        return 0.0, np.inf
    n_sims, max_steps, df = CFG["n_sims"], CFG["max_sim_steps"], CFG["student_t_df"]
    drift = mu - 0.5 * sigma * sigma
    rng = np.random.default_rng()
    z = rng.standard_t(df, size=(n_sims, max_steps)) * T_SCALE
    inc = drift + sigma * z
    lp = np.cumsum(inc, axis=1)
    hit_up = lp >= UPSIDE_LOG
    hit_dn = lp <= DOWNSIDE_LOG
    any_up = np.any(hit_up, axis=1)
    any_dn = np.any(hit_dn, axis=1)
    first_up = np.where(any_up, np.argmax(hit_up, axis=1) + 1, max_steps + 1)
    first_dn = np.where(any_dn, np.argmax(hit_dn, axis=1) + 1, max_steps + 1)
    up_first = first_up < first_dn
    n_up = int(np.sum(up_first))
    n_res = int(np.sum(up_first | (first_dn < first_up)))
    if n_res == 0:
        return 0.0, np.inf
    hr = float(n_up) / float(n_res)
    if n_up == 0:
        return hr, np.inf
    return hr, float(np.median(first_up[up_first]))


def compute_metrics(hr: float, md: float) -> tuple[float, float, float, float]:
    up, dn = CFG["upside_pct"], abs(CFG["downside_pct"])
    ev = hr * up - (1.0 - hr) * dn
    vel = (up / md) if md > 0 and np.isfinite(md) else 0.0
    vel = min(vel, 999.99)
    rs = ((1.0 - hr) * dn / up) if up > 0 else np.inf
    sk = (ev / md) if md > 0 and np.isfinite(md) else 0.0
    return ev, vel, rs, sk


def compute_quality(hr: float, md: float, ev: float, vel: float, rs: float) -> float:
    if md <= 0 or not np.isfinite(md) or hr <= 0:
        return 0.0
    up = CFG["upside_pct"]
    ps = max(0.0, min(1.0, (hr - 0.5) / 0.5))
    ts = max(0.0, min(1.0, np.exp(-LOG2_OVER_SOFT * md)))
    evs = max(0.0, min(1.0, ev / up))
    vs = max(0.0, min(1.0, vel / up)) if vel > 0 else 0.0
    rc = max(0.0, min(1.0, 1.0 - min(rs, 1.0)))
    return (
        CFG["weight_probability"] * ps
        + CFG["weight_time"] * ts
        + CFG["weight_expected_value"] * evs
        + CFG["weight_velocity"] * vs
        + CFG["weight_risk"] * rc
    )


# =============================================================================
# PROCESSING + CONVERSION + KERNEL FILTER
# =============================================================================
def process_ticker(ticker: str, close_series: pd.Series, price: float) -> dict | None:
    closes = close_series.to_numpy(dtype=np.float64)
    if len(closes) < CFG["lookback"] + 1:
        return None
    mu, sigma, pvol = compute_stats(closes, CFG["lookback"], CFG["ewma_span"])
    if sigma <= 1e-10:
        return None
    hr, mb = run_fpt_sim(mu, sigma)
    if hr <= 0 or not np.isfinite(mb):
        return None
    md = (mb * HOURS_PER_BAR) / 24.0
    ev, vel, rs, sk = compute_metrics(hr, md)
    qs = compute_quality(hr, md, ev, vel, rs)
    return {
        "ticker": ticker,
        "original_ticker": ticker,
        "current_price": price,
        "entry_price": price - CFG["entry_factor"] * pvol,
        "projected_price": price * (1.0 + CFG["upside_pct"]),
        "probability": hr * 100.0,
        "median_bars": mb,
        "median_days": md,
        "expected_value": ev,
        "return_velocity": vel,
        "risk_score": rs,
        "sort_key": sk,
        "quality_score": qs,
        "volatility": sigma,
    }


def convert_brl(r: dict, usdbrl: float) -> dict:
    t = r["ticker"]
    orig = r.get("original_ticker", t)
    if t.endswith(".SA"):
        return {**r, "ticker": t[:-3], "original_ticker": orig}
    if t in PARITY_REVERSE:
        br, pf = PARITY_REVERSE[t]
        cf = usdbrl / pf
        return {
            **r,
            "ticker": br[:-3] if br.endswith(".SA") else br,
            "original_ticker": orig,
            "current_price": r["current_price"] * cf,
            "entry_price": r["entry_price"] * cf,
            "projected_price": r["projected_price"] * cf,
        }
    return {**r, "original_ticker": orig}


def apply_kernel_filter_4h(filt_res: list[dict], all_data: dict) -> list[dict]:
    if not filt_res:
        return []
    filtered = []
    skipped = 0
    skipped_bearish = 0
    print(
        f"\nApplying 4-hour kernel regression filter (resampled, bw={KERNEL_BW}, min_points={MIN_KERNEL_POINTS})..."
    )
    for r in tqdm(filt_res, desc="Kernel filter (4h)", unit="ticker"):
        ticker = r["original_ticker"]
        close_series, _ = all_data.get(ticker, (None, None))
        if close_series is None:
            skipped += 1
            continue
        closes_4h = close_series.resample("4h").last().dropna().to_numpy()
        if len(closes_4h) < MIN_KERNEL_POINTS:
            skipped += 1
            continue
        if is_kernel_bullish_4h(closes_4h):
            filtered.append(r)
        else:
            skipped_bearish += 1
    print(f" Passed kernel filter: {len(filtered)}")
    print(f" Rejected (bearish/neutral): {skipped_bearish}")
    print(f" Skipped (data unavailable): {skipped}")
    return filtered


# =============================================================================
# MAIN
# =============================================================================
def main() -> pd.DataFrame:
    print(
        f"FPT Screener (yfinance incremental cache): Processing {len(TICKERS)} tickers..."
    )
    print("\nConfiguration:")
    print(" - Data source: yfinance (incremental cache)")
    print(f" - Interval: {CFG['interval']} ({HOURS_PER_BAR}h per bar)")
    print(f" - Period: {CFG['period']}")
    print(
        f" - Thresholds: +{CFG['upside_pct'] * 100:.1f}% / -{CFG['downside_pct'] * 100:.1f}%"
    )
    print(f" - EWMA Span: {CFG['ewma_span']} | Student-t df: {CFG['student_t_df']}")
    print(f" - Simulations: {CFG['n_sims']}")
    print("\nSoft Scoring Parameters:")
    print(f" - Time half-life: {CFG['soft_max_days']} days")
    print(f" - Min quality score: {CFG['min_quality_score'] * 100:.0f}%")
    print(
        f" - Weights: Prob={CFG['weight_probability']:.0%}, Time={CFG['weight_time']:.0%}, EV={CFG['weight_expected_value']:.0%}, Vel={CFG['weight_velocity']:.0%}, Risk={CFG['weight_risk']:.0%}"
    )
    print("\n4-Hour Kernel Filter:")
    print(f" - Bandwidth: {KERNEL_BW} bars")
    print(f" - Min data points: {MIN_KERNEL_POINTS}")
    print(" - Trend: Bullish and accelerating (kernel[-1] - kernel[-2]) >0 and >(kernel[-2] - kernel[-3])")

    usdbrl = fetch_usdbrl()
    print(f"\nUSD/BRL rate: {fmt_br(usdbrl, 4)}")

    cached_series = load_cache()

    all_data = fetch_all_data(TICKERS, cached_series)

    cache_to_save = {t: s for t, (s, _) in all_data.items()}
    save_cache(cache_to_save)

    print("\nRunning FPT simulations...")
    all_res: list[dict] = []
    filt_res: list[dict] = []
    min_qs = CFG["min_quality_score"]
    for ticker, (close_series, price) in tqdm(
        all_data.items(), desc="Processing tickers", unit="ticker"
    ):
        r = process_ticker(ticker, close_series, price)
        if r is not None:
            r = convert_brl(r, usdbrl)
            all_res.append(r)
            if r["quality_score"] >= min_qs:
                filt_res.append(r)

    print(f"\nTotal processed: {len(all_res)} tickers")
    print(f"Passing quality threshold ({min_qs * 100:.0f}%): {len(filt_res)} tickers")

    if filt_res:
        filt_res = apply_kernel_filter_4h(filt_res, all_data)

    if not filt_res:
        print("\nNo tickers met all screening criteria.")
        return pd.DataFrame()

    filt_res.sort(key=lambda x: (-x["quality_score"], -x["sort_key"]))
    result_df = pd.DataFrame(
        [
            {
                "Ticker": r["ticker"],
                "Current Price": fmt_br(r["current_price"], 2),
                "Entry Price": fmt_br(r["entry_price"], 2),
                "Projected Price": fmt_br(r["projected_price"], 2),
                "Bias": "Bullish",
                "Quality Score": f"{fmt_br(r['quality_score'] * 100, 1)}%",
                "Probability %": fmt_br(r["probability"], 0),
                "Median Time": bars_display(r["median_bars"]),
                "Expected Value %": fmt_br(r["expected_value"] * 100, 2),
                "Return Velocity %/day": fmt_br(r["return_velocity"] * 100, 2),
                "Risk Score": fmt_br(r["risk_score"], 3),
                "Volatility": f"{fmt_br(r['volatility'] * 100, 2)}%",
            }
            for r in filt_res
        ]
    )

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("\n" + "=" * 140)
    print(
        f"SCREENING RESULTS: Bullish +9% / -3% | Quality ≥80% | 4h Kernel Bullish | {ts}"
    )
    print("Model: EWMA + Student-t | Data: yfinance")
    print(
        "Sorted by: Quality Score (composite of probability, time, EV, velocity, risk)"
    )
    print("=" * 140)
    if not result_df.empty:
        print(result_df.to_string(index=False))
        print(f"\nTotal qualifying tickers: {len(result_df)}")
    return result_df


if __name__ == "__main__":
    result_df = main()
