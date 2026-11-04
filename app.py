import streamlit as st
import requests
import datetime

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="JC ALPHA EDGE - BTC SIGNAL v4.6.1",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------
# ESTILOS CSS - INTERFAZ NEÓN CYBERPUNK EXACTA
# ---------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Roboto:wght@300;400;700&display=swap');

    .stApp {
        background-color: #020617;
        color: #FFFFFF;
        font-family: 'Roboto', sans-serif;
    }

    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}

    .block-container {
        padding-top: 0.8rem;
        padding-bottom: 2rem;
        max-width: 450px;
    }

    /* ENCABEZADO */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(217, 119, 6, 0.4);
        border-radius: 14px;
        padding: 8px 10px;
        margin-bottom: 12px;
    }

    .profile-section {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .profile-avatar {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: linear-gradient(135deg, #F59E0B, #B45309);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        border: 1px solid #F59E0B;
    }

    .profile-text .title {
        font-family: 'Orbitron', sans-serif;
        font-size: 10px;
        font-weight: 900;
        color: #F59E0B;
        letter-spacing: 0.5px;
        line-height: 1.1;
    }

    .center-title-box {
        text-align: center;
    }

    .center-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 12px;
        font-weight: 900;
        color: #FFFFFF;
        letter-spacing: 0.8px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
    }

    .center-version {
        font-size: 9px;
        color: #9CA3AF;
        font-family: 'Orbitron', sans-serif;
    }

    .live-badge {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid #10B981;
        color: #10B981;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 9px;
        font-weight: bold;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .live-dot {
        width: 6px;
        height: 6px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 6px #10B981;
    }

    /* SEÑAL PRINCIPAL UP */
    .main-signal-box {
        background: linear-gradient(180deg, rgba(6, 78, 59, 0.5) 0%, rgba(3, 7, 18, 0.9) 100%);
        border: 2px solid #00FF88;
        box-shadow: 0 0 18px rgba(0, 255, 136, 0.3);
        border-radius: 16px;
        text-align: center;
        padding: 12px 8px 10px 8px;
        margin-bottom: 12px;
    }

    .signal-arrow {
        font-size: 44px;
        color: #00FF88;
        line-height: 1;
        text-shadow: 0 0 12px #00FF88;
    }

    .signal-text {
        font-family: 'Orbitron', sans-serif;
        font-size: 40px;
        font-weight: 900;
        color: #00FF88;
        letter-spacing: 2px;
        text-shadow: 0 0 15px #00FF88;
        margin-bottom: 6px;
    }

    .engine-banner {
        background: linear-gradient(90deg, transparent, rgba(0, 255, 136, 0.25), transparent);
        border-top: 1px solid #00FF88;
        border-bottom: 1px solid #00FF88;
        color: #00FF88;
        font-family: 'Orbitron', sans-serif;
        font-size: 11px;
        font-weight: bold;
        padding: 4px 0;
        letter-spacing: 1px;
    }

    /* TARJETAS DE MÉTRICAS */
    .metric-card {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(217, 119, 6, 0.5);
        box-shadow: 0 0 8px rgba(217, 119, 6, 0.2);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 8px;
        min-height: 72px;
    }

    .metric-card-standard {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(51, 65, 85, 0.8);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 8px;
        min-height: 72px;
    }

    .card-label {
        font-size: 9px;
        color: #9CA3AF;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    .card-value {
        font-family: 'Orbitron', sans-serif;
        font-size: 17px;
        font-weight: 700;
        color: #FFFFFF;
        margin-top: 2px;
    }

    .card-subtext-green {
        font-size: 10px;
        color: #00FF88;
        font-weight: bold;
    }

    /* BARRA DE PROGRESO */
    .progress-box {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid #1E293B;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 12px;
    }

    .progress-title {
        font-size: 10px;
        font-weight: bold;
        color: #E2E8F0;
        margin-bottom: 6px;
        letter-spacing: 0.5px;
    }

    .custom-progress-container {
        height: 10px;
        width: 100%;
        background-color: #EF4444;
        border-radius: 5px;
        overflow: hidden;
        display: flex;
    }

    .progress-fill-up {
        height: 100%;
        background: linear-gradient(90deg, #10B981, #00FF88);
        width: 75%;
        box-shadow: 0 0 6px #00FF88;
    }

    .progress-footer {
        display: flex;
        justify-content: space-between;
        font-size: 10px;
        font-weight: bold;
        margin-top: 5px;
    }

    /* LECTOR DE CIERRE */
    .closure-card {
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid #00FF88;
        box-shadow: 0 0 12px rgba(0, 255, 136, 0.2);
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 12px;
    }

    .closure-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }

    .closure-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 11px;
        font-weight: bold;
        color: #FFFFFF;
        font-style: italic;
    }

    .closure-active-badge {
        background: rgba(16, 185, 129, 0.2);
        color: #00FF88;
        border: 1px solid #00FF88;
        padding: 2px 6px;
        border-radius: 8px;
        font-size: 9px;
        font-weight: bold;
    }

    .closure-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .closure-sub-signal {
        border: 1px solid #00FF88;
        border-radius: 8px;
        padding: 6px;
        text-align: center;
        width: 38%;
        background: rgba(0, 255, 136, 0.05);
    }

    .closure-ring {
        width: 65px;
        height: 65px;
        border-radius: 50%;
        border: 5px solid #00FF88;
        border-top: 5px solid #1E293B;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Orbitron', sans-serif;
        font-size: 16px;
        font-weight: 900;
        color: #FFFFFF;
        box-shadow: 0 0 10px rgba(0, 255, 136, 0.3);
    }

    .mini-candles {
        display: flex;
        align-items: flex-end;
        gap: 3px;
        height: 45px;
        padding: 0 4px;
    }

    .candle {
        width: 6px;
        border-radius: 2px;
    }

    /* MOVIMIENTO ÚLTIMOS SEGUNDOS */
    .seconds-box {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid #1E293B;
        border-radius: 10px;
        padding: 8px;
        margin-bottom: 12px;
    }

    .seconds-title {
        text-align: center;
        font-size: 9px;
        font-weight: bold;
        color: #9CA3AF;
        letter-spacing: 0.8px;
        margin-bottom: 6px;
    }

    .seconds-grid {
        display: flex;
        justify-content: space-around;
        text-align: center;
    }

    .sec-label {
        font-size: 10px;
        color: #9CA3AF;
    }

    .sec-val {
        font-family: 'Orbitron', sans-serif;
        font-size: 12px;
        font-weight: bold;
        color: #00FF88;
    }

    .green-text { color: #00FF88 !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# LÓGICA DE DATOS
# ---------------------------------------------------------
@st.cache_data(ttl=5)
def get_live_metrics():
    try:
        res = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=2)
        btc_val = float(res.json()['price'])
    except:
        btc_val = 77763.00

    return {
        "btc_price": f"${btc_val:,.0f}",
        "target": "$77,726",
        "distance": "+$37",
        "percent": "+0.07%",
        "timer": "12:00",
        "support_pct": 75,
        "closure_pct": 62,
        "sec_30": "+$28",
        "sec_10": "+$12",
        "sec_5": "+$6",
        "velocity": "ESTABLE",
        "position": "POSICIÓN ACTUAL UP"
    }

data = get_live_metrics()

# ---------------------------------------------------------
# RENDERIZADO VISUAL DE LA APP
# ---------------------------------------------------------

# 1. Encabezado
st.markdown("""
<div class="header-container">
    <div class="profile-section">
        <div class="profile-avatar">👤</div>
        <div class="profile-text">
            <div class="title">JC</div>
            <div class="title">ALPHA EDGE</div>
        </div>
    </div>
    <div class="center-title-box">
        <div class="center-title">🪙 BTC SIGNAL</div>
        <div class="center-version">v4.6.1</div>
    </div>
    <div class="live-badge">
        <div class="live-dot"></div>
        Mercado en vivo
    </div>
</div>
""", unsafe_allow_html=True)

# 2. Señal Principal UP
st.markdown(f"""
<div class="main-signal-box">
    <div class="signal-arrow">▲</div>
    <div class="signal-text">UP</div>
    <div class="engine-banner">APOYO DEL MOTOR {data['support_pct']}%</div>
</div>
""", unsafe_allow_html=True)

# 3. Fila 1: BTC y Target
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-label">🪙 BTC</div>
        <div class="card-value">{data['btc_price']}</div>
        <div class="card-subtext-green">{data['percent']}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-label">🎯 TARGET</div>
        <div class="card-value">{data['target']}</div>
    </div>
    """, unsafe_allow_html=True)

# 4. Fila 2: Distancia y Tiempo
col3, col4 = st.columns(2)
with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-label">📊 DISTANCIA AL TARGET</div>
        <div class="card-value green-text">{data['distance']}</div>
        <div class="card-subtext-green">+0.05%</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class="metric-card-standard">
        <div class="card-label">⏱️ TIEMPO RESTANTE</div>
        <div class="card-value">{data['timer']}</div>
    </div>
    """, unsafe_allow_html=True)

