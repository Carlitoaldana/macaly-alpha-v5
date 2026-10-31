"""JC ALPHA EDGE — maqueta visual solamente.
Ejecutar: streamlit run JC_ALPHA_EDGE_SOLO_VISUAL.py
No se conecta a exchanges, no calcula señales y no opera.
"""
import streamlit as st
import random

st.set_page_config(page_title='JC ALPHA EDGE | Vista previa', page_icon='⚡', layout='wide', initial_sidebar_state='collapsed')

random.seed(46)
price=76640
candles=[]
for i in range(48):
    opening=price
    delta= random.randint(-38,38) + (16 if 18<i<31 else -13 if i>39 else 0)
    closing=opening+delta
    hi=max(opening,closing)+random.randint(7,23)
    lo=min(opening,closing)-random.randint(7,23)
    candles.append((opening,closing,hi,lo))
    price=closing
lo=min(c[3] for c in candles)-15
hi=max(c[2] for c in candles)+15
Y=lambda v: 208-(v-lo)/(hi-lo)*174
w=10.4
parts=[]
for i,(o,c,h,l) in enumerate(candles):
    x=18+i*11.9
    color='#00f2c6' if c>=o else '#ff4058'
    top=min(Y(o),Y(c)); height=max(2,abs(Y(o)-Y(c)))
    parts.append(f'<line x1="{x+4.5:.1f}" y1="{Y(h):.1f}" x2="{x+4.5:.1f}" y2="{Y(l):.1f}" stroke="{color}" stroke-width="1.5"/><rect x="{x:.1f}" y="{top:.1f}" width="9" height="{height:.1f}" fill="{color}"/>')
    vh=random.randint(4,20) if i!=27 else 38
    parts.append(f'<rect x="{x:.1f}" y="{263-vh}" width="9" height="{vh}" fill="{color}" opacity=".68"/>')
ema=' '.join(f'{18+i*11.9:.1f},{Y(76640 + 30 * __import__("math").sin(i/8)):.1f}' for i in range(48))
ema2=' '.join(f'{18+i*11.9:.1f},{Y(76630 + 20 * __import__("math").sin(i/11+1)):.1f}' for i in range(48))
grid=''.join(f'<line x1="0" y1="{y}" x2="600" y2="{y}" stroke="#19345d" stroke-width=".8"/>' for y in [42,83,124,165,206,245])
grid+=''.join(f'<line x1="{x}" y1="0" x2="{x}" y2="270" stroke="#122d50" stroke-width=".8"/>' for x in [70,170,270,370,470,570])
chart=f'''<svg viewBox="0 0 600 275" preserveAspectRatio="none" aria-label="Gráfica de velas de ejemplo">{grid}<polyline points="{ema}" fill="none" stroke="#db19fc" stroke-width="2"/><polyline points="{ema2}" fill="none" stroke="#00c6dc" stroke-width="1.5"/>{''.join(parts)}<line x1="0" y1="168" x2="600" y2="168" stroke="#f94359" stroke-dasharray="3 4" opacity=".8"/></svg>'''

