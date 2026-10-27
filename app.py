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

def _entry_route_checks(sig, seconds_left):
    """Evaluate both sides from the same evidence; shared by engine and UI."""
    required = ("rsi", "rsi3", "rsi5", "adx", "vwap_atr", "macd1", "macd3",
                "vol_ratio", "mom3", "mom5", "target_atr", "price_ema9_atr")
    if sig.get("data_valid") is False or any(_plan_number(sig.get(k)) is None for k in required):
        return {"valid":False, "sides":{}, "noise_ok":False}
    r1,r3,r5,adx,vw,m1,m3,vol,mom,mom5,cushion,live_ema = (float(sig[k]) for k in required)
    d3,d5 = sig.get("trend3"), sig.get("trend5")
    impulse = sig.get("impulse_internal") or {}
    noise_ok = not (abs(vw)<.18 and (sig.get("distance") is None or abs(cushion)<.22) and adx<20)
    sides = {}
    for side,sign,other in (("UP",1,"DOWN"),("DOWN",-1,"UP")):
        up = sign == 1
        exhausted = bool(impulse.get("exhaust_up" if up else "exhaust_down"))
        strength = float(impulse.get("up" if up else "down", 0))
        reliable = bool(impulse.get("reliable"))
        current = [
            ("EMA de 1 minuto y precio actual a favor", sig.get("ema") == ("BULL" if up else "BEAR") and live_ema*sign>0),
            ("RSI y momentum actuales a favor", (r1>=53 if up else r1<=47) and mom*sign>=.025),
            ("MACD de 1 minuto y VWAP a favor", m1*sign>0 and vw*sign>=.03),
            ("Impulso actual sin agotamiento detectado", not exhausted),
        ]
        early_five = d5 != other or (reliable and strength>=.75 and mom*sign>.04 and vol>=.9)
        rsi_vwap = (r1>=52 and vw>=.05) if up else (r1<=48 and vw<=-.05)
        routes = [
            ("IMPULSO ACTUAL", current),
            ("TENDENCIA ALINEADA", [
                ("Tendencias de 3 y 5 minutos a favor", d3==side and d5==side),
                ("Fuerza de tendencia o RSI suficientes", adx>=20 or ((r3>=52 and r5>=50) if up else (r3<=48 and r5<=50))),
                ("VWAP y momentum actual respaldan la tendencia", (vw>-.15 if up else vw<.15) and mom*sign>=.012),
                ("Sin agotamiento detectado", not exhausted),
            ]),
            ("TEMPRANA", [
                ("MACD de 3 minutos a favor", m3*sign>0),
                ("RSI de 1 minuto y VWAP a favor", rsi_vwap),
                ("Momentum de 3 minutos a favor", mom*sign>.015),
                ("Contexto de 5 minutos respaldado o superado por fuerza actual", early_five),
                ("Sin agotamiento detectado", not exhausted),
            ]),
            ("TEMPRANA ACELERADA", [
                ("MACD y momentum a favor", m3*sign>0 and mom*sign>.015),
                ("Contexto de 5 minutos no contrario", d5!=other),
                ("Impulso fuerte con volumen y ADX", reliable and strength>=.65 and adx>=20 and vol>=.8),
                ("Sin agotamiento detectado", not exhausted),
            ]),
            ("GIRO TEMPRANO", [
                ("MACD y momentum respaldan el giro", m3*sign>0 and mom*sign>.04),
                ("RSI de 1 y 3 minutos respaldan el giro", (r1>=54 and r3>=50) if up else (r1<=46 and r3<=50)),
                ("VWAP y distancia suficientes", vw*sign>=.08 and abs(cushion)>=.30),
                ("Impulso y volumen suficientes", reliable and strength>=.70 and vol>=.9),
                ("Sin agotamiento detectado", not exhausted),
            ]),
        ]
        flow = sig.get("flow_context_internal") or {}
        flow_ok = flow.get("direction")==side and flow.get("valid",False)
        routes.append(("FLUJO + IMPULSO", [
            ("Flujo agresor significativo a favor", flow_ok),
            ("RSI, MACD y precio actuales a favor", (r1>=50 if up else r1<=50) and m1*sign>0 and live_ema*sign>0),
            ("Momentum y VWAP a favor", mom*sign>=.012 and vw*sign>=-.04),
            ("Contexto contrario corroborado por momentum", d5!=other or (mom5*sign>=.025 and abs(mom)>=.025)),
            ("Impulso fiable sin agotamiento", reliable and not exhausted),
        ]))
        target_ok = True
        if sig.get("distance") is not None and seconds_left is not None:
            remaining = float(np.clip(seconds_left,0,900))
            weight = .12+.88*(1-remaining/900)**1.6
            tolerance = 1.8-1.4*weight
            if -sign*cushion>tolerance:
                target_ok = (reliable and strength>=.75 and mom*sign>.04 and not exhausted
                             and (all(ok for _,ok in current) or d3==side or d5==side))
        sides[side] = []
        for name,checks in routes:
            checks = checks+[("Fuera de la zona de ruido",noise_ok),
                            ("Distancia al target y tiempo respaldan la dirección",target_ok)]
            sides[side].append({"name":name,"checks":checks,"met":sum(bool(ok) for _,ok in checks),
                                "total":len(checks),"complete":all(bool(ok) for _,ok in checks)})
    return {"valid":True,"sides":sides,"noise_ok":noise_ok}