# 5. Barra de Progreso
st.markdown(f"""
<div class="progress-box">
    <div class="progress-title">APOYO CALCULADO · UP / DOWN</div>
    <div class="custom-progress-container">
        <div class="progress-fill-up" style="width: {data['support_pct']}%;"></div>
    </div>
    <div class="progress-footer">
        <span class="green-text">▲ UP {data['support_pct']}%</span>
        <span style="color:#EF4444;">▼ DOWN {100 - data['support_pct']}%</span>
    </div>
</div>
""", unsafe_allow_html=True)

# 6. Lector de Cierre
st.markdown(f"""
<div class="closure-card">
    <div class="closure-top">
        <div class="closure-title">🎯 LECTOR DE CIERRE</div>
        <div class="closure-active-badge">● ACTIVO</div>
    </div>
    <div class="closure-content">
        <div class="closure-sub-signal">
            <div style="font-size:9px; color:#9CA3AF; margin-bottom:2px;">SEÑAL DE CIERRE</div>
            <div style="font-size:18px; color:#00FF88; font-weight:900; font-family:'Orbitron';">︽ UP</div>
        </div>
        <div class="closure-ring">{data['closure_pct']}%</div>
        <div class="mini-candles">
            <div class="candle" style="height: 15px; background: #EF4444;"></div>
            <div class="candle" style="height: 25px; background: #EF4444;"></div>
            <div class="candle" style="height: 20px; background: #10B981;"></div>
            <div class="candle" style="height: 35px; background: #10B981;"></div>
            <div class="candle" style="height: 42px; background: #10B981;"></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 7. Movimiento Últimos Segundos
st.markdown(f"""
<div class="seconds-box">
    <div class="seconds-title">MOVIMIENTO ÚLTIMOS SEGUNDOS</div>
    <div class="seconds-grid">
        <div>
            <div class="sec-label">30s</div>
            <div class="sec-val">{data['sec_30']} 📈</div>
        </div>
        <div>
            <div class="sec-label">10s</div>
            <div class="sec-val">{data['sec_10']} 📈</div>
        </div>
        <div>
            <div class="sec-label">5s</div>
            <div class="sec-val">{data['sec_5']} 📈</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 8. Tarjetas Inferiores
b_col1, b_col2 = st.columns(2)
with b_col1:
    st.markdown(f"""
    <div class="metric-card-standard">
        <div class="card-label">🎯 DISTANCIA AL TARGET</div>
        <div style="font-family:'Orbitron'; font-size:15px; font-weight:bold;" class="green-text">{data['distance']} <span style="font-size:9px;">+0.05%</span></div>
    </div>
    <div class="metric-card-standard">
        <div class="card-label">🥞 POSICIÓN ACTUAL</div>
        <div style="font-family:'Orbitron'; font-size:10px; font-weight:bold;" class="green-text">{data['position']}</div>
    </div>
    """, unsafe_allow_html=True)
with b_col2:
    st.markdown(f"""
    <div class="metric-card-standard">
        <div class="card-label">⏱️ VELOCIDAD</div>
        <div style="font-family:'Orbitron'; font-size:14px; font-weight:bold;" class="green-text">{data['velocity']} <span style="font-size:9px; color:#9CA3AF;">-0.1/s</span></div>
    </div>
    <div class="metric-card-standard">
        <div class="card-label">︽ APOYO A UP</div>
        <div style="font-family:'Orbitron'; font-size:16px; font-weight:900;" class="green-text">{data['closure_pct']}%</div>
    </div>
    """, unsafe_allow_html=True)
