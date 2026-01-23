import streamlit as st
import yfinance as yf
import pandas as pd
import concurrent.futures
import plotly.graph_objects as go
import numpy as np
import pytz
import requests
from datetime import datetime, time, timedelta

# ==========================================
# 🔑 API 설정 (Finnhub)
# ==========================================
FINNHUB_API_KEY = "d5p0p81r01qu6m6bocv0d5p0p81r01qu6m6bocvg"

# === [1. 페이지 설정] ===
st.set_page_config(page_title="QUANT NEXUS : FINAL MASTER", page_icon="🦅", layout="wide", initial_sidebar_state="expanded")

# === [2. 관심종목 세션] ===
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = set()

# === [3. 유틸리티] ===
def get_market_status():
    ny_tz = pytz.timezone('America/New_York')
    now_ny = datetime.now(ny_tz)
    if now_ny.weekday() >= 5: return "CLOSE", "마감(휴일)", "mkt-cls"
    curr = now_ny.time()
    if time(4,0) <= curr < time(9,30): return "PRE", "프리장", "mkt-pre"
    elif time(9,30) <= curr <= time(16,0): return "REG", "정규장", "mkt-reg"
    elif time(16,0) < curr <= time(20,0): return "AFTER", "애프터", "mkt-aft"
    else: return "CLOSE", "마감", "mkt-cls"

def check_recent_news(ticker):
    if not FINNHUB_API_KEY: return False, None
    try:
        fr = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        to = datetime.now().strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={fr}&to={to}&token={FINNHUB_API_KEY}"
        res = requests.get(url, timeout=2)
        if res.status_code == 200:
            data = res.json()
            if data and isinstance(data, list) and len(data) > 0:
                return True, data[0].get('headline', '뉴스 내용 없음')
    except: pass
    return False, None

def get_timestamp_str():
    ny_tz = pytz.timezone('America/New_York')
    return datetime.now(ny_tz).strftime("%Y-%m-%d %H:%M:%S")