css='''
<style>
:root{color-scheme:dark}html,body,[data-testid="stAppViewContainer"]{background:#02060e!important;color:#e8f4ff!important}
#MainMenu,footer,header,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important}
[data-testid="stAppViewContainer"]>.main{background:radial-gradient(ellipse at top,#061b3b 0%,#02060e 60%)!important}
.block-container{max-width:1240px!important;padding:12px 15px 30px!important}
.ae *{box-sizing:border-box}.ae{font-family:Arial,Helvetica,sans-serif;color:#e7f3ff;font-size:13px;line-height:1.25}
.ae .frame{padding:12px;background:linear-gradient(135deg,#07172e,#020813 52%,#051124);border:1px solid #0b57b8;box-shadow:0 0 24px #005dff26}
.ae .panel{border:1px solid #087bff;border-radius:10px;background:linear-gradient(135deg,#061b3b 0%,#030c1c 72%);box-shadow:inset 0 0 12px #0056c44a,0 0 9px #006dff52;min-width:0}
.ae .muted{color:#91b5dd}.ae .tiny{font-size:11px}.ae .tag{border:1px solid #067dff;border-radius:14px;padding:4px 10px;color:#90c9ff;font-size:11px;white-space:nowrap}
.ae .top{height:55px;display:flex;align-items:center;justify-content:space-between;padding:0 7px 9px;border-bottom:1px solid #0b4b91;margin-bottom:9px;gap:10px}
.ae .brand{text-align:center}.ae .brand b{display:block;font-size:26px;letter-spacing:2px;color:#56b7ff;text-shadow:0 0 9px #008dff,0 0 20px #086eff}.ae .brand small{color:#a6c6e8;font-size:11px;letter-spacing:1px}
.ae .blue{color:#16a9ff}.ae .green{color:#00e5b3}.ae .red{color:#ff4258}.ae .big{font-size:24px;font-weight:900}.ae .row{display:grid;gap:9px;margin-bottom:9px}.ae .hero{grid-template-columns:1fr 1fr}.ae .hero>.panel{min-height:117px;padding:12px 16px}.ae .signal{display:flex;align-items:center;gap:17px}.ae .arrow{font-size:76px;line-height:1;color:#ff3b4e;text-shadow:0 0 25px #ff1b4f}.ae .down{font-size:55px;letter-spacing:2px;font-weight:900;color:#ff4259;text-shadow:0 0 15px #e31638}.ae .pill{display:inline-block;border:1px solid #ff3557;border-radius:15px;padding:3px 13px;box-shadow:0 0 9px #ef154c7d;font-size:12px;font-weight:bold}
.ae .state{display:flex;justify-content:space-between;align-items:center}.ae .bitcoin{font-size:78px;font-weight:900;color:#1487ff;text-shadow:0 0 17px #067bff;line-height:1}
.ae .pre{padding:12px 17px}.ae .prehead{display:flex;justify-content:space-between;gap:8px}.ae .pre .big{margin:5px 0}.ae .track{height:10px;background:#102b4b;border-radius:9px;overflow:hidden}.ae .fill{height:100%;background:#ff3e56;box-shadow:0 0 12px #ff3155;border-radius:9px}.ae .pre p{margin:5px 0 0;color:#a6bfdc;font-size:12px}
.ae .metrics{grid-template-columns:repeat(4,minmax(0,1fr))}.ae .metric{height:87px;padding:12px;display:flex;gap:10px;align-items:center}.ae .metric .ico{font-size:33px;color:#14a6ff}.ae .metric strong{display:block;font-size:22px;white-space:nowrap}.ae .metric small{display:block;color:#9fc1e5;font-size:10px}.ae .metric em{font-size:11px;font-style:normal}
.ae .support{padding:9px 15px}.ae .supportbar{display:grid;grid-template-columns:36% 64%;gap:4px;margin-top:8px}.ae .supportbar>div{height:21px;border-radius:5px;text-align:center;font-weight:800;line-height:21px}.ae .upbar{background:#00e8ae;color:#002a25}.ae .downbar{background:#f84758;color:#250008}.ae .split{display:flex;justify-content:space-between;margin-top:5px;font-weight:bold}
.ae .readers{grid-template-columns:1fr 1fr}.ae .reader{padding:12px 15px;min-height:105px}.ae .readbody{display:flex;align-items:center;gap:16px;margin-top:8px}.ae .donut{height:72px;width:72px;flex:none;border-radius:50%;background:conic-gradient(#ff4156 0 73%,#173653 73% 100%);display:grid;place-items:center}.ae .donut span{height:55px;width:55px;border-radius:50%;display:grid;place-items:center;background:#07152a;font-size:19px;font-weight:bold}.ae .motion{display:flex;justify-content:space-around;text-align:center;margin-top:13px}.ae .motion>div{flex:1;border-right:1px solid #21426d}.ae .motion>div:last-child{border:0}.ae .motion strong{font-size:22px;display:block}
.ae .chartpanel{padding:10px 14px}.ae .charthead{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}.ae .tabs{display:flex;gap:5px;flex-wrap:wrap}.ae .tabs span{border:1px solid #214c7f;border-radius:5px;padding:4px 9px;color:#9cc2e6;font-size:11px}.ae .tabs .selected{background:#076dff;color:white;box-shadow:0 0 10px #007bff}.ae .chartwrap{height:305px;position:relative;margin-top:9px;padding-right:65px}.ae .chartwrap svg{width:100%;height:100%;display:block;background:linear-gradient(#041126,#03101f)}.ae .levels{position:absolute;right:0;top:7px;width:64px;display:flex;flex-direction:column;justify-content:space-around;height:91%;font-size:10px}.ae .levels span{padding:4px 2px;text-align:center;border-radius:3px}.ae .levels .res{background:#ff4155;color:#fff}.ae .levels .target{background:#00d9ae;color:#002e29}.ae .levels .btc{background:#168aff;color:#fff}.ae .times{display:flex;justify-content:space-between;color:#83a8ce;font-size:10px;margin:3px 68px 0 0}
.ae .indicators{grid-template-columns:1.25fr 1fr}.ae .indicator{padding:11px 15px}.ae .chips{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}.ae .chip{border:1px solid #174c9c;border-radius:16px;padding:6px 8px;white-space:nowrap;font-size:11px;text-align:center}.ae .rsi{width:100%;height:46px;margin-top:7px}
.ae .history{padding:11px 15px}.ae table{border-collapse:collapse;width:100%;font-size:11px;margin-top:9px}.ae th{color:#93bce8;background:#082047;text-align:left;font-weight:normal}.ae td,.ae th{padding:6px;border-bottom:1px solid #0d2d55}.ae tr:last-child td{border-bottom:0}
.ae .notice{text-align:center;color:#6086ae;font-size:11px;padding:10px 0 0}
@media(max-width:700px){.block-container{padding:4px 5px 16px!important}.ae .frame{padding:7px}.ae .top{height:51px}.ae .brand b{font-size:17px;letter-spacing:1px}.ae .brand small{font-size:9px}.ae .hero{grid-template-columns:1fr 1fr;gap:6px}.ae .hero>.panel{min-height:100px;padding:8px}.ae .arrow{font-size:42px}.ae .signal{gap:4px}.ae .down{font-size:27px}.ae .pill{font-size:9px;padding:3px 5px}.ae .bitcoin{font-size:43px}.ae .state{gap:3px}.ae .metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.ae .metric{height:74px;padding:8px}.ae .metric strong{font-size:17px}.ae .metric .ico{font-size:25px}.ae .readers{grid-template-columns:1fr;gap:6px}.ae .chartwrap{height:240px}.ae .indicators{grid-template-columns:1fr;gap:6px}.ae .chips{grid-template-columns:repeat(3,minmax(0,1fr))}.ae .tag{font-size:9px}.ae .pre{padding:9px}.ae .pre .big{font-size:19px}.ae .charthead strong{font-size:12px}.ae .tabs span{padding:3px 7px}.ae table{font-size:9px}.ae td,.ae th{padding:5px 3px}}
@media(max-width:390px){.ae .down{font-size:23px}.ae .arrow{font-size:36px}.ae .bitcoin{font-size:33px}.ae .metric strong{font-size:15px}.ae .brand b{font-size:15px}.ae .top{gap:4px}.ae .chartwrap{height:200px}}
</style>
'''

