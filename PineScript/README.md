# Read Me
### Indicador TradeView Double Linear Regression Trend Channel and Nadaraya-Watson Envelope
### 
This study includes two highly customized indicators via *PineScript* coding for technical stock prices trend analysis in *TradeView plattaform*.

###### Double Linear Regression Trend Channel
###### 
The first indicator is in script lines 10 to 102 that define two linear regression channels over the same historical series of stock prices. Each of them is calculated for different length periods, arbitrarily named "short-channel" and "long-channel". The slope difference between the two channels makes it possible to *objectively* identify changes in the trend: when the rising price forms a top, or when the falling price forms a bottom.

##### Nadaraya-Watson Envelope

The second indicator, in lines 25 to 30 and 105 to 173, is a non-parametric kernel estimator based on the Nadaraya-Watson formulation, represented in the form of a price envelope.

The code was changed so that the estimator calculation period window automatically adapts to the smallest value between the number of bars available in the historical series and a fixed number of 200 bars (corresponding to about 6 months of the series in a daily timeframe) . The calculation of the most recent slope of the estimator was also added, informing in a label on the present date whether it is positive ("rises") or negative ("descends") and the price values ​​in the upper and lower range of the envelope measured in the bar last.

##### Conclusion
##### 
In the practical application of swing trade on the Brazilian Stock Exchange (B3), both for shares of companies listed only in Brazil and for BDRs of companies and ETFs listed on American exchanges, these two indicators are interesting, both for identifying anticipated reversal of trends as for price forecast for trade entry and exit.


Credits to original sources:
* [Linear Regresion Trend Channel Source](https://www.tradingview.com/script/CD7yUWRV-Linear-Regression-Trend-Channel/) - midtownsk8rguy
* [Nadaraya-Watson Envelope \[LUX\] source](https://www.tradingview.com/script/Iko0E2kL-Nadaraya-Watson-Envelope-LUX/%20) - LuxAlgo

*Copyright: The code may be freely reproduced and altered by the community. It is recommended to cite credits to the author.*
*Disclaimer: The author is not responsible for the results obtained from applying the code.*
