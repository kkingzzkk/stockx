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
# 🔑 API & CONSTANTS
# ==========================================
try:
    FINNHUB_API_KEY = st.secrets["FINNHUB_API_KEY"]
except:
    FINNHUB_API_KEY = "d5p0p81r01qu6m6bocv0d5p0p81r01qu6m6bocvg"

# [0] 불변의 법칙
MAX_RAW_SCORE = 25
MIN_FILL_SCORE = 5 
MAX_RISK = 0.01

# === [1. 페이지 설정] ===
st.set_page_config(page_title="QUANT NEXUS : HEDGE FUND", page_icon="🏛️", layout="wide", initial_sidebar_state="expanded")

# === [2. 세션 초기화] ===
if 'watchlist' not in st.session_state: st.session_state.watchlist = set()
if 'scan_option' not in st.session_state: st.session_state.scan_option = "💎 AI 추천 TOP 50"
if 'REAL_NAV' not in st.session_state: st.session_state.REAL_NAV = 10000.0  
if 'CONSEC_LOSS' not in st.session_state: st.session_state.CONSEC_LOSS = 0

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

@st.cache_data(ttl=600)
def get_market_regime():
    try:
        spy = yf.Ticker("SPY").history(period="1y")
        vix = yf.Ticker("^VIX").history(period="5d")
        if spy.empty: return "NEUTRAL"
        spy_cur = spy['Close'].iloc[-1]
        spy_ma200 = spy['Close'].rolling(200).mean().iloc[-1]
        vix_cur = vix['Close'].iloc[-1] if not vix.empty else 20
        
        if spy_cur > spy_ma200 and vix_cur < 20: return "BULL"
        elif spy_cur < spy_ma200 or vix_cur > 25: return "BEAR"
        return "NEUTRAL"
    except: return "NEUTRAL"

@st.cache_data(ttl=300) 
def check_recent_news(ticker):
    if not FINNHUB_API_KEY: return False, None
    try:
        fr = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        to = datetime.now().strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={fr}&to={to}&token={FINNHUB_API_KEY}"
        res = requests.get(url, timeout=1)
        if res.status_code == 200:
            data = res.json()
            if data and isinstance(data, list) and len(data) > 0:
                return True, data[0].get('headline', '뉴스 내용 없음')
    except: pass
    return False, None

