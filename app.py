from __future__ import annotations
import types
import json
from urllib.request import Request, urlopen
from urllib.parse import urlencode

class Response:
    def __init__(self, data):
        self.data = data
    def raise_for_status(self):
        pass  # urlopen has already rejected non-2xx responses.
    def json(self):
        return self.data

class requests:
    @staticmethod
    def get(url, params=None, headers=None, timeout=8):
        if params:
            url += ('&' if '?' in url else '?') + urlencode(params)
        req = Request(url, headers=headers or {'User-Agent': 'AlphaEdge/1.0'}, method='GET')
        with urlopen(req, timeout=timeout) as response:
            return Response(json.load(response))

import math
import numpy as np
import pandas as pd
import threading
from datetime import datetime, timezone
NEW_ROUND_WAIT = 8
NEW_ENTRY_LOCK = 75
SIGNAL_CONFIRM_READINGS = 2
SIGNAL_CONFIRM_INTERVAL = 2.0
SIGNAL_CONFIRM_MAX_GAP = 10.0
LIVE_PRICE_MAX_AGE = 30.0
_PRICE_OBSERVATIONS = threading.local()

def _valid_live_observation(price, observed_at, source):
    value = float(price)
    stamp = pd.to_datetime(observed_at, utc=True, errors="coerce")
    if not np.isfinite(value) or value <= 0 or pd.isna(stamp):
        raise ValueError("Precio o fecha de origen inválidos.")
    age = (pd.Timestamp.now(tz="UTC") - stamp).total_seconds()
    if age < -5 or age > LIVE_PRICE_MAX_AGE:
        raise ValueError("Precio de origen atrasado o fechado en el futuro.")
    observations = getattr(_PRICE_OBSERVATIONS, "values", {})
    observations[source] = stamp.timestamp()
    _PRICE_OBSERVATIONS.values = observations
    return value

def _plan_number(value):
    if isinstance(value,bool):return None
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (TypeError,ValueError,OverflowError):return None

def new_round_state(ticker, seconds_left):
    now = datetime.now(timezone.utc)
    return {
        "ticker": ticker,
        "detected_at": now,
        "detected_seconds_left": seconds_left,
        "first_direction": None,
        "first_signal_time": None,
        "first_signal_seconds": None,
        "first_signal_price": None,
        "active_direction": None,
        "active_since": None,
        "last_score": 0.0,
        "previous_score": 0.0,
        "opposite_count": 0,
        "last_live_price": None,
        "previous_live_price": None,
        "reversal_warning": False,
        "reversal_text": "",
        "fresh_samples": [],
        "candidate_history": [],
        "pending_direction": None,
        "pending_count": 0,
        "pending_since": None,
        "pending_last_at": None,
        "pending_price_source": None,
    }