def _signal_engine_without_trace(df, target, seconds_left, live_price=None, whale=None):
    one=add_indicators(df); three=_resample_indicators(df,3); five=_resample_indicators(df,5)
    l1,l3,l5=one.iloc[-1],three.iloc[-1],five.iloc[-1]
    candle_price=float(l1["close"]); price=float(live_price) if live_price is not None else candle_price
    def direction(row):
        bull=(row["ema9"]>row["ema21"] and row["macd_hist"]>=0 and row["plus_di"]>=row["minus_di"])
        bear=(row["ema9"]<row["ema21"] and row["macd_hist"]<=0 and row["minus_di"]>=row["plus_di"])
        return "UP" if bull else "DOWN" if bear else "NEUTRAL"
    d3,d5=direction(l3),direction(l5); aligned=d3 if d3==d5 and d3!="NEUTRAL" else "NEUTRAL"
    atr=float(l1["atr"]) if pd.notna(l1["atr"]) and l1["atr"]>0 else max(price*.0005,1)
    distance=(price-target) if target is not None else None; distance_pct=(distance/target*100) if target else None
    target_atr=(distance/atr) if distance is not None else 0.0
    vwap=float(l1["vwap"]) if pd.notna(l1["vwap"]) else price; vwap_atr=(price-vwap)/atr
    adx5=float(l5["adx"]) if pd.notna(l5["adx"]) else 0.0; rsi1=float(l1["rsi"]); rsi3=float(l3["rsi"]); rsi5=float(l5["rsi"])
    rvol=float(l1["vol_ratio"]) if pd.notna(l1["vol_ratio"]) else 1.0
    mom3=float(l1["mom3"]) if pd.notna(l1["mom3"]) else 0.0; mom5=float(l1["mom5"]) if pd.notna(l1["mom5"]) else 0.0; mom15=float(l1["mom15"]) if pd.notna(l1["mom15"]) else 0.0
    trend_strong=adx5>=20; near_noise=abs(vwap_atr)<0.18 and (distance is None or abs(target_atr)<0.22)
    impulse = _internal_impulse_context(one, price, atr, mom3, mom5, mom15, rvol)
    # Evaluate all routes for both directions before choosing any candidate.
    flow_side = (whale or {}).get("flow_direction") if isinstance(whale,dict) else None
    flow_context = {"direction":flow_side, "valid":False}
    if isinstance(whale,dict):
        flow_context["valid"] = (flow_side in ("UP","DOWN") and
            float(whale.get("buy30") or 0)+float(whale.get("sell30") or 0)>=500_000 and
            float(whale.get("flow_strength") or 0)>=.20)
    route_input = {"rsi":rsi1,"rsi3":rsi3,"rsi5":rsi5,"adx":adx5,"vwap_atr":vwap_atr,
        "macd1":float(l1["macd_hist"]),"macd3":float(l3["macd_hist"]),"vol_ratio":rvol,
        "mom3":mom3,"mom5":mom5,"target_atr":target_atr,"distance":distance,
        "price_ema9_atr":(price-float(l1["ema9"]))/atr,
        "ema":"BULL" if l1["ema9"]>l1["ema21"] else "BEAR",
        "trend3":d3,"trend5":d5,"impulse_internal":impulse,"flow_context_internal":flow_context}
    route_view = _entry_route_checks(route_input, seconds_left)
    eligible = {side:[route for route in route_view["sides"].get(side,[]) if route["complete"]]
                for side in ("UP","DOWN")}
    choices = [side for side in ("UP","DOWN") if eligible[side]]
    candidate = choices[0] if len(choices)==1 else None
    quality = eligible[candidate][0]["name"] if candidate else "SIN CONFIRMACIÓN" if not choices else "EVIDENCIA CONTRADICTORIA"
    flow_support = {"used":quality=="FLUJO + IMPULSO", "direction":flow_side if flow_context["valid"] else None,
                    "reason":"FLUJO CORROBORADO" if quality=="FLUJO + IMPULSO" else "CONTEXTO"}
    # Compatibility score: descriptive evidence for existing UI/closing reader; no longer gates entries at +/-4.
    evidence=(1 if d3=="UP" else -1 if d3=="DOWN" else 0)+(1.5 if d5=="UP" else -1.5 if d5=="DOWN" else 0)+(0.75 if l3["macd_hist"]>0 else -0.75)+(0.75 if l5["plus_di"]>l5["minus_di"] else -0.75)+float(np.clip(target_atr,-2,2))
    # Closing support adapts continuously; it is NOT a calibrated win probability.
    if seconds_left is not None and 0 < seconds_left <= 180 and distance is not None:
        weight = .35 + .35 * (180 - seconds_left) / 180
        evidence = (1-weight)*evidence + weight*float(np.clip(target_atr, -2, 2))*3
    up_probability=float(np.clip(50+evidence*7,5,95)); down_probability=100-up_probability
    momentum="ALCISTA" if aligned=="UP" else "BAJISTA" if aligned=="DOWN" else "NEUTRAL"
    return {"price":price,"candle_price":candle_price,"rsi":rsi1,"rsi3":rsi3,"rsi5":rsi5,"mom3":mom3,"mom5":mom5,"mom15":mom15,"vol_ratio":rvol,"ema":"BULL" if l1["ema9"]>l1["ema21"] else "BEAR","technical_score":evidence,"target_score":target_atr,"final_score":evidence,"distance":distance,"distance_pct":distance_pct,"momentum":momentum,"up_probability":round(up_probability),"down_probability":round(down_probability),"candidate":candidate,"quality":quality,"trend3":d3,"trend5":d5,"adx":adx5,"plus_di":float(l5["plus_di"]),"minus_di":float(l5["minus_di"]),"macd3":float(l3["macd_hist"]),"macd5":float(l5["macd_hist"]),"atr":atr,"vwap":vwap,"vwap_atr":vwap_atr,"target_atr":target_atr,"impulse_internal":impulse,"entry_route_internal":quality,"flow_support_internal":flow_support,"flow_context_internal":flow_context,"macd1":float(l1["macd_hist"]),"price_ema9_atr":(price-float(l1["ema9"]))/atr}

