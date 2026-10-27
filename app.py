"""ALPHA EDGE — BTC 15 minutos. Primera fase: ejecución automática simulada.
Run: python app.py. Only public GET requests leave this process.
"""
from __future__ import annotations
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
import types

"""HTTP GET only. This application never submits orders to Kalshi."""
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

"""Motor extraído literalmente de app 61(1).py. No importa ni ejecuta su interfaz.
SHA256 original: 951af0078d752782234f396201935c846d562bbe14d5fae4c1d6ca6f29e71f39
Las funciones de señal y confirmación conservan sus reglas originales.
"""
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


# Exact original engine functions exposed as a namespace.
engine = types.SimpleNamespace(**{name: globals()[name] for name in ['_valid_live_observation', '_plan_number', 'new_round_state', '_fetch_current_btc_candles', 'get_event_ticker_from_market', 'extract_kalshi_btc_price', '_indicator_frame', '_resample_indicators', 'add_indicators', 'get_target_from_market', 'get_seconds_remaining', 'numeric_kalshi_price', 'get_yes_ask', 'get_no_ask', '_internal_impulse_context', '_entry_route_checks', '_signal_engine_without_trace', '_retention_assessment', '_retention_supported', '_reset_withdrawal', '_review_active_retention', '_round_opening_crosscheck', '_confirmation_without_trace']})

