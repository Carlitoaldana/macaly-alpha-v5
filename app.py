import copy
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Gráfica BTC · UP / DOWN", layout="wide", initial_sidebar_state="collapsed")


def _validate_btc_candle_frame(frame, requested_at, source):
    """Common contract for a single BTC/USD venue; no filling/interpolation."""
    columns = ["time", "low", "high", "open", "close", "volume"]
    frame = frame[columns].copy()
    frame["time"] = pd.to_numeric(frame["time"], errors="coerce")
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True, errors="coerce")
    if frame["time"].isna().any():
        raise ValueError(source + ": fechas inválidas.")
    start = requested_at.replace(second=0, microsecond=0) - pd.Timedelta(minutes=299)
    frame = frame[(frame["time"] >= pd.Timestamp(start)) &
                  (frame["time"] <= pd.Timestamp(requested_at))]
    frame = frame.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    if len(frame) < 30:
        raise ValueError(source + ": menos de 30 velas actuales.")
    for column in columns[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    values = frame[columns[1:]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError(source + ": precios o volúmenes inválidos.")
    if ((frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any()
            or (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any()):
        raise ValueError(source + ": máximos/mínimos inconsistentes.")
    if (frame["time"] != frame["time"].dt.floor("min")).any():
        raise ValueError(source + ": intervalos distintos de 1 minuto.")
    gaps = frame["time"].diff().dropna() != pd.Timedelta(minutes=1)
    if gaps.any():
        missing = frame.loc[gaps[gaps].index[0], "time"] - pd.Timedelta(minutes=1)
        raise ValueError(source + ": historial incompleto cerca de " + missing.strftime("%H:%M UTC") + ".")
    received_at = datetime.now(timezone.utc)
    latest = frame.iloc[-1]["time"]
    age = (received_at - latest.to_pydatetime()).total_seconds()
    if not -5 <= age <= 120:
        raise ValueError(source + f": última vela atrasada ({age:.0f} s).")
    frame.attrs.update(received_at=received_at.isoformat(), latest_candle_at=latest.isoformat(),
                       candle_age_seconds=age, candle_source=source, candle_pair="BTC/USD")
    return frame


def _fetch_btc_candle_source(source, requested_at):
    """Normalize real public 1m candles, retaining their original OHLCV."""
    start = requested_at.replace(second=0, microsecond=0) - pd.Timedelta(minutes=299)
    headers = {"User-Agent": "MacalyAlphaBot/4.6.1", "Cache-Control": "no-cache"}
    if source == "COINBASE":
        response = requests.get(
            "https://api.exchange.coinbase.com/products/BTC-USD/candles",
            params={"granularity": 60, "start": start.isoformat(), "end": requested_at.isoformat()},
            headers=headers, timeout=8)
        response.raise_for_status()
        rows = response.json()
        if (not isinstance(rows, list) or not rows or
                any(not isinstance(row, (list, tuple)) or len(row) != 6 for row in rows)):
            raise ValueError("COINBASE: respuesta de velas inválida.")
        frame = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    elif source == "KRAKEN":
        response = requests.get("https://api.kraken.com/0/public/OHLC",
            params={"pair": "XBTUSD", "interval": 1, "since": int(start.timestamp())},
            headers=headers, timeout=8)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("error"):
            raise ValueError("KRAKEN: consulta de velas no disponible.")
        result = data.get("result")
        # Bind the response to the requested dollar market, never another pair.
        rows = result.get("XXBTZUSD") if isinstance(result, dict) else None
        if rows is None and isinstance(result, dict):
            rows = result.get("XBTUSD")
        if (not isinstance(rows, list) or not rows or
                any(not isinstance(row, (list, tuple)) or len(row) != 8 for row in rows)):
            raise ValueError("KRAKEN: respuesta BTC/USD inválida.")
        frame = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"])
    else:
        raise ValueError("Fuente de velas desconocida.")
    return _validate_btc_candle_frame(frame, requested_at, source)


def _fetch_current_btc_candles():
    """Use one complete venue history, not bars stitched across exchanges.

    Coinbase stays primary. If its response is missing minute buckets, the
    entire analysis window comes from Kraken BTC/USD and is validated under
    the same contract. Both failures keep the existing no-signal behavior.
    """
    failures = []
    for source in ("COINBASE", "KRAKEN"):
        try:
            frame = _fetch_btc_candle_source(source, datetime.now(timezone.utc))
            frame.attrs["candle_fallback"] = bool(failures)
            return frame
        except Exception as error:
            failures.append(source + ": " + str(error))
    raise ValueError("No hay historial BTC/USD completo y actual. " + " | ".join(failures))


@st.cache_data(ttl=5)
def get_btc_data():
    return _fetch_current_btc_candles()


def _chart_ut_state(candles, atr_period=10, sensitivity=1.0):
    """UT Bot Alerts by QuantNomad, using regular candles and Wilder's ATR."""
    ranges = []
    markers = []
    previous_close = None
    atr = None
    stop = None
    for candle in candles.itertuples(index=False):
        close = float(candle.close)
        high = float(candle.high)
        low = float(candle.low)
        true_range = high - low
        if previous_close is not None:
            true_range = max(true_range, abs(high - previous_close), abs(low - previous_close))
        prior_close, previous_close = previous_close, close

        if atr is None:
            ranges.append(true_range)
            if len(ranges) < atr_period:
                continue
            atr = sum(ranges) / atr_period
        else:
            atr += (true_range - atr) / atr_period
        gap = sensitivity * atr
        prior_stop = stop
        reference = 0.0 if prior_stop is None else prior_stop
        if close > reference and prior_close is not None and prior_close > reference:
            stop = max(reference, close - gap)
        elif close < reference and prior_close is not None and prior_close < reference:
            stop = min(reference, close + gap)
        else:
            stop = close - gap if close > reference else close + gap

        if prior_stop is None:
            continue
        if prior_close <= prior_stop and close > stop:
            markers.append({"time": int(candle.time.timestamp()), "direction": "UP"})
        elif prior_close >= prior_stop and close < stop:
            markers.append({"time": int(candle.time.timestamp()), "direction": "DOWN"})
    side = None
    if stop is not None and previous_close != stop:
        side = "UP" if previous_close > stop else "DOWN"
    return markers, side


def _neon_payload(df, live_price, target, active, timeframe, sig, whale, market=None, round_df=None):
    intervals = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1D": 1440}
    minutes = intervals[timeframe]
    frame = df.copy().sort_values("time").drop_duplicates("time")
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    if timeframe in ("3m", "5m", "4h"):
        frame = frame.set_index("time").resample(f"{minutes}min").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna().reset_index()
    now = pd.Timestamp.now(tz="UTC")
    bucket = now.floor(f"{minutes}min")
    price = float(live_price) if live_price is not None else None
    if price is not None and len(frame) and frame.iloc[-1]["time"] == bucket:
        idx = frame.index[-1]
        frame.loc[idx, "close"] = price
        frame.loc[idx, "high"] = max(float(frame.loc[idx, "high"]), price)
        frame.loc[idx, "low"] = min(float(frame.loc[idx, "low"]), price)
    reversal_markers, ut_side = _chart_ut_state(frame)
    close = frame["close"].astype(float)
    frame["ema9"] = close.ewm(span=9, adjust=False).mean()
    frame["ema21"] = close.ewm(span=21, adjust=False).mean()
    delta = close.diff()
    gains = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    losses = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    frame["rsi"] = 100 - 100/(1 + gains/losses.replace(0, np.nan))
    frame.loc[(losses == 0) & (gains > 0), "rsi"] = 100
    frame.loc[(losses == 0) & (gains == 0), "rsi"] = 50
    # VWAP diario UTC de la historia disponible; nunca inventa volumen histórico.
    typical = (frame["high"].astype(float) + frame["low"].astype(float) + close)/3
    day = frame["time"].dt.floor("D")
    vol = frame["volume"].astype(float)
    frame["vwap"] = (typical*vol).groupby(day).cumsum()/vol.groupby(day).cumsum().replace(0, np.nan)
    frame = frame.tail(180).reset_index(drop=True)
    rows = []
    for _, row in frame.iterrows():
        item = {k: (float(row[k]) if pd.notna(row[k]) and np.isfinite(float(row[k])) else None)
                for k in ["open", "high", "low", "close", "volume", "ema9", "ema21", "rsi", "vwap"]}
        item["t"] = int(row["time"].timestamp())
        rows.append(item)
    tape = st.session_state.get("whale_flow_tape", []) if whale is not None else []
    stamp = now.timestamp()
    recent = [r for r in tape if 0 <= stamp-float(r["t"]) <= 30]
    buy = sum(float(r["notional"]) for r in recent if r["side"] == "COMPRA")
    sell = sum(float(r["notional"]) for r in recent if r["side"] == "VENTA")
    threshold = 10000
    buys = sum(r["side"] == "COMPRA" and r["notional"] >= threshold for r in recent)
    sells = sum(r["side"] == "VENTA" and r["notional"] >= threshold for r in recent)
    last10 = sum(r["notional"] for r in recent if stamp-r["t"] <= 10)
    prior20 = sum(r["notional"] for r in recent if 10 < stamp-r["t"] <= 30)
    activity = (last10/10)/(prior20/20) if prior20 > 0 else None
    imbalance = abs(buy-sell)/(buy+sell) if buy+sell else 0
    direction = "UP" if buy > sell else "DOWN" if sell > buy else "NEUTRAL"
    round_start = round_end = None
    latest = rows[-1]["close"] if rows else None
    recent_levels = rows[-21:-1]
    support = min((r["low"] for r in recent_levels), default=None)
    resistance = max((r["high"] for r in recent_levels), default=None)
    if rows:
        reversal_markers = [mark for mark in reversal_markers if mark["time"] >= rows[0]["t"]]
    return {"ut_side": ut_side, "observed": int(now.timestamp()), "rows": rows, "reversal_markers": reversal_markers,
            "candle_source": df.attrs.get("candle_source", "COINBASE"), "timeframe": timeframe, "price": price or latest,
            "target": float(target) if target is not None else None,
            "signal": active if active in ("UP", "DOWN") else "ESPERANDO",
            "up": float(sig.get("up_probability", 50)),
            "down": float(sig.get("down_probability", 50)),
            "support": support, "resistance": resistance, "round_start": round_start, "round_end": round_end,
            "flow": {"ok": whale is not None, "buy": buy, "sell": sell,
                     "buys": buys, "sells": sells, "direction": direction,
                     "strength": "ALTA" if imbalance >= .6 else "MEDIA" if imbalance >= .3 else "BAJA",
                     "activity": activity, "threshold": threshold},
            "mom3": sig.get("mom3"), "mom5": sig.get("mom5"), "mom15": sig.get("mom15"),
            "updated": now.strftime("%H:%M:%S UTC"),
            "age": max(0, stamp-rows[-1]["t"]) if rows else None}


_NEON_HTML = r'''<!DOCTYPE html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;background:#06121a;color:#e8edf6;font-family:Inter,system-ui,sans-serif}button,summary{-webkit-tap-highlight-color:transparent}button{font:inherit;cursor:pointer}.panel{box-shadow:0 0 18px #00dfb555,inset 0 0 16px #00dfb518;border:1px solid #00dfb5;border-radius:27px;overflow:hidden;background:radial-gradient(ellipse at 95% 0,rgba(0,100,85,.12),transparent 40%),#06121a;box-shadow:inset 0 0 18px #7b3de31c,0 0 12px #9b54ff20;margin:4px 3px}.header{padding:24px 21px 17px;display:flex;align-items:start;justify-content:space-between;gap:8px}.header h2{margin:0;font-size:25px;letter-spacing:-.8px}.sub{color:#949bb6;font-size:11px;font-weight:700;letter-spacing:1px;margin-top:8px}.price{font-size:25px;letter-spacing:-1px;font-weight:900;color:#00dfb5;text-shadow:0 0 19px #00e4ba40}.live{font-size:10px;color:#00dfb5;text-align:right;margin-top:7px}.cards{padding:0 20px 20px;display:grid;grid-template-columns:1fr 1fr;gap:12px}.card{min-height:104px;padding:17px;border:1px solid #35324d;border-radius:19px;background:linear-gradient(130deg,#0c1421,#080a14)}.card .label{font-size:10px;letter-spacing:1.8px;font-weight:800;color:#7c879d}.card strong{font-size:24px;display:block;margin-top:10px;line-height:1.2}.card small{color:#7e8b9f;font-size:10px;display:block;margin-top:8px}.purple{color:#c080ff}.cyan{color:#54d5f7}.green{color:#00dfb5}.red{color:#e64b4b}.status{font-size:17px!important}.signal{border-color:#9e355b;background:linear-gradient(120deg,#21101e55,#0b0a15)}details{border-top:1px solid #26303c;border-bottom:1px solid #26303c;border-radius:20px;margin:0 0 12px;background:#070c14}summary{cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:22px 20px;font-size:14px;font-weight:850;letter-spacing:.5px}summary::-webkit-details-marker{display:none}summary small{font-size:9px;color:#758894;margin-left:auto;max-width:170px;letter-spacing:1px}summary:after{content:'+';color:#00dfb5;font-size:24px}details[open]>summary:after{content:'−'}.detail{padding:18px 20px 20px;border-top:1px solid #19232e}.detail h3{font-size:13px;margin:0 0 5px}.note{font-size:10px;color:#7e8b9f;line-height:1.7}.watch{font-size:14px;font-weight:800;color:#ffd057;padding:15px 0}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:9px}.metric{border:1px solid #1c2733;background:#080d17;padding:15px;border-radius:13px}.metric small{display:block;color:#8692a9;font-size:10px;font-weight:750;letter-spacing:.4px}.metric b{display:block;font-size:20px;margin-top:9px}.bars{margin:20px 0}.bar{display:flex;gap:12px;align-items:center;font-size:10px;color:#8b96ac;margin:12px 0}.track{height:7px;background:#19202c;border-radius:8px;flex:1}.track i{height:100%;display:block;border-radius:8px}.bar b{width:65px;text-align:right}.count{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:16px}.count .metric{display:flex;align-items:center;justify-content:space-between;gap:6px}.count b{font-size:29px}.difference{margin-top:10px;display:flex;justify-content:space-between;align-items:center}.difference b{font-size:24px}.tools{padding:0 20px}.tools h3{font-size:12px;color:#7f8ca6;letter-spacing:2px;margin:15px 0 12px}.toggles{display:flex;flex-wrap:wrap;gap:9px}.toggle{padding:11px 13px;border:1px solid #23685e;border-radius:30px;background:#130f24;color:#e3e3f5;font-size:11px;font-weight:750}.toggle:before{content:'●';color:var(--c);margin-right:8px;text-shadow:0 0 11px var(--c)}.toggle span{font-size:9px;color:#9390a7;margin-left:6px}.toggle.off{opacity:.4}.legend{font-size:10px;color:#99a4bd;margin:16px 0 10px;display:flex;gap:10px;flex-wrap:wrap;font-weight:700}.canvas{position:relative;width:100%;touch-action:none;cursor:grab}.canvas svg{display:block;width:100%;height:auto;user-select:none}.floatcounts{display:flex;gap:10px;padding:0 20px;margin-top:4px}.floatcounts div{flex:1;border:1px solid #00dfb5;border-radius:14px;padding:10px;color:#00dfb5;font-size:11px;font-weight:800}.floatcounts div:last-child{border-color:#e64b4b;color:#e64b4b}.floatcounts b{font-size:22px;margin-left:8px}.chartnav{display:flex;align-items:center;gap:8px;padding:10px 20px;border-top:1px solid #202738;flex-wrap:wrap}.chartnav button{border:1px solid #393254;border-radius:8px;color:#bec2d6;background:#0e1421;padding:6px 11px;font-size:11px}.chartnav span{font-size:10px;color:#7b879d;margin-left:auto}.tooltip{min-height:33px;padding:6px 20px;color:#aab6cc;font-size:10px;line-height:1.6}.footer{font-size:9px;line-height:1.6;color:#7c889e;padding:10px 20px 18px}.empty{padding:80px 20px;text-align:center;color:#95a0b6}@media(max-width:460px){.header{padding:20px 16px 16px}.header h2,.price{font-size:22px}.cards{grid-template-columns:1fr;padding:0 16px 18px}.card{min-height:106px}.card strong{font-size:25px}.tools,.detail{padding-left:16px;padding-right:16px}summary{padding:20px 16px;font-size:13px}summary small{max-width:135px;font-size:8px}.toggle{padding:10px 12px}.count .metric{padding:10px}.count small{font-size:8px}.count b{font-size:25px}.metric b{font-size:20px}}

/* Strong neon and readable labels across both visual surfaces. */
.green{color:#00dfb5!important;text-shadow:0 0 5px #00dfb588,0 0 14px #00dfb555!important}
.red{color:#e64b4b!important;text-shadow:0 0 5px #e64b4b88,0 0 14px #e64b4b55!important}
.pup,.prob-up{background:#00dfb5!important;box-shadow:0 0 8px #00dfb588,0 0 22px #00dfb544!important}
.pdown,.prob-down{background:#e64b4b!important;box-shadow:0 0 8px #e64b4b88,0 0 22px #e64b4b44!important}
.prenote,.readerbody small,.finalnote,.analysistext span,.features span,.chartfoot{font-size:11px!important;color:#cbd5e1!important;line-height:1.5!important}
.pretitle,.prebadge,.readerhead,.finaltitle,.motionrow small,.analysistext small,.probbox small,.features strong{font-size:10px!important}
.rhero{filter:drop-shadow(0 0 9px var(--accent))}
.note,.footer,.sub,.card small,.metric small,.tooltip,.chartnav span,summary small{color:#cbd5e1!important;font-size:11px!important}
.floatcounts div{border-color:#00dfb5;box-shadow:0 0 9px #00dfb544}.floatcounts div:last-child{border-color:#e64b4b;box-shadow:0 0 9px #e64b4b44}
.canvas svg rect,.canvas svg line{shape-rendering:geometricPrecision}
@media(max-width:460px){.finalgrid{grid-template-columns:1fr 1fr}.finalcard.motion{grid-column:1 / -1}.features{grid-template-columns:1fr}.prehead{flex-wrap:wrap;gap:6px}.prebadge{max-width:100%}.finalanalysis{grid-template-columns:1fr 90px}}


/* Purple neon outlines, consistent across dashboard and chart cards. */
.rcard,.mini,.section,.close-reader,.reader,.presignal,.refapp>section[style],
.finalclose,.finalcard,.analysisbox,.probbox,.chartbox,
.panel,.card,.metric,details,.floatcounts div{
 border-color:#23685e!important;
 box-shadow:0 0 4px #00dfb51a,inset 0 0 4px #00dfb508!important;
}
.panel{border:1.5px solid #23685e!important;margin:8px 6px!important}
.rcard,.mini,.reader,.presignal,.card,.metric,details{border-width:1.5px!important}
.techrow,.rnav,.chartnav{border-color:#23685e!important}


/* Uniform turquoise presentation. Signal values and timing are unchanged. */
.stApp,[data-testid="stAppViewContainer"]{background:#06121a!important}
.refapp .rcard,.refapp .reader,.refapp .presignal,.refapp .finalclose,
.refapp .finalcard,.refapp .analysisbox,.refapp .probbox,.refapp>section[style],
.panel,.panel .card,.panel .metric,.panel details,.panel .floatcounts div{
 background:linear-gradient(125deg,#0c2026,#0a151e)!important;
 border-color:#23685e!important;box-shadow:none!important;
}
.refapp .techrow,.refapp .techrow>div,.refapp .rnav,.panel .chartnav{border-color:#244047!important}
.refapp .gear,.panel summary:after{color:#00dfb5!important;text-shadow:none!important}
.refapp .finalcard,.refapp .finalclose,.refapp .analysisbox,.refapp .probbox{border-color:#244047!important}
.stRadio label,[data-testid="stButton"] button,.panel .toggle,.panel .chartnav button{
 background:#0a151e!important;border-color:#23685e!important;color:#e3f0ee!important;
}
.panel{background:#06121a!important}


/* JC ALPHA EDGE — champagne claro de referencia; solo CSS */
:root{--jc-gold:#e1c99c;--jc-gold-soft:rgba(225,201,156,.92)}
.refapp .rcard,.refapp .reader,.refapp .presignal,.refapp .finalclose,
.refapp .finalcard,.refapp .analysisbox,.refapp .probbox,.refapp .chartbox,
.refapp>section[style],.refapp .tech,.refapp .rconf,
.panel,.panel .card,.panel .metric,.panel details,.panel .floatcounts div,
.panel .chartnav button,.panel .toggle,
#alpha-recent-alerts .ra93-panel,#alpha-recent-alerts .ra93-card{
 border-color:var(--jc-gold-soft)!important;
 box-shadow:0 0 2px rgba(225,201,156,.13)!important;
}
.refapp .techrow,.refapp .techrow>div,.refapp .rnav,
.refapp .motionrow>div,.panel .chartnav{
 border-color:rgba(225,201,156,.30)!important;
}
.refapp .prebadge,.refapp .readerhead em{
 border-color:var(--jc-gold-soft)!important;
}
.refapp .rtitle{color:#f1d6a5!important;text-shadow:none!important}
.refapp .gear{color:#f1d6a5!important;text-shadow:none!important}
.refapp .rconf{border-color:var(--jc-gold-soft)!important}
.refapp .rlive{color:#e7d5b8!important;border:1px solid var(--jc-gold-soft)!important;border-radius:18px!important;padding:3px 7px!important;bottom:-2px!important}
.refapp .rlive i{background:var(--accent)!important;box-shadow:0 0 9px var(--glow)!important}
/* Colores de señales, alertas, barras y números intactos. */

/* TradingView Lightweight Charts: gestures managed by the native library */
#canvas{height:420px!important;position:relative!important;overflow:hidden!important;touch-action:none!important;-webkit-user-select:none!important;user-select:none!important}
#canvas canvas{touch-action:none!important}
#whale,#momentum,.floatcounts,.tooltip{display:none!important}
#rsi-pane{position:relative;overflow:hidden}
@media(max-width:480px){#canvas{height:375px!important}}
.expanded-chart #canvas{height:max(180px,calc(100dvh - 260px))!important}
</style>
<section class="panel">
<div style="padding:8px 16px;color:#f1d6a5;font-size:14px">Ronda Kalshi · <strong id="round-clock" style="font-variant-numeric:tabular-nums">—</strong></div>
<!-- Panel BTC/USD y tarjetas visuales retirados. Se conservan los nodos que usa el JavaScript para actualizar datos. -->
<div style="display:none!important" aria-hidden="true"><span id="subtitle"></span><span id="price"></span><span id="live"></span><span id="signal"></span><span id="model"></span><span id="status"></span><span id="updated"></span></div>
<details id="whale"><summary>🐋 WHALE FLOW <small>EN VIVO · TOCA PARA ABRIR</small></summary><div class="detail"><h3>🐋 WHALE FLOW — LIVE</h3><div class="note">Operaciones observadas de Coinbase · últimos 30 s</div><div class="watch" id="watch"></div><div class="metrics"><div class="metric"><small>BUY FLOW</small><b class="green" id="buy"></b></div><div class="metric"><small>SELL FLOW</small><b class="red" id="sell"></b></div><div class="metric"><small>DIFERENCIA</small><b id="diff"></b></div><div class="metric"><small>ACTIVIDAD</small><b id="activity"></b></div><div class="metric"><small>FUERZA DEL DESEQUILIBRIO</small><b id="strength"></b></div></div><div class="bars"><div class="bar">BUY<div class="track"><i id="buybar" style="background:#00dfb5"></i></div><b id="buytotal"></b></div><div class="bar">SELL<div class="track"><i id="sellbar" style="background:#e64b4b"></i></div><b id="selltotal"></b></div></div><div class="count"><div class="metric"><small>🐋 BUY WHALES</small><b class="green" id="buys"></b></div><div class="metric"><small>🐋 SELL WHALES</small><b class="red" id="sells"></b></div></div><div class="metric difference"><small>DIFERENCIA DE OPERACIONES</small><b id="countdiff"></b></div><p class="note">«Whales»: operaciones individuales de al menos $10,000, no personas identificadas. Muestra recibida por la API; puede omitir operaciones entre consultas. Actividad: ritmo de los últimos 10 s frente a los 20 s anteriores. En el laboratorio, el flujo puede apoyar una candidatura solo con confirmación técnica; no decide por sí solo.</p></div></details>
<details id="momentum"><summary>⚡ SHORT-TERM MOMENTUM <small>EN VIVO · TOCA PARA ABRIR</small></summary><div class="detail"><h3>MOVIMIENTO RECIENTE DE BTC</h3><div class="metrics" id="momrows"></div><p class="note">Cambio porcentual calculado por el motor en 3, 5 y 15 minutos. La temporalidad de la gráfica no cambia estos valores.</p></div></details>
<div class="tools"><h3>INDICADORES</h3><div class="toggles" id="toggles"></div><div class="legend" id="legend"></div></div>
<div class="floatcounts"><div>🐋 BUY WHALES <b id="floatbuy"></b></div><div>🐋 SELL WHALES <b id="floatsell"></b></div></div>
<div class="tooltip" id="tooltip">Arrastra velas y escala de precios · pellizca para zoom · AHORA regresa al presente.</div><div class="canvas" id="canvas"></div><div id="rsi-pane" style="height:110px;display:none;background:#06121a;border-top:1px solid #294c69"></div>
<div class="chartnav"><button id="older" aria-label="Velas anteriores">←</button><button id="newer" aria-label="Velas siguientes">→</button><button id="zoomin" aria-label="Acercar">＋</button><button id="zoomout" aria-label="Alejar">−</button><button id="reset">AHORA</button><button id="expand" type="button" aria-pressed="false">AMPLIAR</button><span id="viewtf"></span></div>
<div id="signal-state" role="status" style="padding:6px 12px;color:#c4d2e2;font-size:12px"></div>
</section>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
let D=__PAYLOAD__; const $=id=>document.getElementById(id), fmt=(v,n=2)=>v==null?'—':Number(v).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n}), usd=v=>v==null?'—':'$'+fmt(v), compact=v=>v==null?'—':v>=1e6?'$'+(v/1e6).toFixed(2)+'M':v>=1000?'$'+(v/1000).toFixed(0)+'K':'$'+fmt(v,0);
let saved={};try{saved=JSON.parse(localStorage.getItem('btc-neon-panel-v1')||'{}')}catch(e){}
let toggles=Object.assign({ema9:true,ema21:true,vwap:true,volume:true,rsi:true,},saved.toggles),visible=saved.visible||32,offset=saved.offset||0,pricePan=Number.isFinite(saved.pricePan)?saved.pricePan:0;
$('expand').addEventListener('click',()=>{
 const host=window.frameElement?.parentElement;
 if(!host)return;
 const expanded=host.classList.toggle('expanded');
 document.documentElement.classList.toggle('expanded-chart',expanded);
 $('expand').textContent=expanded?'SALIR':'AMPLIAR';
 $('expand').setAttribute('aria-pressed',String(expanded));
});
function persist(){try{localStorage.setItem('btc-neon-panel-v1',JSON.stringify({toggles,visible,offset,pricePan,whale:$('whale').open,momentum:$('momentum').open}))}catch(e){}}
for(const name of ['whale','momentum']){$(name).open=!!saved[name];$(name).addEventListener('toggle',persist)}
function updateRoundClock(){
 const label=$('round-clock');
 if(!Number.isFinite(D.round_close_ms)){label.textContent='Esperando ronda';return;}
 const seconds=Math.max(0,Math.ceil((D.round_close_ms-Date.now())/1000));
 label.textContent=seconds
   ? Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')
   : '0:00 · Esperando nueva ronda';
}
setInterval(updateRoundClock,1000);
function refreshLabels(){
 updateRoundClock();
$('subtitle').textContent=D.timeframe.toUpperCase()+' · '+(D.candle_source||'COINBASE')+' · BTC SIGNAL';$('price').textContent=usd(D.price);$('live').textContent=D.price==null?'● SIN COTIZACIÓN':'● PRECIO RECIBIDO';$('model').textContent=fmt(D.signal==='UP'?D.up:D.signal==='DOWN'?D.down:Math.max(D.up,D.down),1)+'%';$('status').textContent=D.rows.length?'DATOS RECIBIDOS':'SIN VELAS';$('updated').textContent='Actualizado '+D.updated;$('viewtf').textContent=D.timeframe+' · VELAS REALES';$('signal-state').textContent=D.signal_status||'';
const F=D.flow,total=F.buy+F.sell,known=F.ok;
$('watch').textContent=!known?'SIN DATOS DE FLUJO':total===0?'ESPERANDO OPERACIONES':F.direction==='NEUTRAL'?'FLUJO EQUILIBRADO':'WATCH '+F.direction;
for(const [id,value] of [['buy',F.buy],['sell',F.sell],['buytotal',F.buy],['selltotal',F.sell]])$(id).textContent=known?compact(value):'—';
$('diff').textContent=known?compact(Math.abs(F.buy-F.sell))+' '+(F.buy>F.sell?'BUY':F.sell>F.buy?'SELL':'NEUTRAL'):'—';$('diff').className=F.buy>F.sell?'green':'red';$('activity').textContent=known&&F.activity!=null?fmt(F.activity,1)+'×':'—';$('strength').textContent=known&&total?F.strength:'—';
for(const [id,v] of [['buys',F.buys],['sells',F.sells],['floatbuy',F.buys],['floatsell',F.sells]])$(id).textContent=known?v:'—';
$('countdiff').textContent=known?Math.abs(F.buys-F.sells)+' '+(F.buys>F.sells?'BUY':F.sells>F.buys?'SELL':'NEUTRAL'):'—';$('buybar').style.width=(total?100*F.buy/total:0)+'%';$('sellbar').style.width=(total?100*F.sell/total:0)+'%';
$('momrows').replaceChildren();
for(const key of ['mom3','mom5','mom15']){const v=D[key],box=document.createElement('div');box.className='metric';box.innerHTML='<small>'+key.slice(3)+' MINUTOS</small><b class="'+(v>=0?'green':'red')+'">'+(v==null?'—':(v>0?'+':'')+fmt(v,2)+'%')+'</b>';$('momrows').append(box)}
}
refreshLabels();
const colors={ema9:'#f000ff',ema21:'#00eaff',vwap:'#6261ff',volume:'#00d7b0',rsi:'#f000ff'};
for(const [key,label] of Object.entries({ema9:'EMA9',ema21:'EMA21',vwap:'VWAP',volume:'VOLUME',rsi:'RSI'})){const b=document.createElement('button');b.style.setProperty('--c',colors[key]);b.dataset.key=key;b.onclick=()=>{toggles[key]=!toggles[key];persist();draw()};$('toggles').append(b);b.dataset.label=label}
// The original custom SVG/pointer engine has been fully replaced by TradingView Lightweight Charts.
// The surrounding cards, signals, toolbars, Python payload and market calculations remain unchanged.
let lwChart=null, candleSeries=null, volumeSeries=null, overlays={}, levelLines=[], rsiChart=null, rsiSeries=null;
let applyingData=false, syncing=false;
const candleOptions={upColor:'#00dfb5',downColor:'#e64b4b',borderUpColor:'#00dfb5',borderDownColor:'#e64b4b',wickUpColor:'#00dfb5',wickDownColor:'#e64b4b'};
function chartRows(data){return (data.rows||[]).filter(r=>Number.isFinite(r.t)&&[r.open,r.high,r.low,r.close].every(Number.isFinite))
 .map(r=>({time:r.t,open:r.open,high:r.high,low:r.low,close:r.close}));}
function seriesRows(key){return (D.rows||[]).filter(r=>Number.isFinite(r.t)&&Number.isFinite(r[key]))
 .map(r=>({time:r.t,value:r[key]}));}
function refreshToggles(){
 for(const b of $('toggles').children){const k=b.dataset.key;b.className='toggle'+(toggles[k]?'':' off');b.setAttribute('aria-pressed',String(!!toggles[k]));b.innerHTML=b.dataset.label+'<span>'+(toggles[k]?'ON':'OFF')+'</span>'}
 const last=D.rows?.[D.rows.length-1];
 $('legend').innerHTML=last?['ema9','ema21','vwap'].filter(k=>toggles[k]).map(k=>'<span><i style="color:'+colors[k]+'">●</i> '+k.toUpperCase()+' '+usd(last[k])+'</span>').join(''):'';
}
function initChart(){
 if(!window.LightweightCharts){$('canvas').textContent='No se pudo cargar la gráfica de TradingView. Verifica la conexión de internet.';return false;}
 if(lwChart)return true;
 const L=window.LightweightCharts;
 lwChart=L.createChart($('canvas'),{
  width:$('canvas').clientWidth,height:$('canvas').clientHeight,
  layout:{background:{type:L.ColorType.Solid,color:'#06121a'},textColor:'#b9c8d9',fontFamily:'Inter,system-ui,sans-serif',fontSize:11},
  grid:{vertLines:{color:'#142b3a'},horzLines:{color:'#142b3a'}},
  rightPriceScale:{borderColor:'#34546c',scaleMargins:{top:.12,bottom:.17}},
  timeScale:{borderColor:'#34546c',rightOffset:2,barSpacing:11,minBarSpacing:3,timeVisible:true,secondsVisible:false,fixLeftEdge:false,fixRightEdge:false},
  crosshair:{mode:L.CrosshairMode.Normal,vertLine:{color:'#849cb7',style:L.LineStyle.Dashed,labelBackgroundColor:'#20354c'},horzLine:{color:'#849cb7',style:L.LineStyle.Dashed,labelBackgroundColor:'#20354c'}},
  kineticScroll:{touch:true,mouse:true},
  handleScroll:{mouseWheel:true,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:true},
  handleScale:{axisPressedMouseMove:{time:true,price:true},mouseWheel:true,pinch:true,axisDoubleClickReset:true}
 });
 candleSeries=lwChart.addCandlestickSeries({...candleOptions,priceFormat:{type:'price',precision:2,minMove:.01},lastValueVisible:true,priceLineVisible:true});
 for(const k of ['ema9','ema21','vwap'])overlays[k]=lwChart.addLineSeries({color:colors[k],lineWidth:2,visible:!!toggles[k],lastValueVisible:false,priceLineVisible:false,...(k==='vwap'?{lineStyle:L.LineStyle.Dashed}:{})});
 volumeSeries=lwChart.addHistogramSeries({priceScaleId:'',visible:!!toggles.volume,priceLineVisible:false,lastValueVisible:false});
 volumeSeries.priceScale().applyOptions({scaleMargins:{top:.82,bottom:0}});
 rsiChart=L.createChart($('rsi-pane'),{
  width:$('rsi-pane').clientWidth,height:110,
  layout:{background:{type:L.ColorType.Solid,color:'#06121a'},textColor:'#b9c8d9',fontSize:10},
  grid:{vertLines:{color:'#142b3a'},horzLines:{color:'#142b3a'}},
  rightPriceScale:{borderColor:'#34546c'},timeScale:{visible:false,borderColor:'#34546c'},
  handleScroll:false,handleScale:false,crosshair:{mode:L.CrosshairMode.Normal}
 });
 rsiSeries=rsiChart.addLineSeries({color:colors.rsi,lineWidth:2,priceLineVisible:false,lastValueVisible:true});
 // Keep RSI time aligned with the BTC chart when panning/zooming.
 lwChart.timeScale().subscribeVisibleLogicalRangeChange(range=>{
  if(!range||syncing)return;
  syncing=true;try{rsiChart.timeScale().setVisibleLogicalRange(range)}catch(_){}syncing=false;
  if(!applyingData)persistView();
 });
 lwChart.subscribeCrosshairMove(param=>{
  if(!param||!param.time||!param.seriesData){return;}
  const r=param.seriesData.get(candleSeries);if(!r)return;
  const date=new Date(Number(param.time)*1000).toLocaleString('en-US',{timeZone:'America/New_York'});
  $('tooltip').textContent=date+' · O '+fmt(r.open)+' H '+fmt(r.high)+' L '+fmt(r.low)+' C '+fmt(r.close);
 });
 const resize=()=>{if(!lwChart)return;lwChart.applyOptions({width:$('canvas').clientWidth,height:$('canvas').clientHeight});rsiChart.applyOptions({width:$('rsi-pane').clientWidth,height:110})};
 if(window.ResizeObserver){new ResizeObserver(resize).observe($('canvas'));new ResizeObserver(resize).observe($('rsi-pane'))}else window.addEventListener('resize',resize);
 return true;
}
function persistView(){
 if(!lwChart)return;
 const range=lwChart.timeScale().getVisibleLogicalRange();
 if(!range)return;
 const n=D.rows.length;visible=Math.max(12,Math.round(range.to-range.from));offset=Math.max(0,Math.round((n-1)-range.to));persist();
}
function redrawData(preserve=true){
 refreshToggles();if(!initChart())return;
 applyingData=true;
 let oldRange=preserve?lwChart.timeScale().getVisibleLogicalRange():null;
 const newC=chartRows(D),newN=newC.length;
 if(!newN){candleSeries.setMarkers([]);applyingData=false;return;}
 candleSeries.setData(newC);
 candleSeries.setMarkers((D.reversal_markers||[]).map(mark => {
  const up=mark.direction==='UP';
  return {time:mark.time,position:up?'belowBar':'aboveBar',
          shape:up?'arrowUp':'arrowDown',color:up?'#38eac3':'#ff7777',size:1.6,text:mark.direction};
 }));
 for(const k of ['ema9','ema21','vwap']){overlays[k].setData(seriesRows(k));overlays[k].applyOptions({visible:!!toggles[k]});}
 volumeSeries.setData((D.rows||[]).filter(r=>Number.isFinite(r.t)&&Number.isFinite(r.volume)).map(r=>({time:r.t,value:r.volume,color:r.close>=r.open?'#00dfb573':'#e64b4b73'})));
 volumeSeries.applyOptions({visible:!!toggles.volume});
 rsiSeries.setData(seriesRows('rsi'));
 $('rsi-pane').style.display=toggles.rsi?'block':'none';
 for(const l of levelLines)candleSeries.removePriceLine(l);levelLines=[];
 for(const [value,label,color] of [[D.target,'TARGET KALSHI','#f1c46b'],[D.support,'SUPPORT','#00dfb5'],[D.resistance,'RESISTANCE','#e64b4b']]){
  if(Number.isFinite(value))levelLines.push(candleSeries.createPriceLine({price:value,color,lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title:label}));
 }
 try{
  if(oldRange&&preserve){
   // Preserve the user's camera even when a new candle arrives.
   // Move one logical bar if old range was already anchored to the live edge.
   lwChart.timeScale().setVisibleLogicalRange(oldRange);
  }else if(saved.visible){
   lwChart.timeScale().setVisibleLogicalRange({from:Math.max(0,newN-saved.visible-saved.offset),to:newN-1-saved.offset});
  }else{
   // Show recent candles at a readable size, with only two future candle spaces.
   const count=Math.min(35,newN);
   lwChart.timeScale().setVisibleLogicalRange({from:newN-count-0.5,to:newN+1.5});
  }
 }catch(_) {lwChart.timeScale().fitContent()}
 applyingData=false;
}
function draw(){redrawData(true)}
$('zoomin').onclick=()=>{if(!lwChart)return;const t=lwChart.timeScale(),r=t.getVisibleLogicalRange();if(r){const m=(r.from+r.to)/2,w=(r.to-r.from)*.72;t.setVisibleLogicalRange({from:m-w/2,to:m+w/2})}};
$('zoomout').onclick=()=>{if(!lwChart)return;const t=lwChart.timeScale(),r=t.getVisibleLogicalRange();if(r){const m=(r.from+r.to)/2,w=(r.to-r.from)*1.35;t.setVisibleLogicalRange({from:m-w/2,to:m+w/2})}};
$('older').onclick=()=>{if(!lwChart)return;lwChart.timeScale().scrollToPosition(lwChart.timeScale().scrollPosition()+10,false)};
$('newer').onclick=()=>{if(!lwChart)return;lwChart.timeScale().scrollToPosition(lwChart.timeScale().scrollPosition()-10,false)};
$('reset').onclick=()=>{if(!lwChart)return;lwChart.timeScale().scrollToRealTime();persistView()};
// Controls call draw(), so toggles update the native series without a new chart element.
window.addEventListener('message',function(event){
 if(!event.data||event.data.kind!=='alpha-chart-update')return;
 const next=event.data.payload;
 if(!next||!Array.isArray(next.rows))return;
 const previous=D;
 const sameTimeframe=previous.timeframe===next.timeframe;
 D=next;refreshLabels();
 if(!initChart())return;
 if(!sameTimeframe){redrawData(false);return;}
 // Native data update never rebuilds the canvas; gestures and scroll are preserved.
 redrawData(true);
});
draw();
</script></html>'''


@st.cache_data(ttl=1)
def get_recent_coinbase_trades():
    response = requests.get(
        "https://api.exchange.coinbase.com/products/BTC-USD/trades",
        params={"limit": 100},
        timeout=3,
    )
    response.raise_for_status()
    trades = {}
    if not isinstance(response.json(), list):
        raise ValueError("Operaciones BTC no disponibles.")
    for row in response.json():
        try:
            trade_id = int(row["trade_id"])
            timestamp = pd.Timestamp(row["time"]).timestamp()
            price = float(row["price"])
            size = float(row["size"])
            # Coinbase reports the resting maker side, opposite the aggressor.
            side = {"sell": "UP", "buy": "DOWN"}[row["side"]]
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
        if np.isfinite([timestamp, price, price * size]).all() and price > 0 and size > 0:
            trades[trade_id] = (timestamp, price, price * size, side)
    return trades


def update_aggressor_flow(tape, trades, now):
    tape.update(trades)
    for trade_id, trade in list(tape.items()):
        if trade[0] < now - 5:
            del tape[trade_id]
    recent = [trade for trade in tape.values() if now - 5 <= trade[0] <= now]
    if not recent:
        return None, None
    latest = max(recent)
    if now - latest[0] > 3:
        return None, None
    if len(recent) < 8:
        return latest[1], None
    buy = sum(trade[2] for trade in recent if trade[3] == "UP")
    sell = sum(trade[2] for trade in recent if trade[3] == "DOWN")
    imbalance = (buy - sell) / (buy + sell)
    side = "UP" if imbalance >= 0.25 else "DOWN" if imbalance <= -0.25 else None
    return latest[1], side


@st.cache_resource
def confirmed_chart_signals():
    # Share signals observed by this server across browser sessions.
    return threading.Lock(), {}


def confirm_round_marker(payload, saved, market, flow_side):
    now = payload["observed"]
    minute = now // 60 * 60
    rows = payload["rows"]
    for ticker, marker in list(saved.items()):
        # Versiones anteriores guardaban {minuto: "UP" o "DOWN"}.
        if isinstance(ticker, int) and isinstance(marker, str) and marker in ("UP", "DOWN"):
            marker = saved[ticker] = {"time": ticker, "direction": marker}
        if (not isinstance(marker, dict)
                or not isinstance(marker.get("time"), int)
                or marker.get("direction") not in ("UP", "DOWN")
                or marker["time"] < now - 4 * 3600):
            del saved[ticker]
    active = market and _KalshiPublicReads._is_current(
        market, datetime.fromtimestamp(now, timezone.utc))
    ticker = market["ticker"] if active else None
    side = payload["ut_side"]
    if ticker and rows and rows[-1]["t"] == minute and side in ("UP", "DOWN") and side == flow_side:
        saved.setdefault(ticker, {"time": minute, "direction": side})
        saved.pop(saved[ticker]["time"], None)
    visible = {row["t"] for row in rows}
    payload["reversal_markers"] = sorted(
        (marker for marker in saved.values() if marker["time"] in visible),
        key=lambda marker: marker["time"],
    )
    return saved.get(ticker)


class _KalshiPublicReads:
    """Una consulta por recurso para todas las sesiones e hilos del proceso."""
    def __init__(self):
        self.lock = threading.RLock()
        self.cache = {}
        self.failures = {}
        self.retry_at = 0.0
        self.rate_failures = 0
        self.current_round = None

    @staticmethod
    def _is_current(market, now=None):
        if not isinstance(market, dict) or not str(market.get("ticker", "")).startswith("KXBTC15M-"):
            return False
        if market.get("status") not in (None, "open", "active"):
            return False
        now = now or datetime.now(timezone.utc)
        try:
            close = datetime.fromisoformat(str(market["close_time"]).replace("Z", "+00:00"))
            # Nunca seleccionar la ronda futura ni conservar la anterior.
            if close.tzinfo is None or not 0 < (close - now).total_seconds() <= 900:
                return False
            if market.get("open_time"):
                opened = datetime.fromisoformat(str(market["open_time"]).replace("Z", "+00:00"))
                if opened.tzinfo is None or opened > now:
                    return False
            return True
        except (KeyError, TypeError, ValueError):
            return False

    @staticmethod
    def _has_target(market):
        return any(_KalshiPublicReads._valid_strike(market.get(key))
                   for key in ("floor_strike", "cap_strike"))

    @staticmethod
    def _valid_strike(value):
        try:
            return np.isfinite(float(value)) and float(value) > 1000
        except (TypeError, ValueError):
            return False

    def _round_metadata(self):
        # El target y el cierre verificados siguen siendo válidos para ESTE ticker.
        # Las cotizaciones no: no reutilizar bids/asks ni precios de contrato antiguos.
        keys = ("ticker", "event_ticker", "open_time", "close_time", "status",
                "floor_strike", "cap_strike")
        return {key: copy.deepcopy(self.current_round[key]) for key in keys
                if key in self.current_round}

    def current_market(self):
        with self.lock:
            if not self._is_current(self.current_round):
                self.current_round = None
            try:
                if self.current_round:
                    ticker = self.current_round["ticker"]
                    market = self.get("/markets/" + ticker, ttl=2.0, timeout=6).get("market")
                    if not isinstance(market, dict) or market.get("ticker") != ticker:
                        raise ValueError("Kalshi devolvió una respuesta incompleta para la ronda actual.")
                    market = copy.deepcopy(market)
                    for key in ("open_time", "close_time", "event_ticker"):
                        if not market.get(key) and key in self.current_round:
                            market[key] = self.current_round[key]
                    if not self._is_current(market):
                        self.current_round = None
                        return None
                    market = copy.deepcopy(market)
                    # Un detalle parcial no borra un strike ya verificado del mismo ticker.
                    if not self._has_target(market):
                        for key in ("floor_strike", "cap_strike"):
                            if key in self.current_round:
                                market[key] = self.current_round[key]
                else:
                    # El filtro status=open puede omitir una ronda que figura como active.
                    # Acotar por cierre y validar estado/horario localmente.
                    minute = int(datetime.now(timezone.utc).timestamp()) // 60 * 60
                    data = self.get("/markets", params={"limit": 100,
                                    "series_ticker": "KXBTC15M",
                                    "min_close_ts": minute,
                                    "max_close_ts": minute + 960}, ttl=2.0, timeout=10)
                    markets = [m for m in data.get("markets", []) if self._is_current(m)]
                    if not markets:
                        return None
                    markets.sort(key=lambda m: str(m["close_time"]))
                    market = copy.deepcopy(markets[0])
                    if not self._has_target(market):
                        ticker = market["ticker"]
                        detail = self.get("/markets/" + ticker, ttl=2.0, timeout=6).get("market")
                        if not isinstance(detail, dict) or detail.get("ticker") != ticker:
                            raise ValueError("Kalshi no entregó el detalle de la ronda actual.")
                        market = detail
                if not self._is_current(market):
                    self.current_round = None
                    return None
                if not self._has_target(market):
                    raise ValueError("La ronda actual todavía no entregó un target verificable.")
                self.current_round = copy.deepcopy(market)
                return copy.deepcopy(market)
            except (requests.RequestException, ValueError, TypeError) as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in (404, 410) or not self._is_current(self.current_round):
                    self.current_round = None
                    raise
                # El reloj se calcula desde close_time, nunca desde un contador guardado.
                result = self._round_metadata()
                result["_round_refresh_error"] = str(exc)
                return result

    def get(self, path, params=None, ttl=2.0, timeout=6):
        params = dict(params or {})
        key = (path, json.dumps(params, sort_keys=True))
        with self.lock:
            now = time.monotonic()
            cached = self.cache.get(key)
            if cached and now < cached[0]:
                return copy.deepcopy(cached[1])
            if now < self.retry_at:
                raise requests.HTTPError(
                    "Kalshi 429: límite temporal; reintento en "
                    + str(max(1, int(self.retry_at - now + 0.999))) + " s.")
            failed = self.failures.get(key)
            if failed and now < failed[0]:
                raise requests.RequestException(failed[1])
            try:
                response = requests.get(
                    "https://external-api.kalshi.com/trade-api/v2" + path,
                    params=params,
                    headers={"User-Agent": "MacalyAlphaBot/4.6.1", "Cache-Control": "no-cache"},
                    timeout=timeout,
                )
                if response.status_code == 429:
                    self.rate_failures = min(self.rate_failures + 1, 5)
                    delay = min(30.0, 2.0 ** self.rate_failures) + random.uniform(0, 0.5)
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            requested_delay = float(retry_after)
                        except (TypeError, ValueError):
                            try:
                                stamp = parsedate_to_datetime(retry_after)
                                if stamp.tzinfo is None:
                                    stamp = stamp.replace(tzinfo=timezone.utc)
                                requested_delay = (stamp - datetime.now(timezone.utc)).total_seconds()
                            except (TypeError, ValueError, OverflowError):
                                requested_delay = 0.0
                        if np.isfinite(requested_delay):
                            delay = max(delay, requested_delay)
                    self.retry_at = time.monotonic() + delay
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Kalshi devolvió una respuesta incompleta.")
            except (requests.RequestException, ValueError) as exc:
                # Los errores tampoco se vuelven a consultar por cada sesión.
                if len(self.failures) >= 256:
                    self.failures.pop(next(iter(self.failures)))
                self.failures[key] = (time.monotonic() + 2.0, str(exc))
                raise
            self.rate_failures = 0
            self.retry_at = 0.0
            self.failures.pop(key, None)
            if len(self.cache) >= 256:
                self.cache.pop(next(iter(self.cache)))
            effective_ttl = float(ttl)
            if path == "/markets":
                # No reutilizar el listado de la ronda cerrada en el cambio de ronda.
                for market in payload.get("markets", []):
                    try:
                        close = datetime.fromisoformat(str(market["close_time"]).replace("Z", "+00:00"))
                        remaining = (close - datetime.now(timezone.utc)).total_seconds()
                        if remaining > 0:
                            effective_ttl = min(effective_ttl, remaining)
                    except (KeyError, TypeError, ValueError):
                        pass
            self.cache[key] = (time.monotonic() + effective_ttl, copy.deepcopy(payload))
            return payload


@st.cache_resource(validate=lambda reader: callable(getattr(reader, "current_market", None)) and hasattr(reader, "current_round"))
def _kalshi_public_reads():
    # Cambiar el cuerpo también invalida el recurso de versiones anteriores.
    reader = _KalshiPublicReads()
    return reader


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


@st.cache_resource
def kalshi_target_executor():
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="kalshi-target")


def current_chart_market(state, reader):
    future = state.get("kalshi_target_future")
    if future is not None and future.done():
        try:
            state["kalshi_target_market"] = future.result()
        except (requests.RequestException, ValueError, TypeError):
            pass
        future = None
    if future is None:
        state["kalshi_target_future"] = kalshi_target_executor().submit(reader.current_market)
    market = state.get("kalshi_target_market")
    return market if reader._is_current(market) else None


@st.fragment(run_every="2s")
def live_chart():
    try:
        candles = get_btc_data()
        price = float(candles.iloc[-1]["close"])
        error = None
    except (ValueError, requests.RequestException) as exc:
        candles = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        price = None
        error = str(exc)

    flow_side = None
    flow_status = "Flujo de Coinbase no disponible"
    if candles.attrs.get("candle_source") == "COINBASE":
        try:
            trades = get_recent_coinbase_trades()
            tape = st.session_state.setdefault("aggressor_tape", {})
            trade_price, flow_side = update_aggressor_flow(tape, trades, datetime.now(timezone.utc).timestamp())
            if trade_price is None:
                flow_status = "Sin operaciones recientes"
            else:
                price = trade_price
                flow_status = "Flujo sin presión suficiente" if flow_side is None else f"Flujo {flow_side}"
        except (ValueError, requests.RequestException):
            flow_status = "Error al consultar el flujo de Coinbase"

    market = current_chart_market(st.session_state, _kalshi_public_reads())
    target = get_target_from_market(market) if market else None
    payload = _neon_payload(candles, price, target, None, "1m", {}, None)
    lock, saved = confirmed_chart_signals()
    payload["round_close_ms"] = int(pd.Timestamp(market["close_time"]).timestamp()*1000) if market else None
    with lock:
        confirmed = confirm_round_marker(payload, saved, market, flow_side)
    if confirmed:
        status = f"Señal de la ronda · {confirmed['direction']}"
    elif not market:
        status = "Esperando ronda Kalshi"
    else:
        status = f"Esperando coincidencia UT y flujo · {flow_status}"
    payload["signal_status"] = status
    safe_payload = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    st.session_state["_alpha_chart_html_initial"] = _NEON_HTML.replace("__PAYLOAD__", safe_payload)
    st.html(
        "<script>window.__alphaNextChart=" + safe_payload + ";"
        "if(window.__alphaPushChart)window.__alphaPushChart(window.__alphaNextChart);</script>",
        unsafe_allow_javascript=True,
    )
    if error:
        st.warning("Velas BTC no disponibles. Reintentando.")


st.markdown(
    '<style>.stApp{background:#06121a}[data-testid="stHeader"]{display:none}.block-container{max-width:none;padding:.25rem .35rem 0}#alpha-chart-stable-host.expanded{position:fixed;inset:0;z-index:2147483647;height:100dvh;background:#06121a;overflow:hidden}#alpha-chart-stable-host.expanded iframe{height:100%!important}</style>',
    unsafe_allow_html=True,
)
live_chart()
initial_html = st.session_state["_alpha_chart_html_initial"]
safe_html = json.dumps(initial_html, ensure_ascii=False).replace("<", "\\u003c")
st.html(
    '<div id="alpha-chart-stable-host" style="width:100%;min-height:0"></div>'
    '<script>(function(){'
    'const host=document.getElementById("alpha-chart-stable-host");'
    'if(!host)return;'
    'let frame=host.querySelector("iframe");'
    'if(!frame){frame=document.createElement("iframe");'
    'frame.setAttribute("title","Gráfica BTC interactiva");'
    'frame.style.cssText="width:100%;height:600px;border:0;display:block;background:#06121a";'
    'frame.setAttribute("scrolling","yes");'
    'frame.srcdoc=' + safe_html + ';host.appendChild(frame);}'
    'window.__alphaPushChart=function(payload){'
    'window.__alphaNextChart=payload;'
    'if(frame.contentWindow)frame.contentWindow.postMessage({kind:"alpha-chart-update",payload:payload},"*");'
    '};'
    'function fitChartHeight(){try{'
    'const panel=frame.contentDocument&&frame.contentDocument.querySelector(".panel");'
    'if(!panel)return;const pixels=Math.max(360,Math.ceil(panel.getBoundingClientRect().bottom+8));'
    'if(frame.style.height!==pixels+"px")frame.style.height=pixels+"px";'
    '}catch(e){}}'
    'window.addEventListener("resize",fitChartHeight);'
    'frame.addEventListener("load",function(){'
    'if(window.__alphaNextChart)window.__alphaPushChart(window.__alphaNextChart);'
    'fitChartHeight();try{const panel=frame.contentDocument.querySelector(".panel");'
    'if(panel)new ResizeObserver(fitChartHeight).observe(panel);}catch(e){}'
    '});'
    'if(window.__alphaNextChart)window.__alphaPushChart(window.__alphaNextChart);'
    '})();</script>',
    unsafe_allow_javascript=True,
)
