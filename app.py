import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
import time

# Configuración de página
st.set_page_config(
    page_title="JC ALPHA EDGE - BTC SIGNAL",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS personalizados para replicar el diseño Neón/Futurista
st.markdown("""
<style>
    .stApp {
        background-color: #030816;
        color: #e2e8f0;
        font-family: 'Segoe UI', Roboto, sans-serif;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .neon-card {
        background: linear-gradient(135deg, #071228 0%, #030a1c 100%);
        border: 1px solid #1e3a8a;
        box-shadow: 0 0 12px rgba(14, 165, 233, 0.15);
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
    }

    .header-title {
        text-align: center;
        color: #38bdf8;
        font-weight: 800;
        font-size: 24px;
        text-shadow: 0 0 10px rgba(56, 189, 248, 0.5);
        margin-bottom: 2px;
    }
    .header-sub {
        text-align: center;
        color: #0284c7;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 1px;
    }

    .signal-card {
        background: radial-gradient(circle, #1a050d 0%, #071228 100%);
        border: 1.5px solid #ef4444;
        box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
        border-radius: 12px;
        padding: 15px;
        text-align: center;
    }
    .signal-title {
        color: #ef4444;
        font-size: 42px;
        font-weight: 900;
        margin: -10px 0;
        text-shadow: 0 0 15px rgba(239, 68, 68, 0.6);
    }
    .badge-support {
        background-color: #991b1b;
        color: #fecaca;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: bold;
        display: inline-block;
    }

    .metric-box {
        background-color: #0b1938;
        border: 1px solid #1d4ed8;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
    }
    .metric-title {
        color: #64748b;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
    }
    .metric-val {
        color: #ffffff;
        font-size: 18px;
        font-weight: 800;
    }

    .ind-pill {
        background: #0d2149;
        border: 1px solid #1e40af;
        border-radius: 15px;
        padding: 4px 10px;
        font-size: 11px;
        color: #38bdf8;
        display: inline-block;
        margin: 2px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# ZONA DE CONEXIÓN CON LAS FUNCIONES DE TU BOT
# ---------------------------------------------------------
def obtener_datos_bot_en_tiempo_real():
    """
    Aquí es donde debes integrar o llamar las funciones actuales de tu bot
    que obtienen los precios, señales, porcentajes de motor y estados.
    """
    # Ejemplo de estructura de datos que tu bot debería devolver:
    return {
        "senal": "DOWN", # o "UP"
        "apoyo_motor": 64,
        "presignal": "POSIBLE DOWN",
        "coincidencia": 93,
        "btc_usd": 76637.00,
        "variacion": -0.15,
        "target": 76739.00,
        "distancia": 102.00,
        "tiempo_restante": "10:42",
        "up_pct": 36,
        "down_pct": 64,
        "lector_cierre_pct": 73,
        "movimiento_segundos": {"30s": "-", "10s": "-3", "5s": "-2"}
    }

# Cargamos los datos del bot
datos_bot = obtener_datos_bot_en_tiempo_real()

# ---------------------------------------------------------
# CABECERA
# ---------------------------------------------------------
col_h1, col_h2, col_h3 = st.columns([1, 4, 1])
with col_h2:
    st.markdown('<div class="header-title">👑 JC ALPHA EDGE</div>', unsafe_allow_html=True)
    st.markdown('<div class="header-sub">BTC SIGNAL v4.6.1</div>', unsafe_allow_html=True)
with col_h3:
    st.markdown("<p style='text-align: right; color: #10b981; font-size: 12px;'>🟢 Mercado en vivo</p>", unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------
# SECCIÓN SUPERIOR: SEÑAL OFICIAL Y ESTADO ACTUAL
# ---------------------------------------------------------
col_s1, col_s2 = st.columns([1, 1])

with col_s1:
    st.markdown(f"""
    <div class="signal-card">
        <span style="color: #94a3b8; font-size: 10px; font-weight: bold;">SEÑAL OFICIAL DEL BOT</span>
        <div class="signal-title">⬇ {datos_bot['senal']}</div>
        <div class="badge-support">APOYO DEL MOTOR {datos_bot['apoyo_motor']}%</div>
    </div>
    """, unsafe_allow_html=True)

with col_s2:
    st.markdown("""
    <div class="neon-card" style="height: 100%;">
        <span style="color: #64748b; font-size: 10px; font-weight: bold;">ESTADO ACTUAL</span>
        <h4 style="color: #38bdf8; margin: 5px 0;">OPERACIÓN ACTIVA</h4>
        <p style="color: #94a3b8; font-size: 12px; margin: 0;">Analizando el mercado en tiempo real para el mejor punto de entrada.</p>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# PRESÉÑAL / PRESIÓN ACTUAL
# ---------------------------------------------------------
st.markdown(f"""
<div class="neon-card">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="color: #ef4444; font-weight: bold; font-size: 13px;">PRESÉÑAL - PRESIÓN ACTUAL: {datos_bot['presignal']}</span>
        <span style="color: #ef4444; font-weight: bold; font-size: 16px;">{datos_bot['coincidencia']}%</span>
    </div>
    <p style="color: #64748b; font-size: 11px; margin: 3px 0 8px 0;">Presión bajista temprana detectada. Esperando evolución del mercado.</p>
</div>
""", unsafe_allow_html=True)
st.progress(datos_bot['coincidencia'] / 100.0)

# ---------------------------------------------------------
# MÉTRICAS CLAVE
# ---------------------------------------------------------
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-title">BTC / USD</div>
        <div class="metric-val">${datos_bot['btc_usd']:,.2f}</div>
        <span style="color: #ef4444; font-size: 11px;">{datos_bot['variacion']}%</span>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-title">TARGET</div>
        <div class="metric-val">${datos_bot['target']:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-title">DISTANCIA AL TARGET</div>
        <div class="metric-val" style="color: #ef4444;">${datos_bot['distancia']:,.2f}</div>
        <span style="color: #ef4444; font-size: 11px;">0.13%</span>
    </div>
    """, unsafe_allow_html=True)

with m4:
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-title">TIEMPO RESTANTE</div>
        <div class="metric-val" style="color: #38bdf8;">{datos_bot['tiempo_restante']}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# ---------------------------------------------------------
# APOYO CALCULADO
# ---------------------------------------------------------
st.markdown("<span style='font-size: 11px; color: #94a3b8;'>APOYO CALCULADO - UP / DOWN</span>", unsafe_allow_html=True)
col_u, col_d = st.columns([datos_bot['up_pct'], datos_bot['down_pct']])
with col_u:
    st.markdown(f"<div style='background-color: #10b981; text-align: center; color: white; font-size: 11px; border-radius: 4px; padding: 2px;'>UP {datos_bot['up_pct']}%</div>", unsafe_allow_html=True)
with col_d:
    st.markdown(f"<div style='background-color: #ef4444; text-align: center; color: white; font-size: 11px; border-radius: 4px; padding: 2px;'>DOWN {datos_bot['down_pct']}%</div>", unsafe_allow_html=True)

st.write("")

# ---------------------------------------------------------
# LECTOR DE CIERRE Y MOVIMIENTO
# ---------------------------------------------------------
col_lc1, col_lc2 = st.columns(2)

with col_lc1:
    st.markdown(f"""
    <div class="neon-card">
        <span style="color: #38bdf8; font-size: 11px; font-weight: bold;">LECTOR DE CIERRE &nbsp; <span style="background: #065f46; color: #34d399; padding: 2px 6px; border-radius: 8px; font-size: 9px;">ACTIVO</span></span>
        <div style="display: flex; align-items: center; margin-top: 8px;">
            <div style="border: 3px solid #ef4444; border-radius: 50%; width: 45px; height: 45px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px; color: white; margin-right: 12px;">{datos_bot['lector_cierre_pct']}%</div>
            <div>
                <strong style="color: white; font-size: 13px;">VENTAJA MODERADA PARA DOWN</strong><br>
                <span style="color: #64748b; font-size: 10px;">La dirección sigue activa, pero la presión inmediata aún puede cambiar.</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_lc2:
    mov = datos_bot['movimiento_segundos']
    st.markdown(f"""
    <div class="neon-card">
        <span style="color: #38bdf8; font-size: 11px; font-weight: bold;">MOVIMIENTO ÚLTIMOS SEGUNDOS</span>
        <div style="display: flex; justify-content: space-around; text-align: center; margin-top: 10px;">
            <div><span style="color: #64748b; font-size: 10px;">30s</span><br><strong style="color: white;">{mov['30s']}</strong></div>
            <div><span style="color: #64748b; font-size: 10px;">10s</span><br><strong style="color: #ef4444;">{mov['10s']}</strong></div>
            <div><span style="color: #64748b; font-size: 10px;">5s</span><br><strong style="color: #ef4444;">{mov['5s']}</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# GRÁFICO DE VELAS
# ---------------------------------------------------------
st.markdown("<span style='font-size: 12px; color: #38bdf8; font-weight: bold;'>₿ BTC / USD · 1M · KRAKEN</span>", unsafe_allow_html=True)

df = pd.DataFrame({
    'time': [datetime.now() - timedelta(minutes=i) for i in range(20, 0, -1)],
    'open': [76600, 76580, 76590, 76610, 76600, 76630, 76620, 76640, 76650, 76630, 76660, 76680, 76670, 76690, 76710, 76700, 76680, 76660, 76650, 76637],
    'high': [76610, 76600, 76620, 76630, 76640, 76650, 76640, 76670, 76680, 76660, 76690, 76710, 76700, 76720, 76730, 76710, 76690, 76670, 76660, 76645],
    'low':  [76580, 76560, 76570, 76590, 76580, 76610, 76600, 76630, 76630, 76610, 76650, 76660, 76650, 76670, 76680, 76670, 76650, 76630, 76620, 76620],
    'close': [76580, 76590, 76610, 76600, 76630, 76620, 76640, 76650, 76630, 76660, 76680, 76670, 76690, 76710, 76700, 76680, 76660, 76650, 76637, 76637]
})

fig = go.Figure(data=[go.Candlestick(
    x=df['time'],
    open=df['open'], high=df['high'],
    low=df['low'], close=df['close'],
    increasing_line_color='#10b981', 
    decreasing_line_color='#ef4444'
)])

fig.update_layout(
    template='plotly_dark',
    paper_bgcolor='#030a1c',
    plot_bgcolor='#030a1c',
    margin=dict(l=10, r=10, t=10, b=10),
    height=300,
    xaxis_rangeslider_visible=False
)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# INDICADORES Y RSI
# ---------------------------------------------------------
col_ind, col_rsi = st.columns([1, 1])

with col_ind:
    st.markdown("<span style='font-size: 11px; color: #64748b;'>INDICADORES</span>", unsafe_allow_html=True)
    st.markdown("""
    <div>
        <span class="ind-pill">EMA9 <b style="color: #10b981;">ON</b></span>
        <span class="ind-pill">EMA21 <b style="color: #10b981;">ON</b></span>
        <span class="ind-pill">VWAP <b style="color: #10b981;">ON</b></span>
        <br>
        <span class="ind-pill">VOLUME <b style="color: #10b981;">ON</b></span>
        <span class="ind-pill">RSI <b style="color: #10b981;">ON</b></span>
    </div>
    """, unsafe_allow_html=True)

with col_rsi:
    st.markdown("<span style='font-size: 11px; color: #64748b;'>RSI 14</span>", unsafe_allow_html=True)
    fig_rsi = go.Figure(data=[go.Scatter(
        x=df['time'], y=[45, 48, 52, 50, 58, 55, 60, 62, 58, 65, 70, 64, 68, 72, 65, 58, 52, 49, 51, 50.73],
        mode='lines',
        line=dict(color='#c084fc', width=2)
    )])
    fig_rsi.update_layout(
        template='plotly_dark',
        paper_bgcolor='#030a1c',
        plot_bgcolor='#030a1c',
        margin=dict(l=5, r=5, t=5, b=5),
        height=90,
        xaxis_visible=False,
        yaxis=dict(range=[20, 80])
    )
    st.plotly_chart(fig_rsi, use_container_width=True)

# ---------------------------------------------------------
# TABLA DE OPERACIONES RECIENTES (Conectable a tu base de datos o registro)
# ---------------------------------------------------------
st.markdown("<span style='font-size: 12px; color: #38bdf8; font-weight: bold;'>⚡ OPERACIONES RECIENTES (ÚLTIMAS 5)</span>", unsafe_allow_html=True)

history_data = [
    {"#": 895, "HORA": "6:20 PM", "PAR": "BTC 15M", "SEÑAL": "🔻 DOWN", "OBJETIVO": "$76,701.15", "RESULTADO": "PENDIENTE", "P/L": "-"},
    {"#": 894, "HORA": "6:05 PM", "PAR": "BTC 15M", "SEÑAL": "🔺 UP", "OBJETIVO": "$76,689.40", "RESULTADO": "GANADA", "P/L": "+$9.20"},
    {"#": 893, "HORA": "5:50 PM", "PAR": "BTC 15M", "SEÑAL": "🔻 DOWN", "OBJETIVO": "$76,728.10", "RESULTADO": "PERDIDA", "P/L": "-$10.00"},
    {"#": 892, "HORA": "5:35 PM", "PAR": "BTC 15M", "SEÑAL": "🔺 UP", "OBJETIVO": "$76,612.85", "RESULTADO": "GANADA", "P/L": "+$8.50"},
    {"#": 891, "HORA": "5:20 PM", "PAR": "BTC 15M", "SEÑAL": "🔻 DOWN", "OBJETIVO": "$76,745.30", "RESULTADO": "PERDIDA", "P/L": "-$10.00"}
]

df_hist = pd.DataFrame(history_data)
st.dataframe(df_hist, use_container_width=True, hide_index=True)

# Opcional: Refresco automático de la app para simular tiempo real
if st.checkbox("Activar actualización automática en vivo"):
    time.sleep(5)
    st.rerun()
