"""Alpha Lab: experimental historical-analogue signals. No order execution."""
import math
import bisect
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests
import streamlit as st

"""Round-labelled analogue candidate. Research signals only; no execution."""
import math
import numpy as np
import pandas as pd

def context_features(candles, price, target, seconds):
    x=candles.sort_values('time').tail(300)
    p=x.close.to_numpy(dtype=float)
    if len(p)<40:raise ValueError('Contexto insuficiente')
    r=np.diff(np.log(p));sigma=float(np.std(r[-20:],ddof=1))
    if not math.isfinite(sigma) or sigma<=0:raise ValueError('Volatilidad inválida')
    travel=float(np.abs(r[-10:]).sum())
    f=[np.log(p[-1]/p[-4])/(sigma*np.sqrt(3)),np.log(p[-1]/p[-11])/(sigma*np.sqrt(10)),np.log(p[-1]/p[-11])/max(travel,1e-12),np.log1p(float(x.volume.iloc[-1])/max(float(x.volume.tail(30).median()),1e-8)),math.log(sigma),math.log(price/target)/(sigma*math.sqrt(max(seconds,60)/60))]
    return np.asarray(f,dtype=float)

def predict_round(samples,query):
    """Samples contain only earlier completed rounds at the same elapsed time."""
    if len(samples)<40:return {'direction':None,'reason':'Menos de 40 rondas anteriores completas','n':len(samples)}
    matrix=np.asarray([s['features'] for s in samples],dtype=float)
    scale=np.maximum(np.percentile(matrix,75,axis=0)-np.percentile(matrix,25,axis=0),1e-6)
    distance=np.sqrt(np.mean(((matrix-query)/scale)**2,axis=1))
    k=min(40,max(12,int(2*math.sqrt(len(samples)))))
    selected=np.argsort(distance)[:k]
    weights=1/(.25+distance[selected]);weights/=weights.sum()
    up=float(np.dot(weights,np.asarray([s['up'] for s in samples])[selected]))
    effective=float(1/np.sum(weights**2));support=max(up,1-up)
    # A conservative sampling screen, not a calibrated confidence interval:
    # weighted neighbours and market rounds may be dependent.
    z=1.96;lower=(support+z*z/(2*effective)-z*math.sqrt(support*(1-support)/effective+z*z/(4*effective*effective)))/(1+z*z/effective)
    direction='UP' if up>=.65 else 'DOWN' if up<=.35 else None
    if effective<10 or float(np.median(distance[selected]))>2 or lower<=.5:direction=None
    return {'direction':direction,'up':up,'n':k,'available':len(samples),'effective':effective,'support_lower_screen':lower,'reason':'Candidato' if direction else 'Evidencia insuficiente'}

class Confirmation:
    def __init__(self):self.direction=None;self.count=0;self.last_minute=None;self.first=None
    def update(self,candidate,minute,timestamp,seconds):
        if minute==self.last_minute:return self.first
        self.last_minute=minute
        if not candidate or seconds<=60:self.direction=None;self.count=0;return self.first
        if candidate==self.direction:self.count+=1
        else:self.direction=candidate;self.count=1
        if self.count>=3 and self.first is None:self.first={'direction':candidate,'time_utc':timestamp,'seconds_left':seconds}
        return self.first


st.set_page_config(page_title='Alpha Lab · Señales', layout='wide')
API='https://external-api.kalshi.com/trade-api/v2'
COIN='https://api.exchange.coinbase.com'
HEADERS={'User-Agent':'AlphaLab/0.1','Accept':'application/json'}

def get_json(url, params=None):
    r=requests.get(url,params=params,headers=HEADERS,timeout=12)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=900,show_spinner=False)
def history():
    # Fixed completed UTC-hour anchor makes the sample reproducible during a session.
    end=pd.Timestamp.now(tz='UTC').floor('h')
    chunks=[]
    for block in range(7):
        stop=end-pd.Timedelta(hours=4*block)
        start=stop-pd.Timedelta(hours=4)
        rows=get_json(COIN+'/products/BTC-USD/candles',{
            'granularity':60,'start':start.isoformat(),'end':stop.isoformat()})
        if not isinstance(rows,list):
            raise ValueError('Respuesta de velas no válida.')
        chunks.extend(rows)
    x=pd.DataFrame(chunks,columns=['time','low','high','open','close','volume'])
    x['time']=pd.to_datetime(x['time'],unit='s',utc=True)
    for c in ['low','high','open','close','volume']:
        x[c]=pd.to_numeric(x[c],errors='coerce')
    return x.dropna().drop_duplicates('time').sort_values('time').reset_index(drop=True)