# === [4. 스타일 (CSS)] ===
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    .metric-card { 
        background-color: #1E1E1E; 
        border: 1px solid #444; 
        border-radius: 10px; 
        padding: 15px; 
        margin-bottom: 15px; 
    }
    .price-row { display: flex; justify-content: space-between; align-items: center; padding: 3px 0; border-bottom: 1px solid #333; }
    .price-label { color: #aaa; font-size: 12px; }
    .price-val { font-weight: bold; color: white; font-family: monospace; font-size: 14px; }
    
    .score-container { display: flex; justify-content: space-between; margin-top: 10px; background-color: #252526; padding: 8px; border-radius: 6px; }
    .score-item { text-align: center; width: 24%; }
    .score-title { font-size: 10px; color: #888; }
    .score-val { font-weight: bold; font-size: 13px; display: block; margin-top: 2px; }
    .sc-high { color: #00FF00; } .sc-mid { color: #FFD700; } .sc-low { color: #FF4444; }
    
    .price-target-box { display: flex; justify-content: space-between; background-color: #151515; padding: 10px; border-radius: 6px; margin-top: 10px; border: 1px dashed #444; }
    .pt-item { text-align: center; width: 33%; }
    .pt-label { font-size: 10px; color: #aaa; display:block; }
    .pt-val { font-weight: bold; font-size: 13px; }
    
    .exit-box { background-color: #2d3436; border-left: 3px solid #636e72; padding: 8px; font-size: 11px; color: #dfe6e9; margin-top: 10px; border-radius: 0 4px 4px 0; }
    
    .ticker-header { font-size: 18px; font-weight: bold; color: #00CCFF; text-decoration: none !important; }
    .badge { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; color: white; margin-left: 5px; vertical-align: middle; }
    
    .news-line { color: #ffa502; font-size: 12px; margin-top: 8px; padding: 5px; background-color: #2d2d2d; border-radius: 4px; display: block; border-left: 3px solid #ffa502; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
    .ai-desc { font-size: 11px; color: #ccc; margin-top: 5px; font-style: italic; text-align: center; }
    
    /* Strategy Colors */
    .st-gamma { background-color: #6c5ce7; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .st-squeeze { background-color: #0984e3; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .st-value { background-color: #00b894; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .st-dip { background-color: #e17055; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .st-none { background-color: #333; color: #777; padding: 3px 8px; border-radius: 4px; font-size: 11px; }
    .st-highconv { background-color: #e17055; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-left: 5px; }
    
    .mkt-pre { background-color: #d29922; } .mkt-reg { background-color: #238636; } .mkt-aft { background-color: #1f6feb; } .mkt-cls { background-color: #6e7681; }
</style>
""", unsafe_allow_html=True)

# === [5. 27개 섹터 데이터 (레버리지 2종 포함)] ===
SECTORS = {
    "01. 🔥 지수 레버리지 (2x/3x)": ["TQQQ", "SQQQ", "SOXL", "SOXS", "UPRO", "SPXU", "TMF", "TMV", "LABU", "LABD", "FNGU", "FNGD", "BULZ", "BERZ", "YINN", "YANG", "UVXY", "BOIL", "KOLD"],
    "02. 💣 개별주 레버리지 (2x/3x)": ["NVDL", "NVDS", "TSLL", "TSLQ", "AMZU", "AAPU", "GOOX", "MSFU", "CONL", "MSTX", "MSTY", "BITX", "NVDX", "BABX"],
    "03. AI & Cloud (Big Tech)": ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "PLTR", "AVGO", "ADBE", "CRM", "AMD", "IBM", "NOW", "INTC", "QCOM", "AMAT", "MU", "LRCX", "ADI", "SNOW", "DDOG", "NET", "MDB", "PANW", "CRWD", "ZS", "FTNT", "TEAM", "WDAY", "SMCI", "ARM", "PATH", "AI", "SOUN", "BBAI", "ORCL", "CSCO"],
    "04. Semiconductors": ["NVDA", "TSM", "AVGO", "AMD", "INTC", "ASML", "AMAT", "LRCX", "MU", "QCOM", "ADI", "TXN", "MRVL", "KLAC", "NXPI", "STM", "ON", "MCHP", "MPWR", "TER", "ENTG", "SWKS", "QRVO", "WOLF", "COHR", "IPGP", "LSCC", "RMBS", "FORM", "ACLS", "CAMT", "UCTT", "ICHR", "AEHR", "GFS"],
    "05. Rare Earth & Strategic": ["MP", "UUUU", "LAC", "ALTM", "SGML", "PLL", "LTHM", "REMX", "TMC", "NB", "TMQ", "TMRC", "UAMY", "AREC", "IDR", "RIO", "BHP", "VALE", "FCX", "SCCO", "AA", "CENX", "KALU", "CRS", "ATI", "HAYW", "LYC.AX", "ARU.AX", "ASM.AX"],
    "06. Weight Loss & Bio": ["LLY", "NVO", "AMGN", "PFE", "VKTX", "ALT", "ZP", "GILD", "BMY", "JNJ", "ABBV", "MRK", "BIIB", "REGN", "VRTX", "MRNA", "BNTX", "NVS", "AZN", "SNY", "ALNY", "SRPT", "BMRN", "INCY", "UTHR", "GERN", "CRSP", "EDIT", "NTLA", "BEAM", "SAGE", "ITCI", "AXSM"],
    "07. Fintech & Crypto": ["COIN", "MSTR", "HOOD", "SQ", "PYPL", "SOFI", "AFRM", "UPST", "MARA", "RIOT", "CLSK", "HUT", "WULF", "CIFR", "BTBT", "IREN", "CORZ", "SDIG", "GREE", "BITF", "V", "MA", "AXP", "DFS", "COF", "NU", "DAVE", "LC", "GLBE", "BILL", "TOST", "MQ", "FOUR"],
    "08. Defense & Space": ["RTX", "LMT", "NOC", "GD", "BA", "LHX", "HII", "LDOS", "AXON", "KTOS", "AVAV", "RKLB", "SPCE", "ASTS", "LUNR", "PL", "SPIR", "BKSY", "VSAT", "IRDM", "JOBY", "ACHR"],
    "09. Uranium & Nuclear": ["CCJ", "UUUU", "NXE", "UEC", "DNN", "SMR", "BWXT", "LEU", "OKLO", "FLR", "URA", "CEG", "VST", "XOM", "CVX", "SLB", "OXY", "VLO", "HAL", "MPC"],
    "10. Consumer & Luxury": ["LVMUY", "RACE", "NKE", "LULU", "ONON", "DECK", "CROX", "SKX", "RL", "TPR", "CPRI", "EL", "COTY", "ULTA", "ELF", "WMT", "COST", "TGT", "HD", "LOW", "SBUX", "MCD", "CMG", "KO", "PEP"],
    "11. Meme & Reddit": ["GME", "AMC", "RDDT", "DJT", "TSLA", "PLTR", "SOFI", "OPEN", "LCID", "RIVN", "CHPT", "NKLA", "SPCE", "BB", "NOK", "KOSS", "CVNA", "AI"],
    "12. Quantum Computing": ["IONQ", "RGTI", "QUBT", "HON", "IBM", "GOOGL", "INTC", "FORM", "AMAT", "ASML", "KEYS", "ADI", "TXN", "NVDA", "AMD", "QCOM", "AVGO", "TSM", "MU", "D-WAVE", "ARQQ", "QBTS", "QMCO"],
    "13. Robotics & Automation": ["ISRG", "TER", "PATH", "SYM", "RKLY", "ABB", "CGNX", "ROCK", "ATSG", "BRKS", "TKR", "ROBO", "BOTZ", "IRBT", "DE", "CAT", "EMR"],
    "14. Biotech (High Growth)": ["VRTX", "AMGN", "MRNA", "BNTX", "REGN", "GILD", "BIIB", "ILMN", "CRSP", "BEAM", "NTLA", "EDIT", "NVTA", "ARWR", "IONS", "SRPT", "BMRN", "INCY", "UTHR", "EXEL", "HALO", "TECH", "WST", "RGEN", "TXG", "PACB", "QGEN", "GMAB", "ARGX", "BGNE"],
    "15. E-commerce & Retail": ["AMZN", "WMT", "COST", "HD", "SHOP", "MELI", "BABA", "PDD", "EBAY", "ETSY", "CPNG", "SE", "JMIA", "JD", "VIPS", "TGT", "LOW", "BBY", "M", "KSS", "JWN", "GPS", "ANF", "AEO", "URBN", "ROST", "TJX", "DLTR", "DG", "BJ"],
    "16. Gaming & Metaverse": ["RBLX", "U", "EA", "TTWO", "SONY", "NTES", "MSFT", "NVDA", "CRSR", "LOGI"],
    "17. Streaming & Media": ["NFLX", "DIS", "WBD", "PARA", "SPOT", "ROKU", "AMC", "CNK", "LYV", "MSG", "TKO", "FOXA", "CMCSA", "IQ", "FUBO", "GOOGL", "AMZN", "AAPL", "SIRI", "LGF-A", "WMG", "UMG", "TR", "NXST", "SBGI"],
    "18. Banking & Finance": ["JPM", "BAC", "WFC", "C", "GS", "MS", "HSBC", "UBS", "BLK", "SCHW"],
    "19. Energy (Oil & Gas)": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "OXY", "PSX", "VLO", "HAL", "BKR", "HES", "DVN", "FANG", "MRO", "APA", "CTRA", "PXD", "WMB", "KMI", "OKE", "TRGP", "LNG", "EQT", "RRC", "SWN", "CHK", "MTDR", "PDCE", "CIVI"],
    "20. Renewables": ["ENPH", "SEDG", "FSLR", "NEE", "BEP", "RUN", "ARRY", "CSIQ", "DQ", "JKS", "MAXN", "SPWR", "NOVA", "SHLS", "GEV", "CWEN", "AY", "HASI", "ORA", "TPIC", "BLDP", "PLUG", "FCEL", "BE", "STEM", "TAN", "ICLN"],
    "21. Gold & Miners": ["GOLD", "NEM", "KL", "AU", "GDX", "GDXJ", "AEM", "FNV", "WPM", "KGC", "PAAS", "MAG", "SAND", "OR", "PHYS", "HMY", "GFI", "IAG", "NGD", "EGO", "DRD", "SBSW", "CDE", "HL", "AG", "EXK", "FSM", "MUX", "USAS", "GORO"],
    "22. Industrial": ["UPS", "FDX", "CAT", "DE", "HON", "GE", "MMM", "UNP", "EMR", "ITW", "PH", "ETN", "NSC", "CSX", "CMI", "ROK", "AME", "DOV", "XYL", "TT", "CARR", "OTIS", "JCI", "LII", "GWW", "FAST", "URI", "PWR", "EME", "ACM"],
    "23. Real Estate (REITs)": ["AMT", "PLD", "CCI", "EQIX", "O", "DLR", "WELL", "SPG", "VICI", "PSA"],
    "24. Travel & Leisure": ["BKNG", "ABNB", "MAR", "HLT", "RCL", "CCL", "DAL", "UAL", "LUV", "EXPE", "TRIP", "MGM", "LVS", "DKNG"],
    "25. Food & Beverage": ["PEP", "KO", "MDLZ", "MNST", "HSY", "KDP", "GIS", "K", "SBUX", "CMG", "MCD", "YUM", "DPZ"],
    "26. Cybersecurity": ["PANW", "CRWD", "FTNT", "NET", "ZS", "OKTA", "CYBR", "HACK", "CIBR", "DOCU", "DBX"],
    "27. Space Economy": ["SPCE", "RKLB", "ASTS", "BKSY", "PL", "SPIR", "LUNR", "VSAT", "IRDM", "JOBY", "ACHR", "UP", "MNTS", "RDW", "SIDU", "LLAP", "VORB", "ASTR", "DCO", "TL0", "BA", "LMT", "NOC", "RTX", "LHX", "GD", "HII", "LDOS", "TXT", "HWM"],
    "28. 🇺🇸 시장 지수 (1x)": ["SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "TLT", "HYG", "VXX"]
}
ALL_TICKERS = sorted(list(set([ticker for s in SECTORS.values() for ticker in s])))

INDEX_CONSTITUENTS = {
    "NASDAQ100": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AVGO", "COST", "PEP", "CSCO", "TMUS", "CMCSA", "INTC", "AMD", "QCOM", "TXN", "AMGN", "HON", "INTU", "SBUX", "GILD", "MDLZ", "BKNG", "ADI", "ISRG", "ADP", "REGN", "VRTX", "LRCX", "PANW", "SNPS", "CDNS", "KLAC", "ASML", "MELI", "MNST", "ORCL", "MAR", "NXPI", "CTAS", "FTNT", "DXCM", "WDAY", "MCHP", "AEP", "KDP", "LULU", "MRVL", "ADSK"],
    "SP500_TOP": ["MSFT", "AAPL", "NVDA", "AMZN", "GOOGL", "META", "BRK.B", "TSLA", "LLY", "AVGO", "JPM", "V", "UNH", "XOM", "MA", "JNJ", "HD", "PG", "COST", "MRK", "ABBV", "CRM", "CVX", "BAC", "AMD", "NFLX", "PEP", "KO", "WMT", "ADBE", "TMO", "ACN", "LIN", "MCD", "CSCO", "ABT", "DIS", "INTU", "WFC", "VZ", "CMCSA", "QCOM", "DHR", "CAT", "TXN", "AMGN", "IBM", "PM", "UNP", "GE"],
    "RUSSELL_GROWTH": ["SMCI", "MSTR", "COIN", "CVNA", "AFRM", "DKNG", "HOOD", "RIVN", "SOFI", "PLTR", "PATH", "U", "RBLX", "OPEN", "LCID", "MARA", "RIOT", "CLSK", "GME", "AMC", "UPST", "AI", "IONQ", "RGTI", "QUBT", "JOBY", "ACHR", "ASTS", "LUNR", "RKLB"]
}

# === [6. 설정값] ===
CONFIG = {"NAV": 10000, "BASE_BET": 0.15}

# === [7. 엔진: AI Logic] ===
@st.cache_data(ttl=600)
def get_market_data(tickers):
    tickers = list(set(tickers))
    try:
        spy = yf.download("SPY", period="6mo", progress=False)
        vix = yf.Ticker("^VIX").history(period="5d")
        regime_score = 5.0
        if not spy.empty:
            spy_ma200 = spy['Close'].rolling(200).mean().iloc[-1]
            if spy['Close'].iloc[-1] > spy_ma200: regime_score += 2.0
        if not vix.empty:
            v_val = vix['Close'].iloc[-1]
            if v_val < 20: regime_score += 3.0
            elif v_val > 30: regime_score -= 3.0
    except: regime_score = 5.0

    data_list = []
    mkt_code, mkt_label, mkt_class = get_market_status()
    
    def fetch_single(ticker):
        try:
            stock = yf.Ticker(ticker)
            # [수정] 데이터 검증 완화 (최소 2일치면 OK) -> 레버리지/신규주 에러 방지
            hist_day = stock.history(period="1y") 
            if hist_day.empty or len(hist_day) < 2: return None
            
            hist_rt = stock.history(period="1d", interval="1m", prepost=True)
            cur = hist_rt['Close'].iloc[-1] if not hist_rt.empty else hist_day['Close'].iloc[-1]
            open_p = hist_day['Open'].iloc[-1]
            prev_c = hist_day['Close'].iloc[-2]
            
            # Indicators
            ma20 = hist_day['Close'].rolling(20).mean()
            ma200 = hist_day['Close'].rolling(200).mean()
            std20 = hist_day['Close'].rolling(20).std()
            
            upper_bb = ma20 + (std20 * 2)
            lower_bb = ma20 - (std20 * 2)
            bbw = (upper_bb - lower_bb) / ma20
            
            bbw_val = bbw.rank(pct=True).iloc[-1]
            sc_squeeze = (1 - (bbw_val if not np.isnan(bbw_val) else 0.5)) * 10
            
            sc_trend = 7.0 if cur > ma20.iloc[-1] else 3.0
            
            vol_avg = hist_day['Volume'].rolling(20).mean().iloc[-1]
            vol_ratio = (hist_day['Volume'].iloc[-1] / vol_avg) if vol_avg > 0 else 1.0
            sc_vol = min(10, vol_ratio * 3)
            
            # RSI
            delta = hist_day['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
            rsi = 100 - (100 / (1 + gain/(loss if loss != 0 else 0.0001)))
            
            # Options Check
            pcr = 1.0; c_vol = 0; p_vol = 0; sc_option = 5.0
            try:
                opts = stock.options
                if opts:
                    chain = stock.option_chain(opts[0])
                    c_vol = chain.calls['volume'].sum(); p_vol = chain.puts['volume'].sum()
                    if c_vol > 0: pcr = p_vol / c_vol
                    sc_option = 7.0 if pcr < 0.7 else 3.0 if pcr > 1.2 else 5.0
            except: pass

            # === [AI 전략 로직] ===
            category = "NONE"
            strat_name = "관망"
            strat_class = "st-none"
            desc = "특이사항 없음"
            
            target_pct, stop_pct, trail_pct = 0.05, 0.03, 0.02
            time_stop_days = 5
            
            # 1. 🚀 단타 (수급 돌파)
            if cur > upper_bb.iloc[-1] and vol_ratio > 1.8:
                category = "SHORT"
                strat_name = "🚀 수급 돌파"
                strat_class = "st-gamma"
                desc = f"거래량 폭발({vol_ratio:.1f}배) + 밴드 상단 돌파"
                target_pct, stop_pct, trail_pct = 0.12, 0.05, 0.03
                time_stop_days = 2

            # 2. 🌊 스윙 (에너지 응축)
            elif sc_squeeze > 8.0:
                category = "SWING"
                strat_name = "🌊 에너지 응축"
                strat_class = "st-squeeze"
                desc = "변동성 극소화, 시세 분출 임박"
                target_pct, stop_pct, trail_pct = 0.15, 0.05, 0.04
                time_stop_days = 10
                
            # 3. 🛡️ 스윙 (과매도 반등)
            elif cur <= lower_bb.iloc[-1] and rsi < 35:
                category = "SWING"
                strat_name = "🛡️ 과매도 반등"
                strat_class = "st-dip"
                desc = f"단기 낙폭 과대 (RSI {rsi:.0f}), 기술적 반등 기대"
                target_pct, stop_pct, trail_pct = 0.08, 0.07, 0.03
                time_stop_days = 5
                
            # 4. 🌲 장투 (대세 상승)
            elif cur > ma20.iloc[-1] and (len(ma200) > 0 and cur > ma200.iloc[-1]) and 50 < rsi < 70:
                category = "LONG"
                strat_name = "💎 대세 상승"
                strat_class = "st-value"
                desc = "이평선 정배열 + 안정적 우상향"
                target_pct, stop_pct, trail_pct = 0.30, 0.10, 0.10
                time_stop_days = 60

            # 뉴스 체크
            news_ok, news_hl = False, None
            if vol_ratio >= 3.0: 
                try: news_ok, news_hl = check_recent_news(ticker)
                except: pass

            # [수정] 익절라인(TrailStop)은 무조건 현재가보다 위(+)에 있어야 함
            tgt_val = cur * (1 + target_pct)
            trl_val = cur * (1 + trail_pct)  # +로 수정 완료
            stp_val = cur * (1 - stop_pct)

            # 비중 계산
            base_amt = CONFIG["NAV"] * CONFIG["BASE_BET"]
            multiplier = 1.0
            if sc_squeeze > 8.0: multiplier = 1.2
            if category == "NONE": multiplier = 0.0
            
            bet_text = "관망"
            if multiplier > 0:
                bet_text = "비중:최대" if multiplier >= 1.2 else "비중:보통" if multiplier >= 1.0 else "비중:축소"

            journal_txt = {
                "Ticker": ticker, "Strategy": strat_name, "Entry": round(cur, 2), 
                "Target": round(tgt_val, 2), "Stop": round(stp_val, 2), "Desc": desc, "Time": get_timestamp_str()
            }

            return {
                "Ticker": ticker, "Price": cur, "Category": category, "StratName": strat_name, "StratClass": strat_class,
                "Squeeze": sc_squeeze, "Trend": sc_trend, "Vol": sc_vol, "Option": sc_option, "Desc": desc,
                "BetAmount": base_amt * multiplier, "BetText": bet_text,
                "Target": tgt_val, "Stop": stp_val, "HardStop": stp_val, "TrailStop": trl_val, "TimeStop": time_stop_days,
                "Journal": journal_txt, "History": hist_day['Close'],
                "ChgOpen": (cur - open_p)/open_p * 100, "ChgPrev": (cur - prev_c)/prev_c * 100,
                "DiffOpen": cur - open_p, "DiffPrev": cur - prev_c,
                "RSI": rsi, "PCR": pcr,
                "MktLabel": mkt_label, "MktClass": mkt_class, "HighConviction": news_ok, "NewsHeadline": news_hl
            }
        except: return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_single, t) for t in tickers]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: data_list.append(res)
    return data_list

def create_chart(data, ticker, unique_id):
    color = '#00FF00' if data.iloc[-1] >= data.iloc[0] else '#FF4444'
    fig = go.Figure(go.Scatter(y=data, mode='lines', line=dict(color=color, width=2), fill='tozeroy'))
    fig.update_layout(height=50, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# === [8. UI 메인] ===
with st.sidebar:
    st.title("🪟 KOREAN MASTER")
    st.caption(f"Account NAV: ${CONFIG['NAV']:,}")
    mode = st.radio("분석 모드", ["📌 섹터별 보기", "🔍 무제한 검색", "🔥 인덱스 스캔", "🏆 AI 추천 포트폴리오", "⭐ 내 관심종목 보기"])
    
    target_tickers = []
    
    if mode == "⭐ 내 관심종목 보기":
        if not st.session_state.watchlist:
            st.warning("관심종목이 없습니다.")
        else:
            target_tickers = list(st.session_state.watchlist)
            if st.button("🗑️ 전체 삭제"):
                st.session_state.watchlist = set()
                st.rerun()
                
    elif "섹터" in mode:
        # [수정] 드래그 방식 삭제 -> 드롭다운(Selectbox) 적용 (깔끔하게 하나 선택)
        selected_sector = st.selectbox("섹터 선택", list(SECTORS.keys()))
        target_tickers = SECTORS[selected_sector]
        
    elif "검색" in mode:
        st.info("티커 입력 (예: NVDA, TSLA)")
        search_txt = st.text_input("종목 입력", value="")
        if search_txt: target_tickers = [t.strip().upper() for t in search_txt.split(',')]
        
    elif "인덱스" in mode:
        index_choice = st.radio("인덱스 선택", list(INDEX_CONSTITUENTS.keys()))
        target_tickers = INDEX_CONSTITUENTS[index_choice]
        
    elif "추천" in mode:
        if st.button("🚀 전체 시장 스캔"): target_tickers = ALL_TICKERS
            
    if st.button("🔄 새로고침"): st.cache_data.clear(); st.rerun()

st.title(f"🇺🇸 {mode}")

if target_tickers:
    with st.spinner(f"데이터 분석 중... ({len(target_tickers)} 종목)"):
        market_data = get_market_data(target_tickers)
    
    if not market_data:
        if mode != "⭐ 내 관심종목 보기":
            st.warning("데이터를 불러올 수 없습니다.")
    else:
        # [렌더링 함수: 이미지 깨짐 방지 및 안전한 HTML]
        def render_card(row, unique_id):
            def get_color(val): return "sc-high" if val >= 7 else "sc-mid" if val >= 4 else "sc-low"
            color_open = "#00FF00" if row['ChgOpen'] >= 0 else "#FF4444"
            color_prev = "#00FF00" if row['ChgPrev'] >= 0 else "#FF4444"
            is_fav = row['Ticker'] in st.session_state.watchlist
            fav_icon = "❤️" if is_fav else "🤍"
            
            badge_html = "<span class='st-highconv'>🔥 High Conviction</span>" if row['HighConviction'] else ""
            news_html = f"<span class='news-line'>📰 {row['NewsHeadline']}</span>" if row['HighConviction'] and row['NewsHeadline'] else ""

            html_content = f"""<div class="metric-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
                    <div><a href="https://finance.yahoo.com/quote/{row['Ticker']}" target="_blank" class="ticker-header">{row['Ticker']}</a>{badge_html} <span class="badge {row['MktClass']}">{row['MktLabel']}</span></div>
                </div>
                {news_html}
                <div class="price-row" style="margin-top:8px;"><span class="price-label">현재가</span><span class="price-val">${row['Price']:.2f}</span></div>
                <div class="price-row"><span class="price-label">시가대비</span><span class="price-val" style="color:{color_open}">{row['DiffOpen']:+.2f} ({row['ChgOpen']:+.2f}%)</span></div>
                <div class="price-row"><span class="price-label">전일대비</span><span class="price-val" style="color:{color_prev}">{row['DiffPrev']:+.2f} ({row['ChgPrev']:+.2f}%)</span></div>
                
                <div style="margin-top:12px; margin-bottom:8px; text-align:center;">
                    <span class="{row['StratClass']}">{row['StratName']}</span>
                    <div class="ai-desc">💡 {row['Desc']}</div>
                </div>
                
                <div class="score-container">
                    <div class="score-item">응축<br><span class="score-val {get_color(row['Squeeze'])}">{row['Squeeze']:.0f}</span></div>
                    <div class="score-item">추세<br><span class="score-val {get_color(row['Trend'])}">{row['Trend']:.0f}</span></div>
                    <div class="score-item">수급<br><span class="score-val {get_color(row['Vol'])}">{row['Vol']:.0f}</span></div>
                    <div class="score-item">옵션<br><span class="score-val {get_color(row['Option'])}">{row['Option']:.0f}</span></div>
                </div>

                <div class="price-target-box">
                    <div class="pt-item"><span class="pt-label">목표가</span><span class="pt-val" style="color:#00FF00">${row['Target']:.2f}</span></div>
                    <div class="pt-item"><span class="pt-label">손절가</span><span class="pt-val" style="color:#FF4444">${row['Stop']:.2f}</span></div>
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div class="exit-box">
                        <span style="color:#00FF00; font-weight:bold;">✅ 익절: ${row['TrailStop']:.2f}</span><br>
                        <span style="color:#FF4444;">🚨 손절: ${row['HardStop']:.2f}</span><br>
                        <span style="color:#aaa;">⏳ 기한: {row['TimeStop']}일</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="color:#888; font-size:10px;">권장 비중</span><br>
                        <span class="bet-badge" style="background-color:#74b9ff; color:black; font-weight:bold; padding:2px 5px; border-radius:3px;">{row['BetText']}</span>
                    </div>
                </div>
            </div>"""
            
            c1, c2 = st.columns([0.85, 0.15])
            with c2:
                if st.button(fav_icon, key=f"fav_{unique_id}"):
                    if is_fav: st.session_state.watchlist.remove(row['Ticker'])
                    else: st.session_state.watchlist.add(row['Ticker'])
                    st.rerun()
            
            st.markdown(html_content, unsafe_allow_html=True)
            st.plotly_chart(create_chart(row['History'], row['Ticker'], unique_id), use_container_width=True, key=f"chart_{unique_id}", config={'displayModeBar':False})

        # [AI 추천 포트폴리오 탭 복구]
        if "추천" in mode or "인덱스" in mode:
            df = pd.DataFrame(market_data)
            t1, t2, t3 = st.tabs(["🚀 단타 (수급/돌파)", "🌊 스윙 (응축/반등)", "🌲 장투 (대세상승)"])
            
            short_df = df[df['Category'] == 'SHORT'].sort_values('Vol', ascending=False)
            swing_df = df[df['Category'] == 'SWING'].sort_values('Squeeze', ascending=False)
            long_df = df[df['Category'] == 'LONG'].sort_values('Trend', ascending=False)

            with t1: 
                cols = st.columns(3)
                for i, (_, r) in enumerate(short_df.iterrows()):
                    with cols[i % 3]: render_card(r, f"s_{i}")
            with t2:
                cols = st.columns(3)
                for i, (_, r) in enumerate(swing_df.iterrows()):
                    with cols[i % 3]: render_card(r, f"sw_{i}")
            with t3:
                cols = st.columns(3)
                for i, (_, r) in enumerate(long_df.iterrows()):
                    with cols[i % 3]: render_card(r, f"l_{i}")
        
        else:
            tab1, tab2 = st.tabs(["📊 대시보드", "💰 투자 리포트"])
            with tab1:
                cols = st.columns(3)
                for i, row in enumerate(market_data):
                    with cols[i % 3]: render_card(row, f"main_{i}")
            with tab2:
                cols = st.columns(3)
                for i, row in enumerate(market_data):
                    with cols[i % 3]:
                        render_card(row, f"list_{i}")
                        st.json(row['Journal'])