def _retention_assessment(state, signal):
    """Separate affirmative, opposite and unknown evidence for an active side."""
    side = state.get("active_direction")
    if side not in ("UP", "DOWN") or not signal or signal.get("data_valid") is False:
        return 0, 0
    sign = 1 if side == "UP" else -1
    support = contrary = 0
    ema = signal.get("ema")
    if ema in ("BULL", "BEAR"):
        if ema == ("BULL" if sign == 1 else "BEAR"):
            support += 1
        else:
            contrary += 1
    for name in ("mom5", "distance"):
        value = _plan_number(signal.get(name))
        if value is None:
            continue
        if value * sign > 0:
            support += 1
        elif value * sign < 0:
            contrary += 1
    return support, contrary

def _retention_supported(state, signal, seconds_left):
    """Partial weakening is not sufficient to withdraw an existing signal."""
    if seconds_left is None or seconds_left <= 0:
        return False
    support, _ = _retention_assessment(state, signal)
    return support >= 2

def _reset_withdrawal(state):
    state.update(withdraw_direction=None, withdraw_source=None, withdraw_count=0,
                 withdraw_since=None, withdraw_last_at=None, retention_warning=None)

def _review_active_retention(state, signal, seconds_left, now):
    """Withdraw only after two opposite conditions persist in spaced readings.

    Neutral/missing evidence never counts as an opposite vote. This helper is
    only for candidate=None; entry and reversal confirmation are unchanged.
    """
    side = state.get("active_direction")
    if side not in ("UP", "DOWN"):
        _reset_withdrawal(state)
        return
    support, contrary = _retention_assessment(state, signal)
    warning = side + " PERDIENDO FUERZA • REEVALUANDO RESPALDO" if support < 3 else None
    if contrary < 2:
        _reset_withdrawal(state)
        state["retention_warning"] = warning
        return
    source = (signal or {}).get("price_source")
    stamp = now.timestamp()
    last = state.get("withdraw_last_at")
    same = (state.get("withdraw_direction") == side and state.get("withdraw_source") == source
            and last is not None and 0 <= stamp-last <= SIGNAL_CONFIRM_MAX_GAP)
    if not same:
        state.update(withdraw_direction=side, withdraw_source=source, withdraw_count=1,
                     withdraw_since=stamp, withdraw_last_at=stamp)
    elif stamp-last >= SIGNAL_CONFIRM_INTERVAL:
        state["withdraw_count"] += 1
        state["withdraw_last_at"] = stamp
    state["retention_warning"] = warning
    if (state["withdraw_count"] >= SIGNAL_CONFIRM_READINGS and
            stamp-state["withdraw_since"] >= SIGNAL_CONFIRM_INTERVAL*(SIGNAL_CONFIRM_READINGS-1)):
        state["active_direction"] = None
        state["active_since"] = None
        _reset_withdrawal(state)