def calculate_rsi(series, period=14):
    if len(series) < period: period = max(1, len(series) - 1)
    if period < 1: return pd.Series([50]*len(series))
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# === [4. 스타일] ===
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    .metric-card { background-color: #1E1E1E; border: 1px solid #444; border-radius: 8px; padding: 15px; margin-bottom: 15px; position: relative; transition: all 0.3s ease; }
    .price-row { display: flex; justify-content: space-between; align-items: center; padding: 2px 0; border-bottom: 1px solid #333; font-size: 13px; }
    .price-label { color: #aaa; font-size: 11px; }
    .price-val { font-weight: bold; color: white; font-family: monospace; font-size: 13px; }
    .score-container { display: flex; justify-content: space-between; margin-top: 10px; margin-bottom: 8px; background-color: #252526; padding: 6px; border-radius: 4px; }
    .score-item { text-align: center; font-size: 10px; color: #888; width: 19%; }
    .score-val { font-weight: bold; font-size: 13px; display: block; margin-top: 2px; }
    .sc-high { color: #00FF00; } .sc-mid { color: #FFD700; } .sc-low { color: #FF4444; }
    .indicator-box { background-color: #252526; border-radius: 4px; padding: 6px; margin-top: 8px; font-size: 11px; color: #ccc; text-align: center; border: 1px solid #333; }
    .pt-box { display: flex; justify-content: space-between; background-color: #151515; padding: 8px; border-radius: 4px; margin-top: 8px; border: 1px dashed #444; }
    .pt-item { text-align: center; width: 33%; font-size: 12px; }
    .pt-label { color: #aaa; font-size: 10px; display: block; }
    .pt-val { font-weight: bold; font-size: 13px; color: white; }
    .exit-box { background-color: #2d3436; border-left: 3px solid #636e72; padding: 8px; font-size: 11px; color: #dfe6e9; margin-top: 10px; }
    .bet-badge { font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; color: black; float: right; margin-top: 5px; }
    .bet-bg { background-color: #74b9ff; }
    
    .act-sbuy { border: 2px solid #00FF00 !important; box-shadow: 0 0 15px rgba(0,255,0,0.3); } 
    .act-buy { border: 1px solid #00FF00 !important; }
    .act-watch { border: 1px solid #FFD700 !important; } 
    .act-fill { border: 1px solid #333 !important; opacity: 0.4; filter: grayscale(100%); }
    .act-ignore { border: 1px solid #333 !important; opacity: 0.3; }
    
    .st-gamma { background-color: #6c5ce7; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block; }
    .st-squeeze { background-color: #0984e3; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block; }
    .st-value { background-color: #00b894; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block; }
    .st-dip { background-color: #e17055; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block; }
    .st-none { background-color: #333; color: #777; padding: 2px 6px; border-radius: 4px; font-size: 11px; display:inline-block; }
    .news-line { color: #ffa502; font-size: 12px; margin-top: 4px; padding: 4px; background-color: #2d2d2d; border-radius: 4px; display: block; border-left: 3px solid #ffa502; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
""", unsafe_allow_html=True)

# === [5. 27개 섹터 데이터] ===
SECTORS = {
    "01. 🔥 지수 레버리지 (2x/3x)": ["TQQQ", "SQQQ", "SOXL", "SOXS", "UPRO", "SPXU", "TMF", "TMV", "LABU", "LABD", "FNGU", "FNGD", "BULZ", "BERZ", "YINN", "YANG", "UVXY", "BOIL", "KOLD"],
    "02. 💣 개별주 레버리지 (2x/3x)": ["NVDL", "NVDS", "TSLL", "TSLQ", "AMZU", "AAPU", "GOOX", "MSFU", "CONL", "MSTX", "MSTY", "BITX", "NVDX", "BABX"],
    "03. 🇺🇸 시장 지수": ["SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "TLT", "HYG", "UVXY", "VXX"],
    "04. 🚀 빅테크 (M7+)": ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AAPL", "PLTR", "AVGO", "ORCL", "SMCI", "ARM", "IBM", "CSCO"],
    "05. 💾 반도체": ["NVDA", "TSM", "AVGO", "AMD", "INTC", "ASML", "AMAT", "MU", "QCOM", "LRCX", "TXN", "ADI", "MRVL", "ON", "STM"],
    "06. 💊 바이오": ["LLY", "NVO", "AMGN", "PFE", "VKTX", "GILD", "BMY", "JNJ", "ISRG", "MRK", "BIIB", "REGN", "MRNA", "VRTX", "CRSP"],
    "07. 🛡️ 방산/우주": ["RTX", "LMT", "NOC", "GD", "BA", "RKLB", "AXON", "KTOS", "PL", "SPCE", "LUNR", "ASTS", "LHX", "HII"],
    "08. ⚡ 에너지/원전": ["XOM", "CVX", "SLB", "OXY", "VLO", "HAL", "MPC", "COP", "CCJ", "FCX", "USO", "XLE", "CEG", "SMR", "OKLO", "UUUU"],
    "09. 🏦 금융/핀테크": ["JPM", "BAC", "WFC", "C", "GS", "MS", "NU", "UBS", "XLF", "BLK", "PYPL", "SQ", "HOOD", "AFRM", "UPST", "SOFI"],
    "10. 🪙 크립토": ["IBIT", "BITO", "COIN", "MSTR", "MSTY", "MARA", "RIOT", "CLSK", "HUT", "WULF", "CIFR", "IREN"],
    "11. 🚘 전기차/자율주행": ["TSLA", "RIVN", "LCID", "NIO", "XPEV", "LI", "F", "GM", "LAZR", "MBLY", "QS", "BLNK", "CHPT"],
    "12. 🛍️ 소비재/리테일": ["AMZN", "WMT", "COST", "TGT", "HD", "LOW", "NKE", "LULU", "SBUX", "MCD", "CMG", "KO", "PEP", "CELH"],
    "13. ☁️ 클라우드/SaaS": ["CRM", "NOW", "SNOW", "DDOG", "NET", "MDB", "TEAM", "WDAY", "ADBE", "PANW", "CRWD", "ZS", "OKTA", "PLTR"],
    "14. 🦍 밈(Meme)": ["GME", "AMC", "RDDT", "DJT", "KOSS", "BB", "NOK", "CHWY", "CVNA", "OPEN", "Z"],
    "15. 🇨🇳 중국": ["BABA", "PDD", "JD", "BIDU", "TCEHY", "NIO", "XPEV", "LI", "BEKE", "TCOM", "FXI", "KWEB"],
    "16. ✈️ 여행/항공": ["BKNG", "ABNB", "DAL", "UAL", "CCL", "RCL", "LUV", "JETS", "TRIP", "EXPE", "HLT", "MAR"],
    "17. 🏠 리츠 (부동산)": ["O", "AMT", "PLD", "CCI", "EQIX", "MAIN", "VICI", "XLRE", "SPG", "ADC", "VNO"],
    "18. 🏗️ 산업재": ["CAT", "DE", "GE", "MMM", "HON", "UNP", "EMR", "PAVE", "URI", "ETN"],
    "19. ☀️ 태양광/친환경": ["ENPH", "SEDG", "FSLR", "NEE", "RUN", "CSIQ", "TAN", "ICLN", "BEP"],
    "20. 🧈 금/광물": ["GOLD", "NEM", "KL", "GDX", "GDXJ", "AEM", "FNV", "WPM", "KGC", "PAAS", "MAG", "SAND", "OR", "PHYS", "HMY", "GFI", "IAG", "NGD", "EGO", "DRD", "SBSW", "CDE", "HL", "AG", "EXK", "FSM", "MUX", "USAS", "GORO"],
    "21. ⛏️ 희토류": ["MP", "LAC", "ALTM", "SGML", "VALE", "LIT", "REMX", "ALB"],
    "22. ⚛️ 양자컴퓨터": ["IONQ", "RGTI", "QUBT", "IBM", "GOOGL", "D-WAVE", "QBTS"],
    "23. 🚢 해운/물류": ["ZIM", "GSL", "UPS", "FDX", "DAC", "SBLK", "NAT"],
    "24. 📡 통신/5G": ["VZ", "T", "TMUS", "CMCSA", "CHTR", "NOK", "ERIC"],
    "25. 🎬 미디어": ["NFLX", "DIS", "WBD", "SPOT", "ROKU", "PARA", "CMCSA"],
    "26. 🤖 로봇": ["ISRG", "TER", "PATH", "ABB", "ROBO", "BOTZ"],
    "27. 🧬 유전자": ["VRTX", "CRSP", "NTLA", "BEAM", "EDIT", "ARKG", "DNA"],
    "28. 🥤 식음료": ["KO", "PEP", "MCD", "SBUX", "CMG", "HSY", "MNST", "K", "GIS"],
    "29. 🏥 의료기기": ["ISRG", "SYK", "BSX", "MDT", "EW", "ZBH"],
    "30. 🪵 원자재": ["AA", "X", "CLF", "NUE", "STLD"],
    "31. 🌐 글로벌": ["TSM", "ASML", "BABA", "SONY", "TM", "HMC", "SHEL", "TTE"]
}
ALL_TICKERS = sorted(list(set([ticker for s in SECTORS.values() for ticker in s])))

# === [7. 엔진: Logic Core] ===
# [FIXED: Renamed to v2 to clear cache and fix KeyError]
def get_market_data_v2(tickers):
    tickers = list(set(tickers))
    data_list = []
    regime = get_market_regime()
    ny_tz = pytz.timezone("America/New_York")
    
    def fetch_single(ticker):
        try:
            mkt_code, mkt_label, mkt_class = get_market_status()
            stock = yf.Ticker(ticker)
            
            # [FIXED: 24H Price Sync]
            cur = None
            try:
                # 1. Try 1m History with Prepost (Most Accurate)
                ext_hist = stock.history(period="1d", interval="1m", prepost=True)
                if not ext_hist.empty:
                    cur = ext_hist['Close'].iloc[-1]
            except: pass
            
            # 2. Try Fast Info (Fallback 1)
            if cur is None or np.isnan(cur):
                try: cur = stock.fast_info.last_price
                except: cur = None
            
            # 3. Try Daily History (Fallback 2)
            hist_day = stock.history(period="1y") 
            if hist_day.empty or len(hist_day) < 20: return None
            if cur is None or np.isnan(cur): cur = hist_day['Close'].iloc[-1]
                
            hist_rt_5m = stock.history(period="1d", interval="5m", prepost=False)
            
            rsi_intra = None
            if not hist_rt_5m.empty:
                rsi_intra = calculate_rsi(hist_rt_5m['Close']).iloc[-1]
                if np.isnan(rsi_intra): rsi_intra = None

            open_p = hist_day['Open'].iloc[-1]
            prev_c = hist_day['Close'].iloc[-2]
            diff_open = cur - open_p
            chg_open = (diff_open / open_p) * 100 if open_p > 0 else 0
            diff_prev = cur - prev_c
            chg_prev = (diff_prev / prev_c) * 100 if prev_c > 0 else 0
            
            ma20 = hist_day['Close'].rolling(20).mean()
            ma200 = hist_day['Close'].rolling(200).mean()
            std20 = hist_day['Close'].rolling(20).std()
            upper_bb = ma20 + (std20 * 2)
            lower_bb = ma20 - (std20 * 2)
            
            bbw = (upper_bb - lower_bb) / ma20
            bbw_max = bbw.rolling(20).max().iloc[-1]
            if pd.isna(bbw_max) or bbw_max == 0: bbw_ratio = 1.0
            else: bbw_ratio = bbw.iloc[-1] / bbw_max
            sc_squeeze = (1 - bbw_ratio) * 10
            
            sc_trend = 0
            if cur > ma20.iloc[-1]: sc_trend += 5
            if len(ma200) > 0 and cur > ma200.iloc[-1]: sc_trend += 5
            
            vol_avg = hist_day['Volume'].rolling(5).mean().iloc[-1]
            if vol_avg > 0:
                if not hist_rt_5m.empty: vol_ratio = hist_rt_5m['Volume'].sum() / vol_avg
                else: vol_ratio = hist_day['Volume'].iloc[-1] / vol_avg
            else: vol_ratio = 1.0
            
            sc_vol_ui = min(5, vol_ratio * 2)
            
            hist_day['TR'] = np.maximum(hist_day['High'] - hist_day['Low'], 
                                        np.maximum(abs(hist_day['High'] - hist_day['Close'].shift(1)), 
                                                   abs(hist_day['Low'] - hist_day['Close'].shift(1))))
            atr = hist_day['TR'].rolling(14).mean().iloc[-1]
            if pd.isna(atr) or atr <= 0: atr = cur * 0.03

            rsi_day = calculate_rsi(hist_day['Close']).iloc[-1]
            if np.isnan(rsi_day): rsi_day = None 
            
            # [FIX: Variable Init for Safety]
            has_option = False; score_option = 0; pcr = 1.0; call_wall = cur; put_wall = cur
            c_vol = 0; p_vol = 0; c_pct = 50; p_pct = 50
            
            try:
                opts = stock.options
                if opts and len(opts) > 0:
                    try:
                        chain = stock.option_chain(opts[0])
                        c_cols = chain.calls.columns
                        p_cols = chain.puts.columns
                        
                        c_oi_col = 'openInterest' if 'openInterest' in c_cols else 'oi' if 'oi' in c_cols else None
                        p_oi_col = 'openInterest' if 'openInterest' in p_cols else 'oi' if 'oi' in p_cols else None
                        
                        if 'volume' in c_cols and c_oi_col and p_oi_col:
                            c_vol = chain.calls['volume'].sum(); p_vol = chain.puts['volume'].sum()
                            if c_vol > 0: pcr = p_vol / c_vol
                            
                            # [FIX: Calc PCT]
                            total_opt = c_vol + p_vol
                            if total_opt > 0:
                                c_pct = (c_vol / total_opt) * 100
                                p_pct = 100 - c_pct
                            
                            calls_oi = chain.calls[abs(chain.calls['strike'] - cur) / cur < 0.05]
                            puts_oi = chain.puts[abs(chain.puts['strike'] - cur) / cur < 0.05]
                            
                            if not calls_oi.empty: call_wall = calls_oi.sort_values(c_oi_col, ascending=False).iloc[0]["strike"]
                            if not puts_oi.empty: put_wall = puts_oi.sort_values(p_oi_col, ascending=False).iloc[0]["strike"]
                            has_option = True
                    except: has_option = False
            except: pass
            
            if has_option and (c_vol + p_vol) > 0:
                pass # Already calc above
            
            category = "NONE"; strat_name = "관망"; strat_class = "st-none"; desc = "조건 부족"
            score_penalty = 0 
            rsi_check = rsi_intra if rsi_intra is not None else rsi_day
            
            if cur > (upper_bb.iloc[-1] * 0.98): 
                if rsi_check is not None and rsi_check > 78: 
                    category = "SWING"; strat_name = "⏸️ 과열 (대기)"; strat_class = "st-dip"
                    desc = f"RSI {rsi_check:.0f} 과열 → 눌림 대기"
                    score_penalty = -3 
                elif vol_ratio > 1.2:
                    category = "SCALP"; strat_name = "🚀 수급 돌파"; strat_class = "st-gamma"
                    desc = f"거래량 {vol_ratio:.1f}배 + 밴드 터치"
            
            elif vol_ratio > 2.0 and chg_open > 2.0:
                 if rsi_check is not None and rsi_check < 75:
                     category = "SCALP"; strat_name = "⚡ 급등 포착"; strat_class = "st-gamma"
                 else:
                     category = "NONE"; desc = "과열 갭상승"

            elif sc_squeeze > 2.0: 
                category = "SWING"; strat_name = "🌊 에너지 응축"; strat_class = "st-squeeze"
                desc = "변동성 극소화"
            elif cur <= lower_bb.iloc[-1] and (rsi_day is not None and rsi_day < 35): 
                category = "SWING"; strat_name = "🛡️ 과매도 반등"; strat_class = "st-dip"
                desc = f"일봉 RSI {rsi_day:.0f} 과매도"
            elif cur > ma20.iloc[-1] and (rsi_day is not None and 50 < rsi_day < 70):
                category = "LONG"; strat_name = "💎 대세 상승"; strat_class = "st-value"
                desc = "이평선 정배열"
            
            if regime == "BEAR" and category == "LONG":
                category = "NONE"; strat_name = "관망"; strat_class = "st-none"
                desc = "하락장 장기투자 금지"

            # --- [SCORING SYSTEM] ---
            score = 0
            score_news = 0
            
            if category == "LONG": score += 10
            elif category == "SWING": score += 8 
            elif category == "SCALP": score += 6 
            else: score = 0
            
            raw_option_bonus = 0
            if has_option and score >= 5:
                if cur > put_wall and pcr >= 1.2: 
                    score_option += 3
                    raw_option_bonus = 3
                if pcr > 1.8: score_penalty -= 2
            
            score_vol = 0
            if vol_ratio > 1.5: score_vol += 3
            if sc_trend >= 5: score_vol += 2
            
            if sc_squeeze > 5: score += 3
            
            news_ok = False; news_hl = None
            if score >= 5: 
                try: news_ok, news_hl = check_recent_news(ticker)
                except: pass
            if news_ok: score_news = 8 

            if regime == "BEAR" and category == "SWING" and not news_ok:
                score_penalty -= 3

            raw_score = score + score_news + score_vol + score_penalty
            raw_score = min(raw_score, MAX_RAW_SCORE)

            stop_atr = cur - atr * 1.5
            if category == "SCALP": 
                stop_price = max(stop_atr, cur * 0.97) 
            else:
                if has_option and abs(put_wall - cur)/cur < 0.05:
                    stop_price = max(put_wall * 0.99, stop_atr)
                else: stop_price = stop_atr
            
            if category == "SWING": stop_price = max(stop_price, cur * 0.96)
            stop_price = max(stop_price, cur * 0.90)
            
            return {
                "Ticker": ticker, "Price": cur, "Category": category, "StratName": strat_name, "StratClass": strat_class,
                "Squeeze": sc_squeeze, "Trend": sc_trend, "Vol": sc_vol_ui, "OptionScore": score_option, "Desc": desc, 
                "RawScore": raw_score, "Stop": stop_price, "RawOptionBonus": raw_option_bonus, 
                "History": hist_day['Close'].tail(30).values,
                "ChgOpen": chg_open, "ChgPrev": chg_prev, 
                "DiffOpen": diff_open, "DiffPrev": diff_prev, 
                "RSI": rsi_day, "PCR": pcr, "CallVol": c_vol, "PutVol": p_vol, "CallPct": c_pct, "PutPct": p_pct,
                "MktLabel": mkt_label, "MktClass": mkt_class, 
                "HighConviction": news_ok, "NewsHeadline": news_hl,
                "Regime": regime
            }
        except Exception: return None
    
    max_workers = 4 
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_single, t) for t in tickers]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: data_list.append(res)
    return data_list

# [Step 2] Normalize & Fill
def process_market_data(data, effective_nav, consec_loss):
    if not data: return []
    
    valid = [x for x in data if x['RawScore'] > 0]
    regime = data[0]['Regime'] if data else "NEUTRAL"
    
    if valid:
        raws = np.array([x['RawScore'] for x in valid])
        if len(raws) > 1:
            mu = raws.mean()
            if regime == "BEAR": mu += 3 
            sigma = max(raws.std(), 3.5) + 1e-6
            for item in data:
                if item['RawScore'] <= 0:
                    item['Score'] = 0
                else:
                    z = (item['RawScore'] - mu) / sigma
                    item['Score'] = int(100 / (1 + np.exp(-z)))
                    
                    if item.get('RawOptionBonus', 0) > 0:
                        item['Score'] = int(item['Score'] * 1.05)
                    
                    item['Score'] = max(5, min(item['Score'], 100))
        else:
            for item in data: item['Score'] = 50 if item['RawScore'] > 0 else 0
    else:
        for item in data: item['Score'] = 0

    for item in data:
        s = item['Score']
        raw = item['RawScore']
        
        min_raw = 11 if regime == "BEAR" else 7 
        s_buy_cut = 999 if regime == "BEAR" else 80
        buy_cut = 70 if regime == "BEAR" else 60
        
        if regime == "BEAR": s = s * 0.85 
        item['Score'] = int(s)
        
        if raw < min_raw: item['Action'] = "IGNORE"
        elif s >= s_buy_cut: item['Action'] = "S_BUY"
        elif s >= buy_cut: item['Action'] = "BUY"
        elif s >= 40: item['Action'] = "WATCH"
        else: item['Action'] = "IGNORE"
        
        if item['Category'] == "NONE": item['Action'] = "IGNORE"

        if regime == "BEAR" and item['Action'] in ["S_BUY", "BUY"]:
            item['Action'] = "WATCH"
            item['BetText'] = "👀 하락장 관망"

        cur = item['Price']; stop = item['Stop']
        
        if item['Category'] == "SCALP":
            target_pct = 0.03; trail_pct = 0.01; item['TimeStop'] = 1
        else:
            target_pct = 0.15 if regime == "BULL" else 0.05
            trail_pct = 0.05 if regime == "BULL" else 0.02
            item['TimeStop'] = 20 if regime == "BULL" else 5

        item['Target'] = cur * (1 + target_pct)
        item['TrailStart'] = cur * (1 + trail_pct)
        item['HardStop'] = stop
        
        risk_per_share = max(cur - stop, cur * 0.01)
        item['RiskPerShare'] = risk_per_share
        
        risk_amt = effective_nav * MAX_RISK
        
        multiplier = 0.0
        if item['Action'] == "S_BUY": multiplier = 0.6
        elif item['Action'] == "BUY": multiplier = 0.4
        if regime == "BEAR": multiplier = min(multiplier, 0.15)
        if consec_loss >= 2: multiplier *= 0.5
        if consec_loss >= 3: multiplier = 0.0
        
        # Recovery
        if consec_loss >= 3 and item['Score'] >= 85: multiplier = 0.1
        
        qty = int((risk_amt * multiplier) / risk_per_share)
        
        if consec_loss >= 3 and multiplier == 0: item['BetText'] = "⛔ 멘탈 보호"
        elif qty > 0: item['BetText'] = f"💎 매수: {qty}주"
        elif item['Action'] == "WATCH": item['BetText'] = "👀 관망"
        else: item['BetText'] = "💤 조건 부족"

    qualified = [x for x in data if x['Action'] != "IGNORE"]
    rest = [x for x in data if x['Action'] == "IGNORE"]
    rest = sorted(rest, key=lambda x: x['RawScore'], reverse=True)
    
    final_list = qualified
    if len(final_list) < 50:
        needed = 50 - len(final_list)
        # [FIX: Strict Fill]
        fillers = [x for x in rest if x['RawScore'] >= MIN_FILL_SCORE and x['Category'] != "NONE"]
        f_add = fillers[:needed]
        for f in f_add:
            f['Action'] = "FILL"
            f['BetText'] = "⚠️ 보충 (Rank)"
        final_list.extend(f_add)
    
    return sorted(final_list, key=lambda x: (x['Action'] == "FILL", -x['Score']))[:50]

def create_chart(data, ticker, unique_id):
    if len(data) < 2: return go.Figure()
    color = '#00FF00' if data[-1] >= data[0] else '#FF4444'
    fig = go.Figure(go.Scatter(y=data, mode='lines', line=dict(color=color, width=2), fill='tozeroy'))
    fig.update_layout(height=50, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# === [8. UI 메인] ===
with st.sidebar:
    st.title("🪟 KOREAN MASTER")
    st.info("🏛️ 상태: 헤지펀드 (24H SYNC + FIXED)")
    
    mode = st.radio("분석 모드", ["🏆 AI 랭킹 (TOP 50)", "🔍 무제한 검색", "⭐ 내 관심종목 보기"])
    if 'scan_option' not in st.session_state: st.session_state.scan_option = "💎 AI 추천 TOP 50"
    
    target_tickers = []
    if mode == "⭐ 내 관심종목 보기":
        if not st.session_state.watchlist: st.warning("관심종목이 없습니다.")
        else:
            target_tickers = list(st.session_state.watchlist)
            if st.button("🗑️ 전체 삭제"):
                st.session_state.watchlist = set(); st.rerun()
    elif mode == "🔍 무제한 검색":
        st.info("티커 입력 (예: NVDA, TSLA)")
        search_txt = st.text_input("종목 입력", value="")
        if search_txt: target_tickers = [t.strip().upper() for t in search_txt.split(',')]
    elif mode == "🏆 AI 랭킹 (TOP 50)":
        st.session_state.scan_option = st.radio("스캔 옵션", ["📂 섹터별 보기", "💎 AI 추천 TOP 50"])
        if st.session_state.scan_option == "📂 섹터별 보기":
            sector_list = ["전체(ALL)"] + list(SECTORS.keys())
            selected_sector = st.radio("섹터 선택", sector_list)
            if st.button("🚀 섹터 분석 시작"):
                if selected_sector == "전체(ALL)": 
                    st.toast("⚠️ 전체 스캔은 시간이 걸릴 수 있습니다.", icon="⏳")
                    target_tickers = ALL_TICKERS
                else: target_tickers = SECTORS[selected_sector]
        else:
            if st.button("💎 TOP 50 발굴 시작"):
                st.toast("⚡ 전체 시장 정밀 스캔 중... (잠시만 기다리세요)", icon="🦅")
                target_tickers = ALL_TICKERS

st.title(f"🇺🇸 {mode}")

if target_tickers:
    with st.spinner(f"AI 정밀 분석 중... ({len(target_tickers)} 종목)"):
        # [FIX: Call v2]
        raw_data = get_market_data_v2(target_tickers)
        market_data = process_market_data(raw_data, st.session_state.REAL_NAV, st.session_state.CONSEC_LOSS)
    
    if market_data:
        regime = market_data[0]['Regime']
        scores = [x['Score'] for x in market_data]
        
        if scores:
            max_s = max(scores) if scores else 100
            st.caption(f"📊 최종 점수 분포 (Max: {max_s})")
            hist_values = np.histogram(scores, bins=20, range=(0, max_s if max_s > 0 else 100))[0]
            st.bar_chart(hist_values)
            st.info(f"📏 판단 기준 ({regime}): ⭐ S_BUY(≥80) | ✅ BUY(≥60) | 👀 WATCH(≥40) | ⚠️ FILL")

        if regime == "BULL": st.success(f"🚀 BULL MARKET")
        elif regime == "BEAR": st.error(f"🐻 BEAR MARKET (Score Penalized)")
        else: st.warning(f"⚖️ NEUTRAL MARKET")

        st.caption(f"🔎 분석 완료: {len(market_data)}개 종목")

        def render_card(row, unique_id):
            action_status = row['Action']
            
            if action_status == "S_BUY": card_class = "act-sbuy"; act_badge = "⭐ 최우선"; act_color = "#00FF00"
            elif action_status == "BUY": card_class = "act-buy"; act_badge = "✅ 매수"; act_color = "#00FF00"
            elif action_status == "WATCH": card_class = "act-watch"; act_badge = "👀 관망"; act_color = "#FFD700"
            elif action_status == "FILL": card_class = "act-fill"; act_badge = "⚠️ 보충"; act_color = "#aaa"
            else: card_class = "act-ignore"; act_badge = "💤 제외"; act_color = "#888"
            
            bet_text = row['BetText']
            c_op = "#00FF00" if row['ChgOpen'] >= 0 else "#FF4444"
            c_pr = "#00FF00" if row['ChgPrev'] >= 0 else "#FF4444"
            is_fav = row['Ticker'] in st.session_state.watchlist
            fav = "❤️" if is_fav else "🤍"
            badge_html = f"<span class='st-highconv'>📰 News Alert</span>" if row['HighConviction'] else ""
            news_html = f"<div class='news-line'>{row['NewsHeadline']}</div>" if row['HighConviction'] and row['NewsHeadline'] else ""
            
            # [FIX: Hide info for FILL]
            if action_status == "FILL":
                target_disp = "---"
                stop_disp = "---"
            else:
                target_disp = f"${row['Target']:.2f}"
                stop_disp = f"${row['Stop']:.2f}"
            
            rsi_disp = f"{row['RSI']:.0f}" if row['RSI'] is not None else "N/A"
            time_unit = "거래일" if row['TimeStop'] > 1 else "일"

            def get_color(val): 
                if val >= 7: return "sc-high"
                elif val >= 4: return "sc-mid"
                return "sc-low"

            html_content = f"""<div class="metric-card {card_class}"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;"><div><a href="https://finance.yahoo.com/quote/{row['Ticker']}" target="_blank" class="ticker-header">{row['Ticker']}</a>{badge_html} <span class="badge {row['MktClass']}">{row['MktLabel']}</span></div><div style="font-weight:bold; color:{act_color}; font-size:12px; border:1px solid {act_color}; padding:2px 6px; border-radius:4px;">{act_badge}</div></div>{news_html}<div class="price-row"><span class="price-label">현재 시세(24h)</span><span class="price-val">${row['Price']:.2f}</span></div><div class="price-row"><span class="price-label">시가대비</span><span class="price-val" style="color:{c_op}">{row['ChgOpen']:+.2f}%</span></div><div class="price-row"><span class="price-label">전일대비</span><span class="price-val" style="color:{c_pr}">{row['ChgPrev']:+.2f}%</span></div><div style="margin-top:10px; text-align:center;"><span class="{row['StratClass']}">{row['StratName']}</span></div><div class="ai-desc">💡 {row['Desc']}</div><div class="score-container"><div class="score-item">응축<br><span class="score-val {get_color(row['Squeeze'])}">{row['Squeeze']:.0f}</span></div><div class="score-item">추세<br><span class="score-val {get_color(row['Trend'])}">{row['Trend']:.0f}</span></div><div class="score-item">수급<br><span class="score-val {get_color(row['Vol'])}">{row['Vol']:.0f}</span></div><div class="score-item">옵션<br><span class="score-val {get_color(row['OptionScore'])}">{row['OptionScore']}</span></div></div><div class="pt-box"><div class="pt-item"><span class="pt-label">목표가</span><span class="pt-val" style="color:#00FF00">{target_disp}</span></div><div class="pt-item"><span class="pt-label">진입가</span><span class="pt-val" style="color:#74b9ff">${row['Price']:.2f}</span></div><div class="pt-item"><span class="pt-label">손절가</span><span class="pt-val" style="color:#FF4444">{stop_disp}</span></div></div><div class="indicator-box">RSI: {rsi_disp} | PCR: {row['PCR']:.2f}<div class="opt-row"><span class="opt-call">Call: {int(row['CallVol']):,}</span><span class="opt-put">Put: {int(row['PutVol']):,}</span></div><div class="opt-bar-bg"><div class="opt-bar-c" style="width:{row['CallPct']}%;"></div><div class="opt-bar-p" style="width:{row['PutPct']}%;"></div></div></div><div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;"><div class="exit-box"><span style="color:#00FF00; font-weight:bold;">🌊 트레일 시작: {target_disp} (0.5x)</span><br><span style="color:#aaa;">⏳ 기한: {row['TimeStop']}{time_unit}</span></div><div style="text-align:right;"><span style="color:#888; font-size:10px;">AI 비중 제안</span><br><span class="bet-badge bet-bg">{bet_text}</span></div></div></div>"""
            
            c1, c2 = st.columns([0.85, 0.15])
            with c2:
                if st.button(fav, key=f"fav_{unique_id}"):
                    if is_fav: st.session_state.watchlist.remove(row['Ticker'])
                    else: st.session_state.watchlist.add(row['Ticker'])
                    st.rerun()
            
            st.markdown(html_content, unsafe_allow_html=True)
            st.plotly_chart(create_chart(row['History'], row['Ticker'], unique_id), use_container_width=True, key=f"chart_{unique_id}", config={'displayModeBar':False})

        t1, t2, t3 = st.tabs(["🚀 단타 (SCALP)", "🌊 스윙 (SWING)", "🌲 장투 (LONG)"])
        
        scalp_list = [x for x in market_data if x['Category'] == 'SCALP']
        swing_list = [x for x in market_data if x['Category'] == 'SWING']
        long_list = [x for x in market_data if x['Category'] == 'LONG']
        
        with t1:
            cols = st.columns(3)
            for i, r in enumerate(scalp_list):
                with cols[i%3]: render_card(r, f"s_{i}")
        with t2:
            cols = st.columns(3)
            for i, r in enumerate(swing_list):
                with cols[i%3]: render_card(r, f"sw_{i}")
        with t3:
            cols = st.columns(3)
            for i, r in enumerate(long_list):
                with cols[i%3]: render_card(r, f"l_{i}")
    else:
        st.warning("🔍 데이터 수집 실패 (API 또는 네트워크 확인)")