@st.cache_data(ttl=10,show_spinner=False)
def recent():
    rows=get_json(COIN+'/products/BTC-USD/candles',{'granularity':60})
    x=pd.DataFrame(rows,columns=['time','low','high','open','close','volume'])
    x['time']=pd.to_datetime(x['time'],unit='s',utc=True)
    for c in ['low','high','open','close','volume']:
        x[c]=pd.to_numeric(x[c],errors='coerce')
    # Do not treat unfinished candles as final historical observations.
    now=pd.Timestamp.now(tz='UTC')
    return x.dropna().drop_duplicates('time').sort_values('time').loc[lambda d:d.time+pd.Timedelta(minutes=1)<=now].reset_index(drop=True)

@st.cache_data(ttl=4,show_spinner=False)
def market():
    rows=get_json(API+'/markets',{'series_ticker':'KXBTC15M','status':'open','limit':100}).get('markets',[])
    now=pd.Timestamp.now(tz='UTC')
    valid=[m for m in rows if m.get('close_time') and pd.Timestamp(m['close_time'])>now]
    return min(valid,key=lambda m:pd.Timestamp(m['close_time'])) if valid else None

@st.cache_data(ttl=4,show_spinner=False)
def index_data(event):
    d=get_json(API+'/live_data/events/'+event,{'range':'15min'})
    live=d.get('live_data',{})
    rows=live.get('details',{}).get('timeseries',[])
    points=[]
    for r in rows:
        try:
            t=float(r['t'])/1000;v=float(r['v'])
            if math.isfinite(v) and v>0:
                points.append((t,v))
        except (KeyError,ValueError,TypeError):
            continue
    if not points:
        raise ValueError('Kalshi no entregó una serie con horas identificables.')
    points=sorted(dict(points).items())
    return points, bool(live.get('is_historical',False))