_INDEX = r'''
<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ALPHA EDGE · Terminal BTC</title><style>
:root{color-scheme:dark;--bg:#080e1c;--panel:#101c33;--line:#283b59;--gold:#e5bd68;--gold2:#95713d;--muted:#94a7c3;--text:#ecf2fc;--green:#59d7b0;--red:#f47c8d;--blue:#74acfa}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 60% -30%,#1c355e 0,transparent 60%),var(--bg);font:14px/1.5 system-ui,-apple-system,sans-serif;color:var(--text)}button,input{font:inherit}button{cursor:pointer}button:disabled{cursor:wait;opacity:.6}button:focus-visible,a:focus-visible,input:focus-visible{outline:2px solid var(--gold);outline-offset:4px}button,.button{border:1px solid #435674;color:var(--text);background:#172744;padding:11px 19px;border-radius:7px;font-weight:650;text-decoration:none}button:hover,.button:hover{filter:brightness(1.16)}button.primary{background:linear-gradient(120deg,#e9c779,#bc9149);border-color:#e4c16f;color:#172039}button.danger{background:#512633;border-color:#9d4c5c;color:#ffe0e5}.shell{display:grid;grid-template-columns:222px minmax(0,1fr);min-height:100vh}aside{background:#0b1427d9;border-right:1px solid var(--line);padding:30px 18px;display:flex;flex-direction:column;gap:25px}.logo{font-size:23px;letter-spacing:2.5px;font-weight:850;color:var(--gold);line-height:1.3}.logo small{display:block;font-size:10px;font-weight:500;letter-spacing:3px;color:var(--muted);margin-top:7px}.brandmark{width:34px;height:4px;background:var(--gold);box-shadow:10px -7px 0 -1px #839ac0;margin-bottom:16px}nav{display:grid;gap:9px}nav button{text-align:left;border:1px solid transparent;background:transparent;color:var(--muted);padding:13px 12px}nav button.active{color:var(--gold);background:linear-gradient(90deg,#c29a4524,transparent);border-color:#ad8d4c6b}nav b{margin-right:12px;font:11px ui-monospace,monospace;color:#8194b1}.aside-note{margin-top:auto;border-top:1px solid var(--line);padding-top:18px;color:var(--muted);font-size:12px}.pill{display:inline-flex;align-items:center;gap:7px;border-radius:30px;padding:5px 10px;font-size:10px;letter-spacing:1px;font-weight:750;border:1px solid #517359;background:#143b2d44;color:var(--green);white-space:nowrap}.pill.gold{color:var(--gold);border-color:#786440;background:#6d562122}.pill.red{color:var(--red);border-color:#7c4553;background:#44263355}main{padding:26px 34px 32px;max-width:1540px;width:100%;margin:auto}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:28px}.eyebrow{font-size:10px;letter-spacing:2px;color:var(--muted);font-weight:650}.topbar strong{font-size:14px;display:block;margin-top:5px}.top-right{display:flex;align-items:center;gap:15px}.clock{font:14px ui-monospace,monospace;color:var(--muted)}.pagehead{display:flex;justify-content:space-between;align-items:end;margin:0 0 20px;gap:15px}h1{margin:3px 0 6px;font-size:29px;letter-spacing:-.8px}h2{font-size:12px;letter-spacing:1.4px;margin:0;font-weight:750;text-transform:uppercase}h3{font-size:13px;margin:0 0 15px}p{margin:5px 0;color:var(--muted)}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}.stat,.panel{border:1px solid var(--line);border-radius:10px;background:linear-gradient(145deg,#14233d,#0d182b);box-shadow:0 6px 30px #00000012}.stat{padding:19px 20px}.stat .value{font-size:26px;font-weight:650;letter-spacing:-.6px;margin-top:7px;font-variant-numeric:tabular-nums}.sub{font-size:11px;color:var(--muted);margin-top:4px}.grid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(280px,1fr);gap:18px}.panel{padding:22px;margin-bottom:18px}.panelhead{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:20px;gap:10px}.panelhead h2:before{content:'';display:inline-block;background:var(--gold);width:3px;height:11px;margin-right:10px}.radar-wrap{position:relative;display:grid;place-items:center;min-height:285px}.radar{width:min(100%,310px);aspect-ratio:1;border:1px solid #927440;border-radius:50%;position:relative;background:repeating-radial-gradient(circle,transparent 0,transparent calc(25% - 1px),#43638966 25%,transparent calc(25% + 1px)),linear-gradient(90deg,transparent calc(50% - .5px),#52709c77 50%,transparent calc(50% + .5px)),linear-gradient(transparent calc(50% - .5px),#52709c77 50%,transparent calc(50% + .5px)),radial-gradient(circle,#1d3d68,#0a1831);box-shadow:0 0 45px #102e6850,inset 0 0 30px #244d7b44}.radar:before{content:'';position:absolute;inset:11px;border:1px dashed #56729a44;border-radius:50%}.sweep{position:absolute;inset:0;border-radius:50%;background:conic-gradient(from 0deg,transparent 270deg,#dcb86a22 328deg,#dfbf7c66 359deg,transparent 360deg);animation:sweep 12s linear infinite;opacity:.3}.radar.running .sweep{opacity:1}.center{position:absolute;inset:28%;border-radius:50%;background:#0b1830ed;border:1px solid #9e824f;display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:0 0 35px #071024}.direction{font-size:29px;font-weight:850;letter-spacing:-1px}.center small{font-size:9px;color:var(--muted);letter-spacing:1px}.up{color:var(--green)}.down{color:var(--red)}.neutral{color:var(--gold)}.radar-label{position:absolute;font:10px ui-monospace,monospace;color:#9db5d5}.radar-label.n{top:5px;left:calc(50% - 8px)}.radar-label.s{bottom:5px;left:calc(50% - 8px)}.radar-label.w{top:calc(50% - 8px);left:5px}.radar-label.e{top:calc(50% - 8px);right:5px}@keyframes sweep{to{transform:rotate(360deg)}}.radar-caption{display:flex;align-items:center;justify-content:space-between;margin-top:20px;gap:10px}.countdown{font:26px ui-monospace,monospace;letter-spacing:2px}.row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 0;border-bottom:1px solid #24344e88}.row:last-child{border:0}.row span:first-child{color:var(--muted);font-size:12px}.row strong{font-size:13px}.price{font-size:30px;font-weight:700;letter-spacing:-.7px}.quotes{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:18px 0}.quote{border:1px solid #395a5a;background:#183f382a;border-radius:7px;padding:12px}.quote.no{border-color:#61434f;background:#492b3b22}.quote span{font-size:10px;letter-spacing:1px}.quote strong{display:block;font-size:22px;margin-top:3px}.statusbar{border:1px solid #364b6b;border-radius:8px;padding:13px 16px;color:var(--muted);display:flex;gap:10px;align-items:start;font-size:12px;margin-bottom:20px;background:#101d32}.dot{flex:none;width:7px;height:7px;border-radius:50%;background:var(--gold);margin-top:6px}.actions{display:flex;gap:10px;flex-wrap:wrap}.actions button{flex:1;min-width:120px}.chart{height:125px;position:relative}canvas{width:100%;height:100%}.empty{padding:26px 8px;color:var(--muted);text-align:center;font-size:12px;border:1px dashed #334562;border-radius:8px}.position{padding:16px;border:1px solid #4e6181;border-radius:8px;margin-bottom:10px}.position .heading{display:flex;justify-content:space-between;font-size:18px;font-weight:750}.formgrid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.field label{display:block;color:#c8d6e9;font-size:12px;margin-bottom:7px}.field input{width:100%;background:#091426;border:1px solid #3b506f;color:var(--text);border-radius:6px;padding:12px 13px;min-height:44px}.field small{display:block;color:var(--muted);font-size:10px;margin-top:5px}.toggle{display:flex;gap:10px;align-items:center;padding:12px;background:#0d1930;border-radius:7px}.toggle input{accent-color:var(--gold);width:18px;height:18px}.formfooter{display:flex;align-items:center;justify-content:space-between;border-top:1px solid var(--line);margin-top:20px;padding-top:19px;gap:15px}.tablewrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap}th{text-align:left;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);padding:12px;border-bottom:1px solid #476080}td{padding:13px 12px;border-bottom:1px solid #263852}td small{color:var(--muted);font-size:10px}.log{display:grid;gap:10px;max-height:330px;overflow:auto}.logitem{display:grid;grid-template-columns:65px 70px 1fr;gap:10px;font-size:11px;padding:10px 0;border-bottom:1px solid #283b54}.logitem time{color:var(--muted)}.logitem b{color:var(--gold);font-size:9px;padding-top:2px}.footer{font-size:10px;color:#7f94b2;display:flex;justify-content:space-between;gap:15px;margin-top:18px}section[hidden]{display:none}.toast{position:fixed;right:22px;bottom:22px;background:#234d42;color:#e5fff4;border:1px solid #528b76;padding:14px 20px;max-width:min(440px,90vw);border-radius:8px;box-shadow:0 10px 40px #0008;z-index:10}.toast.error{background:#552d38;border-color:#a75d70}.login{position:fixed;inset:0;background:#080f20f7;z-index:20;display:grid;place-items:center;padding:20px}.login[hidden]{display:none}.login form{width:360px;max-width:100%}.login input{width:100%;padding:13px;background:#101e34;color:white;border:1px solid #506482;border-radius:6px;margin:20px 0}.login button{width:100%}.note{font-size:11px;color:var(--muted);line-height:1.7}.goldtext{color:var(--gold)}
@media(min-width:1450px){main{padding:32px 44px}.radar-wrap{min-height:350px}.radar{width:335px}}@media(max-width:1050px){.shell{grid-template-columns:170px minmax(0,1fr)}aside{padding:25px 12px}.logo{font-size:18px}main{padding:22px}.grid{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}.radar-wrap{min-height:270px}.radar{width:270px}}@media(max-width:640px){.shell{display:block}aside{padding:18px 16px 10px;border-right:0;border-bottom:1px solid var(--line);gap:16px}.brandmark,.aside-note{display:none}.logo{font-size:19px;display:flex;align-items:center;justify-content:space-between}.logo small{font-size:8px;letter-spacing:1px;margin:0}nav{display:flex;gap:5px}nav button{flex:1;text-align:center;padding:9px 3px;font-size:11px}nav b{display:none}main{padding:18px 14px}.topbar{margin-bottom:20px}.clock{display:none}.topbar strong{font-size:12px}.top-right{gap:4px}.pill{font-size:9px}h1{font-size:24px}.pagehead{align-items:center}.stats{gap:9px}.stat{padding:13px}.stat .value{font-size:22px}.eyebrow{font-size:9px;letter-spacing:1px}.panel{padding:17px}.grid{gap:0}.formgrid{gap:14px}.formfooter{align-items:start;flex-direction:column}.formfooter button{width:100%}.row strong{font-size:12px}.logitem{grid-template-columns:52px 55px 1fr;font-size:10px;gap:6px}.pagehead .button{font-size:10px;padding:8px}.footer{font-size:9px}.radar{width:260px}.panelhead h2{font-size:11px;letter-spacing:1px}.topbar .eyebrow{letter-spacing:.8px}}
@media(prefers-reduced-motion:reduce){.sweep{animation:none}}
</style></head><body>
<div class="shell"><aside><div class="logo"><div><div class="brandmark"></div>ALPHA EDGE</div><small>BTC EXECUTION TERMINAL</small></div><nav aria-label="Navegación principal"><button class="active" data-page="overview"><b>01</b>Resumen</button><button data-page="settings"><b>02</b>Operación y ajustes</button><button data-page="history"><b>03</b>Registro</button></nav><div class="aside-note"><span class="pill gold">ENTORNO DE PRUEBA</span><p style="margin-top:14px">Una estrategia.<br>Un mercado.<br>Control en cada entrada.</p><div class="row"><span>Mercado</span><strong>BTC · 15 min</strong></div><div class="row"><span>Motor</span><strong>APP 61</strong></div><div class="row"><span>Ejecución</span><strong>Simulada</strong></div></div></aside>
<main><header class="topbar"><div><div class="eyebrow">KALSHI / KXBTC15M</div><strong>Bitcoin · Mercado de 15 minutos</strong></div><div class="top-right"><span class="clock" id="clock">—</span><span class="pill gold">SIMULACIÓN</span><span class="pill" id="connection">CONECTANDO</span></div></header>
<div class="stats"><div class="stat"><div class="eyebrow">Saldo disponible</div><div class="value" id="cash">—</div><div class="sub">Capital virtual</div></div><div class="stat"><div class="eyebrow">Resultado del día</div><div class="value" id="daily">—</div><div class="sub">Neto · hora de Miami</div></div><div class="stat"><div class="eyebrow">Resultado acumulado</div><div class="value" id="realized">—</div><div class="sub">Operaciones cerradas · neto</div></div><div class="stat"><div class="eyebrow">Operaciones cerradas</div><div class="value" id="completed">—</div><div class="sub" id="wintext">Sin operaciones</div></div></div>
<section id="overview"><div class="pagehead"><div><div class="eyebrow">01 / CENTRO DE CONTROL</div><h1>Lectura. Decisión. Ejecución.</h1><p>Tu cerebro de señales, con control de operación.</p></div></div><div class="statusbar" role="status"><span class="dot"></span><span id="message">Esperando la primera lectura de mercado.</span></div><div class="grid"><div><div class="panel"><div class="panelhead"><h2>Radar de sesión</h2><span class="pill gold" id="botstatus">PAUSADO</span></div><div class="radar-wrap"><div class="radar" id="radar"><span class="radar-label n">00</span><span class="radar-label e">15</span><span class="radar-label s">30</span><span class="radar-label w">45</span><div class="sweep"></div><div class="center"><small>SEÑAL ACTIVA</small><span class="direction neutral" id="direction">—</span><small id="signalnote">ANALIZANDO</small></div></div></div><div class="radar-caption"><div><div class="eyebrow">Cierre de ronda</div><div class="countdown" id="countdown">—:—</div></div><div style="text-align:right"><div class="eyebrow">Primera señal</div><strong id="firstsignal">Sin confirmar</strong><div class="sub">Registro inmutable de la ronda</div></div></div><div class="row"><span>Ronda actual</span><strong id="ticker">Esperando mercado</strong></div><div class="row"><span>Estado del cerebro</span><strong id="quality">Esperando lectura</strong></div></div><div class="panel"><div class="panelhead"><h2>Recorrido BTC</h2><span class="sub">Lecturas recibidas en esta pantalla</span></div><div class="chart"><canvas id="chart" aria-label="Recorrido del precio BTC observado"></canvas></div><div class="sub" id="chartnote">La gráfica se construye al recibir precios actuales.</div></div><div class="actions"><button class="primary" id="start" onclick="command('start')">Activar simulación</button><button onclick="command('pause')">Pausar entradas</button><button class="danger" onclick="command('close')">Cerrar todo</button></div><p class="note" style="margin:12px 0 20px">Pausar mantiene la gestión de salidas. Cerrar todo espera un libro actual con liquidez; una posición vencida espera su liquidación oficial.</p></div><div><div class="panel"><div class="panelhead"><h2>Mercado en vivo</h2><span class="sub" id="source">—</span></div><div class="eyebrow">Bitcoin / USD</div><div class="price" id="btc">—</div><div class="row"><span>Target de la ronda</span><strong id="target">—</strong></div><div class="quotes"><div class="quote"><span class="up">UP / YES · COMPRA</span><strong id="yesask">—</strong></div><div class="quote no"><span class="down">DOWN / NO · COMPRA</span><strong id="noask">—</strong></div></div><div class="row"><span>RSI · 1 min</span><strong id="rsi">—</strong></div><div class="row"><span>Tendencia EMA</span><strong id="ema">—</strong></div><div class="row"><span>Última lectura válida</span><strong id="updated">—</strong></div><p class="note" id="retention"></p></div><div class="panel"><div class="panelhead"><h2>Posición en gestión</h2><span class="pill gold" id="positioncount">0 ABIERTAS</span></div><div id="positions"><div class="empty">Sin posición abierta.<br>El bot espera una señal confirmada.</div></div></div><div class="panel"><div class="panelhead"><h2>Plan de ejecución</h2><button style="padding:4px 9px;font-size:10px" onclick="page('settings')">Editar</button></div><div id="plan"></div><p class="note">Las entradas simuladas exigen profundidad para la cantidad completa. Las comisiones son una estimación configurable.</p></div></div></div></section>
<section id="settings" hidden><div class="pagehead"><div><div class="eyebrow">02 / OPERACIÓN</div><h1>Configura tu ejecución.</h1><p>Precios, tamaño y salidas en un solo lugar.</p></div><span class="pill gold">SIMULACIÓN</span></div><form id="settingsform"><div class="grid"><div><div class="panel"><div class="panelhead"><h2>Entradas automáticas</h2><span class="sub">UP y DOWN según el cerebro</span></div><div class="formgrid"><div class="field"><label for="contracts">Contratos por compra</label><input id="contracts" type="number" min="1" max="1000" required></div><div class="field"><label for="max_trade_dollars">Presupuesto máximo / compra ($)</label><input id="max_trade_dollars" type="number" min="1" max="100000" required><small>Incluye la comisión simulada.</small></div><div class="field"><label for="min_entry_cents">Precio mínimo (¢)</label><input id="min_entry_cents" type="number" min="1" max="98" required></div><div class="field"><label for="max_entry_cents">Precio máximo (¢)</label><input id="max_entry_cents" type="number" min="2" max="99" required><small>Se aplica a cada nivel de compra.</small></div><div class="field"><label for="max_entries_round">Máximo de entradas / ronda</label><input id="max_entries_round" type="number" min="1" max="100" required><small>Limita compras; el cerebro sigue cambiando de dirección.</small></div><div class="field"><label for="fee_cents_per_contract">Comisión estimada (¢ / contrato)</label><input id="fee_cents_per_contract" type="number" min="0" max="20" required><small>Se cobra en cada compra y venta simulada.</small></div></div></div><div class="panel"><div class="panelhead"><h2>Salidas y protección</h2><span class="sub">0 = desactivado</span></div><div class="formgrid"><div class="field"><label for="take_profit_cents">Take profit (+¢ por contrato)</label><input id="take_profit_cents" type="number" min="0" max="98" required><small>Sobre el precio medio de entrada; antes de comisiones.</small></div><div class="field"><label for="stop_loss_cents">Stop loss (−¢ por contrato)</label><input id="stop_loss_cents" type="number" min="0" max="98" required><small>Salida al precio disponible; puede superar este umbral.</small></div><div class="field"><label for="exit_before_close">Salir antes del cierre (segundos)</label><input id="exit_before_close" type="number" min="0" max="300" required></div></div><label class="toggle" style="margin-top:18px"><input id="close_on_reverse" type="checkbox"><span>Salir si el cerebro confirma la dirección contraria</span></label></div></div><div><div class="panel"><div class="panelhead"><h2>Control de sesión</h2></div><div class="field"><label for="starting_balance">Saldo virtual inicial ($)</label><input id="starting_balance" type="number" min="1" max="1000000" required><small>Se fija al realizar la primera operación.</small></div><div class="field" style="margin-top:18px"><label for="daily_loss_dollars">Pérdida diaria máxima ($)</label><input id="daily_loss_dollars" type="number" min="1" max="100000" required><small>Detiene compras nuevas al alcanzar la pérdida registrada.</small></div><div class="field" style="margin-top:18px"><label for="daily_goal_dollars">Meta diaria ($)</label><input id="daily_goal_dollars" type="number" min="0" max="100000" required><small>0 = sin meta. El día se calcula en hora de Miami.</small></div></div><div class="panel"><h3 class="goldtext">Tu estrategia permanece separada.</h3><p class="note">Estos ajustes controlan la ejecución. El análisis y las confirmaciones se extraen de «app 61» sin agregar filtros de IA ni fijar una dirección.</p><div class="row"><span>Conexión de datos</span><strong>Kalshi + Coinbase</strong></div><div class="row"><span>Cuenta Kalshi</span><strong>Sin vincular</strong></div><p class="note" style="margin-top:12px">Esta fase usa capital virtual y datos públicos. La activación con API y dinero real corresponde a la siguiente fase.</p></div></div></div><div class="formfooter"><p class="note">Los cambios de salida se aplican a compras nuevas.<br>Las posiciones abiertas conservan su take profit, stop loss y criterio de cierre.</p><button class="primary" type="submit">Guardar ajustes</button></div></form></section>
<section id="history" hidden><div class="pagehead"><div><div class="eyebrow">03 / REGISTRO</div><h1>Cada decisión, registrada.</h1><p>Entradas, salidas y resultado neto de la simulación.</p></div><a class="button" href="/api/history.csv">Exportar CSV</a></div><div class="panel"><div class="panelhead"><h2>Operaciones</h2><span class="sub">Últimas 200 · CSV completo</span></div><div class="tablewrap"><table><thead><tr><th>ID / Ronda</th><th>Dirección</th><th>Cantidad</th><th>Entrada</th><th>Salida</th><th>Resultado neto</th><th>Estado</th></tr></thead><tbody id="trades"></tbody></table></div></div><div class="panel"><div class="panelhead"><h2>Primera señal por ronda</h2><span class="sub">Independiente de las compras</span></div><div class="tablewrap"><table><thead><tr><th>Ronda</th><th>Primera señal</th><th>Hora</th><th>Señal activa</th></tr></thead><tbody id="rounds"></tbody></table></div></div><div class="panel"><div class="panelhead"><h2>Actividad del sistema</h2><span class="sub">Últimos 60 eventos</span></div><div class="log" id="events"></div></div></section>
<div class="footer"><span>ALPHA EDGE / APP 61 · BTC 15 MIN</span><span>Simulación con liquidez observada · sin dinero real</span></div></main></div><div class="toast" id="toast" hidden role="status"></div><div class="login" id="login" hidden><form id="loginform"><div class="logo">ALPHA EDGE</div><h1 style="margin-top:25px">Tu terminal privada.</h1><p>Introduce la contraseña de este servidor.</p><input id="password" type="password" placeholder="Contraseña" aria-label="Contraseña" autocomplete="current-password" required><button class="primary">Entrar</button><p id="loginerror" class="down"></p></form></div>
<script>
const $=id=>document.getElementById(id),money=n=>n==null?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n),cent=n=>n==null?'—':Number(n).toFixed(1)+'¢',esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),localtime=v=>v?new Date(v).toLocaleTimeString('es-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}):'—';let state=null,dirty=false,initialized=false,toastTimer,samples=[],laststamp='',closeAt=null;
function page(name){for(const k of ['overview','settings','history'])$(k).hidden=k!==name;document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===name));if(name==='overview')setTimeout(draw,0)}document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>page(b.dataset.page));
function toast(msg,error=false){$('toast').textContent=msg;$('toast').className='toast'+(error?' error':'');$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6000)}
async function api(path,data){const r=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{cache:'no-store'});const result=await r.json();if(r.status===401){$('login').hidden=false;throw Error('Inicia sesión.')}if(!r.ok)throw Error(result.error||'No se pudo completar la operación.');return result}
async function command(command){if(command==='close'&&!confirm('¿Pausar compras y solicitar el cierre de todas las posiciones simuladas?'))return;try{await api('/api/command',{command});toast(command==='start'?'Simulación activada.':command==='pause'?'Entradas pausadas. Las salidas siguen vigiladas.':'Cierre solicitado; esperando precios y liquidez.');await refresh()}catch(e){toast(e.message,true)}}
function row(a,b){return '<div class="row"><span>'+esc(a)+'</span><strong>'+esc(b)+'</strong></div>'}
function render(s){state=s;const totals=s.totals;for(const k of ['cash','daily','realized']){$(k).textContent=money(totals[k]);$(k).className='value'+(k!=='cash'?(totals[k]>=0?' up':' down'):'')} $('completed').textContent=totals.completed;$('wintext').textContent=totals.completed?totals.wins+' con resultado positivo':'Sin operaciones cerradas';$('message').textContent=s.message;$('botstatus').textContent=s.status;$('botstatus').className='pill '+(s.status==='SIN DATOS'?'red':s.running?'':'gold');$('radar').classList.toggle('running',s.running&&s.status!=='SIN DATOS');$('direction').textContent=s.signal||'—';$('direction').className='direction '+(s.signal==='UP'?'up':s.signal==='DOWN'?'down':'neutral');$('signalnote').textContent=s.signal?'CONFIRMADA':'ANALIZANDO';$('firstsignal').textContent=s.first_signal||'Sin confirmar';$('ticker').textContent=s.market?.ticker||'Esperando mercado';$('quality').textContent=s.quality||'Esperando lectura';$('source').textContent=s.source||'—';$('btc').textContent=money(s.price);$('target').textContent=money(s.target);$('rsi').textContent=s.rsi?.toFixed(1)||'—';$('ema').textContent=s.ema==='BULL'?'ALCISTA':s.ema==='BEAR'?'BAJISTA':'—';$('updated').textContent=localtime(s.updated);$('retention').textContent=s.retention||'';closeAt=s.market?.close_time?new Date(s.market.close_time):null;
const fresh=s.updated&&Date.now()-Date.parse(s.updated)<12000&&s.status!=='SIN DATOS';$('connection').textContent=fresh?'DATOS ACTIVOS':'ESPERANDO DATOS';$('connection').className='pill '+(fresh?'':'red');$('yesask').textContent=fresh?cent(s.book?.UP?.asks?.[0]?.[0]):'—';$('noask').textContent=fresh?cent(s.book?.DOWN?.asks?.[0]?.[0]):'—';$('start').disabled=s.running;$('start').textContent=s.running?'Simulación activa':'Activar simulación';
$('positioncount').textContent=s.positions.length+' ABIERTAS';$('positions').innerHTML=s.positions.length?s.positions.map(p=>{let bids=p.ticker===s.market?.ticker&&fresh?s.book?.[p.side]?.bids:[];let left=p.quantity,total=0;for(const [price,n] of bids||[]){let take=Math.min(left,n);left-=take;total+=take*price;if(left<=0)break}let net=left<=0?(total-p.entry*p.quantity)/100-p.entry_fee-s.settings.fee_cents_per_contract*p.quantity/100:null;return '<div class="position"><div class="heading"><span class="'+(p.side==='UP'?'up':'down')+'">'+esc(p.side)+'</span><span>'+esc(p.quantity)+' contrato(s)</span></div><div class="sub">'+esc(p.ticker)+'</div>'+row('Precio medio de entrada',cent(p.entry))+row('Valor neto de salida estimado',money(net))+row('Take profit / Stop loss',(p.tp?'+'+p.tp+'¢':'OFF')+' / '+(p.sl?'−'+p.sl+'¢':'OFF'))+'<div class="sub">'+(net==null?'Esperando libro actual o liquidación oficial.':'Incluye comisiones simuladas.')+'</div></div>'}).join(''):'<div class="empty">Sin posición abierta.<br>El bot espera una señal confirmada.</div>';
const cfg=s.settings;$('plan').innerHTML=row('Tamaño',cfg.contracts+' contrato(s)')+row('Rango de compra',cfg.min_entry_cents+'–'+cfg.max_entry_cents+'¢')+row('Take profit / Stop loss',(cfg.take_profit_cents?'+'+cfg.take_profit_cents+'¢':'OFF')+' / '+(cfg.stop_loss_cents?'−'+cfg.stop_loss_cents+'¢':'OFF'))+row('Máximo por ronda',cfg.max_entries_round+' entrada(s)');if(!initialized||!dirty){for(const [key,value]of Object.entries(cfg)){if($(key).type==='checkbox')$(key).checked=value;else $(key).value=value}initialized=true}$('starting_balance').disabled=s.trades.length>0;
$('trades').innerHTML=s.trades.length?s.trades.map(t=>'<tr><td>#'+t.id+'<br><small>'+esc(t.ticker)+'</small></td><td class="'+(t.side==='UP'?'up':'down')+'">'+esc(t.side)+'</td><td>'+t.quantity+'</td><td>'+cent(t.entry)+'</td><td>'+cent(t.exit)+'</td><td class="'+(t.pnl==null?'':t.pnl>=0?'up':'down')+'">'+money(t.pnl)+'</td><td>'+esc(t.reason||'ABIERTA')+'<br><small>'+localtime(t.closed||t.opened)+'</small></td></tr>').join(''):'<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:35px">Todavía no hay operaciones. Activa la simulación para comenzar.</td></tr>';
$('rounds').innerHTML=s.rounds.length?s.rounds.map(r=>'<tr><td>'+esc(r.ticker)+'</td><td>'+esc(r.first_direction||'SIN CONFIRMAR')+'</td><td>'+localtime(r.first_signal_time)+'</td><td>'+esc(r.active_direction||'ANALIZANDO')+'</td></tr>').join(''):'<tr><td colspan="4">Esperando la primera ronda.</td></tr>';$('events').innerHTML=s.events.map(e=>'<div class="logitem"><time>'+localtime(e.at)+'</time><b>'+esc(e.kind)+'</b><span>'+esc(e.message)+'</span></div>').join('');if(fresh&&s.updated!==laststamp&&s.price){laststamp=s.updated;samples.push(s.price);samples=samples.slice(-150);draw();$('chartnote').textContent=samples.length+' lecturas · '+(s.source||'')+' · precio observado'}tick()}
function tick(){$('clock').textContent=new Date().toLocaleTimeString('es-US',{timeZone:'America/New_York',hour12:false})+' ET';let left=closeAt?Math.max(0,Math.floor((closeAt-Date.now())/1000)):null;$('countdown').textContent=left==null?'—:—':String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0');if(state?.updated&&Date.now()-Date.parse(state.updated)>12000){$('connection').textContent='DATOS ATRASADOS';$('connection').className='pill red';$('radar').classList.remove('running')}}setInterval(tick,1000);
function draw(){const c=$('chart'),r=c.getBoundingClientRect();if(!r.width)return;let d=window.devicePixelRatio||1;c.width=r.width*d;c.height=r.height*d;let x=c.getContext('2d');x.scale(d,d);const w=r.width,h=r.height;x.strokeStyle='#283b5777';for(let i=1;i<4;i++){x.beginPath();x.moveTo(0,i*h/4);x.lineTo(w,i*h/4);x.stroke()}if(samples.length<2)return;let min=Math.min(...samples)-2,max=Math.max(...samples)+2;const points=samples.map((v,i)=>[i/(samples.length-1)*w,h-10-(v-min)/(max-min)*(h-20)]);let g=x.createLinearGradient(0,0,0,h);g.addColorStop(0,'#e5bd6830');g.addColorStop(1,'#e5bd6800');x.beginPath();x.moveTo(0,h);points.forEach(p=>x.lineTo(...p));x.lineTo(w,h);x.closePath();x.fillStyle=g;x.fill();x.beginPath();points.forEach((p,i)=>i?x.lineTo(...p):x.moveTo(...p));x.lineWidth=2;x.strokeStyle='#e5bd68';x.stroke()}window.addEventListener('resize',draw);
$('settingsform').addEventListener('input',()=>dirty=true);$('settingsform').onsubmit=async e=>{e.preventDefault();if(!state)return;let raw={};for(const k of Object.keys(state.settings))raw[k]=$(k).type==='checkbox'?$(k).checked:Number($(k).value);try{await api('/api/settings',raw);dirty=false;toast('Ajustes guardados. Se aplican a entradas nuevas.');await refresh()}catch(err){toast(err.message,true)}};
$('loginform').onsubmit=async e=>{e.preventDefault();try{await api('/api/login',{password:$('password').value});$('password').value='';$('login').hidden=true;await refresh()}catch(e){$('loginerror').textContent=e.message}};
let refreshing=false;async function refresh(){if(refreshing)return;refreshing=true;try{const s=await api('/api/state');$('login').hidden=true;render(s)}catch(e){$('connection').textContent='SIN CONEXIÓN';$('connection').className='pill red';if(!$('login').hidden)return;$('message').textContent='No se pudo conectar con el servidor. Última lectura conservada con su hora original.'}finally{refreshing=false}}refresh();setInterval(refresh,2000);
</script></body></html>

'''