def _fetch_current_btc_candles():
    """Solicita una ventana explícita y verifica la fecha de las velas recibidas.

    Una respuesta HTTP correcta puede contener velas antiguas. No se sustituye
    una vela antigua por un precio live para calcular los indicadores.
    """
    last_error = None
    for attempt in range(2):
        requested_at = datetime.now(timezone.utc)
        minute_start = requested_at.replace(second=0, microsecond=0)
        start = minute_start - pd.Timedelta(minutes=299)
        response = requests.get(
            "https://api.exchange.coinbase.com/products/BTC-USD/candles",
            params={
                "granularity": 60,
                "start": start.isoformat(),
                "end": requested_at.isoformat(),
            },
            headers={
                "User-Agent": "MacalyAlphaBot/4.6.1",
                "Cache-Control": "no-cache, no-store, max-age=0",
                "Pragma": "no-cache",
            },
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or len(rows) < 30:
            raise ValueError("Coinbase no devolvió suficientes velas.")
        frame = pd.DataFrame(
            rows, columns=["time", "low", "high", "open", "close", "volume"]
        )
        for column in ["time", "low", "high", "open", "close", "volume"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True, errors="coerce")
        frame = frame.dropna().drop_duplicates("time").sort_values("time").reset_index(drop=True)
        if len(frame) < 30:
            raise ValueError("Coinbase devolvió velas inválidas o insuficientes.")
        values = frame[["low", "high", "open", "close", "volume"]].to_numpy(dtype=float)
        if (not np.isfinite(values).all() or (values[:, :4] <= 0).any()
                or (values[:, 4] < 0).any()
                or (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any()
                or (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any()
                or (frame["time"].diff().dropna() != pd.Timedelta(minutes=1)).any()):
            raise ValueError("Velas inválidas o con huecos; no se calcula una señal.")
        received_at = datetime.now(timezone.utc)
        latest_start = frame.iloc[-1]["time"]
        age = (received_at - latest_start.to_pydatetime()).total_seconds()
        # Una vela de 1m puede estar abierta o ser la última cerrada. Se permite
        # hasta un minuto adicional de publicación, sin aceptar varios minutos.
        if -5 <= age <= 120:
            frame.attrs["received_at"] = received_at.isoformat()
            frame.attrs["latest_candle_at"] = latest_start.isoformat()
            frame.attrs["candle_age_seconds"] = age
            return frame
        last_error = ValueError(
            "Velas Coinbase desactualizadas: última vela "
            f"{latest_start.strftime('%H:%M:%S UTC')} ({age:.0f} s). "
            "El motor necesita velas actuales."
        )
    raise last_error

def get_event_ticker_from_market(market):
    if not market:
        return None
    event_ticker = market.get("event_ticker")
    if event_ticker:
        return str(event_ticker)
    ticker = market.get("ticker")
    if not ticker:
        return None
    parts = str(ticker).split("-")
    return "-".join(parts[:-1]) if len(parts) >= 2 else None

def extract_kalshi_btc_price(data):
    if not isinstance(data, dict):
        return None

    live_data = data.get("live_data", data)
    details = live_data.get("details", {}) if isinstance(live_data, dict) else {}
    # Prefiere la observación fechada más reciente a un cierre anterior.
    timed_points = []
    points = details.get("timeseries", []) if isinstance(details, dict) else []
    for index, point in enumerate(points if isinstance(points, list) else []):
        if not isinstance(point, dict):
            continue
        try:
            stamp, value = float(point["t"]), float(point["v"])
        except (KeyError, TypeError, ValueError):
            continue
        if np.isfinite(stamp) and stamp > 0 and np.isfinite(value) and 10000 < value < 1000000:
            # La serie puede devolver epoch en segundos o milisegundos.
            stamp = stamp / 1000 if stamp > 100_000_000_000 else stamp
            timed_points.append((stamp, index, value))
    if timed_points:
        stamp, _, value = max(timed_points)
        try:
            return _valid_live_observation(value, pd.to_datetime(stamp, unit="s", utc=True), "KALSHI LIVE")
        except (ValueError, TypeError, OverflowError):
            return None
    # Un precio sin fecha verificable no se anuncia como live.
    return None

def _indicator_frame(df):
    x = df.copy().sort_values("time").reset_index(drop=True)
    close, high, low = x["close"], x["high"], x["low"]
    x["ema9"] = close.ewm(span=9, adjust=False).mean()
    x["ema21"] = close.ewm(span=21, adjust=False).mean()
    delta = close.diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    al = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = ag / al.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.mask((al == 0) & (ag > 0), 100.0)
    rsi = rsi.mask((ag == 0) & (al > 0), 0.0)
    x["rsi"] = rsi.fillna(50.0)
    e12=close.ewm(span=12,adjust=False).mean(); e26=close.ewm(span=26,adjust=False).mean()
    x["macd"]=e12-e26; x["macd_signal"]=x["macd"].ewm(span=9,adjust=False).mean(); x["macd_hist"]=x["macd"]-x["macd_signal"]
    prev=close.shift(1); tr=pd.concat([(high-low),(high-prev).abs(),(low-prev).abs()],axis=1).max(axis=1)
    x["atr"]=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    up=high.diff(); dn=-low.diff(); plus=up.where((up>dn)&(up>0),0.0); minus=dn.where((dn>up)&(dn>0),0.0)
    atr=x["atr"].replace(0,np.nan); pdi=100*plus.ewm(alpha=1/14,adjust=False).mean()/atr; mdi=100*minus.ewm(alpha=1/14,adjust=False).mean()/atr
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    x["plus_di"]=pdi; x["minus_di"]=mdi; x["adx"]=dx.ewm(alpha=1/14,adjust=False).mean()
    typical=(high+low+close)/3; vol=x["volume"].fillna(0); x["vwap"]=(typical*vol).rolling(60,min_periods=1).sum()/vol.rolling(60,min_periods=1).sum().replace(0,np.nan)
    x["vol_ratio"]=vol/vol.rolling(20).mean().replace(0,np.nan)
    return x

def _resample_indicators(df, minutes):
    if minutes == 1: return _indicator_frame(df)
    x=df.set_index("time").resample(f"{minutes}min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna().reset_index()
    return _indicator_frame(x)

def add_indicators(df):
    x=_indicator_frame(df)
    x["mom3"]=x["close"].pct_change(3)*100; x["mom5"]=x["close"].pct_change(5)*100; x["mom15"]=x["close"].pct_change(15)*100
    return x

def get_target_from_market(market):
    if not market:
        return None

    for key in ("floor_strike", "cap_strike"):
        value = market.get(key)
        if value not in [None, ""]:
            try:
                number = float(value)
                if number > 1000:
                    return number
            except Exception:
                pass
    return None

def get_seconds_remaining(market):
    if not market or not market.get("close_time"):
        return None
    try:
        close_dt = datetime.fromisoformat(
            str(market["close_time"]).replace("Z", "+00:00")
        )
        seconds = int(
            (close_dt - datetime.now(timezone.utc)).total_seconds()
        )
        return max(0, seconds)
    except Exception:
        return None

def numeric_kalshi_price(dollar_value, cent_value):
    if dollar_value not in [None, ""]:
        try:
            return float(dollar_value)
        except Exception:
            pass
    if cent_value not in [None, ""]:
        try:
            return float(cent_value) / 100
        except Exception:
            pass
    return None

def get_yes_ask(market):
    if not market:
        return None
    return numeric_kalshi_price(
        market.get("yes_ask_dollars"), market.get("yes_ask")
    )

def get_no_ask(market):
    if not market:
        return None

    direct = numeric_kalshi_price(
        market.get("no_ask_dollars"), market.get("no_ask")
    )
    if direct is not None:
        return direct

    yes_bid = numeric_kalshi_price(
        market.get("yes_bid_dollars"), market.get("yes_bid")
    )
    if yes_bid is not None:
        return max(0.0, min(1.0, 1.0 - yes_bid))
    return None

def _internal_impulse_context(one, price, atr, mom3, mom5, mom15, rvol):
    """Directional persistence / exhaustion in comparable ATR units.

    Informational internally; never imposes a permanent UP/DOWN lock.
    Percent momentum is converted to dollars before ATR normalization.
    Uses completed/current candle history, not fabricated price targets.
    """
    if not np.isfinite(price) or price <= 0 or not np.isfinite(atr) or atr <= 0:
        return {"up": 0.0, "down": 0.0, "exhaust_up": False,
                "exhaust_down": False, "reliable": False}
    close = one["close"].astype(float).tail(9).to_numpy()
    if len(close) < 7 or not np.all(np.isfinite(close)):
        return {"up": 0.0, "down": 0.0, "exhaust_up": False,
                "exhaust_down": False, "reliable": False}
    changes = np.diff(close)
    # Directional efficiency: net movement divided by total absolute movement.
    travel = float(np.sum(np.abs(changes[-5:])))
    efficiency = abs(float(close[-1] - close[-6])) / max(travel, 1e-8)
    recent = float(np.sum(changes[-2:])) / atr
    previous = float(np.sum(changes[-5:-2])) / atr
    m3 = float(np.clip(price * mom3 / 100.0 / atr, -3, 3))
    m5 = float(np.clip(price * mom5 / 100.0 / atr, -3, 3))
    m15 = float(np.clip(price * mom15 / 100.0 / atr, -3, 3))
    volume = float(np.clip(rvol, 0, 3)) if np.isfinite(rvol) else 1.0
    # No invented dollar target: these are dimensionless internal strengths.
    trend = .48 * m3 + .32 * m5 + .20 * m15
    strength = float(np.clip(trend * (.75 + .25 * efficiency) *
                             (.90 + .10 * min(volume, 1.5)), -3, 3))
    exhaust_up = (previous > .35 and recent < -.10) or (m5 > .35 and m3 < -.12)
    exhaust_down = (previous < -.35 and recent > .10) or (m5 < -.35 and m3 > .12)
    return {"up": max(0., strength), "down": max(0., -strength),
            "exhaust_up": bool(exhaust_up), "exhaust_down": bool(exhaust_down),
            "reliable": True, "efficiency": round(float(efficiency), 3),
            "recent_atr": round(recent, 3)}

def _price_level_context(df, price, atr, now=None):
    """Causal 20-bar levels and five-bar rejection evidence, mirrored by side.

    Recent tests use levels fixed before those bars, so tests cannot move the
    obstacle they are evaluated against. An open candle never confirms a break.
    """
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    x = df.sort_values("time").copy()
    closed = x[pd.to_datetime(x["time"], utc=True) + pd.Timedelta(minutes=1) <= now]
    if len(closed) < 25 or not np.isfinite(price) or not np.isfinite(atr) or atr <= 0:
        return {"valid": False, "sides": {}}
    anchor, recent = closed.iloc[-25:-5], closed.iloc[-5:]
    prior = closed.tail(20)
    tolerance, margin, setback = .15*atr, .15*atr, .35*atr
    sides = {}
    for side, sign in (("UP", 1), ("DOWN", -1)):
        level = float(prior["high"].max() if sign == 1 else prior["low"].min())
        old = float(anchor["high"].max() if sign == 1 else anchor["low"].min())
        # A breakout must be beyond the previous fixed level both at the last
        # completed close and at the verified live price.
        # Exclude the confirmation bar, but include newer obstacles formed
        # after the anchor window. Clearing an older level is not enough.
        obstacles = closed.iloc[-21:-1]
        obstacle = float(obstacles["high"].max() if sign == 1 else obstacles["low"].min())
        breakout = sign*(float(closed.iloc[-1]["close"])-obstacle) > margin and sign*(price-obstacle) > margin
        near = -margin <= sign*(level-price) <= .35*atr
        rejected = False
        for _, bar in recent.iterrows():
            extreme = float(bar["high"] if sign == 1 else bar["low"])
            touched = sign*(extreme-old) >= -tolerance
            returned = sign*(old-float(bar["close"])) >= setback
            adverse_body = sign*(float(bar["close"])-float(bar["open"])) < 0
            if touched and returned and adverse_body:
                rejected = True
        # A clear new completed break releases any previous rejection.
        rejected = rejected and not breakout
        allowed = breakout or not (near or rejected)
        reason = ("RUPTURA RESPALDADA" if breakout else
                  "RECHAZO EN RESISTENCIA" if rejected and sign == 1 else
                  "REBOTE EN SOPORTE" if rejected else
                  "ESPERANDO RUPTURA DE RESISTENCIA" if near and sign == 1 else
                  "ESPERANDO RUPTURA DE SOPORTE" if near else "SIN OBSTÁCULO CERCANO")
        sides[side] = dict(allowed=allowed, rejected=rejected, breakout=breakout,
                           level=level, tested_level=old, reason=reason)
    return {"valid": True, "sides": sides}


def _structure_context(df, price, atr, now=None):
    """Causal price action: closed-bar breakouts and failed breaks, no EMA gate."""
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    x = df.sort_values("time").drop_duplicates("time", keep="last")
    x = x[pd.to_datetime(x["time"], utc=True)+pd.Timedelta(minutes=1)<=now]
    if len(x)<21 or not np.isfinite(atr) or atr<=0 or not np.isfinite(price):
        return {"valid":False,"sides":{}}
    bars=x.tail(21)
    if pd.to_datetime(bars["time"],utc=True).diff().dropna().dt.total_seconds().ne(60).any():
        return {"valid":False,"sides":{}}
    age=(now-pd.to_datetime(bars.iloc[-1]["time"],utc=True)).total_seconds()
    if age>150:
        return {"valid":False,"sides":{}}
    prior,last=bars.iloc[:-1],bars.iloc[-1]
    o,h,l,c=(float(last[k]) for k in ("open","high","low","close"))
    values=bars[["open","high","low","close"]].to_numpy(dtype=float)
    volumes=bars['volume'].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or (values<=0).any()
            or not np.isfinite(volumes).all() or (volumes<0).any()
            or (bars['high']<bars[['open','close','low']].max(axis=1)).any()
            or (bars['low']>bars[['open','close','high']].min(axis=1)).any()
            or h<=l):
        return {"valid":False,"sides":{}}
    upper,lower=float(prior["high"].max()),float(prior["low"].min())
    recent=bars["close"].tail(6).to_numpy(dtype=float)
    steps=np.diff(recent)
    efficiency=abs(recent[-1]-recent[0])/max(float(np.abs(steps).sum()),1e-9)
    move=(c-float(prior.iloc[-3]["close"]))/atr
    median_volume=float(prior["volume"].median())
    volume_ok=median_volume>0 and float(last["volume"])>=.8*median_volume
    sides={}
    for side,sign,level in (("UP",1,upper),("DOWN",-1,lower)):
        body=sign*(c-o)/atr
        close_location=(c-l)/(h-l) if sign==1 else (h-c)/(h-l)
        breakout=(sign*(c-level)>.08*atr and sign*(price-level)>.04*atr
                  and body>.20 and close_location>=.70 and sign*move>.25
                  and efficiency>=.45)
        # A failed break can reverse direction without waiting for lagging EMAs.
        obstacle=lower if sign==1 else upper
        probe=l if sign==1 else h
        wick=(min(o,c)-l) if sign==1 else (h-max(o,c))
        rejection=(sign*(probe-obstacle)<-.08*atr and sign*(c-obstacle)>.08*atr
                   and wick>=.35*(h-l) and body>.12 and close_location>=.65
                   and sign*(price-c)>=-.10*atr)
        # Freeze the level before the breakout bar; only later bars may retest it.
        retest=False
        for offset in (2,3,4):
            index=len(bars)-offset
            history=bars.iloc[:index]
            if len(history)<15:
                continue
            fixed=float(history["high"].max() if sign==1 else history["low"].min())
            broken=bars.iloc[index]
            after=bars.iloc[index+1:]
            cleared=sign*(float(broken["close"])-fixed)>.12*atr
            held=all(sign*(float(v)-fixed)>-.15*atr for v in after["close"])
            tested=abs(probe-fixed)<=.20*atr
            response=(body>.12 and close_location>=.65 and sign*(c-fixed)>.08*atr
                      and sign*(price-fixed)>.05*atr)
            retest = retest or (cleared and held and tested and response)
        # Range bounce requires a previously sideways market and a real rejection.
        path=np.diff(prior["close"].to_numpy(dtype=float))
        range_efficiency=abs(float(prior.iloc[-1]["close"])-float(prior.iloc[0]["close"]))/max(float(np.abs(path).sum()),1e-9)
        width=upper-lower
        room=sign*((upper if sign==1 else lower)-price)/atr
        edge_bounce=(range_efficiency<=.35 and 1.5<=width/atr<=6
                     and abs(probe-obstacle)<=.20*atr and sign*(c-obstacle)>.12*atr
                     and body>.12 and wick>=.30*(h-l) and close_location>=.65
                     and room>=.75)
        # Local obstacles count too: a bounce off the bottom of the 20-bar
        # range must not buy straight into a more recent lower high (or low).
        local=prior.tail(5)
        obstacles=local['high'] if sign==1 else local['low']
        ahead=[sign*(float(v)-price)/atr for v in obstacles if sign*(float(v)-price)>0]
        room_ahead=min(ahead) if ahead else float('inf')
        reversal_room=room_ahead>=.60 and room>=.75
        fresh= -.10<=sign*(price-c)/atr<=.50
        not_extended=(h-l)/atr<=2.2 and abs(move)<=2.5
        sides[side]={"breakout":bool(breakout),"rejection":bool(rejection),
                     "retest":bool(retest),"range_bounce":bool(edge_bounce),
                     "fresh":bool(fresh),"not_extended":bool(not_extended),
                     "volume_ok":bool(volume_ok),
                     "level":level,"opposite_level":obstacle,
                     "body_atr":body,"close_location":close_location,
                     "live_change_atr":sign*(price-c)/atr,
                     "range_efficiency":range_efficiency,"remaining_room_atr":room}
        sides[side]['reversal_room']=bool(reversal_room)
        sides[side]['continuation_room']=bool(room_ahead>=.60)
    return {"valid":True,"sides":sides,"bar_time":str(last["time"]),
            "closed_price":c,"live_price":price,"atr":atr,"efficiency":efficiency}


def _entry_route_checks(sig, seconds_left):
    """One independent price-structure strategy, mirrored for UP and DOWN."""
    context=sig.get("structure_internal") or {}
    valid=context.get("valid",False) and sig.get("data_valid") is not False
    sides={}
    for side in ("UP","DOWN"):
        info=context.get("sides",{}).get(side,{})
        sides[side]=[]
        for name,key in (("RUPTURA Y RETEST","retest"),("RUPTURA DE ESTRUCTURA","breakout"),
                         ("RECHAZO CONFIRMADO","rejection"),("REBOTE EN RANGO","range_bounce")):
            checks=[("Estructura cerrada y datos actuales",valid),
                    (name,info.get(key,False)),
                    ("Precio actual confirma sin perseguir",info.get("fresh",False)),
                    ("Movimiento sin extensión excesiva",info.get("not_extended",False)),
                    ("Volumen de vela cerrada suficiente",info.get("volume_ok",False))]
            if key in ('rejection','range_bounce'):
                checks.append(("Espacio antes del siguiente obstáculo",info.get('reversal_room',False)))
            elif key=='retest':
                checks.append(("Retest con espacio para continuar",info.get('continuation_room',False)))
            sides[side].append({"name":name,"checks":checks,"met":sum(bool(v) for _,v in checks),
                                "total":len(checks),"complete":all(bool(v) for _,v in checks)})
    return {"valid":bool(valid),"sides":sides,"noise_ok":bool(valid)}

STRUCTURE_ENGINE_REVISION = "jc_price_structure_v3"

def _signal_engine_without_trace(df, target, seconds_left, live_price=None, whale=None):
    """JC decides from price structure alone; indicators below are display-only.

    ATR measures size, never direction. No EMA/RSI/MACD, whale score or target
    position participates in selecting UP or DOWN.
    """
    now=pd.Timestamp.now(tz="UTC")
    completed=df[pd.to_datetime(df["time"],utc=True)+pd.Timedelta(minutes=1)<=now].copy()
    completed=completed.sort_values('time').drop_duplicates('time',keep='last')
    if len(completed)<25:
        raise ValueError("Esperando al menos 25 velas cerradas para evaluar estructura.")
    price=_plan_number(live_price)
    if price is None or price<=0:
        raise ValueError("El motor de estructura necesita un precio live verificado.")
    previous=completed['close'].shift(1)
    tr=pd.concat([completed['high']-completed['low'],
                  (completed['high']-previous).abs(),
                  (completed['low']-previous).abs()],axis=1).max(axis=1)
    atr=float(tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean().iloc[-1])
    structure=_structure_context(completed,price,atr,now)
    routes=_entry_route_checks({'structure_internal':structure},seconds_left)
    eligible={side:[r for r in routes['sides'][side] if r['complete']] for side in ('UP','DOWN')}
    choices=[side for side in ('UP','DOWN') if eligible[side]]
    candidate=choices[0] if len(choices)==1 and (seconds_left is None or seconds_left>0) else None
    quality=(eligible[candidate][0]['name'] if candidate else
             'ESTRUCTURA CONTRADICTORIA' if len(choices)>1 else 'ESPERANDO ESTRUCTURA CONFIRMADA')
    evidence=1.0 if candidate=='UP' else -1.0 if candidate=='DOWN' else 0.0
    # Preserve the existing technical panel without feeding it back into decisions.
    one=add_indicators(completed); last=one.iloc[-1]
    def display_number(key,default=0.0):
        value=_plan_number(last.get(key))
        return default if value is None else value
    distance=price-target if target is not None else None
    return {'engine_revision':STRUCTURE_ENGINE_REVISION,'structure_internal':structure,
            'price':price,'candle_price':float(last['close']),
            'candidate':candidate,'quality':quality,'entry_route_internal':quality,
            'technical_score':evidence,'final_score':evidence,
            'distance':distance,'distance_pct':distance/target*100 if target else None,
            'target_atr':distance/atr if distance is not None and atr>0 else None,
            'target_score':0.0,'atr':atr,
            'ema':'BULL' if last['ema9']>last['ema21'] else 'BEAR',
            'rsi':display_number('rsi',50),'mom3':display_number('mom3'),
            'mom5':display_number('mom5'),'mom15':display_number('mom15'),
            'vol_ratio':display_number('vol_ratio'), 'vwap':display_number('vwap'),
            'momentum':'ALCISTA' if candidate=='UP' else 'BAJISTA' if candidate=='DOWN' else 'NEUTRAL',
            'up_probability':50,'down_probability':50}

def _retention_assessment(state, signal):
    """Compatibility helper: no legacy indicator can sustain a structure signal."""
    side=state.get('active_direction')
    if side not in ('UP','DOWN') or not signal or signal.get('data_valid') is not True:
        return 0,0
    routes=_entry_route_checks(signal,None)
    allowed=lambda direction:any(r['complete'] for r in routes['sides'].get(direction,[]))
    return int(allowed(side)),int(allowed('DOWN' if side=='UP' else 'UP'))

def _retention_supported(state, signal, seconds_left):
    return (seconds_left is not None and seconds_left>0
            and _retention_assessment(state,signal)[0]>0)

def _reset_withdrawal(state):
    state.update(withdraw_direction=None, withdraw_source=None, withdraw_count=0,
                 withdraw_since=None, withdraw_last_at=None, retention_warning=None)

def _review_active_retention(state, signal, seconds_left, now):
    """An unconfirmed structure never leaves an old direction on screen."""
    if not _retention_supported(state,signal,seconds_left):
        state['active_direction']=None
        state['active_since']=None
    _reset_withdrawal(state)

def _round_opening_crosscheck(state, candidate, signal, now):
    """Use the same price-action evidence for first and later signals."""
    if not signal or signal.get("data_valid") is not True:
        state["opening_conflict"]="Esperando datos actuales"
        return None
    routes=_entry_route_checks(signal,None)
    allowed=candidate in ("UP","DOWN") and any(r["complete"] for r in routes["sides"].get(candidate,[]))
    state["opening_conflict"]=None if allowed else "Esperando estructura confirmada"
    return candidate if allowed else None

def _confirmation_without_trace(state, candidate, market, seconds_left, now, signal=None):
    """Confirmación compartida por la pantalla y el registrador de fondo.

    La primera señal queda como historial. Cada dirección necesita estructura
    actual y dos lecturas; una señal anterior no se conserva mientras se espera
    confirmar la contraria. EMA/RSI/MACD no intervienen.
    """
    if state.get('engine_revision') != STRUCTURE_ENGINE_REVISION:
        # Keep round history; discard pending/active decisions from older engines.
        state.update(engine_revision=STRUCTURE_ENGINE_REVISION,active_direction=None,
                     active_since=None,pending_direction=None,pending_count=0,
                     pending_since=None,pending_last_at=None,pending_price_source=None)
        _reset_withdrawal(state)
    candidate = _round_opening_crosscheck(state, candidate, signal, now)
    # Recalcular el cierre aquí: las consultas de red pueden agotar el contador.
    closed = seconds_left is not None and seconds_left <= 0
    close_time = (market or {}).get("close_time")
    if close_time:
        end = pd.to_datetime(close_time, utc=True, errors="coerce")
        if pd.isna(end):
            candidate = None
        else:
            actual_left = (end - pd.Timestamp(now)).total_seconds()
            seconds_left = actual_left if seconds_left is None else min(seconds_left, actual_left)
            closed = seconds_left <= 0
    if closed:
        _reset_withdrawal(state)
        for key in ("pending_direction", "pending_since", "pending_last_at", "pending_price_source",
                    "active_direction", "active_since"):
            state[key] = None
        state["pending_count"] = 0
        return
    if signal is not None and signal.get("data_valid") is False:
        _reset_withdrawal(state)
        # No current data means no actionable displayed direction.
        state['active_direction'] = None
        state['active_since'] = None
        state["pending_direction"] = None
        state["pending_count"] = 0
        state["pending_since"] = None
        state["pending_last_at"] = None
        if seconds_left is not None and seconds_left <= 0:
            state["active_direction"] = None
            state["active_since"] = None
        return
    source = signal.get("price_source") if signal else None
    if source in ("KALSHI LIVE", "COINBASE", "COINBASE CANDLE"):
        if state.get("pending_count", 0) and state.get("pending_price_source") != source:
            # Tres lecturas deben pertenecer a una misma referencia de precio.
            state["pending_direction"] = None
            state["pending_count"] = 0
            state["pending_since"] = None
            state["pending_last_at"] = None
        state["pending_price_source"] = source
    if candidate not in ("UP", "DOWN"):
        state["pending_direction"] = None
        state["pending_count"] = 0
        state["pending_since"] = None
        state["pending_last_at"] = None
        state["active_direction"] = None
        state["active_since"] = None
        _reset_withdrawal(state)
        return

    _reset_withdrawal(state)
    if candidate == state.get("active_direction"):
        state["pending_direction"] = None
        state["pending_count"] = 0
        state["pending_since"] = None
        state["pending_last_at"] = None
        return

    # Withdraw the former direction while the opposite structure is confirmed.
    state['active_direction'] = None
    state['active_since'] = None
    last = state.get("pending_last_at")
    if isinstance(last, str):
        try:
            last = datetime.fromisoformat(last)
        except ValueError:
            last = None
    since = state.get("pending_since")
    if isinstance(since, str):
        try:
            since = datetime.fromisoformat(since)
        except ValueError:
            since = None

    if (last is not None and ((now - last).total_seconds() > SIGNAL_CONFIRM_MAX_GAP
                              or (now - last).total_seconds() < 0)):
        state["pending_direction"] = None
        state["pending_count"] = 0
        state["pending_since"] = None
        state["pending_last_at"] = None
        last = since = None
    if state.get("pending_direction") != candidate:
        state["pending_direction"] = candidate
        state["pending_count"] = 1
        state["pending_since"] = now.isoformat()
        state["pending_last_at"] = now.isoformat()
        return

    if last is None or (now - last).total_seconds() >= SIGNAL_CONFIRM_INTERVAL:
        state["pending_count"] = int(state.get("pending_count", 0)) + 1
        state["pending_last_at"] = now.isoformat()

    elapsed = (now - since).total_seconds() if since else 0
    if (state["pending_count"] >= SIGNAL_CONFIRM_READINGS
            and elapsed >= SIGNAL_CONFIRM_INTERVAL * (SIGNAL_CONFIRM_READINGS - 1)):
        state["active_direction"] = candidate
        state["active_since"] = now
        if state.get("first_direction") is None:
            state["first_direction"] = candidate
            state["first_signal_time"] = now
            state["first_signal_seconds"] = seconds_left
            state["first_signal_price"] = (get_yes_ask(market) if candidate == "UP"
                                           else get_no_ask(market))
        state["pending_direction"] = None
        state["pending_count"] = 0
        state["pending_since"] = None
        state["pending_last_at"] = None

engine=types.SimpleNamespace(**{n:globals()[n] for n in ['_valid_live_observation', '_plan_number', 'new_round_state', '_fetch_current_btc_candles', 'get_event_ticker_from_market', 'extract_kalshi_btc_price', '_indicator_frame', '_resample_indicators', 'add_indicators', 'get_target_from_market', 'get_seconds_remaining', 'numeric_kalshi_price', 'get_yes_ask', 'get_no_ask', '_internal_impulse_context', '_entry_route_checks', '_signal_engine_without_trace', '_retention_assessment', '_retention_supported', '_reset_withdrawal', '_review_active_retention', '_round_opening_crosscheck', '_confirmation_without_trace']})
import csv
import hashlib
import hmac
import io
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, quote
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
API = 'https://external-api.kalshi.com/trade-api/v2'
DEFAULTS = dict(contracts=1, max_entry_cents=60,
                take_profit_pct=90, stop_loss_pct=10,
                max_entries_round=1, daily_loss_dollars=25, daily_goal_dollars=50,
                max_trade_dollars=10, starting_balance=1000,
                fee_cents_per_contract=2, close_on_reverse=True)

def utcnow():
    return datetime.now(timezone.utc)

def stamp():
    return utcnow().isoformat()

def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, 'item'):
        return clean_json(value.item())
    return value

def dumps(value):
    return json.dumps(clean_json(value), ensure_ascii=False, allow_nan=False)

def valid_settings(raw):
    if not isinstance(raw, dict) or set(raw) != set(DEFAULTS):
        raise ValueError('Envía todos los ajustes; hay campos desconocidos o ausentes.')
    bounds = {'contracts':(1,1000), 'max_entry_cents':(2,99),
              'take_profit_pct':(0,100), 'stop_loss_pct':(0,100),
              'max_entries_round':(1,100),
              'daily_loss_dollars':(1,100000), 'daily_goal_dollars':(0,100000),
              'max_trade_dollars':(1,100000), 'starting_balance':(1,1000000),
              'fee_cents_per_contract':(0,20)}
    out = {}
    for key, (low, high) in bounds.items():
        v = raw[key]
        if isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or (key != 'max_trade_dollars' and int(v) != v) or not low <= v <= high:
            raise ValueError(f'Valor inválido para {key}: {low}–{high}.')
        out[key] = round(float(v), 2) if key == 'max_trade_dollars' else int(v)
    if not isinstance(raw['close_on_reverse'], bool):
        raise ValueError('El cierre por cambio de señal debe ser sí o no.')
    out['close_on_reverse'] = raw['close_on_reverse']
    return out

class MarketData:
    def __init__(self):
        self.candles = None
        self.candle_at = 0
        self.market = None
        self.retry_at = 0

    def get(self, path, params=None):
        if time.monotonic() < self.retry_at:
            raise ValueError('Kalshi en espera tras límite de consultas.')
        try:
            result = requests.get(API+path, params=params, timeout=7).json()
        except Exception as e:
            if getattr(e, 'code', None) == 429:
                self.retry_at = time.monotonic()+15
            raise
        if not isinstance(result, dict):
            raise ValueError('Respuesta Kalshi incompleta.')
        return result

    def current(self):
        now = utcnow()
        def eligible(m):
            try:
                end = datetime.fromisoformat(m['close_time'].replace('Z','+00:00'))
                start = datetime.fromisoformat(m['open_time'].replace('Z','+00:00'))
                return (str(m['ticker']).startswith('KXBTC15M-') and
                        m.get('status') in ('active','open') and start <= now < end and
                        0 < (end-now).total_seconds() <= 900)
            except (KeyError,ValueError,TypeError):
                return False
        if self.market and eligible(self.market):
            m = self.get('/markets/'+quote(self.market['ticker'],safe=''))['market']
        else:
            data = self.get('/markets', {'series_ticker':'KXBTC15M','limit':100,
                       'min_close_ts':int(now.timestamp()),'max_close_ts':int(now.timestamp())+901})
            options = sorted([x for x in data.get('markets',[]) if eligible(x)], key=lambda x:x['close_time'])
            if not options:
                raise ValueError('No hay ronda BTC 15 min abierta y verificable.')
            m = self.get('/markets/'+quote(options[0]['ticker'],safe=''))['market']
        if not eligible(m) or engine.get_target_from_market(m) is None:
            self.market = None
            raise ValueError('Ronda sin horario o target verificable; esperando.')
        self.market = m
        return m

    def signal(self, market):
        # Same sources and validations as app 61; no synthetic replacement.
        source = 'KALSHI LIVE'
        try:
            event = engine.get_event_ticker_from_market(market)
            live = self.get('/live_data/events/'+quote(event,safe=''), {'range':'15min'})
            price = engine.extract_kalshi_btc_price(live)
            if price is None:
                raise ValueError('Sin precio fechado.')
        except Exception:
            source = 'COINBASE'
            tick = requests.get('https://api.exchange.coinbase.com/products/BTC-USD/ticker',
                                params={'_':int(time.time())}, timeout=6).json()
            price = engine._valid_live_observation(tick.get('price'),tick.get('time'),'COINBASE')
        if self.candles is None or time.monotonic()-self.candle_at >= 5:
            self.candles = engine._fetch_current_btc_candles()
            self.candle_at = time.monotonic()
        age = (utcnow()-self.candles.iloc[-1]['time'].to_pydatetime()).total_seconds()
        if not -5 <= age <= 120:
            raise ValueError('Velas atrasadas: esperando actualización.')
        remaining = engine.get_seconds_remaining(market)
        sig = engine._signal_engine_without_trace(self.candles,engine.get_target_from_market(market),remaining,price)
        sig.update(price_source=source, data_valid=True)
        return sig

    def book(self, ticker):
        data = self.get('/markets/'+quote(ticker,safe='')+'/orderbook',{'depth':0})
        if 'orderbook_fp' in data:
            b = data['orderbook_fp']
            yes = self._levels(b.get('yes_dollars'), dollar=True)
            no = self._levels(b.get('no_dollars'), dollar=True)
        elif 'orderbook' in data:
            b = data['orderbook']
            yes = self._levels(b.get('yes'), dollar=False)
            no = self._levels(b.get('no'), dollar=False)
        else:
            raise ValueError('Libro de órdenes no reconocido.')
        # Bid on NO is an ask on YES at 1 - price, and conversely.
        return {'UP':{'bids':yes,'asks':sorted([(100-p,q) for p,q in no])},
                'DOWN':{'bids':no,'asks':sorted([(100-p,q) for p,q in yes])},
                'at':time.monotonic(), 'ticker':ticker}

    @staticmethod
    def _levels(levels, dollar):
        if levels is None:
            return []
        out = []
        for price, qty in levels:
            p = float(Decimal(str(price))*(100 if dollar else 1))
            q = float(qty)
            if not math.isfinite(p) or not math.isfinite(q) or not 0 <= p <= 100 or q < 0:
                raise ValueError('Profundidad inválida.')
            if q:
                out.append((p,q))
        return sorted(out, reverse=True)

def fill_book(levels, quantity, limit=None):
    """FOK simulation: entire size must exist; never infer fills from last price."""
    left = quantity
    total = 0.0
    for price, size in levels:
        if limit is not None and price > limit:
            continue
        take = min(left,size)
        total += take*price
        left -= take
        if left <= 1e-9:
            return total/quantity
    return None

def size_for_budget(levels, dollars, fee_cents, limit):
    """Spend the dollar budget on whole contracts, including simulated fees.

    Require enough depth to size the full budget; do not silently buy a tiny
    partial amount when the requested dollar amount cannot be filled.
    """
    remaining = Decimal(str(dollars)) * 100
    fee = Decimal(str(fee_cents))
    quantity = 0
    value = Decimal('0')
    last_unit = None
    for raw_price, raw_size in sorted(levels):
        price = Decimal(str(raw_price))
        if price > Decimal(str(limit)):
            continue
        unit = price + fee
        if unit <= 0:
            continue
        available = int(Decimal(str(raw_size)))
        if available <= 0:
            continue
        affordable = int(remaining // unit)
        if affordable == 0:
            break
        take = min(available, affordable)
        quantity += take
        value += price * take
        remaining -= unit * take
        last_unit = unit
        if take < available:
            break
    else:
        if last_unit is not None and remaining >= last_unit:
            return None
    if quantity == 0:
        return None
    return quantity, float(value / quantity)

class Bot:
    def __init__(self, db_path=None, feed=None):
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.feed = feed or MarketData()
        self.db = sqlite3.connect(str(db_path or os.environ.get('ALPHA_DB',ROOT/'data'/'alpha.sqlite3')), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS rounds(ticker TEXT PRIMARY KEY,state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS trades(
              id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, side TEXT NOT NULL, quantity INTEGER NOT NULL,
              entry REAL NOT NULL, entry_fee REAL NOT NULL, opened TEXT NOT NULL,
              exit REAL, exit_fee REAL, closed TEXT, reason TEXT, pnl REAL,
              tp INTEGER, sl INTEGER, exit_seconds INTEGER, reverse INTEGER);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at TEXT,kind TEXT,message TEXT);
        ''')
        columns={r[1] for r in self.db.execute('PRAGMA table_info(trades)')}
        for column in ('tp_pct','sl_pct','entry_evidence'):
            if column not in columns:
                self.db.execute('ALTER TABLE trades ADD COLUMN '+column+(' TEXT' if column=='entry_evidence' else ' REAL'))
        saved=self.kv('settings') or {}
        self.settings={key:saved.get(key,value) for key,value in DEFAULTS.items()}
        self.put('settings',self.settings)
        self.db.commit()
        self.running = False  # Never resumes buying after a server restart.
        self.close_requested = False
        self.snapshot = {'status':'INICIANDO','message':'Esperando la primera lectura verificada.', 'mode':'SIMULACIÓN', 'signal':None}
        self.thread = None
        self.event('SISTEMA','Servidor iniciado. Nuevas entradas pausadas; salidas siguen vigiladas.')

    def kv(self,key):
        r=self.db.execute('SELECT value FROM kv WHERE key=?',(key,)).fetchone()
        return json.loads(r[0]) if r else None

    def put(self,key,value):
        self.db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)',(key,dumps(value)))

    def event(self,kind,message):
        self.db.execute('INSERT INTO events(at,kind,message) VALUES (?,?,?)',(stamp(),kind,message))
        self.db.commit()

    def save_settings(self,raw):
        settings=valid_settings(raw)
        with self.lock:
            if settings['starting_balance'] != self.settings['starting_balance'] and self.db.execute('SELECT 1 FROM trades LIMIT 1').fetchone():
                raise ValueError('El saldo inicial ya tiene operaciones y no puede cambiarse.')
            self.settings=settings
            self.put('settings',settings)
            self.event('AJUSTES','Ajustes guardados; se aplican a entradas nuevas. Las posiciones conservan su plan de salida.')

    def command(self,name):
        with self.lock:
            if name=='start':
                self.running=True
                self.close_requested=False
            elif name=='pause':
                self.running=False
            elif name=='close':
                self.running=False
                self.close_requested=True
            else:
                raise ValueError('Comando desconocido.')
            self.snapshot.update(status='ACTIVO' if self.running else 'PAUSADO')
            self.event('CONTROL',{'start':'Simulación automática activada.','pause':'Entradas pausadas. Gestión de salidas activa.',
                                 'close':'Cierre solicitado; esperando liquidez actual. Entradas pausadas.'}[name])

    def positions(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM trades WHERE closed IS NULL')]

    def totals(self):
        rows=[dict(r) for r in self.db.execute('SELECT * FROM trades')]
        realized=sum(r['pnl'] or 0 for r in rows)
        cash=self.settings['starting_balance']+sum((r['exit']*r['quantity']/100-(r['exit_fee'] or 0)) if r['closed'] else 0 for r in rows)-sum(r['entry']*r['quantity']/100+r['entry_fee'] for r in rows)
        day=utcnow().astimezone(ZoneInfo('America/New_York')).date()
        daily=sum(r['pnl'] or 0 for r in rows if r['closed'] and datetime.fromisoformat(r['closed']).astimezone(ZoneInfo('America/New_York')).date()==day)
        open_fee=sum(r['entry_fee'] for r in rows if not r['closed'] and datetime.fromisoformat(r['opened']).astimezone(ZoneInfo('America/New_York')).date()==day)
        # Count known fees immediately, without waiting for settlement.
        daily-=open_fee
        return dict(cash=round(cash,4), realized=round(realized,4), daily=round(daily,4),
                    completed=sum(bool(r['closed']) for r in rows), wins=sum((r['pnl'] or 0)>0 for r in rows),
                    open_cost=round(sum(r['entry']*r['quantity']/100 for r in rows if not r['closed']),4))

    def _close(self,p,price,reason,settlement=False):
        fee=0 if settlement else self.settings['fee_cents_per_contract']*p['quantity']/100
        pnl=(price-p['entry'])*p['quantity']/100-p['entry_fee']-fee
        cur=self.db.execute('UPDATE trades SET exit=?,exit_fee=?,closed=?,reason=?,pnl=? WHERE id=? AND closed IS NULL',
                            (price,fee,stamp(),reason,pnl,p['id']))
        if cur.rowcount:
            self.db.execute('INSERT INTO events(at,kind,message) VALUES (?,?,?)',
                            (stamp(),'SALIDA',f"#{p['id']} {p['side']} · {reason} · neto simulado ${pnl:.2f}"))
        self.db.commit()

    def settle(self):
        # Settlement uses the official result; never the local BTC/target comparison.
        with self.lock:
            positions=self.positions()
        for p in positions:
            try:
                m=self.feed.get('/markets/'+quote(p['ticker'],safe=''))['market']
                if m.get('status')=='finalized' and m.get('result') in ('yes','no') and not m.get('is_provisional',False):
                    won=(p['side']=='UP')==(m['result']=='yes')
                    with self.lock:
                        self._close(p,100 if won else 0,'LIQUIDACIÓN OFICIAL',True)
            except Exception:
                continue  # Position remains open/pending, not guessed.

    def manage(self,p,book,signal,remaining):
        if book['ticker']!=p['ticker'] or time.monotonic()-book['at']>5:
            return
        bids=book[p['side']]['bids']
        price=fill_book(bids,p['quantity'])
        if price is None:
            return
        paid=p['entry']*p['quantity']/100+p['entry_fee']
        net=(price-p['entry'])*p['quantity']/100-p['entry_fee']-self.settings['fee_cents_per_contract']*p['quantity']/100
        roi=net/paid*100 if paid>0 else 0
        reason=None
        if self.close_requested:
            reason='CIERRE MANUAL'
        elif (p.get('tp_pct') is not None and p['tp_pct'] and price+1e-9>=p['tp_pct']) or (p.get('tp_pct') is None and p['tp'] and price>=p['entry']+p['tp']):
            reason='TAKE PROFIT'
        elif (p.get('sl_pct') is not None and p['sl_pct'] and roi<=-p['sl_pct']+1e-9) or (p.get('sl_pct') is None and p['sl'] and price<=p['entry']-p['sl']):
            reason='STOP LOSS'
        elif p['reverse'] and signal in ('UP','DOWN') and signal!=p['side']:
            reason='CAMBIO DE SEÑAL'
        if reason:
            self._close(p,price,reason)

    def enter(self,market,book,side,remaining,signal=None):
        s=self.settings
        if not self.running or self.close_requested or self.positions() or side not in ('UP','DOWN'):
            return 'Entradas pausadas o posición en gestión.'
        # Retaining a displayed direction is not permission for a new entry.
        # Recheck every route using the current signal, including level vetoes.
        if not signal or signal.get('data_valid') is not True or signal.get('candidate') != side:
            return 'Esperando respaldo actual para una compra nueva.'
        current_routes = engine._entry_route_checks(signal, engine.get_seconds_remaining(market))
        if not current_routes.get('valid') or not any(r['complete'] for r in current_routes.get('sides', {}).get(side, [])):
            return 'La señal conservada ya no cumple los requisitos actuales de entrada.'
        if book['ticker']!=market['ticker'] or time.monotonic()-book['at']>5:
            return 'Libro atrasado; esperando datos actuales.'
        # Remaining recalculated after every network request.
        actual=engine.get_seconds_remaining(market)
        if actual is None or actual<=0:
            return 'Fuera de ventana de entrada.'
        total=self.totals()
        if total['daily']<=-s['daily_loss_dollars']:
            return 'Límite diario de pérdida alcanzado.'
        if s['daily_goal_dollars'] and total['daily']>=s['daily_goal_dollars']:
            return 'Meta diaria alcanzada.'
        count=self.db.execute('SELECT COUNT(*) FROM trades WHERE ticker=?',(market['ticker'],)).fetchone()[0]
        if count>=s['max_entries_round']:
            return 'Máximo de entradas de esta ronda alcanzado.'
        budget=s['max_trade_dollars']
        if Decimal(str(total['cash'])) < Decimal(str(budget)):
            return 'Saldo virtual insuficiente para el importe configurado.'
        sized=size_for_budget(book[side]['asks'],budget,s['fee_cents_per_contract'],s['max_entry_cents'])
        if sized is None:
            return 'Sin liquidez suficiente para el importe configurado dentro del precio máximo.'
        quantity,price=sized
        fee=quantity*s['fee_cents_per_contract']/100
        cost=price*quantity/100+fee
        if cost>budget+1e-8 or cost>total['cash']+1e-8:
            return 'La compra supera el importe o el saldo virtual disponible.'
        entry_cursor=self.db.execute('INSERT INTO trades(ticker,side,quantity,entry,entry_fee,opened,tp,sl,exit_seconds,reverse,tp_pct,sl_pct) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (market['ticker'],side,quantity,price,fee,stamp(),0,0,0,s['close_on_reverse'],s['take_profit_pct'],s['stop_loss_pct']))
        evidence={"engine_revision":STRUCTURE_ENGINE_REVISION,"side":side,
                  "candidate":signal.get("candidate"),"route":signal.get("quality"),
                  "price_source":signal.get("price_source"),"remaining":remaining,
                  "structure":signal.get("structure_internal"),
                  "checks":current_routes["sides"].get(side,[])}
        self.db.execute('UPDATE trades SET entry_evidence=? WHERE id=?',
                        (dumps(evidence),entry_cursor.lastrowid))
        self.event('ENTRADA',f"{side} · {quantity} contrato(s) · Compró ${cost:.2f} incluyendo comisión · {price:.2f}¢ · ejecución simulada FOK")
        return 'Compra simulada ejecutada.'

    def step(self):
        self.settle()
        # Existing positions are managed even if market discovery or candles fail.
        with self.lock:
            old_positions=self.positions()
        for p in old_positions:
            try:
                m=self.feed.get('/markets/'+quote(p['ticker'],safe=''))['market']
                rem=engine.get_seconds_remaining(m)
                if m.get('status') in ('active','open') and rem is not None and rem>0:
                    b=self.feed.book(p['ticker'])
                    with self.lock:
                        self.manage(p,b,None,engine.get_seconds_remaining(m))
            except Exception:
                pass
        market=self.feed.current()
        sig=self.feed.signal(market)
        signal_at=time.monotonic()
        book=self.feed.book(market['ticker'])
        remaining=engine.get_seconds_remaining(market)
        if remaining is None or remaining<=0 or time.monotonic()-signal_at>5:
            raise ValueError('Lectura vencida durante la consulta; esperando ronda actual.')
        with self.lock:
            row=self.db.execute('SELECT state FROM rounds WHERE ticker=?',(market['ticker'],)).fetchone()
            state=json.loads(row[0]) if row else engine.new_round_state(market['ticker'],remaining)
            engine._confirmation_without_trace(state,sig.get('candidate'),market,remaining,utcnow(),sig)
            self.db.execute('INSERT OR REPLACE INTO rounds VALUES (?,?)',(market['ticker'],dumps(state)))
            self.db.commit()
            active=state.get('active_direction')
            had_position=bool(self.positions())
            for p in self.positions():
                if p['ticker']==market['ticker']:
                    self.manage(p,book,active,remaining)
            # Do not reuse the same liquidity snapshot for both a close and a new buy.
            message=self.enter(market,book,active,remaining,signal=sig) if not had_position else 'Gestión de posición abierta.'
            if not self.positions() and self.close_requested:
                self.close_requested=False
            if active is None:
                message=state.get('opening_conflict') or 'El cerebro todavía no confirma una dirección.'
            self.snapshot={'status':'ACTIVO' if self.running else 'PAUSADO','message':message,
                           'mode':'SIMULACIÓN','signal':active,'candidate':sig.get('candidate'),
                           'first_signal':state.get('first_direction'),'market':market,'seconds_left':remaining,
                           'price':sig['price'],'source':sig['price_source'],'quality':sig['quality'],
                           'rsi':sig['rsi'],'ema':sig['ema'],'metrics':clean_json(sig),'updated':stamp(),
                           'book':book,'target':engine.get_target_from_market(market),
                           'retention':state.get('retention_warning')}

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.step()
            except Exception as e:
                with self.lock:
                    self.snapshot.update(status='SIN DATOS',message=f'{type(e).__name__}: {e}',signal=None)
                    # Previous observation remains displayed with its original timestamp.
            self.stop_event.wait(2)

    def start_worker(self):
        self.thread=threading.Thread(target=self.loop,name='alpha-paper-worker',daemon=True)
        self.thread.start()

    def view(self):
        with self.lock:
            result=dict(self.snapshot)
            result.update(running=self.running,close_requested=self.close_requested,settings=self.settings.copy(),
                          positions=self.positions(),totals=self.totals(),
                          trades=[dict(r) for r in self.db.execute('SELECT * FROM trades ORDER BY id DESC LIMIT 200')],
                          events=[dict(r) for r in self.db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 60')])
            result['rounds']=[{'ticker':r['ticker'],**json.loads(r['state'])} for r in self.db.execute('SELECT * FROM rounds ORDER BY rowid DESC LIMIT 50')]
            return clean_json(result)


_TERMINAL_HTML = r"""

<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alpha Edge · Terminal</title>
<style>
:root{--bg:#080e22;--panel:#101b3d;--blue:#193c89;--gold:#efc864;--text:#edf3ff;--muted:#a6b8df;--line:#687aa8;--green:#45edbe}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(ellipse at 45% 5%,#243e83 0,#101b3e 38%,#070c1c 100%);color:var(--text);font:13px Arial,sans-serif}
button,input,select{font:inherit}
button{cursor:pointer;color:var(--text);border:1px solid #7790c8;background:linear-gradient(#294c94,#142958);border-radius:5px;padding:10px 14px}
button:hover{filter:brightness(1.25)}
button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.app{max-width:1600px;margin:auto;display:grid;grid-template-columns:190px minmax(0,1fr);min-height:100vh;padding:12px;gap:14px}
.sidebar{border:1px solid #6176a6;background:linear-gradient(135deg,#142753,#080e23);padding:18px 10px;display:flex;flex-direction:column;gap:8px;box-shadow:inset 0 0 20px #263d6f}
.brand{text-align:center;color:var(--gold);font-size:23px;font-weight:900;letter-spacing:1px}
.jc-brand-logo{display:block;width:156px;max-width:100%;height:auto;margin:0 auto;object-fit:contain}
@media(max-width:600px){.jc-brand-logo{width:112px}}
.brand small{display:block;color:var(--muted);font-size:9px;letter-spacing:3px;margin-top:5px}
.tag{display:inline-block;font-size:10px;color:var(--green);border:1px solid #2a9e87;padding:5px 8px;border-radius:3px}
.side-state{display:flex;justify-content:space-between;margin:18px 0 10px;font-size:10px}
.nav{display:flex;flex-direction:column;gap:7px}
.nav button{text-align:left;text-transform:uppercase;font-weight:700;font-size:11px;padding:12px 10px}
.nav button.active{color:var(--gold);border-color:var(--gold);background:linear-gradient(100deg,#5a492a,#1e2540)}
.nav button span{color:#90a9da;display:inline-block;width:24px}
.mini-radar{width:110px;height:110px;border:2px solid var(--gold);border-radius:50%;margin:30px auto 10px;display:grid;place-content:center;background:repeating-radial-gradient(circle,#15295a 0 20px,#476899 21px 22px);box-shadow:0 0 30px #183a7e}
.mini-radar strong{color:var(--gold);font-size:25px;text-align:center}
.mini-radar small{text-align:center;font-size:9px}
.sidebar footer{margin-top:auto;border-top:1px solid #354975;padding-top:18px;color:var(--muted);font-size:10px;line-height:1.8}
.topbar{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--gold);background:linear-gradient(100deg,#234483,#131e3d);padding:13px 18px;gap:14px;border-radius:5px;box-shadow:0 4px 15px #020612}
.topbar small,.label{font-size:9px;letter-spacing:1px;color:var(--muted);display:block;margin-bottom:6px}
.topbar strong{font-size:12px}
.demo{margin:12px 0;color:#f9db8e;background:#45391f80;border:1px solid #8d7741;padding:9px 13px;border-radius:4px;font-size:11px}
.section-title{background:linear-gradient(100deg,#254c9b,#131d3d);padding:12px 15px;border:1px solid #788bc0;margin:14px 0 12px;border-radius:5px;font-weight:bold;text-transform:uppercase;letter-spacing:1px}
.section-title b{color:var(--gold);margin-right:15px}
.panel{border:1px solid var(--line);border-left:3px solid var(--gold);background:linear-gradient(145deg,#1a3472aa,#0b132c 70%);border-radius:8px;box-shadow:inset 0 0 24px #112452,0 4px 12px #0005;overflow:hidden}
.panel h2{margin:0;padding:12px 16px;font-size:11px;text-transform:uppercase;letter-spacing:1.2px;color:var(--gold);border-bottom:1px solid #3b5487}
.body{padding:17px}
.summary{display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:12px}
.radar-panel{text-align:center;position:relative}
.radar-sub{font-size:10px;color:var(--muted);margin:10px}
.radar{position:relative;margin:25px auto;width:min(340px,76%);aspect-ratio:1;border-radius:50%;border:2px solid var(--gold);background:repeating-radial-gradient(circle,transparent 0 17%,#6985b3 17.4% 17.8%,transparent 18.2% 23%),conic-gradient(from 275deg,#1ca4bd77,transparent 60deg),radial-gradient(circle,#18316b,#08172e);box-shadow:0 0 0 6px #09142b,0 0 0 7px #5b78ab,0 0 30px #0e6abc66}
.radar:before,.radar:after{content:'';position:absolute;background:#708bb565}
.radar:before{width:1px;height:100%;left:50%}
.radar:after{height:1px;width:100%;top:50%;left:0}
.sweep{position:absolute;inset:0;border-radius:50%;background:conic-gradient(from 0deg,transparent 290deg,#34d7cd22 330deg,#9fffea99 359deg,transparent 360deg);animation:sweep 12s linear infinite}
.radar.paused .sweep{animation-play-state:paused}
@keyframes sweep{to{transform:rotate(360deg)}
}

.profit-orbit{position:absolute;inset:-10px;width:calc(100% + 20px);height:calc(100% + 20px);pointer-events:none;z-index:4;opacity:0;transition:opacity .35s}
.profit-orbit-track{fill:none;stroke:#34d39922;stroke-width:2.5}
.profit-orbit-value{fill:none;stroke:#34d399;stroke-width:2.5;stroke-linecap:round;stroke-dasharray:100;stroke-dashoffset:100;transform:rotate(-90deg);transform-origin:60px 60px;filter:drop-shadow(0 0 3px #34d399);transition:stroke-dashoffset .7s ease}
@media(prefers-reduced-motion:reduce){.profit-orbit,.profit-orbit-value{transition:none}}
.radar-core{position:absolute;inset:35%;border:1px solid var(--gold);border-radius:50%;background:radial-gradient(#1a335c,#080d1e);display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:2;box-shadow:0 0 25px #071327}
.radar-core b{font-size:clamp(14px,2.3vw,25px);color:var(--gold);letter-spacing:1px}
.radar-core small{font-size:9px;letter-spacing:2px}
.rnum{position:absolute;color:#dbe5ff;font-size:10px;z-index:3}
.n{top:8px;left:48%}
.s{bottom:8px;left:48%}
.e{right:8px;top:48%}
.w{left:8px;top:48%}
.radar-meta{display:flex;justify-content:space-between;gap:8px;padding:0 16px 15px}
.chip{border:1px solid #6889bf;padding:8px 12px;background:#102b55;font-size:10px;border-radius:3px}
.chip b{display:block;margin-top:5px;color:var(--green)}
.position{text-align:center;display:flex;flex-direction:column;justify-content:center;min-height:340px}
.position-money{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start}.position-money>div{min-width:0}.position .position-money .amount{font-size:clamp(20px,3vw,32px);overflow-wrap:anywhere}.position .amount{font-size:42px;font-weight:bold;margin:30px 0 4px}
.muted{color:var(--muted)}
.position hr{border:0;border-top:1px solid #354d79;width:80%;margin:22px auto}
.position strong{font-size:12px}
.performance{margin-top:12px}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.metrics strong{font-size:24px}
.gold{color:var(--gold)}
.green{color:var(--green)}
.controls{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:13px 0}
.controls button{padding:14px;font-weight:bold}
.danger{background:linear-gradient(#c34a55,#78212b);border-color:#fc8490}
.primary{background:linear-gradient(#ddbc6a,#8a682a);color:#101a30;border-color:#ffe29a}
.settings-grid{display:grid;grid-template-columns:1.15fr 1fr;gap:12px}
.field{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:11px 0;border-bottom:1px solid #314369}
.field label{font-size:11px;color:#e2eaff}
.field small{display:block;color:var(--muted);font-size:10px;margin-top:4px}
input[type=number],input[type=text],input[type=password],select{width:110px;background:#090f23;border:1px solid #a58d52;color:#fff;padding:9px;border-radius:4px}
input[type=checkbox]{accent-color:#43e7b3;width:19px;height:19px}
input[type=range]{accent-color:var(--gold);width:100%}
.wide{width:100%!important}
.save{width:100%;margin-top:15px}
.table-wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:11px;white-space:nowrap}
th,td{text-align:left;padding:14px 12px;border-bottom:1px solid #2c4068}
th{color:var(--muted);font-size:9px;text-transform:uppercase}
.empty{text-align:center;color:var(--muted);padding:50px 20px}
.hidden{display:none!important}
.notice{padding:16px;border:1px solid #4a638d;margin-top:12px;line-height:1.6;color:var(--muted);font-size:11px;border-radius:5px}
.toast{position:fixed;right:20px;bottom:20px;background:#163f3b;color:#b9ffe6;border:1px solid #4ce4b6;padding:15px 25px;border-radius:6px;z-index:10;box-shadow:0 6px 30px #0008}
.strength{height:8px;border-radius:5px;background:#0b1630;margin:15px 0;overflow:hidden}
.strength i{display:block;height:100%;width:0;background:var(--gold)}
.top-controls{display:flex;align-items:center;justify-content:space-between}
.mobile-brand{display:none}
@media(max-width:850px){.app{grid-template-columns:145px minmax(0,1fr);gap:9px;padding:8px}
.brand{font-size:18px}
.summary{grid-template-columns:1fr 180px}
.position .amount{font-size:30px}
.settings-grid{grid-template-columns:1fr}
.metrics{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:600px){.app{display:block;padding:8px}
.sidebar{padding:10px;margin-bottom:10px}
.brand{font-size:19px}
.side-state,.mini-radar,.sidebar footer{display:none}
.nav{flex-direction:row;overflow-x:auto;margin-top:12px;gap:6px}
.nav button{flex-shrink:0;padding:10px;font-size:10px}
.nav button span{width:18px}
.topbar{grid-template-columns:1fr 1fr;padding:12px;gap:15px}
.summary{grid-template-columns:1fr}
.position{min-height:190px}
.position .amount{margin-top:18px}
.position hr{margin:14px auto}
.radar{width:240px;max-width:78%;margin:22px auto}
.controls{gap:6px}
.controls button{font-size:10px;padding:13px 5px}
.metrics strong{font-size:22px}
.radar-meta{padding:0 10px 14px}
.chip{padding:8px;font-size:9px}
}
@media(prefers-reduced-motion:reduce){.sweep{animation:none}
}

</style>
</head>
<body>
<div class="app">
<aside class="sidebar">
<div class="brand"><img class="jc-brand-logo" src="data:image/webp;base64,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" alt="JC ALPHA EDGE" width="156" height="156"><small>PRECISIÓN · CONTROL</small>
</div>
<div class="side-state">
<span class="muted">ESTADO</span>
<span class="tag" id="sideStatus">PAUSADO</span>
</div>
<nav class="nav">
<button class="active" data-page="resumen">
<span>◈</span>Resumen</button>
<button data-page="operacion">
<span>⚙</span>Operación</button>
<button data-page="entradas">
<span>↗</span>Entradas</button>
<button data-page="registro">
<span>▤</span>Registro</button>
<button data-page="senal">
<span>◎</span>Señal</button>
<button data-page="conexion">
<span>⌁</span>Conexión</button>
</nav>
<div class="mini-radar">
<strong>0%</strong>
<small>OBJETIVO DIARIO</small>
</div>
<footer>
<span class="gold">ENTORNO DE SIMULACIÓN</span>
<br>BTC · Rondas de 15 minutos<br>Cuenta de prueba individual<br>
<span class="green"><span id="feedStatus">● Esperando datos</span></span>
</footer>
</aside>
<main>
<header class="topbar">
<div>
<small>ESTADO DEL BOT</small>
<strong id="status">PAUSADO</strong>
</div>
<div>
<small>MERCADO</small>
<strong>BTC · 15 MINUTOS</strong>
</div>
<div>
<small>SESIÓN</small>
<strong><span id="sessionTime">HORA DE MIAMI</span></strong>
</div>
<div>
<small>MODO</small>
<strong class="green">● SIMULACIÓN</strong>
</div>
</header>
<div class="demo"><span id="liveMessage">Conectando el motor con Kalshi y Coinbase…</span></div>
<div class="section-title">
<b id="pageNum">01</b>
<span id="pageTitle">Resumen</span>
</div>
<section id="resumen" class="page">
<div class="summary">
<article class="panel radar-panel">
<h2>Radar de sesión</h2>
<p class="radar-sub">Lectura de mercado · Confirmación · Ejecución</p>
<div class="top-controls body" style="padding-top:0;padding-bottom:0">
<span class="chip">MERCADO<span class="gold" id="marketLabel"> · ESPERANDO</span>
</span>
<span class="chip">LÍMITE DE ENTRADA <b id="entryLimit">60 ¢</b>
</span>
</div>
<div class="radar paused" id="radar">
<svg class="profit-orbit" id="profitOrbit" viewBox="0 0 120 120" role="progressbar" aria-label="Ganancia hacia el Take Profit" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" aria-hidden="true">
<circle class="profit-orbit-track" cx="60" cy="60" r="57"/>
<circle class="profit-orbit-value" id="profitOrbitValue" cx="60" cy="60" r="57" pathLength="100"/>
</svg>
<div class="sweep">
</div>
<span class="rnum n">00</span>
<span class="rnum e">15</span>
<span class="rnum s">30</span>
<span class="rnum w">45</span>
<div class="radar-core">
<b id="radarSignal">ALPHA</b>
<small id="radarMode">EDGE</small>
</div>
</div>
<div class="radar-meta">
<span class="chip">DIRECCIÓN<b id="activeSignal">ESPERANDO</b>
</span>
<span class="chip">PRIMERA SEÑAL<b id="firstSignal">—</b>
</span>
<span class="chip">RONDA<b id="roundClock">— / 15:00</b>
</span>
</div>
</article>
<article class="panel">
<h2>Posición</h2>
<div class="position">
<div class="position-money">
<div><span class="label">PAGÓ</span><div class="amount" id="positionPaid">$0.00</div></div>
<div><span class="label">GANANCIA / PÉRDIDA ACTUAL</span><div class="amount" id="unrealized">—</div></div>
</div>
<span class="muted" id="positionNote">Sin operaciones</span>
<hr>
<strong id="openContracts" hidden>0 CONTRATOS</strong>
<hr>
<strong class="gold" id="positionSide">SIN POSICIÓN</strong>
</div>
</article>
</div>
<article class="panel performance">
<h2>Performance</h2>
<div class="body metrics">
<div>
<span class="label">RESULTADO DEL DÍA</span>
<strong data-metric="result">$0.00</strong>
</div>
<div>
<span class="label">GANANCIA REALIZADA</span>
<strong data-metric="result">$0.00</strong>
</div>
<div>
<span class="label">META DIARIA</span>
<strong class="gold" id="goalDisplay">$50</strong>
</div>
<div>
<span class="label">PROGRESO DE LA META</span>
<div class="strength">
<i>
</i>
</div>
<small class="muted" id="progressText">0% · Sin operaciones</small>
</div>
</div>
</article>
<div class="controls">
<button class="primary" id="start">▶ INICIAR SIMULACIÓN</button>
<button id="pause">Ⅱ PAUSAR</button>
<button class="danger" id="close">□ CERRAR TODO</button>
</div>
<div class="notice"><span id="radarNotice">El radar sigue las señales confirmadas. Pausar entradas conserva la gestión de salidas.</span></div>
</section>
<section id="operacion" class="page hidden">
<article class="panel" style="margin-bottom:12px">
<h2>Plan de operación</h2>
<div class="body">
<div class="top-controls">
<span>BTC · 15 minutos</span>
<span class="gold"><span id="savedState">AJUSTES DEL SERVIDOR</span></span>
</div>
<div class="strength">
<i style="width:100%">
</i>
</div>
<div class="metrics">
<span>01 · Lectura</span>
<span>02 · Señal</span>
<span>03 · Entrada</span>
<span>04 · Salida</span>
</div>
</div>
</article>
<form id="settings">
<div class="settings-grid">
<article class="panel">
<h2>Control principal</h2>
<div class="body">
<div class="field">
<label>Saldo de simulación<small><span id="cashLabel">Saldo inicial virtual</span></small>
</label>
<input type="number" name="balance" value="1000" min="1" max="1000000" required>
</div>
<div class="field">
<label>Meta diaria ($)</label>
<input type="number" name="goal" value="50" min="0" required>
</div>
<div class="field">
<label>Límite de pérdida diaria ($)</label>
<input type="number" name="loss" value="25" min="1" required>
</div>
<input type="hidden" name="contracts" value="1">
<div class="field">
<label>Importe a comprar ($)</label>
<input type="number" name="maxTrade" value="10" min="1" max="100000" step="0.01" required>
</div>
<div class="field">
<label>Máximo de entradas por ronda</label>
<input type="number" name="entries" value="1" min="1" max="100" required>
</div>
</div>
</article>
<article class="panel">
<h2>Precios y protección</h2>
<div class="body">

<div class="field">
<label>Precio máximo de compra (¢)</label>
<input type="number" name="maxEntry" value="60" min="1" max="99" required>
</div>
<div class="field">
<label>Tomar profit (%)<small>Nivel del contrato: 90% = vender a 90¢ o más; requiere liquidez suficiente.</small></label>
<select name="tp"><option value="0">Desactivado</option><option value="80">80%</option><option value="85">85%</option><option value="90">90%</option><option value="95">95%</option></select>
</div>
<div class="field">
<label>Stop loss (%)<small>Porcentaje de pérdida sobre lo pagado; 0 desactiva.</small></label>
<select name="sl"><option value="0">Desactivado</option><option value="5">−5%</option><option value="10">−10%</option><option value="15">−15%</option><option value="20">−20%</option><option value="25">−25%</option><option value="30">−30%</option><option value="40">−40%</option><option value="50">−50%</option><option value="60">−60%</option><option value="70">−70%</option><option value="80">−80%</option><option value="85">−85%</option><option value="90">−90%</option><option value="95">−95%</option><option value="100">−100%</option></select>
</div>

<div class="field">
<label>Cerrar por señal contraria<small>Ajuste de salida; no fija la dirección del cerebro</small>
</label>
<input type="checkbox" name="reverse" checked>
</div>
<input type="hidden" name="fee" value="2">
</div>
</article>
</div>
<button type="submit" class="primary save">GUARDAR Y APLICAR AJUSTES</button>
</form>
<div class="notice">Los ajustes se guardan en el servidor y se aplican a compras nuevas. Las posiciones abiertas conservan su plan de salida.</div>
</section>
<section id="entradas" class="page hidden">
<article class="panel">
<h2>Entradas de la sesión <button id="exportCSV" style="float:right;padding:4px 10px;font-size:10px">EXPORTAR CSV</button></h2>
<div class="table-wrap">
<table>
<thead>
<tr>
<th>Hora</th>
<th>Ronda</th>
<th>Dirección</th>
<th>Contratos</th>
<th>Precio</th>
<th>Estado</th>
</tr>
</thead><tbody id="entriesRows"></tbody>
</table>
</div>
<div class="empty" id="entriesEmpty">Sin entradas. Activa la simulación para comenzar.</div>
</article>
</section>
<section id="registro" class="page hidden">
<article class="panel">
<h2>Registro de operaciones y eventos</h2>
<div class="table-wrap">
<table>
<thead>
<tr>
<th>Hora local</th>
<th>Acción</th>
<th>Detalle</th>
</tr>
</thead>
<tbody id="logs">
</tbody>
</table>
</div>
</article>
</section>
<section id="senal" class="page hidden">
<div class="settings-grid">
<article class="panel">
<h2>Lectura del cerebro</h2>
<div class="body">
<div class="empty">
<div class="gold" style="font-size:28px;margin-bottom:15px"><span id="signalTitle">ESPERANDO DATOS</span></div><span id="signalDetail">El motor está arrancando.</span></div>
<div class="field">
<label>Dirección actual</label>
<strong id="signalDirection">—</strong>
</div>
<div class="field">
<label>Primera señal de la ronda</label>
<strong id="signalFirst">—</strong>
</div>
<div class="field">
<label>Precio de BTC</label>
<strong id="btcPrice">—</strong>
</div>
<div class="field">
<label>Objetivo de la ronda</label>
<strong id="targetPrice">—</strong>
</div>
</div>
</article>
<article class="panel">
<h2>Indicadores</h2>
<div class="body">
<div class="field">EMA 9 / EMA 21<strong id="emaValue">—</strong>
</div>
<div class="field">RSI 14<strong id="rsiValue">—</strong>
</div>
<div class="field">Momentum<strong id="momentumValue">—</strong>
</div>
<div class="field">Volumen relativo<strong id="volumeValue">—</strong>
</div>
<div class="notice"><span id="indicatorNote">Indicadores del cerebro original. No son probabilidades calibradas.</span></div>
</div>
</article>
</div>
</section>
<section id="conexion" class="page hidden">
<article class="panel">
<h2>Conexión Kalshi</h2>
<div class="body">
<p class="muted">Los datos públicos funcionan sin clave. Puedes verificar una API de Kalshi Demo; no habilita órdenes reales.</p>
<div class="field">
<label>Entorno</label>
<select id="connectionMode"><option value="public">Simulación local</option><option value="demo">Kalshi Demo · lectura</option></select>
</div>
<div class="field">
<label>API Key ID</label>
<input id="apiKey" class="wide" style="max-width:360px" type="text" placeholder="API Key ID de Demo" autocomplete="off">
</div>
<div class="field">
<label>Clave privada</label>
<textarea id="privateKey" class="wide" style="max-width:360px;min-height:100px;background:#090f23;color:white;border:1px solid #a58d52;padding:9px" placeholder="Clave privada PEM de Demo" spellcheck="false" autocomplete="off"></textarea>
</div>
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:15px"><button id="testPublic">VERIFICAR DATOS</button><button id="testApi" class="primary">VERIFICAR API DEMO</button><button id="forgetApi">LIMPIAR CREDENCIALES</button></div><div class="notice"><span id="connectionNotice">Consultando conexión pública…</span></div>
</div>
</article>
</section>
</main>
</div>
<div class="toast hidden" id="toast" role="status">
</div>
<script>
const $=s=>document.querySelector(s),esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>v==null?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(v),cents=v=>v==null?'—':Number(v).toFixed(1)+'¢';
const localtime=v=>v?new Date(v).toLocaleTimeString('es-US',{timeZone:'America/New_York',hour12:true}):'—';
const names={balance:'starting_balance',goal:'daily_goal_dollars',loss:'daily_loss_dollars',contracts:'contracts',maxTrade:'max_trade_dollars',entries:'max_entries_round',maxEntry:'max_entry_cents',tp:'take_profit_pct',sl:'stop_loss_pct',reverse:'close_on_reverse',fee:'fee_cents_per_contract'};
const titles={resumen:'Resumen',operacion:'Operación y ajustes',entradas:'Entradas',registro:'Registro',senal:'Señal',conexion:'Conexión'};
let dirty=false,loaded=false,current=null,pending=null,sequence=0,acknowledged=new Set(),endAt=null;
function post(type,extra={}){window.parent.postMessage({isStreamlitMessage:true,type,...extra},'*')}
let lastHeight=0;function height(){let h=Math.max(650,document.documentElement.scrollHeight);if(h!==lastHeight){lastHeight=h;post('streamlit:setFrameHeight',{height:h})}}
function toast(msg){$('#toast').textContent=msg;$('#toast').classList.remove('hidden');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$('#toast').classList.add('hidden'),4500)}
function busy(on){for(const s of ['#start','#pause','#close','#testPublic','#testApi','#forgetApi','#exportCSV','#settings button[type=submit]'])$(s).disabled=on}
function action(action,payload={}){if(pending){toast('Esperando confirmación del servidor.');return}let id=Date.now()+'-'+(++sequence)+'-'+Math.random().toString(36).slice(2);pending=id;busy(true);post('streamlit:setComponentValue',{value:{id,action,payload},dataType:'json'});setTimeout(()=>{if(pending===id){pending=null;busy(false);toast('Sin confirmación del servidor. Revisa Registro antes de repetir.')}},25000)}
document.querySelectorAll('[data-page]').forEach((b,i)=>b.onclick=()=>{document.querySelectorAll('.page').forEach(p=>p.classList.add('hidden'));$('#'+b.dataset.page).classList.remove('hidden');document.querySelectorAll('[data-page]').forEach(n=>n.classList.remove('active'));b.classList.add('active');$('#pageTitle').textContent=titles[b.dataset.page];$('#pageNum').textContent=String(i+1).padStart(2,'0');height()});
$('#start').onclick=()=>action('command',{command:'start'});$('#pause').onclick=()=>action('command',{command:'pause'});$('#close').onclick=()=>{if(confirm('¿Pausar compras y solicitar cerrar todas las posiciones simuladas?'))action('command',{command:'close'})};
const form=$('#settings');form.oninput=()=>{dirty=true;$('#savedState').textContent='CAMBIOS SIN GUARDAR'};
form.onsubmit=e=>{e.preventDefault();let cfg={};for(const [name,key]of Object.entries(names)){let el=form.elements[name];cfg[key]=el.type==='checkbox'?el.checked:Number(el.value)}action('settings',cfg)};
$('#testPublic').onclick=()=>action('public');$('#testApi').onclick=()=>{if($('#connectionMode').value!=='demo'){toast('Selecciona Kalshi Demo para verificar tu API.');return}action('verify_demo',{key_id:$('#apiKey').value.trim(),pem:$('#privateKey').value});$('#privateKey').value=''};
$('#forgetApi').onclick=()=>{$('#apiKey').value='';$('#privateKey').value='';action('forget_demo')};$('#exportCSV').onclick=()=>action('export');
function profitRingProgress(positions,net,marked,fresh,fee){
 if(!fresh||!marked||!positions.length||!Number.isFinite(net))return null;
 let target=0;
 for(const p of positions){
  const paid=p.entry*p.quantity/100+p.entry_fee;
  let goal=p.tp_pct!=null?(p.tp_pct>0?(p.tp_pct-p.entry)*p.quantity/100-p.entry_fee-fee*p.quantity/100:0):(p.tp>0?p.tp*p.quantity/100-p.entry_fee-fee*p.quantity/100:0);
  if(!Number.isFinite(goal)||goal<=0)return null;
  target+=goal;
 }
 return Math.max(0,Math.min(100,net/target*100));
}
function updateProfitRing(s,net,marked,fresh){
 const progress=profitRingProgress(s.positions,net,marked,fresh,s.settings.fee_cents_per_contract);
 const orbit=$('#profitOrbit');
 orbit.style.opacity=progress===null?'0':'1';
 orbit.setAttribute('aria-hidden',progress===null?'true':'false');
 orbit.setAttribute('aria-valuenow',String(Math.round(progress||0)));
 $('#profitOrbitValue').style.strokeDashoffset=String(100-(progress||0));
}
function update(s){current=s;const fresh=s.updated&&Date.now()-Date.parse(s.updated)<15000&&s.status!=='SIN DATOS',active=fresh?s.signal:null;
$('#status').textContent=s.status;$('#sideStatus').textContent=s.running?'ACTIVO':'PAUSADO';$('#radar').classList.toggle('paused',!s.running||!fresh);$('#radarSignal').textContent=active||'ALPHA';$('#radarMode').textContent=active?'CONFIRMADA':'ESPERANDO';$('#activeSignal').textContent=active||'ESPERANDO';$('#firstSignal').textContent=s.first_signal||'—';$('#marketLabel').textContent=fresh?' · DATOS ACTIVOS':' · SIN DATOS';$('#feedStatus').textContent=fresh?'● Mercado conectado':'● Esperando datos';$('#liveMessage').textContent='SIMULACIÓN · '+s.message;
$('#radarNotice').textContent=(s.retention||'Pausar entradas mantiene las salidas. Cerrar todo espera liquidez y precios actuales.')+' · '+(s.market?.ticker||'Sin ronda verificada');$('#entryLimit').textContent=s.settings.max_entry_cents+' ¢';$('#goalDisplay').textContent=money(s.settings.daily_goal_dollars);$('#sessionTime').textContent='MIAMI · '+localtime(new Date().toISOString());
let metrics=document.querySelectorAll('[data-metric]');[s.totals.daily,s.totals.realized].forEach((value,i)=>{metrics[i].textContent=(value>0?'+':'')+money(value);metrics[i].style.color=value>0?'#34d399':value<0?'#f87171':'inherit'});let progress=s.settings.daily_goal_dollars?Math.max(0,Math.min(100,s.totals.daily/s.settings.daily_goal_dollars*100)):0;$('.performance .strength i').style.width=progress+'%';$('#progressText').textContent=progress.toFixed(0)+'% · '+s.totals.completed+' cerradas';$('.mini-radar strong').textContent=progress.toFixed(0)+'%';
let count=s.positions.reduce((n,p)=>n+p.quantity,0);$('#openContracts').textContent=count+' CONTRATOS';$('#positionSide').textContent=s.positions[0]?.side||'SIN POSICIÓN';let net=0,marked=true;for(const p of s.positions){if(!fresh||p.ticker!==s.market?.ticker){marked=false;break}let left=p.quantity,value=0;for(const [price,n]of s.book?.[p.side]?.bids||[]){let take=Math.min(left,n);left-=take;value+=take*price;if(left<=0)break}if(left>0){marked=false;break}net+=(value-p.entry*p.quantity)/100-p.entry_fee-s.settings.fee_cents_per_contract*p.quantity/100}
updateProfitRing(s,net,marked,fresh);$('#positionPaid').textContent=money(s.positions.reduce((total,p)=>total+p.entry*p.quantity/100+p.entry_fee,0));$('#unrealized').textContent=marked?((net>0?'+':'')+money(net)):'—';$('#unrealized').style.color=marked&&s.positions.length?(net>0?'#34d399':net<0?'#f87171':'inherit'):'inherit';$('#positionNote').textContent=s.positions.length?(marked?'Neto estimado · comisiones simuladas':'Esperando liquidez / liquidación'):'Sin operaciones';$('#cashLabel').textContent='Disponible: '+money(s.totals.cash);
if(!loaded||!dirty){for(const [name,key]of Object.entries(names)){let el=form.elements[name];if(el.type==='checkbox')el.checked=s.settings[key];else {let raw=s.settings[key];let value=(raw!==undefined&&raw!==null&&Number.isFinite(Number(raw)))?Number(raw):(name==='tp'?90:name==='sl'?10:Number(el.value)||0);if(el.tagName==='SELECT'){for(const o of Array.from(el.options)){if(!Number.isFinite(Number(o.value))||o.textContent.includes('undefined')||o.textContent.includes('NaN'))o.remove()}if(!Array.from(el.options).some(o=>Number(o.value)===value)){let option=document.createElement('option');option.value=String(value);option.textContent=value===0?'Desactivado':(name==='sl'?'−':'+')+value+'%';el.add(option)}}el.value=String(value)}}loaded=true;$('#savedState').textContent='AJUSTES DEL SERVIDOR'}form.elements.balance.disabled=s.has_trades;
$('#entriesRows').innerHTML=s.trades.map(t=>'<tr><td>'+localtime(t.opened)+'</td><td>'+esc(t.ticker)+'</td><td>'+esc(t.side)+'</td><td>'+t.quantity+'</td><td>'+cents(t.entry)+'</td><td>'+esc(t.reason||'ABIERTA')+(t.closed?' · '+money(t.pnl):'')+'</td></tr>').join('');$('#entriesEmpty').classList.toggle('hidden',s.trades.length>0);
$('#logs').innerHTML=s.events.map(e=>'<tr><td>'+localtime(e.at)+'</td><td>'+esc(e.kind)+'</td><td>'+esc(e.message)+'</td></tr>').join('');
$('#signalTitle').textContent=active||(!fresh?'ESPERANDO DATOS':'ANALIZANDO');$('#signalDetail').textContent=s.quality||s.message;$('#signalDirection').textContent=active||'—';$('#signalFirst').textContent=s.first_signal||'—';$('#btcPrice').textContent=money(s.price);$('#targetPrice').textContent=money(s.target);$('#emaValue').textContent=s.ema==='BULL'?'ALCISTA':s.ema==='BEAR'?'BAJISTA':'—';$('#rsiValue').textContent=s.rsi?.toFixed(1)||'—';$('#momentumValue').textContent=s.metrics?.mom5==null?'—':s.metrics.mom5.toFixed(3)+'% · 5 min';$('#volumeValue').textContent=s.metrics?.vol_ratio==null?'—':s.metrics.vol_ratio.toFixed(2)+'×';$('#indicatorNote').textContent=(s.source||'Sin fuente')+' · Lectura: '+localtime(s.updated)+' · '+(s.quality||'Esperando');
endAt=s.market?.close_time?Date.parse(s.market.close_time):null;$('#connectionNotice').textContent=(fresh?'DATOS PÚBLICOS CONECTADOS':'ESPERANDO DATOS PÚBLICOS')+' · '+(s.connection?.message||'Simulación local activa; no requiere API privada.');height();tick()}
function tick(){if(endAt){let sec=Math.max(0,Math.floor((endAt-Date.now())/1000));$('#roundClock').textContent=String(Math.floor(sec/60)).padStart(2,'0')+':'+String(sec%60).padStart(2,'0')+' / 15:00'}if(current?.updated&&Date.now()-Date.parse(current.updated)>15000){$('#profitOrbit').style.opacity='0';$('#profitOrbit').setAttribute('aria-hidden','true');$('#marketLabel').textContent=' · DATOS ATRASADOS';$('#activeSignal').textContent='ESPERANDO';$('#radar').classList.add('paused')}}
window.addEventListener('message',e=>{if(e.source!==window.parent||e.data?.type!=='streamlit:render')return;const args=e.data.args||{};if(args.snapshot)update(args.snapshot);let reply=args.reply;if(reply&&reply.id&&!acknowledged.has(reply.id)){acknowledged.add(reply.id);if(acknowledged.size>100)acknowledged.delete(acknowledged.values().next().value);if(pending===reply.id){pending=null;busy(false)}if(reply.ok&&reply.kind==='settings'){dirty=false;if(args.snapshot)update(args.snapshot)}if(reply.csv){let a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+reply.csv],{type:'text/csv;charset=utf-8'}));a.download='alpha_historial.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),2000)}toast(reply.message);post('streamlit:setComponentValue',{value:{id:'ack-'+reply.id,action:'ack',payload:{}},dataType:'json'})}});
window.addEventListener('resize',height);new ResizeObserver(height).observe(document.body);setInterval(tick,1000);post('streamlit:componentReady',{apiVersion:1});height();

</script></body></html>
"""
# Connection verification never submits an order and never stores private keys.
def verify_demo_credentials(payload, getter=None):
    import base64
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa, ed25519
    key_id=payload.get('key_id','')
    pem=payload.get('pem','')
    if not isinstance(key_id,str) or not isinstance(pem,str) or not key_id.strip() or len(key_id)>200 or len(pem)>16000:
        raise ValueError('Introduce el API Key ID y la clave privada PEM de Kalshi Demo.')
    try:
        key=serialization.load_pem_private_key(pem.strip().encode(),password=None)
    except Exception:
        raise ValueError('La clave privada no es un PEM válido sin contraseña.') from None
    timestamp=str(int(time.time()*1000));path='/trade-api/v2/portfolio/balance'
    message=(timestamp+'GET'+path).encode()
    if isinstance(key,ed25519.Ed25519PrivateKey):
        signature=key.sign(message)
    elif isinstance(key,rsa.RSAPrivateKey):
        signature=key.sign(message,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.DIGEST_LENGTH),hashes.SHA256())
    else:
        raise ValueError('Kalshi requiere una clave RSA o Ed25519 compatible.')
    headers={'KALSHI-ACCESS-KEY':key_id.strip(),'KALSHI-ACCESS-TIMESTAMP':timestamp,
             'KALSHI-ACCESS-SIGNATURE':base64.b64encode(signature).decode()}
    try:
        result=(getter or requests.get)('https://external-api.demo.kalshi.co'+path,headers=headers,timeout=8).json()
        balance=float(result['balance'])/100
        if not math.isfinite(balance):
            raise ValueError('Saldo inválido.')
    except Exception as e:
        code=getattr(e,'code',None)
        if code in (401,403):
            raise ValueError('Kalshi rechazó estas credenciales. Usa claves del entorno Demo, no de la cuenta real.') from None
        raise ValueError('No se pudo verificar el saldo de Kalshi Demo. Comprueba la conexión y las credenciales.') from None
    return {'message':f'API DEMO VERIFICADA · saldo de prueba ${balance:.2f}. Ejecución local simulada.', 'balance':balance,'verified_at':stamp()}

class Controller:
    """Idempotent UI actions. Returned snapshots never include credentials."""
    def __init__(self,bot):
        self.bot=bot
        self.seen={}
        self.connection={'message':'Datos públicos sin API privada.'}
    def handle(self,event):
        if not isinstance(event,dict) or event.get('action')=='ack':
            return None
        action=event.get('action');event_id=event.get('id')
        if not isinstance(event_id,str) or len(event_id)>160:
            return None
        if event_id in self.seen:
            return self.seen[event_id]
        reply={'id':event_id,'ok':True,'kind':action}
        try:
            payload=event.get('payload',{})
            if not isinstance(payload,dict):raise ValueError('Solicitud inválida.')
            if action=='command':
                command=payload.get('command')
                self.bot.command(command)
                reply['message']={'start':'Simulación activada.','pause':'Entradas pausadas; salidas vigiladas.',
                                  'close':'Cierre solicitado; esperando liquidez actual.'}[command]
            elif action=='settings':
                self.bot.save_settings(payload);reply['message']='Ajustes guardados y aplicados a compras nuevas.'
            elif action=='public':
                market=self.bot.feed.current();book=self.bot.feed.book(market['ticker'])
                reply['message']='Kalshi responde: '+market['ticker']
                self.connection={'message':'Consulta pública verificada: '+market['ticker'],'verified_at':stamp()}
            elif action=='verify_demo':
                self.connection=verify_demo_credentials(payload)
                reply['message']=self.connection['message']
                with self.bot.lock:self.bot.event('CONEXIÓN','API de Demo verificada en modo de lectura.')
            elif action=='forget_demo':
                self.connection={'message':'Verificación de API eliminada. Datos públicos disponibles.'}
                reply['message']='Campos de credenciales limpiados. No se guardaron claves en disco.'
            elif action=='export':
                stream=io.StringIO();writer=csv.writer(stream)
                with self.bot.lock:
                    cursor=self.bot.db.execute('SELECT * FROM trades ORDER BY id')
                    writer.writerow([x[0] for x in cursor.description]);writer.writerows(cursor.fetchall())
                reply.update(csv=stream.getvalue(),message='Historial completo exportado.')
            else:
                raise ValueError('Acción desconocida.')
        except ValueError as e:
            reply.update(ok=False,message=str(e))
        except Exception:
            reply.update(ok=False,message='No se pudo completar la operación. No se confirmó el cambio.')
        self.seen[event_id]=reply
        if len(self.seen)>500:self.seen.pop(next(iter(self.seen)))
        return reply
    def snapshot(self):
        result=self.bot.view()
        with self.bot.lock:
            result['has_trades']=bool(self.bot.db.execute('SELECT 1 FROM trades LIMIT 1').fetchone())
        result['connection']=self.connection.copy()
        return result


def streamlit_main():
    import streamlit as st
    import streamlit.components.v1 as components
    import tempfile
    st.set_page_config(page_title='ALPHA EDGE · BTC 15 MIN',layout='wide',initial_sidebar_state='collapsed')
    st.markdown('<style>.block-container{padding:0!important;max-width:100%!important}header,footer{display:none!important}.stApp{background:#080e22}</style>',unsafe_allow_html=True)
    try:
        password=os.environ.get('ALPHA_PASSWORD') or st.secrets.get('ALPHA_PASSWORD','')
    except Exception:
        password=os.environ.get('ALPHA_PASSWORD','')
    if password and not st.session_state.get('alpha_authenticated'):
        supplied=st.text_input('Contraseña de ALPHA EDGE',type='password')
        if st.button('Entrar'):
            if hmac.compare_digest(supplied.encode(),password.encode()):
                st.session_state.alpha_authenticated=True;st.rerun()
            else:st.error('Contraseña incorrecta.')
        st.stop()

    @st.cache_resource
    def shared_bot():
        db=Path(os.environ.get('ALPHA_DB',ROOT/'data'/'alpha.sqlite3'))
        db.parent.mkdir(parents=True,exist_ok=True)
        lock=open(str(db)+'.lock','a+')
        try:
            if os.name=='nt':
                import msvcrt
                lock.seek(0);lock.write('0');lock.flush();lock.seek(0)
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            lock.close()
            raise RuntimeError('Ya existe un proceso operando esta base. Reinicia el servicio y usa una instancia.')
        bot=Bot(db);bot._process_lock=lock
        bot.start_worker()
        return bot
    bot=shared_bot()
    if 'alpha_controller' not in st.session_state:
        st.session_state.alpha_controller=Controller(bot)
    controller=st.session_state.alpha_controller
    digest=hashlib.sha256(_TERMINAL_HTML.encode()).hexdigest()[:16]
    directory=Path(tempfile.gettempdir())/('alpha_terminal_'+digest)
    directory.mkdir(parents=True,exist_ok=True)
    index=directory/'index.html'
    if not index.exists():index.write_text(_TERMINAL_HTML,encoding='utf-8')
    terminal=components.declare_component('alpha_edge_terminal',path=str(directory))

    @st.fragment(run_every=2)
    def live_terminal():
        event=terminal(snapshot=controller.snapshot(),reply=st.session_state.get('alpha_reply'),key='alpha_terminal',default=None)
        if isinstance(event,dict) and event.get('action')=='ack':
            st.session_state.alpha_reply=None
        elif isinstance(event,dict) and event.get('id') not in controller.seen:
            reply=controller.handle(event)
            if reply:
                st.session_state.alpha_reply=reply
                st.rerun()
    live_terminal()

if __name__=='__main__':
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is None:
        # Also support the previously supplied Render start command.
        import sys
        from streamlit.web import cli as streamlit_cli
        sys.argv=['streamlit','run',str(Path(__file__).resolve()),
                  '--server.address',os.environ.get('BIND','127.0.0.1'),
                  '--server.port',os.environ.get('PORT','8501'),'--server.headless','true']
        raise SystemExit(streamlit_cli.main())
    else:
        streamlit_main()
