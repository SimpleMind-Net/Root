# Julia code
This folder contains a set of notebooks written in Julia (1) for the analysis of **422 assets** (stocks, ETF, FII, BDR) of the **Brazilian stock exchange, B3**, based on **non-parametric regression** (2) of the historical series of prices of adjusted closes, obtained from **Yahoo Finance**. The non-parametric regression is performed considering a Gaussian Kernel with bandwidth, smoothing parameter, of 11 days.

- ***Acoes-YFinance.ipynb*** performs 260-day series analysis for an asset. Returns the graph of the price series with the regressed curve, the closing mode and the histogram of the daily profitability with the regressed curve.

- ***YFinance-Various-Stocks.ipynb*** analyzes the slope of the regressed curve for an 80-day series of the prices of each of the 422 assets, listing those with long trend.

### Why Julia?
- Is fast! Julia's code is compiled, which runs all this analysis for 422 assets in a very short time.
- Mathematical syntax and functional paradigm. Very suitable for scientific programming, producing concise and readable code.

### References
(1) [https://julialang.org/](https://julialang.org/)

(2) [https://en.wikipedia.org/wiki/Nonparametric_statistics](https://en.wikipedia.org/wiki/Nonparametric_statistics)