ROOT = Path(__file__).resolve().parent
API = 'https://external-api.kalshi.com/trade-api/v2'
DEFAULTS = dict(contracts=1, min_entry_cents=10, max_entry_cents=60,
                take_profit_cents=12, stop_loss_cents=10, exit_before_close=20,
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
    bounds = {'contracts':(1,1000), 'min_entry_cents':(1,98), 'max_entry_cents':(2,99),
              'take_profit_cents':(0,98), 'stop_loss_cents':(0,98),
              'exit_before_close':(0,300), 'max_entries_round':(1,100),
              'daily_loss_dollars':(1,100000), 'daily_goal_dollars':(0,100000),
              'max_trade_dollars':(1,100000), 'starting_balance':(1,1000000),
              'fee_cents_per_contract':(0,20)}
    out = {}
    for key, (low, high) in bounds.items():
        v = raw[key]
        if isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or int(v) != v or not low <= v <= high:
            raise ValueError(f'Valor inválido para {key}: {low}–{high}.')
        out[key] = int(v)
    if not isinstance(raw['close_on_reverse'], bool):
        raise ValueError('El cierre por cambio de señal debe ser sí o no.')
    out['close_on_reverse'] = raw['close_on_reverse']
    if out['min_entry_cents'] > out['max_entry_cents']:
        raise ValueError('El precio mínimo no puede superar al máximo.')
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
        self.settings = self.kv('settings') or DEFAULTS.copy()
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
        reason=None
        if self.close_requested:
            reason='CIERRE MANUAL'
        elif p['tp'] and price>=p['entry']+p['tp']:
            reason='TAKE PROFIT'
        elif p['sl'] and price<=p['entry']-p['sl']:
            reason='STOP LOSS'
        elif p['exit_seconds'] and remaining is not None and 0<remaining<=p['exit_seconds']:
            reason='ANTES DEL CIERRE'
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
        if actual is None or actual<=max(s['exit_before_close'],0):
            return 'Fuera de ventana de entrada.'
        total=self.totals()
        if total['daily']<=-s['daily_loss_dollars']:
            return 'Límite diario de pérdida alcanzado.'
        if s['daily_goal_dollars'] and total['daily']>=s['daily_goal_dollars']:
            return 'Meta diaria alcanzada.'
        count=self.db.execute('SELECT COUNT(*) FROM trades WHERE ticker=?',(market['ticker'],)).fetchone()[0]
        if count>=s['max_entries_round']:
            return 'Máximo de entradas de esta ronda alcanzado.'
        price=fill_book(book[side]['asks'],s['contracts'],s['max_entry_cents'])
        if price is None:
            return 'Sin liquidez suficiente dentro del precio máximo.'
        if price<s['min_entry_cents']:
            return 'Precio inferior al mínimo configurado.'
        fee=s['contracts']*s['fee_cents_per_contract']/100
        cost=price*s['contracts']/100+fee
        if cost>s['max_trade_dollars'] or cost>total['cash']:
            return 'La compra supera el presupuesto o el saldo virtual disponible.'
        self.db.execute('INSERT INTO trades(ticker,side,quantity,entry,entry_fee,opened,tp,sl,exit_seconds,reverse) VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (market['ticker'],side,s['contracts'],price,fee,stamp(),s['take_profit_cents'],s['stop_loss_cents'],s['exit_before_close'],s['close_on_reverse']))
        self.event('ENTRADA',f"{side} · {s['contracts']} contrato(s) · {price:.2f}¢ · ejecución simulada FOK")
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
                           'rsi':sig['rsi'],'ema':sig['ema'],'updated':stamp(),
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

class Handler(BaseHTTPRequestHandler):
    bot: Bot
    password = ''
    sessions = {}
    session_lock = threading.Lock()
    def log_message(self,*args):
        pass

    def send(self,data,status=200,content_type='application/json',headers=None):
        payload=data if isinstance(data,bytes) else dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        for k,v in (headers or {}).items():
            self.send_header(k,v)
        self.end_headers()
        self.wfile.write(payload)

    def authenticated(self):
        if not self.password:
            return True
        cookie=self.headers.get('Cookie','')
        token=next((x.strip()[6:] for x in cookie.split(';') if x.strip().startswith('alpha=')),None)
        with self.session_lock:
            expires=self.sessions.get(token,0)
        return expires>time.time()

    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/healthz':
            return self.send({'ok':True,'mode':'paper'})
        if path=='/':
            return self.send(_INDEX.encode('utf-8'),content_type='text/html; charset=utf-8')
        if not self.authenticated():
            return self.send({'error':'Inicia sesión.'},401)
        if path=='/api/state':
            return self.send(self.bot.view())
        if path=='/api/history.csv':
            stream=io.StringIO()
            with self.bot.lock:
                rows=self.bot.db.execute('SELECT * FROM trades ORDER BY id').fetchall()
                fields=[d[0] for d in self.bot.db.execute('SELECT * FROM trades LIMIT 0').description]
                writer=csv.writer(stream);writer.writerow(fields);writer.writerows([tuple(r) for r in rows])
            return self.send(stream.getvalue().encode('utf-8-sig'),content_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=alpha_historial.csv'})
        self.send({'error':'No encontrado.'},404)

    def do_POST(self):
        # JSON-only + exact Origin prevents browser cross-site form actions.
        origin=self.headers.get('Origin')
        host=self.headers.get('Host','')
        if origin and urlsplit(origin).netloc!=host:
            return self.send({'error':'Origen no autorizado.'},403)
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.send({'error':'Se requiere JSON.'},415)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384:
                raise ValueError('Solicitud demasiado grande o vacía.')
            data=json.loads(self.rfile.read(length))
            path=urlsplit(self.path).path
            if path=='/api/login':
                # Constant-time comparison; use a strong ALPHA_PASSWORD on a hosted instance.
                if not isinstance(data.get('password'),str) or not hmac.compare_digest(data['password'].encode(),self.password.encode()):
                    return self.send({'error':'Contraseña incorrecta.'},403)
                token=secrets.token_urlsafe(32)
                with self.session_lock:
                    self.sessions={k:v for k,v in self.sessions.items() if v>time.time()}
                    type(self).sessions=self.sessions
                    self.sessions[token]=time.time()+43200
                secure='; Secure' if os.environ.get('ALPHA_SECURE_COOKIE')=='1' else ''
                return self.send({'ok':True},headers={'Set-Cookie':f'alpha={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200{secure}'})
            if not self.authenticated():
                return self.send({'error':'Inicia sesión.'},401)
            if path=='/api/settings':
                self.bot.save_settings(data)
            elif path=='/api/command':
                self.bot.command(data.get('command'))
            else:
                return self.send({'error':'No encontrado.'},404)
            self.send({'ok':True})
        except (ValueError,TypeError,AttributeError) as e:
            self.send({'error':str(e)},400)
        except Exception:
            self.send({'error':'No se pudo guardar la operación.'},500)

def main():
    host=os.environ.get('BIND','127.0.0.1')
    password=os.environ.get('ALPHA_PASSWORD','')
    if host not in ('127.0.0.1','localhost','::1') and len(password)<12:
        raise SystemExit('Define ALPHA_PASSWORD de al menos 12 caracteres para acceso externo.')
    db=Path(os.environ.get('ALPHA_DB',ROOT/'data'/'alpha.sqlite3'))
    db.parent.mkdir(parents=True,exist_ok=True)
    lock=open(str(db)+'.lock','a+')
    try:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0); lock.write('0'); lock.flush(); lock.seek(0)
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        raise SystemExit('Ya hay un servidor operando esta base. Usa una sola instancia.')
    Handler.password=password
    Handler.bot=Bot(db)
    server=ThreadingHTTPServer((host,int(os.environ.get('PORT','8000'))),Handler)
    Handler.bot.start_worker()
    print(f'ALPHA EDGE · simulación · http://{host}:{server.server_port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        Handler.bot.stop_event.set()
        server.server_close()
        if Handler.bot.thread:
            Handler.bot.thread.join(timeout=40)
        Handler.bot.db.close()
        lock.close()


# Streamlit entry point. The signal engine and paper execution above are unchanged.
import streamlit as st
import pandas as pd
st.set_page_config(page_title='ALPHA EDGE · Simulación', page_icon='📈', layout='wide')
st.markdown('''<style>
.stApp {background:#080f20;color:#e8edf7}
[data-testid="stSidebar"]{background:#101b32}
h1,h2,h3{color:#e7c36b!important} 
[data-testid="stMetric"]{background:#122039;border:1px solid #344564;border-radius:12px;padding:16px}
.stButton>button,.stFormSubmitButton>button{border:1px solid #c5a659;border-radius:8px}
</style>''',unsafe_allow_html=True)

@st.cache_resource
def paper_bot():
    db=ROOT/'data'/'streamlit_paper.sqlite3'
    db.parent.mkdir(parents=True,exist_ok=True)
    b=Bot(db)
    b.start_worker()
    return b

bot=paper_bot()
st.sidebar.title('ALPHA EDGE')
st.sidebar.caption('BTC · 15 MINUTOS')
st.sidebar.info('SIMULACIÓN · Sin compras con dinero real')
page=st.sidebar.radio('Terminal',['Operación','Ajustes','Historial'])
st.sidebar.caption('En Streamlit Cloud el proceso puede suspenderse. Descarga el historial antes de reiniciar: el disco no es permanente.')
st.title('ALPHA EDGE')
st.caption('Tu cerebro de señales · Ejecución automática simulada')

labels={
'contracts':'Contratos por entrada','min_entry_cents':'Precio mínimo de compra (¢)',
'max_entry_cents':'Precio máximo de compra (¢)','take_profit_cents':'Take profit: subida desde entrada (¢)',
'stop_loss_cents':'Stop loss: caída desde entrada (¢)','exit_before_close':'Salir antes del cierre (segundos)',
'max_entries_round':'Máximo de entradas por ronda','daily_loss_dollars':'Límite de pérdida diaria ($)',
'daily_goal_dollars':'Objetivo diario ($; 0 desactiva)','max_trade_dollars':'Máximo por operación ($)',
'starting_balance':'Saldo inicial simulado ($)','fee_cents_per_contract':'Comisión simulada por contrato (¢)'}
bounds={'contracts':(1,1000),'min_entry_cents':(1,98),'max_entry_cents':(2,99),
 'take_profit_cents':(0,98),'stop_loss_cents':(0,98),'exit_before_close':(0,300),
 'max_entries_round':(1,100),'daily_loss_dollars':(1,100000),'daily_goal_dollars':(0,100000),
 'max_trade_dollars':(1,100000),'starting_balance':(1,1000000),'fee_cents_per_contract':(0,20)}

if page=='Ajustes':
    st.subheader('Plan de operación simulada')
    with st.form('settings'):
        cfg=bot.view()['settings']
        cols=st.columns(2)
        for i,(key,label) in enumerate(labels.items()):
            lo,hi=bounds[key]
            cfg[key]=cols[i%2].number_input(label,min_value=lo,max_value=hi,value=int(cfg[key]),step=1,key=key)
        cfg['close_on_reverse']=st.checkbox('Cerrar posición si el cerebro confirma la dirección contraria',value=cfg['close_on_reverse'])
        st.caption('Take profit y stop loss en 0 desactivan esa salida. Las posiciones abiertas conservan su plan original.')
        if st.form_submit_button('Guardar ajustes'):
            try:
                bot.save_settings(cfg)
                st.success('Ajustes guardados.')
            except ValueError as e:
                st.error(str(e))
else:
    @st.fragment(run_every='2s')
    def live_panel():
        v=bot.view()
        if page=='Operación':
            cols=st.columns(3)
            if cols[0].button('Iniciar simulación',use_container_width=True):
                bot.command('start'); v=bot.view()
            if cols[1].button('Pausar entradas',use_container_width=True):
                bot.command('pause'); v=bot.view()
            if cols[2].button('Cerrar posiciones simuladas',use_container_width=True):
                bot.command('close'); v=bot.view()
            st.caption('Pausar detiene entradas nuevas; las salidas siguen vigiladas mientras el proceso esté activo.')
            a,b,c,d=st.columns(4)
            a.metric('Estado',v['status'])
            b.metric('Dirección confirmada',v.get('signal') or 'ANALIZANDO')
            c.metric('Efectivo simulado',f"${v['totals']['cash']:,.2f}")
            d.metric('Resultado diario',f"${v['totals']['daily']:,.2f}")
            st.info(v.get('message','Esperando lectura'))
            if v.get('status')=='SIN DATOS':
                st.warning('No hay lectura actual válida. Los valores anteriores pueden estar vencidos.')
            a,b,c=st.columns(3)
            price=v.get('price'); target=v.get('target'); remaining=v.get('seconds_left')
            a.metric('BTC observado',f'${price:,.2f}' if price else '—')
            b.metric('Objetivo de la ronda',f'${target:,.2f}' if target else '—')
            c.metric('Tiempo en última lectura',f'{int(remaining)//60:02d}:{int(remaining)%60:02d}' if remaining is not None else '—')
            st.caption(f"Ronda: {v.get('market',{}).get('ticker','—')} · Actualización: {v.get('updated','—')} · Fuente: {v.get('source','—')}")
            st.subheader('Posiciones simuladas abiertas')
            if v['positions']: st.dataframe(pd.DataFrame(v['positions']),hide_index=True,use_container_width=True)
            else: st.caption('Sin posiciones abiertas.')
            st.subheader('Primeras señales de cada ronda')
            if v['rounds']:
                rows=[{'Ronda':r['ticker'],'Primera señal':r.get('first_direction'),'Dirección actual':r.get('active_direction')} for r in v['rounds']]
                st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        else:
            st.subheader('Historial de simulación')
            df=pd.DataFrame(v['trades'])
            st.download_button('Descargar operaciones CSV',df.to_csv(index=False).encode('utf-8-sig'),'alpha_operaciones.csv','text/csv')
            st.dataframe(df,hide_index=True,use_container_width=True)
            st.subheader('Registro del sistema')
            st.dataframe(pd.DataFrame(v['events']),hide_index=True,use_container_width=True)
    live_panel()