def _round_opening_crosscheck(state, candidate, signal, now):
    """Require fresh directional evidence before the first entry of this ticker.

    Old candles remain context, never sufficient evidence for an opening entry.
    Each live feed has a separate short tape. Later reversals are unrestricted.
    """
    if state.get("first_direction") in ("UP", "DOWN"):
        state["opening_conflict"] = None
        return candidate
    def wait(reason):
        state["opening_conflict"] = reason
        return None
    if state.get("opening_gate_revision") != "fresh_first_entry_v1":
        state.update(opening_gate_revision="fresh_first_entry_v1", opening_live_tapes={})
    if not signal or signal.get("data_valid") is False:
        return wait("Esperando datos actuales para la primera señal")
    price = _plan_number(signal.get("price"))
    atr = _plan_number(signal.get("atr"))
    source = signal.get("price_source")
    if (price is None or price <= 0 or atr is None or atr <= 0
            or source not in ("COINBASE", "KALSHI LIVE")):
        return wait("Esperando precio en vivo para la primera señal")
    stamp = now.timestamp()
    tapes = state.setdefault("opening_live_tapes", {})
    tape = tapes.get(source, [])
    if tape and (stamp < tape[-1][0] or stamp-tape[-1][0] > LIVE_PRICE_MAX_AGE):
        tape = []
    tape = [x for x in tape if 0 <= stamp-x[0] <= 30]
    if not tape or stamp-tape[-1][0] >= SIGNAL_CONFIRM_INTERVAL:
        tape.append([stamp, price])
    tapes[source] = tape
    if candidate not in ("UP", "DOWN"):
        return wait("Analizando fuerza actual antes de la primera señal")
    if len(tape) < 3 or tape[-1][0]-tape[0][0] < 6:
        return wait("Observando movimiento actual antes de la primera señal")
    prices = [float(x[1]) for x in tape]
    sign = 1 if candidate == "UP" else -1
    split = len(prices)//2
    net = sign*(prices[-1]-prices[0])
    recent = sign*(prices[-1]-prices[split])
    travel = sum(abs(y-x) for x,y in zip(prices,prices[1:]))
    efficiency = net/max(travel, 1e-8)
    minimum = max(2.0, .10*atr)
    latest = sign*(prices[-1]-prices[-2])
    if (net < minimum or recent < .5*minimum or efficiency < .60
            or latest < -.25*minimum):
        return wait("Sin fuerza actual suficiente para " + candidate)
    state["opening_conflict"] = None
    return candidate

