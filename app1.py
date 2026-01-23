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
st.set_page_config(page_title="QUANT NEXUS : FINAL", page_icon="💎", layout="wide", initial_sidebar_state="expanded")

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
        res = requests.get(url, timeout=1)
        if res.status_code == 200:
            data = res.json()
            if data and isinstance(data, list):
                return True, data[0].get('headline', '뉴스 내용 없음')
    except: pass
    return False, None

def get_timestamp_str():
    ny_tz = pytz.timezone('America/New_York')
    return datetime.now(ny_tz).strftime("%Y-%m-%d %H:%M:%S")

# === [4. 스타일 (깨짐 방지)] ===
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    .metric-card { background-color: #1E1E1E; border: 1px solid #444; border-radius: 8px; padding: 15px; margin-bottom: 15px; position: relative; }
    .price-row { display: flex; justify-content: space-between; align-items: center; padding: 2px 0; border-bottom: 1px solid #333; font-size: 13px; }
    .price-label { color: #aaa; font-size: 11px; }
    .price-val { font-weight: bold; color: white; font-family: monospace; font-size: 13px; }
    .score-container { display: flex; justify-content: space-between; margin-top: 10px; margin-bottom: 8px; background-color: #252526; padding: 6px; border-radius: 4px; }
    .score-item { text-align: center; font-size: 10px; color: #888; width: 19%; }
    .score-val { font-weight: bold; font-size: 13px; display: block; margin-top: 2px; }
    .sc-high { color: #00FF00; } .sc-mid { color: #FFD700; } .sc-low { color: #FF4444; }
    .indicator-box { background-color: #252526; border-radius: 4px; padding: 6px; margin-top: 8px; font-size: 11px; color: #ccc; text-align: center; border: 1px solid #333; }
    .opt-row { display: flex; justify-content: space-between; font-size: 11px; margin-top: 4px; font-weight: bold; }
    .opt-call { color: #00FF00; } .opt-put { color: #FF4444; }
    .opt-bar-bg { background-color: #333; height: 5px; border-radius: 2px; overflow: hidden; display: flex; margin-top: 3px; }
    .opt-bar-c { background-color: #00FF00; height: 100%; }
    .opt-bar-p { background-color: #FF4444; height: 100%; }
    .price-target-box { display: flex; justify-content: space-between; background-color: #151515; padding: 8px; border-radius: 4px; margin-top: 8px; margin-bottom: 8px; border: 1px dashed #444; }
    .pt-item { text-align: center; width: 33%; font-size: 12px; }
    .pt-label { color: #aaa; font-size: 10px; display: block; }
    .pt-val { font-weight: bold; font-size: 13px; color: white; }
    .exit-box { background-color: #2d3436; border-left: 3px solid #636e72; padding: 8px; font-size: 11px; color: #dfe6e9; margin-top: 10px; }
    .bet-badge { font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; color: black; float: right; margin-top: 5px; }
    .bet-bg { background-color: #74b9ff; }
    .ticker-header { font-size: 18px; font-weight: bold; color: #00CCFF; text-decoration: none !important; }
    .badge { padding: 2px 5px; border-radius: 3px; font-size: 9px; font-weight: bold; color: white; margin-left: 5px; vertical-align: middle;}
    .mkt-pre { background-color: #d29922; color: black; }
    .mkt-reg { background-color: #238636; color: white; }
    .mkt-aft { background-color: #1f6feb; color: white; }
    .mkt-cls { background-color: #6e7681; color: white; }
    .st-gamma { background-color: #6c5ce7; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block; }
    .st-squeeze { background-color: #0984e3; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block;}
    .st-value { background-color: #00b894; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block;}
    .st-none { background-color: #333; color: #777; padding: 3px 8px; border-radius: 4px; font-size: 11px; display:inline-block;}
    .st-highconv { background-color: #e17055; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 5px; }
    .news-line { color: #ffa502; font-size: 12px; margin-top: 4px; padding: 4px; background-color: #2d2d2d; border-radius: 4px; display: block; border-left: 3px solid #ffa502; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
""", unsafe_allow_html=True)

# === [5. 데이터 설정] ===
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
    "20. 🧈 금/광물": ["GOLD", "NEM", "KL", "GDX", "GDXJ", "GLD", "SLV", "AEM", "FCX", "SCCO"],
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
ALL_TICKERS = sorted(list(set([ticker for sector in SECTORS.values() for ticker in sector])))

INDEX_CONSTITUENTS = {
    "NASDAQ100": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AVGO", "COST", "PEP", "CSCO", "TMUS", "CMCSA", "INTC", "AMD", "QCOM", "TXN", "AMGN", "HON", "INTU", "SBUX", "GILD", "MDLZ", "BKNG", "ADI", "ISRG", "ADP", "REGN", "VRTX", "LRCX", "PANW", "SNPS", "CDNS", "KLAC", "ASML", "MELI", "MNST", "ORCL", "MAR", "NXPI", "CTAS", "FTNT", "DXCM", "WDAY", "MCHP", "AEP", "KDP", "LULU", "MRVL", "ADSK"],
    "SP500_TOP": ["MSFT", "AAPL", "NVDA", "AMZN", "GOOGL", "META", "BRK.B", "TSLA", "LLY", "AVGO", "JPM", "V", "UNH", "XOM", "MA", "JNJ", "HD", "PG", "COST", "MRK", "ABBV", "CRM", "CVX", "BAC", "AMD", "NFLX", "PEP", "KO", "WMT", "ADBE", "TMO", "ACN", "LIN", "MCD", "CSCO", "ABT", "DIS", "INTU", "WFC", "VZ", "CMCSA", "QCOM", "DHR", "CAT", "TXN", "AMGN", "IBM", "PM", "UNP", "GE"],
    "RUSSELL_GROWTH": ["SMCI", "MSTR", "COIN", "CVNA", "AFRM", "DKNG", "HOOD", "RIVN", "SOFI", "PLTR", "PATH", "U", "RBLX", "OPEN", "LCID", "MARA", "RIOT", "CLSK", "GME", "AMC", "UPST", "AI", "IONQ", "RGTI", "QUBT", "JOBY", "ACHR", "ASTS", "LUNR", "RKLB"]
}

# === [6. 설정값 (기본)] ===
CONFIG = {"NAV": 10000, "BASE_BET": 0.15}

# === [7. 엔진: Logic Core] ===
@st.cache_data(ttl=600)
def get_market_data(tickers):
    tickers = list(set(tickers))
    try:
        spy = yf.download("SPY", period="6mo", progress=False)
        vix = yf.Ticker("^VIX").history(period="5d")
        regime_score = 5.0
        if not spy.empty:
            if isinstance(spy.columns, pd.MultiIndex): spy.columns = spy.columns.get_level_values(0)
            spy_trend = 1 if spy['Close'].iloc[-1] > spy['Close'].rolling(200).mean().iloc[-1] else 0
            if spy_trend: regime_score += 2.0
        if not vix.empty:
            v_val = vix['Close'].iloc[-1]
            if v_val < 20: regime_score += 3.0
            elif v_val < 25: regime_score += 1.0
            elif v_val > 30: regime_score -= 3.0
    except: regime_score = 5.0

    data_list = []
    mkt_code, mkt_label, mkt_class = get_market_status()
    
    def fetch_single(ticker):
        try:
            stock = yf.Ticker(ticker)
            # [수정] 데이터 검증 완화 (최소 2일치) -> 데이터오류 해결
            hist_day = stock.history(period="1y") 
            if hist_day.empty or len(hist_day) < 2: return None
            
            hist_15m = stock.history(period="5d", interval="15m")
            has_intraday = False if (hist_15m is None or len(hist_15m) < 30) else True
            
            hist_rt = stock.history(period="1d", interval="1m", prepost=True)
            if not hist_rt.empty: cur = hist_rt['Close'].iloc[-1]
            else: cur = hist_day['Close'].iloc[-1]

            open_price = hist_day['Open'].iloc[-1]
            prev_close = hist_day['Close'].iloc[-2]
            diff_open = cur - open_price
            diff_prev = cur - prev_close
            chg_open = (diff_open / open_price) * 100
            chg_prev = (diff_prev / prev_close) * 100
            
            ma20 = hist_day['Close'].rolling(20).mean()
            std = hist_day['Close'].rolling(20).std()
            bbw_series = ((ma20 + std*2) - (ma20 - std*2)) / ma20
            bbw_rank = bbw_series.rolling(window=120, min_periods=60).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1]).iloc[-1]
            if np.isnan(bbw_rank): bbw_rank = 0.5
            sc_squeeze = (1 - bbw_rank) * 10
            
            subset = hist_day.iloc[-60:].copy()
            avwap = cur # fallback
            try:
                top3_vol = subset['Volume'].nlargest(3).index
                anchor = top3_vol.max()
                avwap_sub = subset.loc[anchor:]
                avwap = (avwap_sub['Close'] * avwap_sub['Volume']).cumsum().iloc[-1] / avwap_sub['Volume'].cumsum().iloc[-1]
            except: pass
            
            sc_trend = 5.0
            if cur > ma20.iloc[-1]: sc_trend += 2.0
            if cur > avwap: sc_trend += 3.0
            if cur < ma20.iloc[-1]: sc_trend -= 2.0
            sc_trend = max(0, min(10, sc_trend))
            
            vol_avg = hist_day['Volume'].rolling(20).mean().iloc[-1]
            vol_ratio = (hist_day['Volume'].iloc[-1] / vol_avg) if vol_avg > 0 else 1.0
            sc_vol = min(10, vol_ratio * 3)
            
            sc_option = 5.0
            pcr = 1.0; c_vol = 0; p_vol = 0
            
            delta = hist_day['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
            loss_val = loss if loss != 0 else 0.0001
            rsi = 100 - (100 / (1 + gain/loss_val))

            try:
                opts = stock.options
                if opts:
                    chain = stock.option_chain(opts[0])
                    c_vol = chain.calls['volume'].sum(); p_vol = chain.puts['volume'].sum()
                    if c_vol > 0: pcr = p_vol / c_vol
                    if pcr < 0.7: sc_option += 2.0
                    elif pcr > 1.2: sc_option -= 2.0
            except: pass
            sc_option = max(0, min(10, sc_option))
            
            total_opt = c_vol + p_vol
            c_pct = (c_vol / total_opt * 100) if total_opt > 0 else 50
            p_pct = (p_vol / total_opt * 100) if total_opt > 0 else 50

            base_amt = CONFIG["NAV"] * CONFIG["BASE_BET"]
            multiplier = 1.0
            ret_std = hist_day['Close'].pct_change().rolling(5).std().iloc[-1]
            if ret_std > 0.04: multiplier *= 0.7 
            if sc_squeeze > 8.0: multiplier *= 1.2
            if regime_score < 4.0: multiplier *= 0.5
            final_bet = base_amt * multiplier
            bet_text = "비중:최대" if multiplier >= 1.2 else "비중:보통" if multiplier >= 1.0 else "비중:축소" if multiplier > 0.5 else "비중:최소"

            category = "NONE"; strat_name="관망"; strat_class="st-none"
            time_stop_days = 0; target_pct = 0; stop_pct = 0; trail_pct = 0

            if has_intraday and sc_vol > 7 and cur > avwap: 
                category = "SHORT"
                strat_name = "🚀 단타"; strat_class = "st-gamma"
                time_stop_days = 1
                target_pct = 0.03; stop_pct = 0.02; trail_pct = 0.01 
            elif sc_squeeze > 7 and sc_trend > 6: 
                category = "SWING"
                strat_name = "🌊 스윙"; strat_class = "st-squeeze"
                time_stop_days = 14
                target_pct = 0.10; stop_pct = 0.06; trail_pct = 0.04
            elif sc_trend > 8 and regime_score > 7: 
                category = "LONG"
                strat_name = "🌲 장투"; strat_class = "st-value"
                time_stop_days = 90
                target_pct = 0.30; stop_pct = 0.15; trail_pct = 0.10
            else:
                target_pct = 0.05; stop_pct = 0.03; trail_pct = 0.02; time_stop_days = 5
            
            # [수정] 익절라인 정상화 (현재가보다 위 +)
            tgt_price = cur * (1 + target_pct)
            hard_stop_price = cur * (1 - stop_pct)
            trail_stop_price = cur * (1 + trail_pct) 

            news_ok, news_hl = False, None
            if vol_ratio >= 3.0: 
                try: news_ok, news_hl = check_recent_news(ticker)
                except: pass

            journal_txt = f"{ticker} | {category} | Entry: {cur:.2f}"

            return {
                "Ticker": ticker, "Price": cur, "Category": category, "StratName": strat_name, "StratClass": strat_class,
                "Squeeze": sc_squeeze, "Trend": sc_trend, "Regime": regime_score, "Vol": sc_vol, "Option": sc_option,
                "BetAmount": final_bet, "Multiplier": multiplier, "BetText": bet_text,
                "Target": tgt_price, "Stop": hard_stop_price, 
                "HardStop": hard_stop_price, "TrailStop": trail_stop_price, "TimeStop": time_stop_days,
                "PrimaryExit": "Time" if category == "SWING" else "Hard" if category == "SHORT" else "Trail",
                "Journal": journal_txt, "History": hist_day['Close'],
                "ChgOpen": chg_open, "ChgPrev": chg_prev, "DiffOpen": diff_open, "DiffPrev": diff_prev,
                "RSI": rsi, "PCR": pcr, "CallVol": c_vol, "PutVol": p_vol, "CallPct": c_pct, "PutPct": p_pct,
                "MktLabel": mkt_label, "MktClass": mkt_class, "HighConviction": news_ok, "NewsHeadline": news_hl
            }
        except: return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_single, t) for t in tickers]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res is not None: data_list.append(res)
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
            st.warning("아직 관심종목이 없습니다. 하트를 눌러 추가하세요!")
        else:
            target_tickers = list(st.session_state.watchlist)
            if st.button("🗑️ 전체 삭제"):
                st.session_state.watchlist = set()
                st.rerun()
                
    elif "섹터" in mode:
        # [수정] 드래그 삭제 -> 라디오 버튼으로 원복
        selected_sector = st.radio("섹터 선택", list(SECTORS.keys()))
        target_tickers = SECTORS[selected_sector]
        
    elif "검색" in mode:
        st.info("💡 티커 입력 (예: IONQ, RKLB, SPY)")
        search_txt = st.text_input("종목 입력", value="")
        if search_txt: target_tickers = [t.strip().upper() for t in search_txt.split(',')]
        
    elif "인덱스" in mode:
        index_choice = st.radio("인덱스 선택", ["NASDAQ100 (Top 50)", "SP500 (Top 50)", "RUSSELL (Growth Top 30)"])
        if index_choice == "NASDAQ100 (Top 50)": target_tickers = INDEX_CONSTITUENTS["NASDAQ100"]
        elif index_choice == "SP500 (Top 50)": target_tickers = INDEX_CONSTITUENTS["SP500_TOP"]
        elif index_choice == "RUSSELL (Growth Top 30)": target_tickers = INDEX_CONSTITUENTS["RUSSELL_GROWTH"]
        if st.button("🚀 데이터 로드"): pass
        
    elif "추천" in mode:
        if st.button("🚀 전체 시장 스캔"): target_tickers = ALL_TICKERS
            
    if st.button("🔄 새로고침"): st.cache_data.clear(); st.rerun()

st.title(f"🇺🇸 {mode}")

if target_tickers:
    with st.spinner(f"데이터 분석 중... ({len(target_tickers)} 종목)"):
        market_data = get_market_data(target_tickers)
    
    if not market_data:
        if mode != "⭐ 내 관심종목 보기":
            st.warning("데이터를 불러올 수 없거나, 유효하지 않은 티커입니다.")
    else:
        # [Render Function] 화면 깨짐 방지
        def render_card(row, unique_id):
            def get_color(val): return "sc-high" if val >= 7 else "sc-mid" if val >= 4 else "sc-low"
            ex_hard = "exit-primary" if row['PrimaryExit'] == "Hard" else ""
            ex_time = "exit-primary" if row['PrimaryExit'] == "Time" else ""
            ex_trail = "exit-primary" if row['PrimaryExit'] == "Trail" else ""
            
            color_open = "#00FF00" if row['ChgOpen'] >= 0 else "#FF4444"
            color_prev = "#00FF00" if row['ChgPrev'] >= 0 else "#FF4444"
            
            is_fav = row['Ticker'] in st.session_state.watchlist
            fav_icon = "❤️" if is_fav else "🤍"
            
            # Badge & News HTML (f-string 한 줄 처리로 깨짐 방지)
            badge_html = f"<span class='st-highconv'>🔥 High Conviction</span>" if row['HighConviction'] else ""
            news_html = f"<div class='news-line'>📰 {row['NewsHeadline']}</div>" if row['HighConviction'] and row['NewsHeadline'] else ""

            html_content = f"""<div class="metric-card"><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;"><div><a href="https://finance.yahoo.com/quote/{row['Ticker']}" target="_blank" class="ticker-header">{row['Ticker']}</a>{badge_html} <span class="badge {row['MktClass']}">{row['MktLabel']}</span></div></div>{news_html}<div class="price-row"><span class="price-label">현재(24h)</span><span class="price-val">${row['Price']:.2f}</span></div><div class="price-row"><span class="price-label">시가대비</span><span class="price-val" style="color:{color_open}">{row['DiffOpen']:+.2f} ({row['ChgOpen']:+.2f}%)</span></div><div class="price-row"><span class="price-label">전일대비</span><span class="price-val" style="color:{color_prev}">{row['DiffPrev']:+.2f} ({row['ChgPrev']:+.2f}%)</span></div><div style="margin-top:10px; margin-bottom:5px; text-align:center;"><span class="{row['StratClass']}">{row['StratName']}</span></div><div class="score-container"><div class="score-item">응축<br><span class="score-val {get_color(row['Squeeze'])}">{row['Squeeze']:.0f}</span></div><div class="score-item">추세<br><span class="score-val {get_color(row['Trend'])}">{row['Trend']:.0f}</span></div><div class="score-item">장세<br><span class="score-val {get_color(row['Regime'])}">{row['Regime']:.0f}</span></div><div class="score-item">수급<br><span class="score-val {get_color(row['Vol'])}">{row['Vol']:.0f}</span></div><div class="score-item">옵션<br><span class="score-val {get_color(row['Option'])}">{row['Option']:.0f}</span></div></div><div class="price-target-box"><div class="pt-item"><span class="pt-label">진입가</span><span class="pt-val pt-entry">${row['Price']:.2f}</span></div><div class="pt-item"><span class="pt-label">목표가</span><span class="pt-val pt-target">${row['Target']:.2f}</span></div><div class="pt-item"><span class="pt-label">손절가</span><span class="pt-val pt-stop">${row['Stop']:.2f}</span></div></div><div class="indicator-box">RSI: {row['RSI']:.0f} | PCR: {row['PCR']:.2f}<div class="opt-row"><span class="opt-call">Call: {int(row['CallVol']):,}</span><span class="opt-put">Put: {int(row['PutVol']):,}</span></div><div class="opt-bar-bg"><div class="opt-bar-c" style="width:{row['CallPct']}%;"></div><div class="opt-bar-p" style="width:{row['PutPct']}%;"></div></div></div><div style="display:flex; justify-content:space-between; align-items:center;"><div class="exit-box"><span class="{ex_hard}">칼손절: ${row['HardStop']:.2f}</span><br><span class="{ex_trail}">익절라인: ${row['TrailStop']:.2f}</span><br><span class="{ex_time}">유효기간: {row['TimeStop']}일</span></div><div style="text-align:right;"><span style="color:#888; font-size:10px;">권장 비중</span><br><span class="bet-badge bet-bg">{row['BetText']}</span></div></div></div>"""
            
            c1, c2 = st.columns([0.85, 0.15])
            with c2:
                if st.button(fav_icon, key=f"fav_{unique_id}"):
                    if is_fav: st.session_state.watchlist.remove(row['Ticker'])
                    else: st.session_state.watchlist.add(row['Ticker'])
                    st.rerun()
            
            st.markdown(html_content, unsafe_allow_html=True)
            st.plotly_chart(create_chart(row['History'], row['Ticker'], unique_id), use_container_width=True, key=f"chart_{unique_id}", config={'displayModeBar':False})

        if "추천" in mode or "인덱스" in mode:
            df = pd.DataFrame(market_data)
            t1, t2, t3 = st.tabs(["🚀 단타 (수급)", "🌊 스윙 (응축)", "🌲 장투 (추세)"])
            
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
                for i, row in enumerate(market_data):
                    render_card(row, f"list_{i}")