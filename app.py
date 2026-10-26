"""ALPHA EDGE — independent simulation dashboard. No live trading."""
import streamlit as st
from datetime import datetime, timezone

st.set_page_config(page_title='ALPHA EDGE | Trading Console', page_icon='◈', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
.stApp{background:#080f21;color:#edf3ff} [data-testid="stSidebar"]{background:#101c36;border-right:1px solid #304365}
.block-container{padding-top:1.2rem;max-width:1600px} h1,h2,h3{color:#f4f7ff!important;letter-spacing:.03em}
[data-testid="stMetric"]{background:#111e3b;border:1px solid #33496f;border-radius:12px;padding:16px}
.stButton>button{background:#233d6c;color:white;border:1px solid #6280b2;border-radius:8px;font-weight:700;width:100%}
.stButton>button:hover{background:#33558b;color:white} div[data-testid="stAlert"]{border-radius:10px}
</style>''',unsafe_allow_html=True)
if 'orders' not in st.session_state: st.session_state.orders=[]
if 'settings' not in st.session_state: st.session_state.settings={'limit':100.0,'max_contracts':10,'daily_loss':200.0,'notifications':True}
with st.sidebar:
    st.title('◈ ALPHA EDGE')
    st.caption('TRADING CONSOLE • DEMOSTRACIÓN')
    page=st.radio('NAVEGACIÓN',['Resumen','Radar','Operación','Entradas','Registro','Configuración'],label_visibility='collapsed')
    st.divider()
    st.success('MODO SIMULACIÓN',icon='✅')
    st.caption('No se envían órdenes a Kalshi ni se usan fondos reales.')
st.title(page.upper())
st.caption('ALPHA EDGE / BTC 15 MIN / PANEL DE DEMOSTRACIÓN')
if page=='Resumen':
    a,b,c,d=st.columns(4)
    a.metric('Modo','SIMULACIÓN');b.metric('Órdenes simuladas',len(st.session_state.orders));c.metric('Capital real utilizado','$0');d.metric('Motor','No conectado')
    st.info('Diseño de interfaz. El motor v4.6.1 todavía no está conectado a esta demo. No hay precios ni señales en vivo.')
    st.subheader('Módulos de plataforma')
    st.write('Radar de sesión · Operación · Entradas · Registro · Configuración')
elif page=='Radar':
    st.subheader('RADAR DE SESIÓN')
    st.warning('Esperando datos reales del motor. No se muestran lecturas inventadas.')
    st.progress(0,text='Sin fuente de mercado conectada')
    st.caption('Aquí se integrarán fuerza compradora/vendedora, dirección y confirmaciones del v4.6.1.')
elif page=='Operación':
    st.subheader('CONTROL DE OPERACIÓN · SIMULADOR')
    left,right=st.columns([2,1])
    with left:
        with st.form('order'):
            direction=st.segmented_control('Dirección',options=['UP','DOWN'],default='UP')
            price=st.number_input('Precio simulado por contrato ($)',min_value=0.01,max_value=0.99,value=0.50,step=0.01)
            qty=st.number_input('Contratos',min_value=1,max_value=int(st.session_state.settings['max_contracts']),value=1)
            cost=round(price*qty,2)
            st.write(f'Costo estimado simulado: **${cost:.2f}**')
            submitted=st.form_submit_button('REGISTRAR ORDEN SIMULADA')
        if submitted:
            if cost>st.session_state.settings['limit']: st.error('Supera el límite configurado por operación.')
            else:
                st.session_state.orders.append({'UTC':datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),'Dirección':direction,'Contratos':qty,'Precio':price,'Costo':cost,'Estado':'SIMULADA'})
                st.success('Orden simulada registrada. No se envió ninguna compra.')
    with right:
        st.subheader('Protección')
        st.metric('Máximo por orden',f"${st.session_state.settings['limit']:.2f}")
        st.metric('Máximo contratos',st.session_state.settings['max_contracts'])
        st.metric('Límite pérdida diaria',f"${st.session_state.settings['daily_loss']:.2f}")
        st.caption('Estos límites funcionan en el simulador; no controlan una cuenta real.')
elif page in ['Entradas','Registro']:
    st.subheader('HISTORIAL DE SIMULACIÓN')
    if st.session_state.orders: st.dataframe(st.session_state.orders,use_container_width=True,hide_index=True)
    else: st.info('Todavía no hay operaciones simuladas.')
elif page=='Configuración':
    st.subheader('AJUSTES DE SIMULACIÓN')
    with st.form('settings'):
        limit=st.number_input('Límite por orden ($)',min_value=1.0,value=float(st.session_state.settings['limit']))
        max_contracts=st.number_input('Máximo de contratos',min_value=1,max_value=10000,value=int(st.session_state.settings['max_contracts']))
        daily_loss=st.number_input('Límite de pérdida diaria ($)',min_value=1.0,value=float(st.session_state.settings['daily_loss']))
        notifications=st.toggle('Notificaciones visuales',value=st.session_state.settings['notifications'])
        if st.form_submit_button('GUARDAR AJUSTES'):
            st.session_state.settings=dict(limit=limit,max_contracts=max_contracts,daily_loss=daily_loss,notifications=notifications)
            st.success('Ajustes guardados para esta sesión.')
    st.caption('En producción, los ajustes deberán guardarse en base de datos por usuario y validarse en el servidor.')