def _confirmation_without_trace(state, candidate, market, seconds_left, now, signal=None):
    """Confirmación compartida por la pantalla y el registrador de fondo.

    La primera señal queda inmutable. Un cambio UP/DOWN posterior también
    necesita confirmación. Una lectura neutral cancela la candidatura pendiente;
    la activa se conserva solo si mantiene EMA, mom5 y distancia favorables.
    """
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
        # Una interrupción no demuestra neutralidad ni permite confirmar.
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
        _review_active_retention(state, signal, seconds_left, now)
        return

    _reset_withdrawal(state)
    if candidate == state.get("active_direction"):
        state["pending_direction"] = None
        state["pending_count"] = 0
        state["pending_since"] = None
        state["pending_last_at"] = None
        return

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
              'take_profit_pct':(0,10000), 'stop_loss_pct':(0,100),
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
        for column in ('tp_pct','sl_pct'):
            if column not in columns:
                self.db.execute('ALTER TABLE trades ADD COLUMN '+column+' REAL')
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
        elif (p.get('tp_pct') is not None and p['tp_pct'] and roi+1e-9>=p['tp_pct']) or (p.get('tp_pct') is None and p['tp'] and price>=p['entry']+p['tp']):
            reason='TAKE PROFIT'
        elif (p.get('sl_pct') is not None and p['sl_pct'] and roi<=-p['sl_pct']+1e-9) or (p.get('sl_pct') is None and p['sl'] and price<=p['entry']-p['sl']):
            reason='STOP LOSS'
        elif p['reverse'] and signal in ('UP','DOWN') and signal!=p['side']:
            reason='CAMBIO DE SEÑAL'
        if reason:
            self._close(p,price,reason)

    def enter(self,market,book,side,remaining):
        s=self.settings
        if not self.running or self.close_requested or self.positions() or side not in ('UP','DOWN'):
            return 'Entradas pausadas o posición en gestión.'
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
        self.db.execute('INSERT INTO trades(ticker,side,quantity,entry,entry_fee,opened,tp,sl,exit_seconds,reverse,tp_pct,sl_pct) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (market['ticker'],side,quantity,price,fee,stamp(),0,0,0,s['close_on_reverse'],s['take_profit_pct'],s['stop_loss_pct']))
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
            message=self.enter(market,book,active,remaining) if not had_position else 'Gestión de posición abierta.'
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
<div class="brand">ALPHA EDGE<small>PRECISIÓN · CONTROL</small>
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
<label>Tomar profit (%)<small>Ganancia neta sobre lo pagado; requiere precio y liquidez suficientes.</small></label>
<select name="tp"><option value="0">Desactivado</option><option value="80">+80%</option><option value="85">+85%</option><option value="90">+90%</option><option value="95">+95%</option></select>
</div>
<div class="field">
<label>Stop loss (%)<small>Porcentaje de pérdida sobre lo pagado; 0 desactiva.</small></label>
<input type="number" name="sl" value="10" min="0" max="100" required>
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
const localtime=v=>v?new Date(v).toLocaleTimeString('es-US',{timeZone:'America/New_York',hour12:false}):'—';
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
function update(s){current=s;const fresh=s.updated&&Date.now()-Date.parse(s.updated)<15000&&s.status!=='SIN DATOS',active=fresh?s.signal:null;
$('#status').textContent=s.status;$('#sideStatus').textContent=s.running?'ACTIVO':'PAUSADO';$('#radar').classList.toggle('paused',!s.running||!fresh);$('#radarSignal').textContent=active||'ALPHA';$('#radarMode').textContent=active?'CONFIRMADA':'ESPERANDO';$('#activeSignal').textContent=active||'ESPERANDO';$('#firstSignal').textContent=s.first_signal||'—';$('#marketLabel').textContent=fresh?' · DATOS ACTIVOS':' · SIN DATOS';$('#feedStatus').textContent=fresh?'● Mercado conectado':'● Esperando datos';$('#liveMessage').textContent='SIMULACIÓN · '+s.message;
$('#radarNotice').textContent=(s.retention||'Pausar entradas mantiene las salidas. Cerrar todo espera liquidez y precios actuales.')+' · '+(s.market?.ticker||'Sin ronda verificada');$('#entryLimit').textContent=s.settings.max_entry_cents+' ¢';$('#goalDisplay').textContent=money(s.settings.daily_goal_dollars);$('#sessionTime').textContent='MIAMI · '+localtime(new Date().toISOString());
let metrics=document.querySelectorAll('[data-metric]');metrics[0].textContent=money(s.totals.daily);metrics[1].textContent=money(s.totals.realized);let progress=s.settings.daily_goal_dollars?Math.max(0,Math.min(100,s.totals.daily/s.settings.daily_goal_dollars*100)):0;$('.performance .strength i').style.width=progress+'%';$('#progressText').textContent=progress.toFixed(0)+'% · '+s.totals.completed+' cerradas';$('.mini-radar strong').textContent=progress.toFixed(0)+'%';
let count=s.positions.reduce((n,p)=>n+p.quantity,0);$('#openContracts').textContent=count+' CONTRATOS';$('#positionSide').textContent=s.positions[0]?.side||'SIN POSICIÓN';let net=0,marked=true;for(const p of s.positions){if(!fresh||p.ticker!==s.market?.ticker){marked=false;break}let left=p.quantity,value=0;for(const [price,n]of s.book?.[p.side]?.bids||[]){let take=Math.min(left,n);left-=take;value+=take*price;if(left<=0)break}if(left>0){marked=false;break}net+=(value-p.entry*p.quantity)/100-p.entry_fee-s.settings.fee_cents_per_contract*p.quantity/100}
$('#positionPaid').textContent=money(s.positions.reduce((total,p)=>total+p.entry*p.quantity/100+p.entry_fee,0));$('#unrealized').textContent=marked?((net>0?'+':'')+money(net)):'—';$('#unrealized').style.color=marked&&s.positions.length?(net>0?'#34d399':net<0?'#f87171':'inherit'):'inherit';$('#positionNote').textContent=s.positions.length?(marked?'Neto estimado · comisiones simuladas':'Esperando liquidez / liquidación'):'Sin operaciones';$('#cashLabel').textContent='Disponible: '+money(s.totals.cash);
if(!loaded||!dirty){for(const [name,key]of Object.entries(names)){let el=form.elements[name];if(el.type==='checkbox')el.checked=s.settings[key];else el.value=s.settings[key]}loaded=true;$('#savedState').textContent='AJUSTES DEL SERVIDOR'}form.elements.balance.disabled=s.has_trades;
$('#entriesRows').innerHTML=s.trades.map(t=>'<tr><td>'+localtime(t.opened)+'</td><td>'+esc(t.ticker)+'</td><td>'+esc(t.side)+'</td><td>'+t.quantity+'</td><td>'+cents(t.entry)+'</td><td>'+esc(t.reason||'ABIERTA')+(t.closed?' · '+money(t.pnl):'')+'</td></tr>').join('');$('#entriesEmpty').classList.toggle('hidden',s.trades.length>0);
$('#logs').innerHTML=s.events.map(e=>'<tr><td>'+localtime(e.at)+'</td><td>'+esc(e.kind)+'</td><td>'+esc(e.message)+'</td></tr>').join('');
$('#signalTitle').textContent=active||(!fresh?'ESPERANDO DATOS':'ANALIZANDO');$('#signalDetail').textContent=s.quality||s.message;$('#signalDirection').textContent=active||'—';$('#signalFirst').textContent=s.first_signal||'—';$('#btcPrice').textContent=money(s.price);$('#targetPrice').textContent=money(s.target);$('#emaValue').textContent=s.ema==='BULL'?'ALCISTA':s.ema==='BEAR'?'BAJISTA':'—';$('#rsiValue').textContent=s.rsi?.toFixed(1)||'—';$('#momentumValue').textContent=s.metrics?.mom5==null?'—':s.metrics.mom5.toFixed(3)+'% · 5 min';$('#volumeValue').textContent=s.metrics?.vol_ratio==null?'—':s.metrics.vol_ratio.toFixed(2)+'×';$('#indicatorNote').textContent=(s.source||'Sin fuente')+' · Lectura: '+localtime(s.updated)+' · '+(s.quality||'Esperando');
endAt=s.market?.close_time?Date.parse(s.market.close_time):null;$('#connectionNotice').textContent=(fresh?'DATOS PÚBLICOS CONECTADOS':'ESPERANDO DATOS PÚBLICOS')+' · '+(s.connection?.message||'Simulación local activa; no requiere API privada.');height();tick()}
function tick(){if(endAt){let sec=Math.max(0,Math.floor((endAt-Date.now())/1000));$('#roundClock').textContent=String(Math.floor(sec/60)).padStart(2,'0')+':'+String(sec%60).padStart(2,'0')+' / 15:00'}if(current?.updated&&Date.now()-Date.parse(current.updated)>15000){$('#marketLabel').textContent=' · DATOS ATRASADOS';$('#activeSignal').textContent='ESPERANDO';$('#radar').classList.add('paused')}}
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
