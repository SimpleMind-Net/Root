# VISTA — Multi-Model Divergence-Aware Stock Price Forecasting

VISTA is a single-file stock price forecasting pipeline that runs on Google Colab (CPU-only) and queries three distinct Vision-Language Models in parallel via the free NVIDIA NIM API. For each ticker, it downloads three timeframes of market data (weekly, daily, 15-minute) using [yfinance](https://github.com/ranaroussi/yfinance) with Parquet caching, computes [Numba](https://numba.pydata.org/)-accelerated technical indicators, renders text-label-free Heikin-Ashi candlestick charts with a Total-Variation-regularized trend slope overlay, and produces a consensus forecast across all three models using a divergence-aware aggregation strategy. The script is in [`vista_prediction.py`](vista_prediction.py).

## Techniques

- **[Heikin-Ashi Candlesticks](https://www.investopedia.com/terms/h/heikinashi.asp)** — the pipeline computes Heikin-Ashi opens via a sequential recurrence (`_ha_open_loop`) that Numba JITs for speed on CPU. Heikin-Ashi candles smooth wicks and highlight trend persistence, which is the entire basis of the visual trend classification the VLMs perform. Raw OHLC is never shown.

- **[Total-Variation Regularized Derivative](https://arxiv.org/abs/2505.18570)** — a noise-robust trend slope overlay drawn as a yellow line on each chart. Uses the [`deeptime`](https://deeptime-ml.github.io/) library's `tv_derivative` solver with alpha=0.001. Positive slope = uptrend, negative = downtrend, zero-crossing = potential reversal. Falls back to [`np.gradient`](https://numpy.org/doc/stable/reference/generated/numpy.gradient.html) if deeptime is unavailable. Values are intentionally hidden — only the line shape is shown to the VLM.

- **[Numba JIT CPU Kernels](https://numba.pydata.org/numba-doc/latest/user/jit.html)** — the pipeline uses `@numba.jit(nopython=True, nogil=True, cache=True)` on six functions: VWMA rolling sum, log returns, rolling momentum, Heikin-Ashi open recurrence, and NaN initialization. No `prange` or `parallel=True` — those silently produce wrong results on Colab's 2-core CPU (documented in the code comments).

- **Divergence-Aware Multi-Model Consensus** — three distinct architectures (MiniMax-M3 428B MoE, Nemotron 30B reasoning, Ministral-14B instruct) are each called once per ticker. Per-day forecasts: if the relative spread between models is below 1.5%, the consensus is the mean; above it, a trend-extrapolated anchor is injected and the median of (predictions + anchor) is taken — preventing hallucination-driven blowups. The spread is reported as `disagreement_pct` in the output. If only one model succeeds, its forecast is used with a "degraded" confidence flag.

- **[Parquet-Cached yfinance Downloads](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_parquet.html)** — every `(ticker, interval)` pair is cached to `~/.vista_cache/` as a Parquet file with a 12-hour TTL. A cache hit skips the yfinance HTTP call entirely. Combined with a two-pass download strategy (auto-adjust=True first, then auto-adjust=False + manual adjustment) to work around a yfinance bug where `repair=True` crashes with `KeyError('Stock Splits')` on crypto pairs and Brazilian FIIs.

- **[Thread-Safe Sliding-Window Rate Limiter](https://en.wikipedia.org/wiki/Sliding_window_protocol)** — the `_SlidingWindowRateLimiter` class tracks request timestamps in a 60-second deque and blocks when the window is full. `TARGET_RPM=30` enforces a 25% safety margin below the NIM free-tier 40 RPM hard cap. Every VLM call acquires a token before issuing the HTTP request, and `VLM_CONCURRENCY=3` limits in-flight requests to match the tri-model call shape.

- **[VIX Contrarian Signal](https://en.wikipedia.org/wiki/VIX)** — the CBOE Volatility Index is downloaded once per pipeline run (shared across all tickers) and rendered as a fourth chart. Lower VIX = bullish bias; higher VIX = bearish. The prompt instructs the VLM to weight VIX only for equity tickers, not crypto. Thresholds: VIX > 25 = high fear, VIX < 15 = complacency.

- **[Vectorized Matplotlib Rendering](https://matplotlib.org/stable/api/collections_api.html)** — candlestick bodies use `PolyCollection` with a single `(n, 4, 2)` vertex array and wicks use `LineCollection` with a `(n, 2, 2)` segment array. This avoids n individual `Rectangle` patch objects per chart. Charts are rendered text-label-free (no tickers, no prices, no axis labels) to prevent the VLM from relying on prior knowledge of the ticker.

## Technologies

- **[NVIDIA NIM](https://build.nvidia.com/)** — free-tier API endpoint (`https://integrate.api.nvidia.com/v1`) hosting all three models. The pipeline authenticates via a Colab Secrets key (`NVIDIA_API_KEY`).

- **[MiniMax-M3](https://huggingface.co/minimaxai/minimax-m3)** — 428B MoE Vision-Language Model (~22B active parameters). Used for broad-coverage chart reading. Temperature 0.25, max_tokens 4096.

- **[Nemotron 3 Nano Omni 30B A3B (Reasoning)](https://build.nvidia.com/nvidia/nemotron-3-nano-omni-30b-a3b)** — 30B reasoning model with internal thought process enabled via `enable_thinking=True` and a 2048 reasoning budget. Strong on cross-timeframe alignment. Max_tokens 8192.

- **[Ministral 14B Instruct 2512 FP8](https://huggingface.co/mistralai/ministral-14b-instruct-2512)** — 14B instruct VLM in FP8 quantization, optimized for constrained environments. Temperature 0.15 per model card recommendation.

- **[deeptime](https://deeptime-ml.github.io/)** — `deeptime.util.diff.tv_derivative` provides Total-Variation-regularized numerical differentiation. Optional dependency — the pipeline falls back to `np.gradient` if absent or if the solver fails to converge on pathological inputs.

- **[Numba](https://numba.pydata.org/)** — JIT compiler for Python that translates the VWMA, log-return, momentum, and Heikin-Ashi functions to optimized machine code. All JIT functions use `nopython=True, nogil=True, cache=True` for thread-safe, no-GIL execution.

- **[OpenAI Python SDK](https://github.com/openai/openai-python)** — the `OpenAI` client is used with `base_url` pointed at the NVIDIA NIM endpoint. Streaming completions are consumed chunk-by-chunk to extract both `content` and `reasoning_content` (the Nemotron model's internal chain-of-thought).

## Project Structure
```
  vista/
  ├── vista_prediction.py     # entire pipeline — single-file Colab notebook
  ├── .vista_cache/           # Parquet-cached yfinance downloads (auto-created)
  │   └── {ticker}_{interval}.parquet
  ├── output/                 # rendered chart PNGs + forecast matrix (auto-created)
  │   ├── vista_{ticker}_wk.png
  │   ├── vista_{ticker}_dy.png
  │   ├── vista_{ticker}_15.png
  │   ├── vista_vix_daily.png
  │   └── vista_forecast_matrix.png
  └── requirements.txt
```
- **`.vista_cache/`** — Parquet files named `{ticker}_{interval}.parquet`. Expire after 12 hours (configurable via `CACHE_TTL_HOURS`). Sanitizes ticker names to filesystem-safe strings.
- **`output/`** — all chart PNGs and the final forecast matrix. Path auto-detects Colab (`/content`) vs. local (`.`) environment.
- **`vista_prediction.py`** — the entire pipeline in one file: data download, indicator computation, chart rendering, multi-model VLM calls, consensus aggregation, and result formatting. No external config files, no CLI arguments — all knobs are module-level constants at the top of the script.
