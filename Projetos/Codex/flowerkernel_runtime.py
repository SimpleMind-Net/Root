from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from os import cpu_count
from typing import Callable, Iterator

import numpy as np
from numba import njit

DTYPE_PRICE = np.float32
DTYPE_VOLUME = np.float32
DTYPE_SCORE = np.float32
CHUNK_SIZE = 100_000
EPSILON = np.float32(1e-8)

CONFIG: dict[str, object] = {
    "linreg_bars": 250,
    "linreg_slope_threshold": np.float32(0.0002),
    "linreg_r2_threshold": np.float32(0.25),
    "flower_fast": 7,
    "flower_slow": 20,
    "flower_smooth": 5,
    "vwap_rolling_days": 5,
    "bars_per_day_1m": 390,
    "chunk_size": CHUNK_SIZE,
}


def iter_chunks(length: int, chunk_size: int) -> Iterator[tuple[int, int]]:
    starts = range(0, length, chunk_size)
    return ((start, min(start + chunk_size, length)) for start in starts)


def dispatch_chunks(
    length: int,
    chunk_size: int,
    fn: Callable[[tuple[int, int]], tuple[int, np.ndarray]],
) -> np.ndarray:
    output = np.empty(length, dtype=DTYPE_SCORE)
    workers = max(1, cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = (executor.submit(fn, bounds) for bounds in iter_chunks(length, chunk_size))
        for future in futures:
            start, values = future.result()
            output[start : start + values.size] = values
    return output


@njit(nogil=True, cache=True)
def ema_numba(values: np.ndarray, period: int) -> np.ndarray:
    alpha = np.float32(2.0 / (period + 1.0))
    out = np.empty(values.size, dtype=np.float32)
    out[0] = values[0]
    for idx in range(1, values.size):
        out[idx] = out[idx - 1] + alpha * (values[idx] - out[idx - 1])
    return out


@njit(nogil=True, cache=True)
def flower_oscillator_numba(close_1m: np.ndarray, fast: int, slow: int, smooth: int) -> np.ndarray:
    ema_fast = ema_numba(close_1m, fast)
    ema_slow = ema_numba(close_1m, slow)
    spread = np.empty(close_1m.size, dtype=np.float32)
    for idx in range(close_1m.size):
        spread[idx] = ema_fast[idx] - ema_slow[idx]
    smoothed_1 = ema_numba(spread, smooth)
    smoothed_2 = ema_numba(smoothed_1, smooth)
    smoothed_3 = ema_numba(smoothed_2, smooth)
    return ema_numba(smoothed_3, smooth)


@njit(nogil=True, cache=True)
def rolling_vwap_numba(close_1m: np.ndarray, volume_1m: np.ndarray, window_bars: int) -> np.ndarray:
    out = np.empty(close_1m.size, dtype=np.float32)
    pv_prefix = np.empty(close_1m.size + 1, dtype=np.float32)
    v_prefix = np.empty(close_1m.size + 1, dtype=np.float32)
    pv_prefix[0] = 0.0
    v_prefix[0] = 0.0
    for idx in range(close_1m.size):
        pv_prefix[idx + 1] = pv_prefix[idx] + close_1m[idx] * volume_1m[idx]
        v_prefix[idx + 1] = v_prefix[idx] + volume_1m[idx]
    for idx in range(close_1m.size):
        left = idx + 1 - window_bars
        left = 0 if left < 0 else left
        pv = pv_prefix[idx + 1] - pv_prefix[left]
        vol = v_prefix[idx + 1] - v_prefix[left]
        out[idx] = pv / (vol + EPSILON)
    return out


@njit(nogil=True, cache=True)
def ols_slope_r2_numba(close_4h: np.ndarray) -> tuple[np.float32, np.float32]:
    n = close_4h.size
    x_mean = np.float32(0.5 * (n - 1))
    y_mean = np.float32(0.0)
    for val in close_4h:
        y_mean += val
    y_mean /= n

    xx = np.float32(0.0)
    xy = np.float32(0.0)
    yy = np.float32(0.0)
    for idx in range(n):
        dx = np.float32(idx) - x_mean
        dy = close_4h[idx] - y_mean
        xx += dx * dx
        xy += dx * dy
        yy += dy * dy

    slope = xy / (xx + EPSILON)
    mean_price = y_mean if y_mean > EPSILON else EPSILON
    slope_norm = slope / mean_price
    r2 = (xy * xy) / ((xx + EPSILON) * (yy + EPSILON))
    return slope_norm, r2


def compute_prefilter(close_4h: np.ndarray, config: dict[str, object]) -> tuple[bool, np.float32, np.float32]:
    bars = int(config["linreg_bars"])
    window = close_4h[-bars:].astype(DTYPE_PRICE, copy=False)
    slope, r2 = ols_slope_r2_numba(window)
    passed = slope >= np.float32(config["linreg_slope_threshold"]) and r2 >= np.float32(config["linreg_r2_threshold"])
    return passed, slope, r2


def compute_signal(close_1m: np.ndarray, volume_1m: np.ndarray, config: dict[str, object]) -> np.ndarray:
    window_bars = int(config["vwap_rolling_days"]) * int(config["bars_per_day_1m"])
    flower = flower_oscillator_numba(
        close_1m.astype(DTYPE_PRICE, copy=False),
        int(config["flower_fast"]),
        int(config["flower_slow"]),
        int(config["flower_smooth"]),
    )
    vwap = rolling_vwap_numba(
        close_1m.astype(DTYPE_PRICE, copy=False),
        volume_1m.astype(DTYPE_VOLUME, copy=False),
        window_bars,
    )
    return np.where(close_1m > vwap, flower, -flower).astype(DTYPE_SCORE, copy=False)


def select_price_source(source: str, close: np.ndarray, hlc3: np.ndarray) -> np.ndarray:
    match source:
        case "close":
            return close
        case "hlc3":
            return hlc3
        case _:
            return close


def process_universe(data: dict[str, dict[str, np.ndarray]], config: dict[str, object]) -> dict[str, dict[str, np.ndarray | np.float32 | bool]]:
    result: dict[str, dict[str, np.ndarray | np.float32 | bool]] = {}
    for ticker, series in data.items():
        passed, slope, r2 = compute_prefilter(series["close_4h"], config)
        if not passed:
            result[ticker] = {"passed": False, "slope": slope, "r2": r2}
            continue
        signal = compute_signal(series["close_1m"], series["volume_1m"], config)
        result[ticker] = {"passed": True, "slope": slope, "r2": r2, "signal": signal}
    return result


def _chunked_mean_abs(values: np.ndarray, chunk_size: int) -> np.ndarray:
    length = values.size

    def chunk_fn(bounds: tuple[int, int]) -> tuple[int, np.ndarray]:
        start, end = bounds
        chunk = values[start:end]
        return start, np.abs(chunk).astype(DTYPE_SCORE, copy=False)

    return dispatch_chunks(length, chunk_size, chunk_fn)


def _chunked_sign(values: np.ndarray, chunk_size: int) -> np.ndarray:
    length = values.size

    def chunk_fn(bounds: tuple[int, int]) -> tuple[int, np.ndarray]:
        start, end = bounds
        chunk = values[start:end]
        return start, np.sign(chunk).astype(DTYPE_SCORE, copy=False)

    return dispatch_chunks(length, chunk_size, chunk_fn)


def run_self_test() -> None:
    rng = np.random.default_rng(42)
    bars_4h = int(CONFIG["linreg_bars"])
    bars_1m = 20_000

    trend = np.linspace(100.0, 120.0, bars_4h, dtype=np.float32)
    noise = rng.normal(0.0, 0.1, bars_4h).astype(np.float32)
    close_4h = trend + noise

    walk = np.cumsum(rng.normal(0.0, 0.2, bars_1m).astype(np.float32)) + np.float32(100.0)
    volume = rng.integers(50, 500, bars_1m, dtype=np.int32).astype(np.float32)

    payload = {"TEST3": {"close_4h": close_4h, "close_1m": walk, "volume_1m": volume}}
    out = process_universe(payload, CONFIG)
    ticker_out = out["TEST3"]

    assert bool(ticker_out["passed"]), "Prefilter should pass in synthetic trend test."
    signal = ticker_out["signal"]
    assert isinstance(signal, np.ndarray) and signal.size == bars_1m, "Signal shape mismatch."

    abs_parallel = _chunked_mean_abs(signal, int(CONFIG["chunk_size"]))
    sign_parallel = _chunked_sign(signal, int(CONFIG["chunk_size"]))
    assert abs_parallel.dtype == DTYPE_SCORE and sign_parallel.dtype == DTYPE_SCORE
    print(f"self-test-ok bars_1m={bars_1m} slope={ticker_out['slope']:.6f} r2={ticker_out['r2']:.6f}")


if __name__ == "__main__":
    run_self_test()