html=f'''
<div class="ae"><div class="frame">
<div class="top"><span class="blue" style="font-size:26px">☰</span><div class="brand"><b>♛ JC ALPHA EDGE</b><small>BTC SIGNAL v4.6.1</small></div><div style="display:flex;align-items:center;gap:13px"><span class="green tiny">● <span class="muted">Mercado en vivo</span></span><span class="blue" style="font-size:24px">⚙</span></div></div>
<div class="row hero"><div class="panel"><div class="muted tiny">SEÑAL OFICIAL DEL BOT</div><div class="signal"><div class="arrow">⬇</div><div><div class="down">DOWN</div><span class="pill">APOYO DEL MOTOR 64%</span></div></div></div><div class="panel state"><div><div class="muted tiny">ESTADO ACTUAL</div><strong style="display:block;font-size:15px;margin:5px 0">OPERACIÓN ACTIVA</strong><div class="muted tiny">Analizando el mercado en tiempo real para el mejor punto de entrada.</div></div><div class="bitcoin">₿</div></div></div>
<div class="panel pre row"><div class="prehead"><span class="muted tiny">PRESEÑAL · PRESIÓN ACTUAL</span><span class="tag red" style="border-color:#d82c55">COINCIDE CON LA SEÑAL</span></div><div style="display:flex;justify-content:space-between;align-items:center"><span class="red big">POSIBLE DOWN</span><strong class="red big">93%</strong></div><div class="track"><div class="fill" style="width:93%"></div></div><p>Presión bajista temprana detectada. Esperando evolución del mercado.<br>Porcentaje de apoyo, no probabilidad de acierto.</p></div>
<div class="row metrics"><div class="panel metric"><span class="ico" style="color:#ffac22">₿</span><div><small>BTC / USD</small><strong>$76,637</strong><em class="red">-0.15%</em></div></div><div class="panel metric"><span class="ico">◎</span><div><small>TARGET</small><strong>$76,739</strong></div></div><div class="panel metric"><span class="ico red">▂▅▇</span><div><small>DISTANCIA AL TARGET</small><strong class="red">$102</strong><em class="red">0.13%</em></div></div><div class="panel metric"><span class="ico">◷</span><div style="width:100%"><small>TIEMPO RESTANTE</small><strong>10:42</strong><div class="track" style="height:7px;margin-top:7px"><div class="fill" style="width:75%"></div></div></div></div></div>
<div class="panel support row"><div class="muted tiny">APOYO CALCULADO · UP / DOWN</div><div class="supportbar"><div class="upbar">36%</div><div class="downbar">64%</div></div><div class="split"><span class="green">● UP 36%</span><span class="red">● DOWN 64%</span></div></div>
<div class="row readers"><div class="panel reader"><div style="display:flex;justify-content:space-between"><span class="muted tiny">⌁ &nbsp; LECTOR DE CIERRE</span><span class="tag green" style="border-color:#00d9b1">ACTIVO</span></div><div class="readbody"><div class="donut"><span>73%</span></div><div><strong>VENTAJA MODERADA<br>PARA DOWN</strong><div class="muted tiny" style="margin-top:7px">La dirección sigue activa, pero la presión inmediata aún puede cambiar.</div></div></div></div><div class="panel reader"><div class="muted tiny">▥ &nbsp; MOVIMIENTO ÚLTIMOS SEGUNDOS</div><div class="motion"><div><span class="muted tiny">30s</span><strong class="green">−</strong></div><div><span class="muted tiny">10s</span><strong class="red">-3</strong></div><div><span class="muted tiny">5s</span><strong class="red">-2</strong></div></div><div class="muted tiny" style="text-align:center;margin-top:6px">Cambio de precio en los últimos segundos.</div></div></div>
<div class="panel chartpanel row"><div class="charthead"><strong class="muted">₿ &nbsp; BTC / USD · 1M · KRAKEN</strong><div class="tabs"><span class="selected">1m</span><span>3m</span><span>5m</span><span>15m</span><span>1h</span><span>4h</span><span>1D</span></div><span class="blue">⛶</span></div><div class="chartwrap">{chart}<div class="levels"><span>76,850</span><span>76,800</span><span class="res">RESISTANCE<br>76,786</span><span>76,750</span><span class="target">TARGET<br>76,739</span><span class="btc">BTC<br>76,637</span><span>76,600</span><span class="green">SUPPORT<br>76,545</span><span>76,500</span></div></div><div class="times"><span>5:50 PM</span><span>5:55 PM</span><span>6:00 PM</span><span>6:05 PM</span><span>6:10 PM</span><span>6:15 PM</span><span>6:20 PM</span></div></div>
<div class="row indicators"><div class="panel indicator"><div class="muted tiny">INDICADORES</div><div class="chips"><span class="chip"><span style="color:#e500ff">●</span> EMA9 &nbsp; ON</span><span class="chip"><span style="color:#00d6ed">●</span> EMA21 &nbsp; ON</span><span class="chip"><span style="color:#346aff">●</span> VWAP &nbsp; ON</span><span class="chip"><span class="green">●</span> VOLUMEN &nbsp; ON</span><span class="chip"><span style="color:#ff38d6">●</span> RSI &nbsp; ON</span></div></div><div class="panel indicator"><div class="muted tiny">RSI 14</div><svg class="rsi" viewBox="0 0 320 55" preserveAspectRatio="none"><path d="M0 17H320M0 42H320" stroke="#234c77" stroke-dasharray="3 4"/><polyline points="0,38 12,35 24,41 36,29 48,34 60,27 72,31 84,21 96,25 108,18 120,19 132,13 144,17 156,15 168,18 180,16 192,20 204,14 216,18 228,21 240,16 252,22 264,18 276,26 288,23 300,28 320,24" stroke="#e725ff" stroke-width="2" fill="none"/><text x="277" y="12" fill="#c5d7f2" font-size="10">70</text><text x="277" y="52" fill="#c5d7f2" font-size="10">30</text></svg></div></div>
<div class="panel history"><div style="display:flex;justify-content:space-between;align-items:center"><span class="muted tiny">⌁ &nbsp; OPERACIONES RECIENTES (ÚLTIMAS 5)</span><span class="tag">Ver historial →</span></div><div style="overflow-x:auto"><table><thead><tr><th>#</th><th>HORA</th><th>PAR</th><th>SEÑAL</th><th>OBJETIVO</th><th>RESULTADO</th><th>P/L</th></tr></thead><tbody><tr><td>895</td><td>6:20 PM</td><td>BTC 15M</td><td class="red">▼ DOWN</td><td>$76,701.15</td><td>PENDIENTE</td><td>--</td></tr><tr><td>894</td><td>6:05 PM</td><td>BTC 15M</td><td class="green">▲ UP</td><td>$76,689.40</td><td class="green">GANADA</td><td class="green">+$9.20</td></tr><tr><td>893</td><td>5:50 PM</td><td>BTC 15M</td><td class="red">▼ DOWN</td><td>$76,728.10</td><td class="red">PERDIDA</td><td class="red">-$10.00</td></tr><tr><td>892</td><td>5:35 PM</td><td>BTC 15M</td><td class="green">▲ UP</td><td>$76,612.85</td><td class="green">GANADA</td><td class="green">+$8.50</td></tr><tr><td>891</td><td>5:20 PM</td><td>BTC 15M</td><td class="red">▼ DOWN</td><td>$76,745.30</td><td class="red">PERDIDA</td><td class="red">-$10.00</td></tr></tbody></table></div></div>
<div class="notice">VISTA PREVIA ESTÁTICA · DATOS FICTICIOS · SIN CONEXIÓN NI FUNCIONES</div>
</div></div>
'''
st.markdown(css+html,unsafe_allow_html=True)