@st.cache_data(ttl=900,show_spinner=False)
def labelled_history():
    rows=get_json(API+'/markets',{'series_ticker':'KXBTC15M','status':'settled','limit':100}).get('markets',[])
    rows=sorted([m for m in rows if m.get('result') in ('yes','no') and m.get('floor_strike') is not None],key=lambda m:m['close_time'])[-80:]
    if len(rows)<40:
        raise ValueError('Faltan 40 rondas cerradas para el nuevo motor.')
    def fetch(m):
        d=get_json(API+'/live_data/events/'+m['event_ticker'],{'range':'1hour'})
        return m,d
    prices={}
    with ThreadPoolExecutor(max_workers=6) as pool:
        downloaded=list(pool.map(fetch,rows[::-4]))
    for m,d in sorted(downloaded,key=lambda pair:pair[0]['close_time']):
        for p in d.get('live_data',{}).get('details',{}).get('timeseries',[]):
            prices[int(p['t'])//1000]=float(p['v'])
    return rows,prices

def round_model(hist, live, price, target, seconds, close_time, labelled):
    rows,prices=labelled
    end=pd.Timestamp(close_time);start=end-pd.Timedelta(minutes=15)
    elapsed=max(0,min(839,900-int(seconds)))
    offset=(elapsed//60)*60
    samples=[]
    for m in rows:
        prior_end=pd.Timestamp(m['close_time'])
        if prior_end>start:
            continue
        stamp=prior_end-pd.Timedelta(minutes=15)+pd.Timedelta(seconds=offset)
        historical_price=prices.get(int(stamp.timestamp()))
        if historical_price is None:
            continue
        candles=hist[hist.time+pd.Timedelta(minutes=1)<=stamp].tail(300)
        if len(candles)<40 or not candles.time.diff().dropna().eq(pd.Timedelta(minutes=1)).all():
            continue
        samples.append({'features':context_features(candles,historical_price,float(m['floor_strike']),900-offset),'up':float(m['result']=='yes')})
    query=context_features(live,price,target,seconds)
    return predict_round(samples,query)

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
.stApp{background:#0a101b;color:#e5edf8;font-family:'DM Sans',sans-serif}
.block-container{max-width:1180px;padding:28px 28px 45px}
h1,h2,h3,p,[data-testid="stCaptionContainer"]{color:#dce6f3}
[data-testid="stSidebar"]{background:#101a29;border-right:1px solid #213048}
[data-testid="stSidebar"] *{color:#dce6f3}
#MainMenu,footer{visibility:hidden}
.brandrow{display:flex;align-items:center;justify-content:space-between;padding:0 0 24px;border-bottom:1px solid #243044}
.wordmark{font:800 22px Manrope,sans-serif;letter-spacing:4px;color:#f5f7fc}
.brandtag{font-size:10px;color:#8494ad;letter-spacing:2px;margin-top:5px}
.modepill{font-size:10px;color:#83cfc4;border:1px solid #2b4948;border-radius:30px;padding:8px 12px;letter-spacing:1px}
.signalstage{position:relative;padding:34px 0 28px;display:grid;grid-template-columns:1.4fr 1fr;gap:28px;align-items:center}
.eyebrow{font-size:10px;letter-spacing:2.5px;color:#8394af;text-transform:uppercase}
.signalword{font:800 clamp(44px,8vw,90px) Manrope,sans-serif;line-height:1.04;letter-spacing:-4px;margin:12px 0;color:var(--signal)}
.signaldesc{font-size:13px;line-height:1.6;color:#98aac3;max-width:470px}
.signalmark{font-size:12px;font-weight:600;color:var(--signal);letter-spacing:1px;margin-top:17px}
.contextstrip{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;border-top:1px solid #243044;border-bottom:1px solid #243044;padding:21px 0;margin-bottom:25px}
.contextvalue{font:600 24px Manrope,sans-serif;color:#edf3fd;margin-top:7px;letter-spacing:-.7px}
.contextnote{font-size:11px;color:#8fa3bc;margin-top:5px}
.balance{padding:24px 0 15px;border-bottom:1px solid #243044}
.balancehead{display:flex;justify-content:space-between;color:#b8c7dd;font-size:11px;letter-spacing:1px}
.balancebar{display:flex;gap:4px;height:9px;margin:15px 0;border-radius:10px;overflow:hidden}
.balancelabels{display:flex;justify-content:space-between;font:600 27px Manrope,sans-serif}
.scenario{display:flex;gap:20px;justify-content:space-between;padding:17px 0;color:#8da1bc;font-size:11px}
.scenario b{display:block;color:#dce7f6;font:500 17px Manrope,sans-serif;margin-top:7px}
.sessionline{border-top:1px solid #243044;padding-top:17px;margin-top:22px;display:flex;justify-content:space-between;gap:15px;font-size:11px;color:#8ca0bb;flex-wrap:wrap}
@media(max-width:650px){.block-container{padding:18px 17px 35px}.signalstage{grid-template-columns:1fr;gap:10px;padding-top:27px}.signalword{font-size:58px;letter-spacing:-3px}.contextstrip{gap:12px}.contextvalue{font-size:18px}.wordmark{font-size:17px}.modepill{font-size:8px;padding:7px}.scenario{gap:8px}.scenario b{font-size:15px}}
</style><div class="brandrow"><div><div class="wordmark">ALPHA / LAB</div><div class="brandtag">BITCOIN · 15 MINUTE SIGNAL RESEARCH</div></div><div class="modepill">SOLO SEÑALES</div></div>""",unsafe_allow_html=True)
with st.sidebar:
    st.header('Motor corregido · candidato')
    st.write('Analogías con resultados oficiales de rondas anteriores. Umbral fijo del 65% y filtro conservador de evidencia.')
    st.write('Confirma con tres velas de contexto distintas; refrescar los mismos datos no agrega una confirmación.')
    st.caption('Prueba histórica: 2 señales acertadas, 0 fallidas y 8 sin señal en 10 rondas. No equivale a precisión futura ni a rentabilidad.')

@st.fragment(run_every='10s')
def dashboard():
    try:
        m=market()
        if not m:
            st.info('No hay ronda abierta disponible.');return
        target=m.get('floor_strike')
        if target is None:
            st.warning('Sin target oficial: no se emite señal.');return
        target=float(target)
        miami_now=datetime.now(ZoneInfo('America/New_York')).strftime('%I:%M:%S %p')
        miami_close=pd.Timestamp(m['close_time']).tz_convert('America/New_York').strftime('%I:%M %p')
        now=datetime.now(timezone.utc).timestamp()
        seconds=max(0,int(pd.Timestamp(m['close_time']).timestamp()-now))
        points,is_historical=index_data(m['event_ticker'])
        ts,price=points[-1];age=now-ts
        if is_historical or age>15 or age< -5:
            st.warning(f'Precio de Kalshi no apto para una señal en vivo. Antigüedad: {age:.1f} s.');return
        hist=history();live=recent()
        # Require genuinely recent closed candles, not cached data from an earlier regime.
        candle_age=now-(live.time.iloc[-1]+pd.Timedelta(minutes=1)).timestamp()
        if candle_age>120:
            st.warning('Las velas de Coinbase están atrasadas.');return
        with st.spinner('Cargando rondas oficiales para comparar el contexto…'):
            labelled=labelled_history()
        model=round_model(hist,live,price,target,seconds,m['close_time'],labelled)
        if 'up' not in model:
            st.info(model['reason']);return
        suggested=model['direction'] or 'SIN VENTAJA'
        state=st.session_state.setdefault('lab_rounds',{})
        item=state.setdefault(m['ticker'],{'first':None,'time':None,'confirmation':Confirmation()})
        minute=live.time.iloc[-1].isoformat()
        first=item['confirmation'].update(model['direction'],minute,datetime.now(timezone.utc).isoformat(),seconds)
        if first and item['first'] is None:
            item.update(first=first['direction'],time=first['time_utc'])
        if suggested in ('UP','DOWN') and item['confirmation'].count<3:
            suggested='SIN VENTAJA'
        if seconds<=60:suggested='CIERRE · OBSERVACIÓN'
        direction_label={'UP':'ALCISTA','DOWN':'BAJISTA','SIN VENTAJA':'EN ESPERA','CIERRE · OBSERVACIÓN':'CIERRE'}[suggested]
        ink='#69d9bf' if suggested=='UP' else '#f5a68a' if suggested=='DOWN' else '#b1bce8'
        up_width=model['up']*100
        st.markdown(f"""<div class="signalstage" style="--signal:{ink}"><div><div class="eyebrow">Perspectiva del mercado</div><div class="signalword">{direction_label}</div><div class="signaldesc">Contexto actual contrastado con situaciones históricas similares. La lectura se actualiza; la primera señal de la ronda se conserva durante la sesión.</div><div class="signalmark">RONDAS OFICIALES · CANDIDATO</div></div><div><div class="balance"><div class="balancehead"><span>DISTRIBUCIÓN DE ANALOGÍAS</span><span>{model['n']} CASOS</span></div><div class="balancebar"><div style="width:{up_width}%;background:#69d9bf"></div><div style="flex:1;background:#f5a68a"></div></div><div class="balancelabels"><span style="color:#69d9bf">{up_width:.0f}% <small style="font-size:11px">UP</small></span><span style="color:#f5a68a">{100-up_width:.0f}% <small style="font-size:11px">DOWN</small></span></div></div><div class="contextnote">Frecuencia de cierres oficiales similares; no es precisión validada.</div></div></div><div class="contextstrip"><div><div class="eyebrow">Índice Kalshi</div><div class="contextvalue">${price:,.2f}</div><div class="contextnote">{price-target:+,.2f} USD frente al target</div></div><div><div class="eyebrow">Target oficial</div><div class="contextvalue">${target:,.2f}</div><div class="contextnote">Referencia de esta ronda</div></div><div><div class="eyebrow">Tiempo restante</div><div class="contextvalue">{seconds//60:02d}:{seconds%60:02d}</div><div class="contextnote">Índice actualizado hace {max(0,age):.0f} s</div></div></div>""",unsafe_allow_html=True)
        st.markdown(f'<div class="sessionline" style="margin-top:0;border-top:0;padding-top:0;margin-bottom:20px"><span>MIAMI · {miami_now}</span><span>CIERRE · {miami_close}</span><span>FUENTE · KALSHI / BRTI</span></div>',unsafe_allow_html=True)
        st.markdown('<div class="eyebrow">Trayectoria del índice · ronda actual</div>',unsafe_allow_html=True)
        chart=pd.DataFrame(points,columns=['time','BRTI']);chart['time']=pd.to_datetime(chart.time,unit='s',utc=True);chart['Target']=target
        st.line_chart(chart.set_index('time')[['BRTI','Target']],color=['#69d9bf','#71819c'])
        st.markdown(f"""<div class="scenario"><div>RONDAS DISPONIBLES<b>{model['available']}</b></div><div>CASOS EFECTIVOS<b>{model['effective']:.0f}</b></div><div>CONFIRMACIÓN<b>{item['confirmation'].count}/3</b></div></div><div class="sessionline"><span>PRIMERA SEÑAL · {item['first'] or 'SIN CONFIRMAR'}</span><span>{m['ticker']}</span><span>{model['effective']:.0f} analogías efectivas</span></div>""",unsafe_allow_html=True)
        if seconds<=60:
            st.info('Último minuto: se muestra el índice, pero este prototipo no predice el promedio oficial de liquidación.')
        with st.expander('Qué está midiendo'):
            st.json({'evidencia':model,'edad_indice_segundos':round(age,1),'historico_velas':len(hist),'primera_senal_hora':item['time']})
            st.write('Sin órdenes, sin claves privadas y sin lectura del resultado futuro. Primera señal guardada solo en la sesión; no incluye historial autónomo ni un porcentaje de acierto validado.')
    except (requests.RequestException,ValueError,KeyError,IndexError,TypeError) as error:
        st.error('No hay datos fiables suficientes para emitir una señal: '+str(error))

dashboard()
