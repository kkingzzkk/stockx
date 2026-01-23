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
# 🔑 API 설정
# ==========================================
FINNHUB_API_KEY = "d5p0p81r01qu6m6bocv0d5p0p81r01qu6m6bocvg"

# === [1. 페이지 설정] ===
st.set_page_config(page_title="QUANT NEXUS : MASTER", page_icon="🦅", layout="wide", initial_sidebar_state="expanded")

# === [2. 세션 및 자금 관리 초기화] ===
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = set()
if 'REAL_NAV' not in st.session_state:
    st.session_state.REAL_NAV = 10000.0  
if 'REAL_LOSS' not in st.session_state:
    st.session_state.REAL_LOSS = 0.0     
if 'CONSEC_LOSS' not in st.session_state:
    st.session_state.CONSEC_LOSS = 0

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

@st.cache_data(ttl=120) 
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

def get_timestamp_str():
    ny_tz = pytz.timezone('America/New_York')
    return datetime.now(ny_tz).strftime("%Y-%m-%d %H:%M:%S")

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# === [4. 스타일] ===
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    .metric-card { background-color: #1E1E1E; border: 1px solid #444; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
    .price-row { display: flex; justify-content: space-between; align-items: center; padding: 2px 0; border-bottom: 1px solid #333; font-size: 13px; }
    .price-label { color: #aaa; font-size: 11px; }
    .price-val { font-weight: bold; color: white; font-family: monospace; font-size: 13px; }
    .score-container { display: flex; justify-content: space-between; margin-top: 10px; margin-bottom: 8px; background-color: #252526; padding: 6px; border-radius: 4px; }
    .score-item { text-align: center; font-size: 10px; color: #888; width: 19%; }
    .score-val { font-weight: bold; font-size: 13px; display: block; margin-top: 2px; }
    .sc-high { color: #00FF00; } .sc-mid { color: #FFD700; } .sc-low { color: #FF4444; }
    .pt-box { display: flex; justify-content: space-between; background-color: #151515; padding: 8px; border-radius: 4px; margin-top: 8px; border: 1px dashed #444; }
    .pt-item { text-align: center; width: 33%; font-size: 12px; }
    .pt-label { color: #aaa; font-size: 10px; display: block; }
    .pt-val { font-weight: bold; font-size: 13px; color: white; }
    .exit-box { background-color: #2d3436; border-left: 3px solid #636e72; padding: 8px; font-size: 11px; color: #dfe6e9; margin-top: 10px; }
    .bet-badge { font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; color: black; float: right; margin-top: 5px; }
    .bet-bg { background-color: #74b9ff; }
    .ticker-header { font-size: 18px; font-weight: bold; color: #00CCFF; text-decoration: none !important; }
    .badge { padding: 2px 5px; border-radius: 3px; font-size: 9px; font-weight: bold; color: white; margin-left: 5px; vertical-align: middle;}
    .mkt-pre { background-color: #d29922; color: black; } .mkt-reg { background-color: #238636; color: white; } .mkt-aft { background-color: #1f6feb; color: white; } .mkt-cls { background-color: #6e7681; color: white; }
    .st-gamma { background-color: #6c5ce7; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block; }
    .st-squeeze { background-color: #0984e3; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block; }
    .st-value { background-color: #00b894; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block; }
    .st-dip { background-color: #e17055; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block; }
    .st-none { background-color: #333; color: #777; padding: 2px 6px; border-radius: 4px; font-size: 11px; display:inline-block; }
    .st-highconv { background-color: #e17055; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-left: 5px; }
    .news-line { color: #ffa502; font-size: 12px; margin-top: 4px; padding: 4px; background-color: #2d2d2d; border-radius: 4px; display: block; border-left: 3px solid #ffa502; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .ai-desc { font-size: 11px; color: #ccc; margin-top: 5px; font-style: italic; text-align: center; }
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

INDEX_CONSTITUENTS = {
    "NASDAQ100": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AVGO", "COST", "PEP", "CSCO", "TMUS", "CMCSA", "INTC", "AMD", "QCOM", "TXN", "AMGN", "HON", "INTU", "SBUX", "GILD", "MDLZ", "BKNG", "ADI", "ISRG", "ADP", "REGN", "VRTX", "LRCX", "PANW", "SNPS", "CDNS", "KLAC", "ASML", "MELI", "MNST", "ORCL", "MAR", "NXPI", "CTAS", "FTNT", "DXCM", "WDAY", "MCHP", "AEP", "KDP", "LULU", "MRVL", "ADSK"],
    "SP500_TOP": ["MSFT", "AAPL", "NVDA", "AMZN", "GOOGL", "META", "BRK.B", "TSLA", "LLY", "AVGO", "JPM", "V", "UNH", "XOM", "MA", "JNJ", "HD", "PG", "COST", "MRK", "ABBV", "CRM", "CVX", "BAC", "AMD", "NFLX", "PEP", "KO", "WMT", "ADBE", "TMO", "ACN", "LIN", "MCD", "CSCO", "ABT", "DIS", "INTU", "WFC", "VZ", "CMCSA", "QCOM", "DHR", "CAT", "TXN", "AMGN", "IBM", "PM", "UNP", "GE"],
    "RUSSELL_GROWTH": ["SMCI", "MSTR", "COIN", "CVNA", "AFRM", "DKNG", "HOOD", "RIVN", "SOFI", "PLTR", "PATH", "U", "RBLX", "OPEN", "LCID", "MARA", "RIOT", "CLSK", "GME", "AMC", "UPST", "AI", "IONQ", "RGTI", "QUBT", "JOBY", "ACHR", "ASTS", "LUNR", "RKLB"]
}

# === [6. 설정값 (실전용)] ===
CONFIG = {"MAX_RISK": 0.01} 

# === [7. 엔진: Logic Core] ===
@st.cache_data(ttl=120)
def get_market_data(tickers, effective_nav, consec_loss):
    tickers = list(set(tickers))
    is_halted = True if consec_loss >= 2 else False
    data_list = []
    
    def fetch_single(ticker):
        try:
            stock = yf.Ticker(ticker)
            hist_day = stock.history(period="1y") 
            if hist_day.empty or len(hist_day) < 20: return None
            
            hist_rt = stock.history(period="1d", interval="5m", prepost=False)
            if hist_rt.empty: 
                hist_rt = hist_day 
                cur = hist_day['Close'].iloc[-1]
                rsi_intra = 50 
                last_time = datetime.now(pytz.timezone('America/New_York')).time()
            else:
                cur = hist_rt['Close'].iloc[-1]
                last_dt = hist_rt.index[-1]
                if last_dt.tzinfo is None:
                    last_dt = pytz.utc.localize(last_dt).astimezone(pytz.timezone('America/New_York'))
                else:
                    last_dt = last_dt.astimezone(pytz.timezone('America/New_York'))
                last_time = last_dt.time()

                if len(hist_rt) < 20:
                    rsi_intra = 80 
                else:
                    rsi_intra = calculate_rsi(hist_rt['Close']).iloc[-1]
                    if np.isnan(rsi_intra): rsi_intra = 80

            open_p = hist_day['Open'].iloc[-1]
            prev_c = hist_day['Close'].iloc[-2]
            
            ma20 = hist_day['Close'].rolling(20).mean()
            ma200 = hist_day['Close'].rolling(200).mean()
            std20 = hist_day['Close'].rolling(20).std()
            upper_bb = ma20 + (std20 * 2)
            lower_bb = ma20 - (std20 * 2)
            bbw = (upper_bb - lower_bb) / ma20
            bbw_val = bbw.rank(pct=True).iloc[-1]
            sc_squeeze = (1 - (bbw_val if not np.isnan(bbw_val) else 0.5)) * 10
            
            sc_trend = 0
            if cur > ma20.iloc[-1]: sc_trend += 5
            if len(ma200) > 0 and cur > ma200.iloc[-1]: sc_trend += 5
            
            vol_avg = hist_day['Volume'].rolling(20).mean().iloc[-1]
            vol_ratio = (hist_day['Volume'].iloc[-1] / vol_avg) if vol_avg > 0 else 1.0
            sc_vol = min(10, vol_ratio * 3)
            
            hist_day['TR'] = np.maximum(hist_day['High'] - hist_day['Low'], 
                                        np.maximum(abs(hist_day['High'] - hist_day['Close'].shift(1)), 
                                                   abs(hist_day['Low'] - hist_day['Close'].shift(1))))
            atr = hist_day['TR'].rolling(14).mean().iloc[-1]

            rsi_day = calculate_rsi(hist_day['Close']).iloc[-1]
            
            pcr = 1.0; c_vol = 0; p_vol = 0; 
            call_wall = 100000; put_wall = 0
            has_option = False 
            try:
                opts = stock.options
                if opts:
                    chain = stock.option_chain(opts[0])
                    c_vol = chain.calls['volume'].sum(); p_vol = chain.puts['volume'].sum()
                    if c_vol > 0: pcr = p_vol / c_vol
                    call_wall = chain.calls.sort_values('openInterest', ascending=False).iloc[0]['strike']
                    put_wall = chain.puts.sort_values('openInterest', ascending=False).iloc[0]['strike']
                    has_option = True
            except: pass

            category = "NONE"; strat_name = "관망"; strat_class = "st-none"; desc = "특이사항 없음"
            
            if cur > upper_bb.iloc[-1] and vol_ratio > 1.8:
                if rsi_intra > 75: 
                    category = "NONE"; strat_name = "🚫 단기 과열"; strat_class = "st-none"
                    desc = f"장중 RSI {rsi_intra:.0f} 과열. 추격 금지."
                else:
                    category = "SCALP"; strat_name = "🚀 수급 돌파"; strat_class = "st-gamma"
                    desc = f"거래량 폭발({vol_ratio:.1f}배) + 밴드 상단 돌파"

            elif sc_squeeze > 8.0:
                category = "SWING"; strat_name = "🌊 에너지 응축"; strat_class = "st-squeeze"
                desc = "변동성 극소화, 시세 분출 임박"
            elif cur <= lower_bb.iloc[-1] and rsi_day < 35: 
                category = "SWING"; strat_name = "🛡️ 과매도 반등"; strat_class = "st-dip"
                desc = f"일봉 RSI {rsi_day:.0f} 과매도."
            elif cur > ma20.iloc[-1] and (len(ma200) > 0 and cur > ma200.iloc[-1]) and 50 < rsi_day < 70:
                category = "LONG"; strat_name = "💎 대세 상승"; strat_class = "st-value"
                desc = "이평선 정배열 + 안정적 우상향"

            score = 0
            if category == "SCALP":
                if pcr < 0.7: score += 10 
                if pcr > 1.3: score -= 20 
            else:
                if has_option:
                    if cur > put_wall: score += 10 
                    if pcr >= 1.2: score += 20 
                
            if vol_ratio > 2.0: score += 10 
            if sc_squeeze > 8: score += 10
            if 40 <= rsi_day <= 60: score += 10 
            
            if category == "SCALP":
                score = min(score, 75)

            news_ok = False; news_hl = None
            if vol_ratio >= 3.0 and score >= 50:
                try: news_ok, news_hl = check_recent_news(ticker)
                except: pass
            
            if category == "SCALP" and news_ok:
                if last_time < time(10, 0):
                    category = "NONE"; strat_name = "🚫 뉴스 시초가 위험"; strat_class = "st-none"
                    desc = "10시 이전 뉴스 갭상승은 설거지 위험 높음."
                    score = 0
                elif pcr < 0.6:
                    category = "NONE"; strat_name = "🚫 뉴스 설거지 주의"; strat_class = "st-none"
                    desc = "뉴스 호재 + 콜 과열. 고점 매도 위험."
                    score = 0
                else:
                    score += 10 

            target_pct, stop_pct, trail_pct, time_stop_days = 0.05, 0.03, 0.02, 5
            if category == "SCALP": target_pct, stop_pct, trail_pct, time_stop_days = 0.06, 0.05, 0.03, 2
            elif category == "SWING": target_pct, stop_pct, trail_pct, time_stop_days = 0.15, 0.05, 0.04, 10
            elif category == "LONG": target_pct, stop_pct, trail_pct, time_stop_days = 0.30, 0.10, 0.10, 60

            stop_atr = cur - atr * 1.5
            
            if category == "SCALP":
                stop_price = stop_atr
                min_stop_level = cur * 0.97 
            else:
                stop_price = max(put_wall * 0.99, stop_atr) if (has_option and put_wall < cur) else stop_atr
                min_stop_level = cur * 0.95 
            
            # [Fix] 손절가 하드캡: 계산된 손절가가 너무 깊으면(-10%), 최소 유격(-3%)선으로 당김.
            # stop_price(-10%) vs min_stop_level(-3%) -> max 사용 -> -3% 선택 (계좌 보호)
            stop_price = max(stop_price, min_stop_level)
            
            target_calc = cur * (1 + target_pct * 1.5)
            if category == "SCALP":
                target_price = target_calc 
            else:
                target_price = min(call_wall, target_calc) if (has_option and call_wall > cur) else target_calc
                
            trail_price = cur * (1 + trail_pct) 
            
            risk_per_share = cur - stop_price
            risk_per_share = max(risk_per_share, cur * 0.02)
            
            risk_amt = effective_nav * CONFIG["MAX_RISK"]
            tilt_factor = 0.0 if is_halted else 0.8 ** consec_loss 
            
            multiplier = 0.0
            if category == "SCALP":
                if score >= 70: multiplier = 0.4
                elif score >= 60: multiplier = 0.3
            else:
                if score >= 85: multiplier = 0.8
                elif score >= 70: multiplier = 0.6
                elif score >= 60: multiplier = 0.4
            
            final_risk = risk_amt * multiplier * tilt_factor
            qty = int(final_risk / risk_per_share) if risk_per_share > 0 else 0
            
            bet_text = "❌ 패스"
            if is_halted:
                bet_text = "⛔ 매매 금지"
            elif qty > 0:
                bet_text = f"매수: {qty}주" if multiplier >= 0.4 else "소량 진입"

            journal_txt = {
                "Ticker": ticker, "Strategy": strat_name, "Entry": round(cur, 2), 
                "Target": round(target_price, 2), "Stop": round(stop_price, 2), 
                "Score": score, "Time": get_timestamp_str()
            }

            return {
                "Ticker": ticker, "Price": cur, "Category": category, "StratName": strat_name, "StratClass": strat_class,
                "Squeeze": sc_squeeze, "Trend": sc_trend, "Vol": sc_vol, "Option": 0, "Desc": desc,
                "BetAmount": qty * cur, "BetText": bet_text, "Score": score,
                "Target": target_price, "Stop": stop_price, 
                "HardStop": stop_price, "TrailStop": trail_price, "TimeStop": time_stop_days,
                "Journal": journal_txt, "History": hist_day['Close'],
                "ChgOpen": (cur - open_p)/open_p * 100, "ChgPrev": (cur - prev_c)/prev_c * 100,
                "DiffOpen": cur - open_p, "DiffPrev": cur - prev_c,
                "RSI": rsi_day, "PCR": pcr, "CallVol": c_vol, "PutVol": p_vol,
                "MktLabel": mkt_label, "MktClass": mkt_class, "HighConviction": news_ok, "NewsHeadline": news_hl
            }
        except: return None
    
    max_workers = 3 if len(tickers) > 50 else 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
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
    
    st.markdown("### 💰 자금 관리 (Risk Management)")
    st.session_state.REAL_NAV = st.number_input("초기 원금 ($)", value=st.session_state.REAL_NAV, step=1000.0)
    st.session_state.REAL_LOSS = st.number_input("누적 실현 손실 ($)", value=st.session_state.REAL_LOSS, step=100.0)
    st.session_state.CONSEC_LOSS = st.number_input("연속 손실 횟수 (Tilt)", value=st.session_state.CONSEC_LOSS, step=1, min_value=0)
    
    effective_nav = max(st.session_state.REAL_NAV - st.session_state.REAL_LOSS, 1000)
    st.info(f"⚡ 운용 가능 자금: ${effective_nav:,.0f}")
    
    if st.session_state.CONSEC_LOSS >= 2:
        st.error(f"🚨 [경고] 연속 손실 {st.session_state.CONSEC_LOSS}회. 단타 매매 금지.")
    
    mode = st.radio("분석 모드", ["🏆 AI 전체 시장 스캔", "🔍 무제한 검색", "⭐ 내 관심종목 보기"])
    
    target_tickers = []
    
    if mode == "⭐ 내 관심종목 보기":
        if not st.session_state.watchlist:
            st.warning("관심종목이 없습니다.")
        else:
            target_tickers = list(st.session_state.watchlist)
            if st.button("🗑️ 전체 삭제"):
                st.session_state.watchlist = set()
                st.rerun()
                
    elif mode == "🔍 무제한 검색":
        st.info("티커 입력 (예: NVDA, TSLA)")
        search_txt = st.text_input("종목 입력", value="")
        if search_txt: target_tickers = [t.strip().upper() for t in search_txt.split(',')]
        
    elif mode == "🏆 AI 전체 시장 스캔":
        # [수정] 섹터별 보기 vs TOP 50 보기 분리
        scan_option = st.radio("스캔 옵션", ["📂 섹터별 보기", "💎 AI 추천 TOP 50"])
        
        if scan_option == "📂 섹터별 보기":
            # [수정] 드래그 방식 삭제 -> Selectbox로 깔끔하게 (전체 포함)
            sector_list = ["전체(ALL)"] + list(SECTORS.keys())
            selected_sector = st.selectbox("섹터 선택", sector_list)
            
            if st.button("🚀 섹터 분석 시작"):
                if selected_sector == "전체(ALL)":
                    st.toast("⚠️ 전체 스캔은 시간이 걸릴 수 있습니다.", icon="⏳")
                    target_tickers = ALL_TICKERS
                else:
                    target_tickers = SECTORS[selected_sector]
                    
        else: # TOP 50 모드
            if st.button("💎 TOP 50 발굴 시작"):
                st.toast("⚡ 전체 시장 정밀 스캔 중... (잠시만 기다리세요)", icon="🦅")
                target_tickers = ALL_TICKERS

st.title(f"🇺🇸 {mode}")

if target_tickers:
    with st.spinner(f"AI 정밀 분석 중... ({len(target_tickers)} 종목)"):
        market_data = get_market_data(target_tickers, effective_nav, st.session_state.CONSEC_LOSS)
    
    if not market_data:
        if mode != "⭐ 내 관심종목 보기":
            st.warning("데이터를 불러올 수 없습니다.")
    else:
        # [추가] TOP 50 모드일 경우, 점수순 정렬 후 상위 50개만 자름
        if mode == "🏆 AI 전체 시장 스캔" and 'scan_option' in locals() and scan_option == "💎 AI 추천 TOP 50":
            market_data = sorted(market_data, key=lambda x: x['Score'], reverse=True)[:50]
            st.success(f"💎 전체 시장 중 AI 점수가 가장 높은 상위 {len(market_data)}개를 발굴했습니다.")

        def render_card(row, unique_id):
            def get_color(val): return "sc-high" if val >= 7 else "sc-mid" if val >= 4 else "sc-low"
            c_op = "#00FF00" if row['ChgOpen'] >= 0 else "#FF4444"
            c_pr = "#00FF00" if row['ChgPrev'] >= 0 else "#FF4444"
            is_fav = row['Ticker'] in st.session_state.watchlist
            fav = "❤️" if is_fav else "🤍"
            
            badge_html = f"<span class='st-highconv'>📰 News Alert</span>" if row['HighConviction'] else ""
            news_html = f"<div class='news-line'>{row['NewsHeadline']}</div>" if row['HighConviction'] and row['NewsHeadline'] else ""

            html_content = f"""<div class="metric-card"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;"><div><a href="https://finance.yahoo.com/quote/{row['Ticker']}" target="_blank" class="ticker-header">{row['Ticker']}</a>{badge_html} <span class="badge {row['MktClass']}">{row['MktLabel']}</span></div></div>{news_html}<div class="price-row"><span class="price-label">현재(24h)</span><span class="price-val">${row['Price']:.2f}</span></div><div class="price-row"><span class="price-label">시가대비</span><span class="price-val" style="color:{c_op}">{row['DiffOpen']:+.2f} ({row['ChgOpen']:+.2f}%)</span></div><div class="price-row"><span class="price-label">전일대비</span><span class="price-val" style="color:{c_pr}">{row['DiffPrev']:+.2f} ({row['ChgPrev']:+.2f}%)</span></div><div style="margin-top:10px; text-align:center;"><span class="{row['StratClass']}">{row['StratName']}</span></div><div class="ai-desc">💡 {row['Desc']}</div><div class="score-container"><div class="score-item">응축<br><span class="score-val {get_color(row['Squeeze'])}">{row['Squeeze']:.0f}</span></div><div class="score-item">추세<br><span class="score-val {get_color(row['Trend'])}">{row['Trend']:.0f}</span></div><div class="score-item">수급<br><span class="score-val {get_color(row['Vol'])}">{row['Vol']:.0f}</span></div><div class="score-item">점수<br><span class="score-val {get_color(row['Score']/10)}">{row['Score']}</span></div></div><div class="pt-box"><div class="pt-item"><span class="pt-label">목표가</span><span class="pt-val" style="color:#00FF00">${row['Target']:.2f}</span></div><div class="pt-item"><span class="pt-label">진입가</span><span class="pt-val" style="color:#74b9ff">${row['Price']:.2f}</span></div><div class="pt-item"><span class="pt-label">손절가</span><span class="pt-val" style="color:#FF4444">${row['Stop']:.2f}</span></div></div><div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;"><div class="exit-box"><span style="color:#00FF00; font-weight:bold;">🌊 트레일링 시작: ${row['TrailStop']:.2f}</span><br><span style="color:#FF4444;">🚨 손절(Max): ${row['HardStop']:.2f}</span><br><span style="color:#aaa;">⏳ 기한: {row['TimeStop']}일</span></div><div style="text-align:right;"><span style="color:#888; font-size:10px;">AI 비중 제안</span><br><span class="bet-badge bet-bg">{row['BetText']}</span></div></div></div>"""
            
            c1, c2 = st.columns([0.85, 0.15])
            with c2:
                if st.button(fav, key=f"fav_{unique_id}"):
                    if is_fav: st.session_state.watchlist.remove(row['Ticker'])
                    else: st.session_state.watchlist.add(row['Ticker'])
                    st.rerun()
            
            st.markdown(html_content, unsafe_allow_html=True)
            st.plotly_chart(create_chart(row['History'], row['Ticker'], unique_id), use_container_width=True, key=f"chart_{unique_id}", config={'displayModeBar':False})

        if "추천" in mode or "인덱스" in mode:
            df = pd.DataFrame(market_data)
            t1, t2, t3 = st.tabs(["🚀 단타 (SCALP)", "🌊 스윙 (SWING)", "🌲 장투 (LONG)"])
            
            with t1:
                cols = st.columns(3)
                for i, r in enumerate(df[df['Category']=='SCALP'].sort_values('Vol', ascending=False).to_dict('records')):
                    with cols[i%3]: render_card(r, f"s_{i}")
            with t2:
                cols = st.columns(3)
                for i, r in enumerate(df[df['Category']=='SWING'].sort_values('Squeeze', ascending=False).to_dict('records')):
                    with cols[i%3]: render_card(r, f"sw_{i}")
            with t3:
                cols = st.columns(3)
                for i, r in enumerate(df[df['Category']=='LONG'].sort_values('Trend', ascending=False).to_dict('records')):
                    with cols[i%3]: render_card(r, f"l_{i}")
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