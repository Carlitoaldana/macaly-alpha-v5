import json
import time
from datetime import datetime, timezone
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from alpha_poly5_engine import Engine

st.set_page_config(page_title='ALPHA · POLYMARKET BTC 5M',page_icon='⚡',layout='centered')
st.title('ALPHA · POLYMARKET BTC 5M')
st.caption('Solo señales · sin operaciones automáticas · motor experimental independiente')
S=requests.Session()
S.headers.update({'User-Agent':'AlphaPoly5Research/1.0'})
@st.cache_data(ttl=2,show_spinner=False)
def market_for(epoch):
    r=S.get('https://gamma-api.polymarket.com/markets',params={'slug':f'btc-updown-5m-{epoch}'},timeout=5)
    r.raise_for_status()
    data=r.json()
    return data[0] if data else None

def get_market():
    now=int(time.time())
    epoch=now-now%300
    m=market_for(epoch)
    if not m or m.get('closed') or m.get('active') is False:
        raise RuntimeError('No se pudo verificar el mercado de esta ronda de 5 minutos')
    return epoch,m

def btc_price():
    r=S.get('https://api.exchange.coinbase.com/products/BTC-USD/ticker',timeout=5)
    r.raise_for_status()
    return float(r.json()['price'])

@st.cache_resource
def engine():return Engine()

@st.fragment(run_every='1s')
def dashboard():
    try:
        epoch,m=get_market()
        e=engine()
        e.reset(str(epoch))
        price=btc_price()
        e.ingest(price)
        signal=e.evaluate()
        left=max(0,epoch+300-int(time.time()))
        a,b,c=st.columns(3)
        a.metric('BTC · Coinbase',f'${price:,.2f}')
        b.metric('Tiempo',f'{left//60}:{left%60:02d}')
        c.metric('Señal',signal.direction)
        st.metric('Preseñal independiente',signal.presignal)
        st.progress(min(1.,signal.strength/100),text=f'Fuerza indicativa {signal.strength:.0f}%')
        st.caption(signal.reason)
        st.caption('La fuerza no es una probabilidad de ganar. Coinbase no es el oráculo de resolución de Polymarket.')
        st.markdown(f'[Abrir mercado de la ronda](https://polymarket.com/event/btc-updown-5m-{epoch})')
        outcomes=m.get('outcomes',[])
        odds=m.get('outcomePrices',[])
        if isinstance(outcomes,str): outcomes=json.loads(outcomes)
        if isinstance(odds,str): odds=json.loads(odds)
        st.caption('Cotizaciones indicativas publicadas: '+', '.join(f'{x}: {y}' for x,y in zip(outcomes,odds)))
        tabs=st.tabs(['5 segundos','15 segundos','30 segundos'])
        for tab,sec in zip(tabs,(5,15,30)):
            with tab:
                bars=e.candles(sec)
                if bars:
                    d=pd.DataFrame(bars)
                    fig=go.Figure(go.Candlestick(x=d.time,open=d.open,high=d.high,low=d.low,close=d.close))
                    fig.update_layout(height=320,xaxis_rangeslider_visible=False,margin=dict(l=5,r=5,t=10,b=5))
                    st.plotly_chart(fig,use_container_width=True,key=f'candle_{sec}')
                else:st.info('Esperando lecturas')
        st.caption('Actualización solicitada cada segundo; la frecuencia real depende de las API, red y servidor. El historial empieza al abrir la app.')
    except Exception as ex:
        st.error(f'Sin datos verificados: {ex}. Señales suspendidas.')

dashboard()
