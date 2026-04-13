# -*- coding: utf-8 -*-
"""CatBoost Financial Time Series Predictor (walk-forward, 5-day horizon)."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import optuna
import pandas as pd
import talib
import yfinance as yf
from catboost import CatBoostRegressor, Pool
from IPython.display import HTML, display
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")


CONFIG = {
    "TICKERS": [
        'A', 'AAL', 'AALR3.SA', 'AAP', 'AAPL', 'AAZQ11.SA', 'ABBV', 'ABCB4.SA', 'ABCP11.SA', 'ABEV', 'ABNB', 'ABT', 'ACN', 'ACWI11.SA',
        'ADBE', 'ADI', 'ADM', 'ADP', 'ADSK', 'AEE', 'AEP', 'AERI3.SA', 'AES', 'AFHI11.SA', 'AFL', 'AGXY3.SA', 'AIEC11.SA', 'AIG',
        'AIV', 'AIZ', 'AJG', 'AKAM', 'ALB', 'ALC', 'ALGN', 'ALK', 'ALL', 'ALLD3.SA', 'ALLE', 'ALNY', 'ALPA3.SA', 'ALPA4.SA', 'ALPK3.SA',
        'ALUG11.SA', 'ALUP11.SA', 'ALUP3.SA', 'ALUP4.SA', 'ALZR11.SA', 'AMAR3.SA', 'AMAT', 'AMBP3.SA', 'AMC', 'AMCR', 'AMD', 'AME', 'AMER3.SA',
        'AMGN', 'AMP', 'AMT', 'AMZN', 'ANET', 'ANIM3.SA', 'AON', 'AOS', 'APA', 'APD', 'APH', 'APTO11.SA', 'APTV', 'ARE', 'ARES', 'ARGX',
        'ARML3.SA', 'ARRI11.SA', 'ARW', 'ARXD11.SA', 'ASAI3.SA', 'ASML', 'ASND', 'ATHM', 'ATO', 'AUGO', 'AURE3.SA', 'AVB', 'AVGO', 'AVY',
        'AWI', 'AWK', 'AXON', 'AXP', 'AZEV3.SA', 'AZEV4.SA', 'AZN', 'AZO', 'AZTA', 'B3SA3.SA', 'BA', 'BABA', 'BAC', 'BAH', 'BAK', 'BALL',
        'BALM4.SA', 'BAP', 'BAX', 'BAZA3.SA', 'BBAS3.SA', 'BBD', 'BBDO', 'BBFO11.SA', 'BBGO11.SA', 'BBOI11.SA', 'BBOV11.SA', 'BBRC11.SA',
        'BBSE3.SA', 'BBWI', 'BBY', 'BCHI39.SA', 'BCIA11.SA', 'BCRI11.SA', 'BCS', 'BDIF11.SA', 'BDIV11.SA', 'BDOM11.SA', 'BDX', 'BEEF3.SA',
        'BEEM39.SA', 'BEES3.SA', 'BEES4.SA', 'BEN', 'BFH', 'BFXI39.SA', 'BIAU39.SA', 'BIDU', 'BIIB', 'BILI', 'BILL', 'BIME11.SA', 'BIOM3.SA',
        'BITH11.SA', 'BITI11.SA', 'BIVB39.SA', 'BIVE39.SA', 'BK', 'BKNG', 'BKR', 'BL', 'BLAU3.SA', 'BLK', 'BLMG11.SA', 'BMBL', 'BMGB4.SA',
        'BMLC11.SA', 'BMOB3.SA', 'BMRN', 'BMY', 'BNDX11.SA', 'BNFS11.SA', 'BNTX', 'BODB11.SA', 'BOVA11.SA', 'BOVS11.SA', 'BOVV11.SA', 'BOVX11.SA',
        'BP', 'BPAC11.SA', 'BPML11.SA', 'BR', 'BRAP3.SA', 'BRAP4.SA', 'BRAX11.SA', 'BRBI', 'BRCO11.SA', 'BRCR11.SA', 'BRKM3.SA', 'BROF11.SA',
        'BRSR3.SA', 'BRSR6.SA', 'BSAC', 'BSBR', 'BSIL39.SA', 'BSX', 'BTAG11.SA', 'BTAL11.SA', 'BTCI11.SA', 'BTI', 'BTLG11.SA', 'BTRA11.SA',
        'BUD', 'BURA39.SA', 'BWA', 'BXP', 'BYND', 'C', 'CABO', 'CACR11.SA', 'CAG', 'CAH', 'CAMB3.SA', 'CAML3.SA', 'CARE11.SA', 'CARR', 'CASH3.SA',
        'CAT', 'CB', 'CBAV3.SA', 'CBOP11.SA', 'CBRE', 'CCI', 'CCL', 'CCME11.SA', 'CDII11.SA', 'CDNS', 'CDW', 'CE', 'CEAB3.SA', 'CEBR6.SA',
        'CEOC11.SA', 'CF', 'CFG', 'CGNX', 'CGRA3.SA', 'CGRA4.SA', 'CHD', 'CHDN', 'CHIP11.SA', 'CHKP', 'CHPT', 'CHRW', 'CHT', 'CHTR', 'CI',
        'CIG', 'CINF', 'CL', 'CLOV', 'CLSC4.SA', 'CLX', 'CMCSA', 'CME', 'CMG', 'CMI', 'CMIG3.SA', 'CMIN3.SA', 'CMS', 'CNC', 'CNI', 'CNP',
        'COCE5.SA', 'COF', 'COGN3.SA', 'COIN', 'COLM', 'COO', 'COP', 'CORN11.SA', 'COST', 'COTY', 'COUR', 'CPB', 'CPFE3.SA', 'CPRT', 'CPSH11.SA',
        'CPT', 'CPTI11.SA', 'CPTR11.SA', 'CPTS11.SA', 'CRAA11.SA', 'CRI', 'CRM', 'CRNC', 'CRPG5.SA', 'CRPT11.SA', 'CRSP', 'CRWD', 'CSAN', 'CSCO',
        'CSED3.SA', 'CSGP', 'CSMG3.SA', 'CSUD3.SA', 'CSX', 'CTAS', 'CTRA', 'CTSH', 'CTVA', 'CURY3.SA', 'CUZ', 'CVS', 'CVX', 'CX', 'CXCI11.SA',
        'CXCO11.SA', 'CXSE3.SA', 'CYCR11.SA', 'CYRE3.SA', 'CZR', 'D', 'DAL', 'DASA3.SA', 'DASH', 'DB', 'DCRA11.SA', 'DD', 'DDOG', 'DE', 'DEFI11.SA',
        'DELL', 'DEO', 'DESK3.SA', 'DEVA11.SA', 'DEXP3.SA', 'DG', 'DGX', 'DHI', 'DHR', 'DINO', 'DIRR3.SA', 'DIS', 'DIVO11.SA', 'DKNG', 'DKS', 'DLR',
        'DLTR', 'DMVF3.SA', 'DNLI', 'DOC', 'DOCS', 'DOCU', 'DOHL4.SA', 'DOLA11.SA', 'DOTZ3.SA', 'DOV', 'DOW', 'DOX', 'DPZ', 'DRI', 'DTE', 'DUK',
        'DVA', 'DVFF11.SA', 'DVN', 'DXC', 'DXCM', 'DXCO3.SA', 'EA', 'EALT4.SA', 'EBAY', 'EC', 'ECL', 'ED', 'EDU', 'EEFT', 'EFX', 'EGAF11.SA',
        'EGIE3.SA', 'EIX', 'EL', 'ELAS11.SA', 'ELPC', 'ELS', 'ELV', 'EMAE4.SA', 'EMN', 'EMR', 'ENDD11.SA', 'ENEV3.SA', 'ENGI11.SA', 'ENGI3.SA',
        'ENGI4.SA', 'ENJU3.SA', 'ENOV', 'ENPH', 'ENTG', 'EOG', 'EPAM', 'EPD', 'EQIR11.SA', 'EQIX', 'EQNR', 'EQPA3.SA', 'EQR', 'ERIC', 'ES',
        'ESPA3.SA', 'ESS', 'ETER3.SA', 'ETN', 'ETR', 'ETSY', 'EUCA4.SA', 'EVEN3.SA', 'EVRG', 'EW', 'EXC', 'EXEL', 'EXPD', 'EXPE', 'EXR', 'F',
        'FAED11.SA', 'FANG', 'FAST', 'FATN11.SA', 'FCFL11.SA', 'FCX', 'FDX', 'FE', 'FESA4.SA', 'FFIV', 'FGAA11.SA', 'FHER3.SA', 'FICO', 'FIGS11.SA',
        'FIIB11.SA', 'FIND11.SA', 'FIQE3.SA', 'FITB', 'FIVN11.SA', 'FIXX11.SA', 'FLCR11.SA', 'FLMA11.SA', 'FLRP11.SA', 'FLRY3.SA', 'FLS', 'FMC',
        'FNF', 'FNOR11.SA', 'FNV', 'FOMO11.SA', 'FOXA', 'FR', 'FRAS3.SA', 'FRT', 'FSLR', 'FSLY', 'FTI', 'FTNT', 'FTV', 'G2DI33.SA', 'GAME11.SA',
        'GAP', 'GCRI11.SA', 'GD', 'GDDY', 'GDS', 'GE', 'GENB11.SA', 'GEPA4.SA', 'GFI', 'GFSA3.SA', 'GGB', 'GGBR3.SA', 'GGPS3.SA', 'GGRC11.SA',
        'GILD', 'GIS', 'GL', 'GLOG11.SA', 'GLPG', 'GLW', 'GM', 'GMAT3.SA', 'GMED', 'GNTX', 'GOAU3.SA', 'GOAU4.SA', 'GOLD11.SA', 'GOOG', 'GOOGL',
        'GPC', 'GPN', 'GPRK', 'GPRO', 'GRMN', 'GRND3.SA', 'GRWA11.SA', 'GS', 'GSFI11.SA', 'GSK',  'GWRE', 'GWW', 'GZIT11.SA', 'HABT11.SA',
        'HAGA4.SA', 'HAL', 'HAPV3.SA', 'HAS', 'HASH11.SA', 'HBAN', 'HBOR3.SA', 'HBRE3.SA', 'HBSA3.SA', 'HCA', 'HCHG11.SA', 'HCRI11.SA', 'HCTR11.SA',
        'HD', 'HDB', 'HEI', 'HFOF11.SA', 'HGBS11.SA', 'HGCR11.SA', 'HGIC11.SA', 'HGLG11.SA', 'HGPO11.SA', 'HGRE11.SA', 'HGRU11.SA', 'HIG',
        'HII', 'HLOG11.SA', 'HLT', 'HMC', 'HOG', 'HOLX', 'HON', 'HPE', 'HPQ', 'HRB', 'HRL', 'HSAF11.SA', 'HSBC', 'HST', 'HSY',
        'HTEK11.SA', 'HTMX11.SA', 'HUBS', 'HUM', 'HWM', 'HYPE3.SA', 'IAAG11.SA', 'IAGR11.SA', 'IBCR11.SA', 'IBM', 'ICE', 'IDXX',
        'IEX', 'IFCM3.SA', 'IFF', 'IFRA11.SA', 'IGTI11.SA', 'IHG', 'ILMN', 'INCY', 'INEP3.SA', 'INFY', 'INGR', 'INTB3.SA', 'INTC', 'INTR', 'INTU',
        'INVH', 'IP', 'IPGP', 'IQ', 'IQV', 'IR', 'IRBR3.SA', 'IRIM11.SA', 'IRM', 'ISRG', 'IT', 'ITIP11.SA', 'ITIT11.SA', 'ITSA3.SA', 'ITSA4.SA',
        'ITUB', 'ITUB3.SA', 'ITW', 'IVVB11.SA', 'IVZ', 'IX', 'J', 'JALL3.SA', 'JAZZ', 'JBHT', 'JBL', 'JBS', 'JCI', 'JD', 'JEF', 'JFEN3.SA',
        'JGPX11.SA', 'JHSF3.SA', 'JKHY', 'JNJ', 'JOGO11.SA', 'JPM', 'JPPA11.SA', 'JSAF11.SA', 'JSLG3.SA', 'JSRE11.SA', 'JURO11.SA', 'KC',
        'KCRE11.SA', 'KEPL3.SA', 'KEY', 'KEYS', 'KFOF11.SA', 'KHC', 'KIM', 'KISU11.SA', 'KIVO11.SA', 'KLAC', 'KLBN11.SA', 'KLBN3.SA', 'KLBN4.SA',
        'KMB', 'KMI', 'KMPR', 'KMX', 'KNCA11.SA', 'KNCR11.SA', 'KNHF11.SA', 'KNHY11.SA', 'KNIP11.SA', 'KNRE11.SA', 'KNRI11.SA', 'KNSC11.SA',
        'KO', 'KORE11.SA', 'KR', 'KRC', 'KSS', 'L', 'LAND3.SA', 'LAVV3.SA', 'LDOS', 'LEG', 'LEN', 'LEVE3.SA', 'LH', 'LHX', 'LIFE11.SA', 'LIGT3.SA',
        'LIVN', 'LJQQ3.SA', 'LLY', 'LMT', 'LNC', 'LND', 'LOGG3.SA', 'LOW', 'LRCX', 'LSAG11.SA', 'LSCC', 'LULU', 'LUMN', 'LUPA3.SA', 'LUV',
        'LVBI11.SA', 'LVS', 'LW', 'LWSA3.SA', 'LYB', 'LYG', 'LYV', 'M', 'MA', 'MAA', 'MANA11.SA', 'MAR', 'MAS', 'MASI', 'MATB11.SA', 'MATD3.SA',
        'MAXR11.SA', 'MBRF3.SA', 'MCCI11.SA', 'MCD', 'MCHP', 'MCK', 'MCO', 'MDB', 'MDIA3.SA', 'MDLZ', 'MDNE3.SA', 'MDT', 'MELI', 'MELK3.SA',
        'MET', 'META', 'META11.SA', 'MFII11.SA', 'MGHT11.SA', 'MGLU3.SA', 'MGM', 'MHK', 'MILS3.SA', 'MKC', 'MKL', 'MKTX', 'MLAS3.SA', 'MMM',
        'MNPR3.SA', 'MNST', 'MO', 'MOS', 'MP', 'MPC', 'MRK', 'MRNA', 'MRVE3.SA', 'MRVL', 'MS', 'MSCI', 'MSFT', 'MSI', 'MSTR', 'MT', 'MTB', 'MTCH',
        'MTD', 'MTRE3.SA', 'MU', 'MUFG', 'MULT3.SA', 'MXRF11.SA', 'MYPK3.SA', 'NASD11.SA', 'NAVT11.SA', 'NBIX', 'NCLH', 'NCRI11.SA', 'NDAQ', 'NEE',
        'NEM', 'NEOE3.SA', 'NET', 'NEWL11.SA', 'NEWU11.SA', 'NFLX', 'NGG', 'NI', 'NICE', 'NKE', 'NLY', 'NMR', 'NOC', 'NOK', 'NOW', 'NRG', 'NSC',
        'NSLU11.SA', 'NTAP', 'NTES', 'NTRS', 'NU', 'NUE', 'NUTR3.SA', 'NVDA', 'NVO', 'NVR', 'NVS', 'NWG', 'NWL', 'NWS', 'NWSA', 'NXPI', 'O', 'ODFL',
        'ODPV3.SA', 'OGIN11.SA', 'OIAG11.SA', 'OKE', 'OKTA', 'OMC', 'ON', 'ONCO3.SA', 'OPCT3.SA', 'ORCL', 'ORLY', 'ORVR3.SA', 'OTIS', 'OXY', 'PAGS',
        'PANW', 'PATH', 'PATL11.SA', 'PAYC', 'PAYX', 'PBR', 'PCAR', 'PCAR3.SA', 'PCOR', 'PDD', 'PDGR3.SA', 'PDTC3.SA', 'PEG', 'PEP', 'PETR4.SA',
        'PFE', 'PFG', 'PFIN11.SA', 'PFRM3.SA', 'PGMN3.SA', 'PGR', 'PH', 'PHM', 'PIBB11.SA', 'PINE4.SA', 'PINS', 'PKG', 'PKX', 'PLD', 'PLNT',
        'PLPL3.SA', 'PLTR', 'PM', 'PNC', 'PNR', 'PNVL3.SA', 'PNW', 'PODD', 'POMO3.SA', 'POMO4.SA', 'PORD11.SA', 'POSI3.SA', 'PPG', 'PPL',
        'PPLA11.SA', 'PRIO3.SA', 'PRNR3.SA', 'PRU', 'PSA', 'PSSA3.SA', 'PSX', 'PTBL3.SA', 'PTNT4.SA', 'PUK', 'PVBI11.SA', 'PVH', 'PWR', 'PYPL',
        'QBTC11.SA', 'QCOM', 'QDFI11.SA', 'QRVO', 'QS', 'QSOL11.SA', 'QUAL3.SA', 'RADL3.SA', 'RAIL3.SA', 'RAIZ4.SA', 'RANI3.SA', 'RAPT3.SA',
        'RAPT4.SA', 'RBHG11.SA', 'RBHY11.SA', 'RBIR11.SA', 'RBLX', 'RBRD11.SA', 'RBRL11.SA', 'RBRP11.SA', 'RBRR11.SA', 'RBRX11.SA', 'RBRY11.SA',
        'RBVA11.SA', 'RCL', 'RCRB11.SA', 'RCSL3.SA', 'RCSL4.SA', 'RDOR3.SA', 'RDY', 'RECR11.SA', 'RECT11.SA', 'RECV3.SA', 'REDE3.SA', 'REG',
        'REGN', 'RELG11.SA', 'RELX', 'RENT3.SA', 'RF', 'RH', 'RHI', 'RIG', 'RINV11.SA', 'RIO', 'RJF', 'RL', 'RMD', 'RNEW3.SA', 'RNEW4.SA', 'ROK',
        'ROKU', 'ROL', 'ROMI3.SA', 'ROP', 'ROST', 'RPRI11.SA', 'RSG', 'RSUL4.SA', 'RTX', 'RURA11.SA', 'RYAAY', 'RZAG11.SA', 'RZAK11.SA', 'RZTR11.SA',
        'SAN', 'SANB3.SA', 'SANB4.SA', 'SAP', 'SAPR11.SA', 'SAPR3.SA', 'SAPR4.SA', 'SBFG3.SA', 'SBS', 'SBUX', 'SCAR3.SA', 'SCHW', 'SCPF11.SA', 'SE',
        'SEDG', 'SEE', 'SEER3.SA', 'SEQL3.SA', 'SEQR11.SA', 'SGML', 'SHOP', 'SHOW3.SA', 'SHPH11.SA', 'SHUL4.SA', 'SHW', 'SID', 'SIMH3.SA', 'SIRI',
        'SJM', 'SKM', 'SLB', 'SLCE3.SA', 'SMAC11.SA', 'SMAL11.SA', 'SMFG', 'SMFT3.SA', 'SMTO3.SA', 'SNA', 'SNAG11.SA', 'SNAP', 'SNCI11.SA', 'SNFF11.SA',
        'SNID11.SA', 'SNN', 'SNOW', 'SNPS', 'SO', 'SOJA3.SA', 'SOLH11.SA', 'SONY', 'SPG', 'SPGI', 'SPOT', 'SPTW11.SA', 'SPXI11.SA',
        'SPXS11.SA', 'SRE', 'SRPT', 'STE', 'STM', 'STNE', 'STT', 'STZ', 'SUZ', 'SVAL11.SA', 'SWK', 'SWKS', 'SYF', 'SYK', 'SYNE3.SA', 'SYY', 'T',
        'TAEE11.SA', 'TAEE3.SA', 'TAEE4.SA', 'TAL', 'TAP', 'TASA3.SA', 'TASA4.SA', 'TCSA3.SA', 'TDG', 'TDOC', 'TECH', 'TECK11.SA', 'TECN3.SA', 'TEL',
        'TEND3.SA', 'TEPP11.SA', 'TFC', 'TFCO4.SA', 'TFX', 'TGAR11.SA', 'TGMA3.SA', 'TGT', 'THG', 'TIMB', 'TJX', 'TM', 'TMO', 'TMUS', 'TORD11.SA',
        'TOTS3.SA', 'TPIS3.SA', 'TPR', 'TRAD3.SA', 'TRBL11.SA', 'TRIG11.SA', 'TRIP', 'TRIS3.SA', 'TROW', 'TRV', 'TRXF11.SA', 'TS', 'TSCO', 'TSLA',
        'TSM', 'TSN', 'TT', 'TTD', 'TTEN3.SA', 'TTWO', 'TUPY3.SA', 'TWLO', 'TX', 'TXN', 'TXT', 'U', 'UAA', 'UAL', 'UBER', 'UBS', 'UCAS3.SA', 'UDR',
        'UGP', 'UHS', 'UL', 'ULTA', 'UNH', 'UNIP3.SA', 'UNIP6.SA', 'UNM', 'UNP', 'UPS', 'UPST', 'UPWK', 'URI', 'URPR11.SA', 'USAL11.SA', 'USB',
        'USDB11.SA', 'USIM3.SA', 'USIM5.SA', 'USTK11.SA', 'UTEC11.SA', 'V', 'VALE', 'VAMO3.SA', 'VBBR3.SA', 'VCJR11.SA', 'VCRA11.SA', 'VCRI11.SA',
        'VCRR11.SA', 'VEEV', 'VFC', 'VGHF11.SA', 'VGIA11.SA', 'VGIP11.SA', 'VGIR11.SA', 'VGRI11.SA', 'VILG11.SA', 'VINO11.SA', 'VIPS', 'VISC11.SA',
        'VITT3.SA', 'VIUR11.SA', 'VIV', 'VIVA3.SA', 'VIVR3.SA', 'VLID3.SA', 'VLO', 'VLY', 'VMC', 'VNO', 'VOD', 'VRNS', 'VRSK', 'VRSN', 'VRTA11.SA',
        'VRTX', 'VSLH11.SA', 'VSTE3.SA', 'VTEX', 'VTR', 'VULC3.SA', 'VVEO3.SA', 'VZ', 'W', 'WAB', 'WAL', 'WAT', 'WB', 'WBD', 'WDAY', 'WDC', 'WEB311.SA',
        'WEC', 'WEGE3.SA', 'WELL', 'WEST3.SA', 'WEX', 'WFC', 'WHGR11.SA', 'WHR', 'WHRL3.SA', 'WHRL4.SA', 'WIZC3.SA', 'WLY', 'WM', 'WMB', 'WMT', 'WPP',
        'WRB', 'WRLD11.SA', 'WSO', 'WST', 'WU', 'WY', 'WYNN', 'XEL', 'XFIX11.SA', 'XINA11.SA', 'XOM', 'XP', 'XPCA11.SA', 'XPCI11.SA', 'XPCM11.SA',
        'XPEV', 'XPID11.SA', 'XPIE11.SA', 'XPIN11.SA', 'XPLG11.SA', 'XPML11.SA', 'XRAY', 'XRPH11.SA', 'XRX', 'XYL', 'YDUQ3.SA', 'YUM', 'ZAVI11.SA',
        'ZBH', 'ZBRA', 'ZG', 'ZM', 'ZS', 'ZTO', 'ZTS',
    ],
    "MACRO_TICKERS": ["^VIX", "DX-Y.NYB", "GC=F", "BZ=F"],
    "HORIZONS": [1, 2, 3, 4, 5],
    "LAG_DAYS": [1, 2, 3, 5, 10],
    "MIN_HISTORY_DAYS": 80,
    "RSI_PERIOD": 14,
    "MA_VOL_PERIOD": 20,
    "PERIOD": "12mo",
    "INTERVAL": "1d",
    "VAL_SIZE": 0.20,
    "N_FOLDS": 4,
    "OPTUNA_TRIALS": 16,
    "OPTUNA_TIMEOUT_SEC": 480,
    "FINAL_ITERATIONS": 700,
    "TUNE_ITERATIONS": 350,
    "EARLY_STOP_ROUNDS": 80,
    "TABLE_TOP_N": 10,
    "CHART_TOP_N": 10,
    "PARQUET_FILE": "market_data.parquet",
}

MODEL_FEATURES = [
    "Ticker",
    "Log_Ret_1d",
    "Log_Ret_Z",
    "RSI",
    "Rel_Volume",
    "ATR_Norm",
    "Range_Norm",
    "Roll_Vol_10",
    "Roll_Mean_5",
] + [f"Lag_{lag}" for lag in CONFIG["LAG_DAYS"]] + [f"Macro_Ret_{x}" for x in CONFIG["MACRO_TICKERS"]]


@dataclass(frozen=True)
class FoldIndices:
    train_mask: np.ndarray
    val_mask: np.ndarray


def ingest_market_data(tickers: Sequence[str], macro_tickers: Sequence[str]) -> pd.DataFrame:
    all_tickers = list(dict.fromkeys(list(tickers) + list(macro_tickers)))
    raw_df = yf.download(
        all_tickers,
        period=CONFIG["PERIOD"],
        interval=CONFIG["INTERVAL"],
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    close_frame = raw_df["Close"]
    present_main = [x for x in tickers if x in close_frame.columns]
    present_macro = [x for x in macro_tickers if x in close_frame.columns]

    main_stack = raw_df.loc[:, (slice(None), present_main)].stack(level=1, future_stack=True).reset_index()
    main_stack = main_stack.rename(columns={"level_1": "Ticker"})
    cols = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]
    main_df = main_stack[cols].dropna(subset=["Close"]).copy()

    counts = main_df["Ticker"].value_counts()
    valid_tickers = counts[counts >= CONFIG["MIN_HISTORY_DAYS"]].index
    main_df = main_df[main_df["Ticker"].isin(valid_tickers)].copy()

    macro_df = close_frame[present_macro].copy().sort_index().ffill()
    macro_returns = np.log(macro_df / macro_df.shift(1))
    macro_returns.columns = [f"Macro_Ret_{x}" for x in present_macro]

    merged = main_df.merge(macro_returns.reset_index(), on="Date", how="left")
    merged = merged.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    macro_cols = [f"Macro_Ret_{x}" for x in present_macro]
    if macro_cols:
        merged[macro_cols] = merged.groupby("Ticker", observed=True)[macro_cols].ffill().bfill()

    merged.to_parquet(CONFIG["PARQUET_FILE"], index=False)
    return merged


def calculate_technical_indicators(group: pd.DataFrame) -> pd.DataFrame:
    out = group.copy()
    close = out["Close"].to_numpy(dtype=np.float64)
    high = out["High"].to_numpy(dtype=np.float64)
    low = out["Low"].to_numpy(dtype=np.float64)
    volume = out["Volume"].to_numpy(dtype=np.float64)

    out["Mid_Price"] = (high + low + (2.0 * close)) / 4.0
    out["Log_Ret_1d"] = np.insert(np.log(out["Mid_Price"].to_numpy()[1:] / out["Mid_Price"].to_numpy()[:-1]), 0, np.nan)
    out["RSI"] = talib.RSI(close, timeperiod=CONFIG["RSI_PERIOD"])

    ma_vol = talib.SMA(volume, timeperiod=CONFIG["MA_VOL_PERIOD"])
    out["Rel_Volume"] = np.where(ma_vol > 0.0, volume / ma_vol, 1.0)

    atr = talib.ATR(high, low, close, timeperiod=CONFIG["RSI_PERIOD"])
    out["ATR_Norm"] = np.where(close != 0.0, atr / close, np.nan)
    out["Range_Norm"] = np.where(close != 0.0, (high - low) / close, np.nan)

    out["Roll_Vol_10"] = out["Log_Ret_1d"].rolling(10, min_periods=3).std()
    out["Roll_Mean_5"] = out["Log_Ret_1d"].rolling(5, min_periods=2).mean()

    for lag in CONFIG["LAG_DAYS"]:
        out[f"Lag_{lag}"] = out["Log_Ret_1d"].shift(lag)

    rolling_window = CONFIG["MIN_HISTORY_DAYS"]
    rolling_mean = out["Log_Ret_1d"].rolling(rolling_window, min_periods=10).mean()
    rolling_std = out["Log_Ret_1d"].rolling(rolling_window, min_periods=10).std()
    out["Log_Ret_Z"] = (out["Log_Ret_1d"] - rolling_mean) / rolling_std
    return out


def apply_feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    feature_df = df.groupby("Ticker", group_keys=False, observed=True).apply(calculate_technical_indicators)
    feature_df = feature_df.replace([np.inf, -np.inf], np.nan)
    return feature_df.reset_index(drop=True)


def create_ticker_targets(group: pd.DataFrame) -> pd.DataFrame:
    out = group.copy()
    mid_price = out["Mid_Price"]
    for horizon in CONFIG["HORIZONS"]:
        future = mid_price.shift(-horizon)
        target = np.log(future / mid_price)
        out[f"Target_D{horizon}"] = np.clip(target, -0.40, 0.40)
    return out


def build_targets(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("Ticker", group_keys=False, observed=True).apply(create_ticker_targets).reset_index(drop=True)


def get_fold_masks(unique_dates: pd.Series) -> List[FoldIndices]:
    date_count = len(unique_dates)
    fold_count = CONFIG["N_FOLDS"]
    val_points = max(10, int(date_count * CONFIG["VAL_SIZE"] / fold_count))
    train_start_points = max(CONFIG["MIN_HISTORY_DAYS"], int(date_count * 0.40))

    masks: List[FoldIndices] = []
    for fold_idx in range(fold_count):
        train_end = train_start_points + (fold_idx * val_points)
        val_end = min(date_count, train_end + val_points)
        if val_end <= train_end:
            continue
        train_dates = unique_dates.iloc[:train_end]
        val_dates = unique_dates.iloc[train_end:val_end]
        masks.append(
            FoldIndices(
                train_mask=np.isin(unique_dates.to_numpy(), train_dates.to_numpy()),
                val_mask=np.isin(unique_dates.to_numpy(), val_dates.to_numpy()),
            )
        )
    return masks


def prepare_model_matrix(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    required = [target_col] + [x for x in MODEL_FEATURES if x in df.columns]
    model_df = df.dropna(subset=required).sort_values("Date").copy()
    model_df["Ticker"] = model_df["Ticker"].astype(str)
    return model_df


def fold_slices(model_df: pd.DataFrame) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    unique_dates = pd.Series(sorted(model_df["Date"].unique()))
    folds = get_fold_masks(unique_dates)
    slices: List[Tuple[pd.DataFrame, pd.DataFrame]] = []
    for fold in folds:
        train_dates = set(unique_dates[fold.train_mask])
        val_dates = set(unique_dates[fold.val_mask])
        train_df = model_df[model_df["Date"].isin(train_dates)]
        val_df = model_df[model_df["Date"].isin(val_dates)]
        if train_df.empty or val_df.empty:
            continue
        slices.append((train_df, val_df))
    return slices


def choose_catboost_device() -> str:
    return "GPU" if os.environ.get("COLAB_GPU") else "CPU"


def evaluate_random_walk(val_df: pd.DataFrame, target_col: str) -> float:
    y_val = val_df[target_col].to_numpy()
    rw_pred = np.zeros(len(y_val), dtype=np.float64)
    return float(np.mean(np.abs(y_val - rw_pred)))


def objective_factory(train_df: pd.DataFrame, val_df: pd.DataFrame, target_col: str):
    valid_features = [x for x in MODEL_FEATURES if x in train_df.columns]
    train_pool = Pool(train_df[valid_features], train_df[target_col], cat_features=["Ticker"])
    val_pool = Pool(val_df[valid_features], val_df[target_col], cat_features=["Ticker"])
    task_type = choose_catboost_device()

    def objective(trial: optuna.trial.Trial) -> float:
        params = {
            "iterations": CONFIG["TUNE_ITERATIONS"],
            "depth": trial.suggest_int("depth", 5, 9),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.08, log=True),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
            "subsample": trial.suggest_float("subsample", 0.70, 1.00),
            "loss_function": "MAE",
            "eval_metric": "MAE",
            "task_type": task_type,
            "verbose": 0,
            "allow_writing_files": False,
        }
        if task_type == "GPU":
            params["devices"] = "0"

        model = CatBoostRegressor(**params)
        model.fit(train_pool, eval_set=val_pool, use_best_model=True, early_stopping_rounds=CONFIG["EARLY_STOP_ROUNDS"])
        pred = model.predict(val_df[valid_features])
        return float(np.mean(np.abs(val_df[target_col].to_numpy() - pred)))

    return objective


def tune_and_train_for_target(model_df: pd.DataFrame, target_col: str) -> Tuple[CatBoostRegressor, float, float]:
    slices = fold_slices(model_df)
    if not slices:
        raise ValueError(f"No valid walk-forward folds for {target_col}.")

    tune_train, tune_val = slices[-1]
    study = optuna.create_study(direction="minimize", pruner=optuna.pruners.MedianPruner(n_warmup_steps=5))
    study.optimize(
        objective_factory(tune_train, tune_val, target_col),
        n_trials=CONFIG["OPTUNA_TRIALS"],
        timeout=CONFIG["OPTUNA_TIMEOUT_SEC"],
        show_progress_bar=False,
    )

    best = study.best_params
    task_type = choose_catboost_device()
    final_params = {
        "iterations": CONFIG["FINAL_ITERATIONS"],
        "depth": int(best["depth"]),
        "learning_rate": float(best["learning_rate"]),
        "l2_leaf_reg": float(best["l2_leaf_reg"]),
        "subsample": float(best["subsample"]),
        "loss_function": "MAE",
        "eval_metric": "MAE",
        "task_type": task_type,
        "verbose": 0,
        "allow_writing_files": False,
    }
    if task_type == "GPU":
        final_params["devices"] = "0"

    features = [x for x in MODEL_FEATURES if x in model_df.columns]
    oof_mae_catboost: List[float] = []
    oof_mae_rw: List[float] = []
    for fold_train, fold_val in slices:
        train_pool = Pool(fold_train[features], fold_train[target_col], cat_features=["Ticker"])
        val_pool = Pool(fold_val[features], fold_val[target_col], cat_features=["Ticker"])
        fold_model = CatBoostRegressor(**final_params)
        fold_model.fit(train_pool, eval_set=val_pool, use_best_model=True, early_stopping_rounds=CONFIG["EARLY_STOP_ROUNDS"])
        fold_pred = fold_model.predict(fold_val[features])
        oof_mae_catboost.append(float(np.mean(np.abs(fold_val[target_col].to_numpy() - fold_pred))))
        oof_mae_rw.append(evaluate_random_walk(fold_val, target_col))

    final_train_pool = Pool(model_df[features], model_df[target_col], cat_features=["Ticker"])
    final_model = CatBoostRegressor(**final_params)
    final_model.fit(final_train_pool)

    return final_model, float(np.mean(oof_mae_catboost)), float(np.mean(oof_mae_rw))


def build_forecast_table(df_model: pd.DataFrame, models: Dict[str, CatBoostRegressor]) -> pd.DataFrame:
    valid_features = [x for x in MODEL_FEATURES if x in df_model.columns]
    latest_rows = df_model.dropna(subset=valid_features).groupby("Ticker", observed=True).tail(1)
    results: List[Dict[str, float]] = []

    for _, row in latest_rows.iterrows():
        current_price = float(row["Close"])
        ticker_data = {"Ticker": row["Ticker"], "Preço Atual": current_price}
        for horizon in CONFIG["HORIZONS"]:
            target_col = f"Target_D{horizon}"
            pred_log = float(models[target_col].predict(row[valid_features].to_frame().T)[0])
            pred_log = float(np.clip(pred_log, -0.40, 0.40))
            ticker_data[f"Proj. D+{horizon}"] = float(np.exp(pred_log) * current_price)

        max_h = max(CONFIG["HORIZONS"])
        p_max = ticker_data[f"Proj. D+{max_h}"]
        pct = ((p_max / current_price) - 1.0) * 100.0
        ticker_data[f"Var % (D+{max_h})"] = pct
        ticker_data["Direção"] = "ALTA" if pct > 0 else "BAIXA"
        results.append(ticker_data)

    rank_col = f"Var % (D+{max(CONFIG['HORIZONS'])})"
    return pd.DataFrame(results).sort_values(rank_col, ascending=False)


def display_outputs(df_model: pd.DataFrame, report_df: pd.DataFrame, metric_table: pd.DataFrame) -> None:
    max_h = max(CONFIG["HORIZONS"])
    rank_col = f"Var % (D+{max_h})"

    display(HTML("<h3>Comparação MAE (Walk-Forward)</h3>"))
    display(metric_table.style.format({"CatBoost_MAE": "{:.5f}", "RandomWalk_MAE": "{:.5f}", "Gain_vs_RW_%": "{:+.2f}%"}).hide(axis="index"))

    display(HTML(f"<h3>Tabela de Projeções (Top {CONFIG['TABLE_TOP_N']})</h3>"))
    format_dict = {"Preço Atual": "{:.2f}", rank_col: "{:+.2f}%"}
    for horizon in CONFIG["HORIZONS"]:
        format_dict[f"Proj. D+{horizon}"] = "{:.2f}"
    display(report_df.head(CONFIG["TABLE_TOP_N"]).style.format(format_dict).hide(axis="index"))

    n_charts = CONFIG["CHART_TOP_N"]
    if n_charts <= 0:
        return

    tickers_to_plot = report_df.head(n_charts)["Ticker"].tolist()
    row_count = max(1, (len(tickers_to_plot) + 1) // 2)
    fig, axes = plt.subplots(row_count, 2, figsize=(15, row_count * 5))
    axes_array = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for plot_idx, ticker in enumerate(tickers_to_plot):
        ax = axes_array[plot_idx]
        history = df_model[df_model["Ticker"] == ticker].tail(30)
        now_date = history["Date"].iloc[-1]
        proj_row = report_df[report_df["Ticker"] == ticker].iloc[0]

        ax.plot(history["Date"], history["Close"], color="#2c3e50", lw=2, label="Histórico")
        future_dates = [now_date + pd.Timedelta(days=h) for h in CONFIG["HORIZONS"]]
        future_prices = [proj_row[f"Proj. D+{h}"] for h in CONFIG["HORIZONS"]]
        ax.plot(future_dates, future_prices, "o--", color="#27ae60", label="Predição")
        ax.axvline(x=now_date, color="red", ls="--", alpha=0.4)
        ax.set_title(str(ticker), fontweight="bold")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

    for empty_idx in range(len(tickers_to_plot), len(axes_array)):
        fig.delaxes(axes_array[empty_idx])

    plt.tight_layout()
    plt.show()


def run_validation_tests(df_model: pd.DataFrame) -> None:
    required_cols = [f"Target_D{h}" for h in CONFIG["HORIZONS"]] + [f"Proj. D+{h}" for h in CONFIG["HORIZONS"]]
    if df_model.empty:
        raise AssertionError("Model DataFrame is empty after preprocessing.")

    date_sorted = df_model.sort_values(["Ticker", "Date"])
    sample = date_sorted.groupby("Ticker", observed=True).head(20)
    if sample["Date"].isna().any():
        raise AssertionError("Date contains nulls.")

    has_target = [f"Target_D{h}" in df_model.columns for h in CONFIG["HORIZONS"]]
    if not all(has_target):
        raise AssertionError("Missing target columns.")

    _ = required_cols


def main() -> None:
    print("1. Ingesting Data...")
    df_raw = ingest_market_data(CONFIG["TICKERS"], CONFIG["MACRO_TICKERS"])

    print("2. Engineering Features...")
    df_feat = apply_feature_engineering(df_raw)

    print("3. Building Targets...")
    df_model = build_targets(df_feat)
    run_validation_tests(df_model)

    model_by_target: Dict[str, CatBoostRegressor] = {}
    metrics: List[Dict[str, float]] = []

    for horizon in CONFIG["HORIZONS"]:
        target_col = f"Target_D{horizon}"
        print(f"4. Training with walk-forward: {target_col}")
        model_input = prepare_model_matrix(df_model, target_col)
        model, mae_catboost, mae_rw = tune_and_train_for_target(model_input, target_col)
        model_by_target[target_col] = model
        gain = ((mae_rw - mae_catboost) / mae_rw) * 100.0 if mae_rw > 0 else 0.0
        metrics.append({
            "Horizon": f"D+{horizon}",
            "CatBoost_MAE": mae_catboost,
            "RandomWalk_MAE": mae_rw,
            "Gain_vs_RW_%": gain,
        })

    metric_table = pd.DataFrame(metrics)
    report_df = build_forecast_table(df_model, model_by_target)
    display_outputs(df_model, report_df, metric_table)


if __name__ == "__main__":
    main()
