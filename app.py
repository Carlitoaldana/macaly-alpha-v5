"""JC ALPHA EDGE — maqueta visual solamente.
Ejecutar: streamlit run JC_ALPHA_EDGE_VISUAL_PULIDO.py
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
/* Maqueta compacta: mantiene cuatro métricas y dos lectores en móvil */
@media(max-width:700px){
.block-container{max-width:100%!important;padding:0 2px 12px!important}
.ae{font-size:10px;line-height:1.12}.ae .frame{padding:5px}
.ae .row{gap:5px;margin-bottom:5px}.ae .panel{border-radius:7px}
.ae .top{height:43px;gap:4px;padding:0 2px 4px;margin-bottom:5px}
.ae .brand b{font-size:clamp(13px,3.7vw,19px);letter-spacing:.3px}.ae .brand small{font-size:8px}
.ae .top .tiny{font-size:8px}.ae .top>span{font-size:17px!important}
.ae .hero{grid-template-columns:1fr 1fr;gap:5px}.ae .hero>.panel{min-height:72px;padding:6px}
.ae .tiny{font-size:8px}.ae .signal{gap:4px}.ae .arrow{font-size:36px}.ae .down{font-size:clamp(20px,5.2vw,32px);letter-spacing:0}.ae .pill{font-size:8px;padding:2px 4px}
.ae .bitcoin{font-size:38px}.ae .state strong{font-size:11px!important;margin:3px 0!important}
.ae .pre{padding:7px 8px}.ae .pre .big{font-size:19px;margin:3px 0}.ae .pre p{font-size:9px;margin-top:3px}.ae .tag{font-size:7px;padding:3px 5px}
.ae .track{height:7px}
.ae .metrics{grid-template-columns:repeat(4,minmax(0,1fr));gap:4px}
.ae .metric{height:64px;padding:5px 3px;gap:3px;align-items:center}.ae .metric .ico{font-size:clamp(13px,3.6vw,23px)}
.ae .metric small{font-size:clamp(6px,1.6vw,9px);line-height:1.05}.ae .metric strong{font-size:clamp(10px,2.65vw,17px);white-space:normal;overflow-wrap:anywhere}.ae .metric em{font-size:8px}
.ae .support{padding:6px 8px}.ae .supportbar{margin-top:5px}.ae .supportbar>div{height:15px;line-height:15px}.ae .split{margin-top:4px}
.ae .readers{grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.ae .reader{min-height:83px;padding:6px}
.ae .readbody{gap:5px;margin-top:5px}.ae .donut{width:49px;height:49px}.ae .donut span{width:37px;height:37px;font-size:12px}
.ae .readbody strong{font-size:9px}.ae .readbody .tiny{font-size:8px!important}.ae .motion{margin-top:9px}.ae .motion strong{font-size:16px}
.ae .chartpanel{padding:6px}.ae .charthead{gap:4px}.ae .charthead strong{font-size:10px}.ae .tabs{gap:2px}.ae .tabs span{padding:3px 4px;font-size:8px}.ae .chartwrap{height:190px;margin-top:5px;padding-right:45px}
.ae .levels{width:44px;font-size:7px}.ae .levels span{padding:2px 0}.ae .times{font-size:7px;margin-right:46px}
.ae .indicators{grid-template-columns:1.25fr 1fr;gap:5px}.ae .indicator{padding:6px}.ae .chips{grid-template-columns:repeat(3,minmax(0,1fr));gap:3px;margin-top:5px}.ae .chip{font-size:7px;padding:3px 1px}.ae .rsi{height:44px}
.ae .history{padding:6px}.ae table{font-size:7px;margin-top:5px}.ae td,.ae th{padding:4px 2px;white-space:nowrap}.ae .notice{font-size:8px}
}
@media(max-width:390px){.ae .metric .ico{font-size:12px}.ae .metric{gap:2px}.ae .down{font-size:20px}.ae .bitcoin{font-size:30px}.ae .chartwrap{height:175px}}

/* Detalles reconstruidos de la referencia: compactos, brillo y ornamentos */
.ae .frame{position:relative;background:linear-gradient(160deg,#030b1b 0%,#010611 60%,#020918 100%)}
.ae .panel{border-color:#087fff;box-shadow:inset 0 0 11px #035cba55,0 0 3px #0a84ff,0 0 11px #006fff83}
.ae .top{position:relative;background:linear-gradient(126deg,transparent 0 20%,#0641844d 22%,transparent 24%,transparent 29%,#087cf04d 31%,transparent 33%);border-bottom-color:#147fe1}
.ae .brand b{position:relative;font-weight:900;font-style:italic;letter-spacing:1.5px;color:#4eb6ff;text-shadow:0 0 3px #b0e4ff,0 0 10px #007cff,0 0 17px #0059ff}
.ae .crown{position:absolute;left:50%;top:-13px;transform:translateX(-50%);color:#ffbb35;font-style:normal;font-size:16px;text-shadow:0 0 7px #ff9e00}
.ae .arrow{display:flex;align-items:center;justify-content:center;filter:drop-shadow(0 0 7px #ff233b) drop-shadow(0 0 13px #ff133e)}
.ae .arrow svg{width:68px;height:82px;display:block}
.ae .coin{height:96px;width:96px;flex:none;display:grid;place-items:center;border-radius:50%;border:2px solid #037aff;background:radial-gradient(circle at 37% 30%,#073c91 0%,#03132e 56%,#010713 80%);box-shadow:inset 0 0 10px #069cff,0 0 8px #008cff,0 0 22px #036bff90;position:relative}
.ae .coin:before,.ae .coin:after{content:'';position:absolute;inset:6px;border:1px dashed #1689ff;border-radius:50%;opacity:.8}
.ae .coin:after{inset:12px;border-style:solid;opacity:.3}
.ae .coin span{font-size:70px;font-weight:900;color:#158bff;text-shadow:0 0 12px #027bff;z-index:1}
.ae .metric{position:relative;overflow:hidden}.ae .spark{position:absolute;right:6px;bottom:8px;width:40%;height:22px;filter:drop-shadow(0 0 4px #f33)}
.ae .bars{filter:drop-shadow(0 0 5px #ff415c)}.ae .clock,.ae .targeticon{filter:drop-shadow(0 0 5px #078dff)}
.ae .down{filter:drop-shadow(0 0 5px #f13)}
.ae .chartpanel{box-shadow:inset 0 0 12px #006eff44,0 0 13px #006fff99}
.ae .chartwrap svg{background:linear-gradient(180deg,#031126,#030d1e)}
.ae .pre{box-shadow:inset 0 0 15px #045ab944,0 0 11px #0379ff91}
.ae .supportbar{gap:4px}.ae .supportbar>div{box-shadow:0 0 7px currentColor}
.ae .history table{table-layout:auto}
@media(max-width:700px){
.ae .frame{padding:5px 7px}
.ae .top{height:48px}
.ae .brand b{font-size:clamp(14px,4vw,20px)}
.ae .crown{font-size:11px;top:-10px}
.ae .hero>.panel{height:88px;min-height:88px}
.ae .arrow svg{width:36px;height:51px}
.ae .signal{gap:5px}
.ae .down{font-size:clamp(21px,5.6vw,34px)}
.ae .coin{width:60px;height:60px;margin-left:3px}
.ae .coin span{font-size:43px}
.ae .coin:before{inset:4px}.ae .coin:after{inset:8px}
.ae .metric{height:65px;padding:4px 5px}
.ae .metric .ico{font-size:clamp(15px,3.9vw,25px)}
.ae .metric strong{font-size:clamp(10px,2.7vw,17px)}
.ae .spark{height:12px!important;bottom:4px!important}
.ae .chartwrap{height:183px}
.ae .readers .reader{min-height:80px}
.ae .history td,.ae .history th{font-size:clamp(6px,1.7vw,9px)}
}
/* Pulido final: emblema, distancia, proporciones y legibilidad */
.ae .coin{isolation:isolate;transform:rotate(-12deg);border:3px solid #128eff;background:radial-gradient(circle at 29% 20%,#1263bb 0%,#073d90 20%,#001c4d 57%,#02091b 80%);box-shadow:0 0 3px #9de9ff,0 0 10px #008cff,0 0 22px #006aff,inset 0 0 13px #219dff,inset -9px -8px 10px #001331}
.ae .coin:before{inset:5px;border:2px dashed #27a8ff;opacity:.9}.ae .coin:after{inset:12px;border:2px solid #1377d5;opacity:.8}
.ae .coin span{position:relative;z-index:2;color:#128bff;-webkit-text-stroke:1px #59bbff;text-shadow:2px 3px 0 #00194e,-2px -2px 1px #7be0ff,0 0 12px #008aff;transform:rotate(12deg)}
.ae .coinmark{position:absolute;inset:-8px;border-radius:50%;border:1px dotted #1577ff;box-shadow:0 0 12px #005aff;opacity:.8}
.ae .metric .bars{flex:none;width:32px!important;min-width:32px;display:flex;align-items:center;justify-content:center}
.ae .metric .bars svg{width:30px!important;height:34px!important}
.ae .metric:has(.bars){display:grid;grid-template-columns:32px minmax(0,1fr);align-items:center;column-gap:5px}
.ae .metric:has(.bars)>div{min-width:0}
.ae .metric:has(.bars) small{font-size:clamp(7px,1.5vw,10px);line-height:1.1;letter-spacing:-.1px;overflow-wrap:normal;word-break:normal}
.ae .metric:has(.bars) strong{white-space:nowrap;overflow-wrap:normal;font-size:clamp(12px,2.6vw,19px)}
.ae .metric:has(.bars) em{display:block;white-space:nowrap}
.ae .top .brand b{font-style:normal;letter-spacing:1px}
.ae .panel{background:linear-gradient(130deg,#061c3a,#020b1c 70%)}
@media(max-width:700px){.ae .coin{width:57px;height:57px;flex:none}.ae .coin span{font-size:40px}.ae .metric:has(.bars){grid-template-columns:24px minmax(0,1fr);column-gap:3px;padding:4px 3px}.ae .metric .bars{width:24px!important;min-width:24px}.ae .metric .bars svg{width:23px!important;height:30px!important}.ae .metric:has(.bars) small{font-size:clamp(6.5px,1.65vw,9px)}.ae .metric:has(.bars) strong{font-size:clamp(11px,2.65vw,15px)}}
</style>
'''

html=f'''
<div class="ae"><div class="frame">
<div class="top"><span class="blue" style="font-size:26px">☰</span><div class="brand"><b><span class="crown">♛</span>JC ALPHA EDGE</b><small>BTC SIGNAL v4.6.1</small></div><div style="display:flex;align-items:center;gap:13px"><span class="green tiny">● <span class="muted">Mercado en vivo</span></span><span class="blue" style="font-size:24px">⚙</span></div></div>
<div class="row hero"><div class="panel"><div class="muted tiny">SEÑAL OFICIAL DEL BOT</div><div class="signal"><div class="arrow"><svg viewBox="0 0 90 112" aria-hidden="true"><path d="M28 5 H62 V57 H87 L45 106 L3 57 H28 Z" fill="#ff354b"/></svg></div><div><div class="down">DOWN</div><span class="pill">APOYO DEL MOTOR 64%</span></div></div></div><div class="panel state"><div><div class="muted tiny">ESTADO ACTUAL</div><strong style="display:block;font-size:15px;margin:5px 0">OPERACIÓN ACTIVA</strong><div class="muted tiny">Analizando el mercado en tiempo real para el mejor punto de entrada.</div></div><div class="coin"><span>₿</span><i class="coinmark"></i></div></div></div>
<div class="panel pre row"><div class="prehead"><span class="muted tiny">PRESEÑAL · PRESIÓN ACTUAL</span><span class="tag red" style="border-color:#d82c55">COINCIDE CON LA SEÑAL</span></div><div style="display:flex;justify-content:space-between;align-items:center"><span class="red big">POSIBLE DOWN</span><strong class="red big">93%</strong></div><div class="track"><div class="fill" style="width:93%"></div></div><p>Presión bajista temprana detectada. Esperando evolución del mercado.<br>Porcentaje de apoyo, no probabilidad de acierto.</p></div>
<div class="row metrics"><div class="panel metric"><span class="ico" style="color:#ffac22">₿</span><div><small>BTC / USD</small><strong>$76,637</strong><em class="red">-0.15%</em><svg class="spark" viewBox="0 0 90 25"><polyline points="0,20 7,16 13,20 20,11 26,16 32,9 39,13 45,5 52,11 58,7 65,14 72,4 78,9 90,1" fill="none" stroke="#ff3452" stroke-width="2"/></svg></div></div><div class="panel metric"><span class="ico targeticon">◎</span><div><small>TARGET</small><strong>$76,739</strong></div></div><div class="panel metric"><span class="ico red bars"><svg viewBox="0 0 40 42" aria-hidden="true" style="width:31px;height:36px;display:block"><rect x="2" y="26" width="9" height="14" rx="1" fill="#ff3854"/><rect x="15" y="16" width="9" height="24" rx="1" fill="#ff3854"/><rect x="28" y="4" width="9" height="36" rx="1" fill="#ff3854"/></svg></span><div><small>DISTANCIA AL TARGET</small><strong class="red">$102</strong><em class="red">0.13%</em></div></div><div class="panel metric"><span class="ico clock">◷</span><div style="width:100%"><small>TIEMPO RESTANTE</small><strong>10:42</strong><div class="track" style="height:7px;margin-top:7px"><div class="fill" style="width:75%"></div></div></div></div></div>
<div class="panel support row"><div class="muted tiny">APOYO CALCULADO · UP / DOWN</div><div class="supportbar"><div class="upbar">36%</div><div class="downbar">64%</div></div><div class="split"><span class="green">● UP 36%</span><span class="red">● DOWN 64%</span></div></div>
<div class="row readers"><div class="panel reader"><div style="display:flex;justify-content:space-between"><span class="muted tiny">⌁ &nbsp; LECTOR DE CIERRE</span><span class="tag green" style="border-color:#00d9b1">ACTIVO</span></div><div class="readbody"><div class="donut"><span>73%</span></div><div><strong>VENTAJA MODERADA<br>PARA DOWN</strong><div class="muted tiny" style="margin-top:7px">La dirección sigue activa, pero la presión inmediata aún puede cambiar.</div></div></div></div><div class="panel reader"><div class="muted tiny">▥ &nbsp; MOVIMIENTO ÚLTIMOS SEGUNDOS</div><div class="motion"><div><span class="muted tiny">30s</span><strong class="green">−</strong></div><div><span class="muted tiny">10s</span><strong class="red">-3</strong></div><div><span class="muted tiny">5s</span><strong class="red">-2</strong></div></div><div class="muted tiny" style="text-align:center;margin-top:6px">Cambio de precio en los últimos segundos.</div></div></div>
<div class="panel chartpanel row"><div class="charthead"><strong class="muted">₿ &nbsp; BTC / USD · 1M · KRAKEN</strong><div class="tabs"><span class="selected">1m</span><span>3m</span><span>5m</span><span>15m</span><span>1h</span><span>4h</span><span>1D</span></div><span class="blue">⛶</span></div><div class="chartwrap">{chart}<div class="levels"><span>76,850</span><span>76,800</span><span class="res">RESISTANCE<br>76,786</span><span>76,750</span><span class="target">TARGET<br>76,739</span><span class="btc">BTC<br>76,637</span><span>76,600</span><span class="green">SUPPORT<br>76,545</span><span>76,500</span></div></div><div class="times"><span>5:50 PM</span><span>5:55 PM</span><span>6:00 PM</span><span>6:05 PM</span><span>6:10 PM</span><span>6:15 PM</span><span>6:20 PM</span></div></div>
<div class="row indicators"><div class="panel indicator"><div class="muted tiny">INDICADORES</div><div class="chips"><span class="chip"><span style="color:#e500ff">●</span> EMA9 &nbsp; ON</span><span class="chip"><span style="color:#00d6ed">●</span> EMA21 &nbsp; ON</span><span class="chip"><span style="color:#346aff">●</span> VWAP &nbsp; ON</span><span class="chip"><span class="green">●</span> VOLUMEN &nbsp; ON</span><span class="chip"><span style="color:#ff38d6">●</span> RSI &nbsp; ON</span></div></div><div class="panel indicator"><div class="muted tiny">RSI 14</div><svg class="rsi" viewBox="0 0 320 55" preserveAspectRatio="none"><path d="M0 17H320M0 42H320" stroke="#234c77" stroke-dasharray="3 4"/><polyline points="0,38 12,35 24,41 36,29 48,34 60,27 72,31 84,21 96,25 108,18 120,19 132,13 144,17 156,15 168,18 180,16 192,20 204,14 216,18 228,21 240,16 252,22 264,18 276,26 288,23 300,28 320,24" stroke="#e725ff" stroke-width="2" fill="none"/><text x="277" y="12" fill="#c5d7f2" font-size="10">70</text><text x="277" y="52" fill="#c5d7f2" font-size="10">30</text></svg></div></div>
<div class="panel history"><div style="display:flex;justify-content:space-between;align-items:center"><span class="muted tiny">⌁ &nbsp; OPERACIONES RECIENTES (ÚLTIMAS 5)</span><span class="tag">Ver historial →</span></div><div style="overflow-x:auto"><table><thead><tr><th>HORA</th><th>SEÑAL</th><th>OBJETIVO</th><th>RESULTADO</th></tr></thead><tbody><tr><td>6:20 PM</td><td class="red">▼ DOWN</td><td>$76,701.15</td><td>PENDIENTE</td></tr><tr><td>6:05 PM</td><td class="green">▲ UP</td><td>$76,689.40</td><td class="green">GANADA</td></tr><tr><td>5:50 PM</td><td class="red">▼ DOWN</td><td>$76,728.10</td><td class="red">PERDIDA</td></tr><tr><td>5:35 PM</td><td class="green">▲ UP</td><td>$76,612.85</td><td class="green">GANADA</td></tr><tr><td>5:20 PM</td><td class="red">▼ DOWN</td><td>$76,745.30</td><td class="red">PERDIDA</td></tr></tbody></table></div></div>
<div class="notice">VISTA PREVIA ESTÁTICA · DATOS FICTICIOS · SIN CONEXIÓN NI FUNCIONES</div>
</div></div>
'''
st.markdown(css+html,unsafe_allow_html=True)
