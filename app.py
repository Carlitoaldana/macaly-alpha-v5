import streamlit as st
import requests, pandas as pd, numpy as np, sqlite3, json, os, uuid, time, base64
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

st.set_page_config(page_title="Alpha Autónomo", page_icon="⚡", layout="centered", initial_sidebar_state="collapsed")
NEW_ROUND_WAIT=30
NEW_ENTRY_LOCK=75
UP_THRESHOLD=4.0
DOWN_THRESHOLD=-4.0
EARLY_UP_THRESHOLD=3.50
EARLY_DOWN_THRESHOLD=-3.50
EARLY_CONFIRMATIONS=2
FLIP_UP_THRESHOLD=4.75
FLIP_DOWN_THRESHOLD=-4.75
FLIP_CONFIRMATIONS=2
DB_PATH="alpha_autonomo.db"

def utc_now():
    return datetime.now(timezone.utc)


def dt_text(v):
    return v.astimezone(timezone.utc).isoformat() if isinstance(v, datetime) else None


def parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def new_round_state(ticker, seconds_left):
    n = utc_now()
    return {
        "ticker": ticker, "detected_at": n, "detected_seconds_left": seconds_left,
        "first_direction": None, "first_signal_time": None, "first_signal_seconds": None,
        "first_signal_price": None, "first_signal_btc": None, "first_signal_target": None,
        "first_signal_score": None, "first_up_probability": None, "first_down_probability": None,
        "active_direction": None, "active_since": None,
        "last_score": 0.0, "previous_score": 0.0, "opposite_count": 0,
        "candidate_direction": None, "candidate_count": 0,
        "last_live_price": None, "previous_live_price": None,
        "reversal_warning": False, "reversal_text": "",
        "last_target": None, "last_seconds_left": seconds_left, "last_seen_at": n,
    }


DB_COLS = [
    "ticker", "detected_at", "detected_seconds_left", "first_direction", "first_signal_time",
    "first_signal_seconds", "first_signal_price", "first_signal_btc", "first_signal_target",
    "first_signal_score", "first_up_probability", "first_down_probability", "active_direction",
    "active_since", "last_score", "previous_score", "opposite_count", "candidate_direction",
    "candidate_count", "last_live_price", "previous_live_price", "reversal_warning",
    "reversal_text", "last_target", "last_seconds_left", "last_seen_at"
]


def db_connect():
    c = sqlite3.connect(DB_PATH, timeout=5)
    c.execute("""CREATE TABLE IF NOT EXISTS rounds(
        ticker TEXT PRIMARY KEY, detected_at TEXT, detected_seconds_left INTEGER,
        first_direction TEXT, first_signal_time TEXT, first_signal_seconds INTEGER,
        first_signal_price REAL, first_signal_btc REAL, first_signal_target REAL,
        first_signal_score REAL, first_up_probability INTEGER, first_down_probability INTEGER,
        active_direction TEXT, active_since TEXT, last_score REAL, previous_score REAL,
        opposite_count INTEGER, candidate_direction TEXT, candidate_count INTEGER,
        last_live_price REAL, previous_live_price REAL, reversal_warning INTEGER,
        reversal_text TEXT, last_target REAL, last_seconds_left INTEGER, last_seen_at TEXT
    )""")
    c.commit()
    return c


def save_state(s):
    d = dict(s)
    for k in ["detected_at", "first_signal_time", "active_since", "last_seen_at"]:
        d[k] = dt_text(s.get(k))
    d["reversal_warning"] = int(bool(s.get("reversal_warning")))
    try:
        c = db_connect()
        q = ",".join(["?"] * len(DB_COLS))
        updates = ",".join(f"{k}=excluded.{k}" for k in DB_COLS if k != "ticker")
        c.execute(f'INSERT INTO rounds ({",".join(DB_COLS)}) VALUES ({q}) ON CONFLICT(ticker) DO UPDATE SET {updates}', [d.get(k) for k in DB_COLS])
        c.commit(); c.close()
    except Exception:
        pass


def load_state(ticker):
    if not ticker:
        return None
    try:
        c = db_connect(); cur = c.execute("SELECT * FROM rounds WHERE ticker=?", (ticker,)); row = cur.fetchone()
        if not row:
            c.close(); return None
        cols = [x[0] for x in cur.description]; c.close(); d = dict(zip(cols, row))
        s = new_round_state(ticker, d.get("detected_seconds_left")); s.update(d)
        for k in ["detected_at", "first_signal_time", "active_since", "last_seen_at"]:
            s[k] = parse_dt(d.get(k))
        s["detected_at"] = s["detected_at"] or utc_now()
        s["reversal_warning"] = bool(d.get("reversal_warning"))
        s["last_score"] = float(d.get("last_score") or 0); s["previous_score"] = float(d.get("previous_score") or 0)
        s["opposite_count"] = int(d.get("opposite_count") or 0); s["candidate_count"] = int(d.get("candidate_count") or 0)
        return s
    except Exception:
        return None


def load_history(limit=12):
    try:
        c = db_connect(); rows = c.execute("SELECT ticker FROM rounds ORDER BY detected_at DESC LIMIT ?", (limit,)).fetchall(); c.close()
        return [s for s in (load_state(r[0]) for r in rows) if s]
    except Exception:
        return []


if "rounds" not in st.session_state:
    st.session_state.rounds = {}
if "active_ticker" not in st.session_state:
    st.session_state.active_ticker = None


@st.cache_data(ttl=5)
def get_btc_data():
    r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/candles", params={"granularity": 60}, headers={"User-Agent": "MacalyAlphaBot/4.6.1"}, timeout=10)
    r.raise_for_status(); data = r.json()
    if not isinstance(data, list) or len(data) < 30:
        raise ValueError("Coinbase no devolvió suficientes datos.")
    df = pd.DataFrame(data, columns=["time", "low", "high", "open", "close", "volume"])
    for col in ["low", "high", "open", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.dropna().sort_values("time").reset_index(drop=True)


def _find_kalshi_index_price(obj):
    """Extract the newest BTC index value from Kalshi event live-data defensively."""
    preferred = ("current_price", "index_price", "price", "value", "close", "last")

    if isinstance(obj, dict):
        # Direct numeric fields first.
        for key in preferred:
            if key in obj:
                try:
                    value = float(obj[key])
                    if 1000 < value < 1000000:
                        return value
                except Exception:
                    pass
        # Prefer newest entries in arrays/series.
        for key in ("points", "data", "series", "prices", "values", "timeseries", "observations"):
            value = obj.get(key)
            if isinstance(value, list):
                for item in reversed(value):
                    found = _find_kalshi_index_price(item)
                    if found is not None:
                        return found
        for value in obj.values():
            found = _find_kalshi_index_price(value)
            if found is not None:
                return found

    elif isinstance(obj, list):
        for item in reversed(obj):
            found = _find_kalshi_index_price(item)
            if found is not None:
                return found

    return None


def get_kalshi_live_btc_price(market):
    """Public Kalshi event live-data feed used by the Kalshi app for crypto charts."""
    if not market:
        raise ValueError("No hay mercado Kalshi activo.")

    event_ticker = market.get("event_ticker")
    if not event_ticker:
        raise ValueError("La ronda no entregó event_ticker.")

    url = f"https://external-api.kalshi.com/trade-api/v2/live_data/events/{event_ticker}"
    response = requests.get(
        url,
        params={"range": "15min"},
        headers={"User-Agent": "MacalyAlphaBot/4.6.1", "Cache-Control": "no-cache"},
        timeout=6,
    )
    response.raise_for_status()
    payload = response.json()
    price = _find_kalshi_index_price(payload.get("details", payload))

    if price is None:
        raise ValueError("Kalshi live-data no devolvió un precio BTC utilizable.")
    return float(price)


def get_coinbase_live_price():
    """Fallback only. Coinbase candles remain the technical-analysis source."""
    r = requests.get(
        "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
        headers={"User-Agent": "MacalyAlphaBot/4.6.1", "Cache-Control": "no-cache"},
        params={"_": int(utc_now().timestamp())},
        timeout=6,
    )
    r.raise_for_status()
    p = r.json().get("price")
    if p in [None, ""]:
        raise ValueError("Coinbase ticker no devolvió precio.")
    return float(p)


@st.cache_data(ttl=2)
def get_kalshi_btc_market():
    r = requests.get("https://external-api.kalshi.com/trade-api/v2/markets", params={"limit": 100, "status": "open", "series_ticker": "KXBTC15M"}, headers={"User-Agent": "MacalyAlphaBot/4.6.1"}, timeout=10)
    r.raise_for_status(); markets = r.json().get("markets", [])
    if not markets:
        return None
    markets.sort(key=lambda m: str(m.get("close_time") or "9999"))
    return markets[0]


def add_indicators(df):
    df = df.copy(); close = df["close"]
    df["ema9"] = close.ewm(span=9, adjust=False).mean(); df["ema21"] = close.ewm(span=21, adjust=False).mean()
    delta = close.diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean(); al = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    df["rsi"] = (100 - (100 / (1 + ag / al.replace(0, np.nan)))).fillna(50)
    df["mom3"] = close.pct_change(3) * 100; df["mom5"] = close.pct_change(5) * 100; df["mom15"] = close.pct_change(15) * 100
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean().replace(0, np.nan)
    return df


def get_target_from_market(market):
    if not market:
        return None
    for key in ["floor_strike", "cap_strike"]:
        try:
            v = float(market.get(key))
            if v > 1000:
                return v
        except Exception:
            pass
    return None


def get_seconds_remaining(market):
    if not market or not market.get("close_time"):
        return None
    try:
        close_dt = datetime.fromisoformat(str(market["close_time"]).replace("Z", "+00:00"))
        return max(0, int((close_dt - utc_now()).total_seconds()))
    except Exception:
        return None


def format_countdown(seconds):
    if seconds is None:
        return "--:--"
    seconds = max(0, int(seconds)); return f"{seconds//60:02d}:{seconds%60:02d}"


def numeric_kalshi_price(dollar_value, cent_value):
    if dollar_value not in [None, ""]:
        try: return float(dollar_value)
        except Exception: pass
    if cent_value not in [None, ""]:
        try: return float(cent_value) / 100
        except Exception: pass
    return None


def kalshi_price(d, c):
    v = numeric_kalshi_price(d, c); return "--" if v is None else f"${v:.2f}"


def get_yes_ask(m):
    return numeric_kalshi_price(m.get("yes_ask_dollars"), m.get("yes_ask")) if m else None


def get_no_ask(m):
    if not m: return None
    direct = numeric_kalshi_price(m.get("no_ask_dollars"), m.get("no_ask"))
    if direct is not None: return direct
    yb = numeric_kalshi_price(m.get("yes_bid_dollars"), m.get("yes_bid"))
    return max(0, min(1, 1-yb)) if yb is not None else None


def estimated_probabilities(final_score, distance, seconds_left, mom3, mom5):
    score = float(np.clip(final_score, -10, 10)); up = 50 + score * 4.2
    if mom3 > .04: up += 3
    elif mom3 < -.04: up -= 3
    if mom5 > .06: up += 2
    elif mom5 < -.06: up -= 2
    if distance is not None and seconds_left is not None and seconds_left <= 180:
        if distance > 0: up += 3
        elif distance < 0: up -= 3
    up = float(np.clip(up, 5, 95)); return round(up), round(100-up)


def build_signal(df, target, seconds_left, live_price=None):
    last = df.iloc[-1]; candle = float(last["close"]); price = float(live_price) if live_price is not None else candle
    rsi = float(last["rsi"]); mom3 = float(last["mom3"]) if pd.notna(last["mom3"]) else 0.0
    mom5 = float(last["mom5"]) if pd.notna(last["mom5"]) else 0.0; mom15 = float(last["mom15"]) if pd.notna(last["mom15"]) else 0.0
    vol = float(last["vol_ratio"]) if pd.notna(last["vol_ratio"]) else 0.0; tech = 0.0
    if last["ema9"] > last["ema21"]: tech += 2; ema = "ALCISTA 🚀"
    else: tech -= 2; ema = "BAJISTA 🔻"
    if rsi >= 55: tech += 1
    elif rsi <= 45: tech -= 1
    if mom3 > .02: tech += 1.25
    elif mom3 < -.02: tech -= 1.25
    if mom5 > .03: tech += 1
    elif mom5 < -.03: tech -= 1
    if mom15 > .05: tech += .75
    elif mom15 < -.05: tech -= .75
    if vol > 1.20:
        if mom3 > 0: tech += .50
        elif mom3 < 0: tech -= .50
    distance = None; distance_pct = None; target_score = 0.0
    if target is not None:
        distance = price - target; distance_pct = distance / target * 100
        if distance > 0: target_score += 2
        elif distance < 0: target_score -= 2
        if seconds_left is not None:
            if seconds_left <= 30: target_score += 4 if distance > 0 else (-4 if distance < 0 else 0)
            elif seconds_left <= 60: target_score += 3 if distance > 0 else (-3 if distance < 0 else 0)
            elif seconds_left <= 180: target_score += 2 if distance > 0 else (-2 if distance < 0 else 0)
            elif seconds_left <= 300: target_score += 1 if distance > 0 else (-1 if distance < 0 else 0)
            if abs(distance) < 10: target_score *= .60
            elif abs(distance) < 20: target_score *= .80
    score = tech + target_score; momentum = "ALCISTA" if mom3 > .02 else ("BAJISTA" if mom3 < -.02 else "NEUTRAL")
    up, down = estimated_probabilities(score, distance, seconds_left, mom3, mom5)
    return dict(price=price,candle_price=candle,rsi=rsi,mom3=mom3,mom5=mom5,mom15=mom15,vol_ratio=vol,ema=ema,
                technical_score=tech,target_score=target_score,final_score=score,distance=distance,distance_pct=distance_pct,
                momentum=momentum,up_probability=up,down_probability=down)


def entry_quality(price, seconds_left):
    if price is None: return "PRECIO NO DISPONIBLE", "#94a3b8"
    if seconds_left is not None and seconds_left <= NEW_ENTRY_LOCK: return "TARDE ⏰", "#fb7185"
    if price <= .60: return "BUENA 🟢", "#34d399"
    if price <= .70: return "PRECAUCIÓN 🟡", "#fbbf24"
    return "CARA / TARDE 🔴", "#fb7185"


def process_round_signal(ticker, sig, market, seconds_left, target):
    n = utc_now()
    if not ticker or ticker == "--":
        return dict(decision="NO TRADE",signal="SIN RONDA",icon="⚠️",color="#fbbf24",round_state=None,reversal=False,reversal_text="",entry_price=None,entry_quality="SIN DATOS",entry_quality_color="#94a3b8")

    if st.session_state.active_ticker != ticker:
        st.session_state.active_ticker = ticker
        restored = load_state(ticker)
        st.session_state.rounds[ticker] = restored if restored else new_round_state(ticker, seconds_left)

    if ticker not in st.session_state.rounds:
        st.session_state.rounds[ticker] = load_state(ticker) or new_round_state(ticker, seconds_left)

    state = st.session_state.rounds[ticker]
    age = (n - state["detected_at"]).total_seconds(); score = sig["final_score"]
    prev_price = state.get("last_live_price"); state["previous_live_price"] = prev_price; state["last_live_price"] = sig["price"]
    price_change = sig["price"] - prev_price if prev_price is not None else 0.0
    prev_score = float(state.get("last_score") or 0); state["previous_score"] = prev_score; score_change = score - prev_score; state["last_score"] = score
    state["last_target"] = target; state["last_seconds_left"] = seconds_left; state["last_seen_at"] = n

    if age < NEW_ROUND_WAIT and state.get("active_direction") is None:
        save_state(state)
        return dict(decision="ANALIZANDO NUEVA RONDA",signal="ESPERANDO CONFIRMACIÓN",icon="⏳",color="#38bdf8",round_state=state,reversal=False,reversal_text="",entry_price=None,entry_quality="ESPERANDO",entry_quality_color="#38bdf8")

    lock = seconds_left is not None and seconds_left <= NEW_ENTRY_LOCK
    candidate = None
    if score >= UP_THRESHOLD:
        candidate = "UP"
    elif score <= DOWN_THRESHOLD:
        candidate = "DOWN"

    if state.get("active_direction") is None and candidate and not lock:
        p = get_yes_ask(market) if candidate == "UP" else get_no_ask(market)
        state.update(active_direction=candidate,active_since=n,first_direction=candidate,first_signal_time=n,
                     first_signal_seconds=seconds_left,first_signal_price=p,first_signal_btc=sig["price"],first_signal_target=target,
                     first_signal_score=score,first_up_probability=sig["up_probability"],first_down_probability=sig["down_probability"],opposite_count=0)
        save_state(state)

    active = state.get("active_direction"); reversal = False; reversal_text = ""
    if active == "UP":
        w = sum([score < 3, score_change <= -1.25, sig["mom3"] < -.02, sig["mom5"] < 0, price_change < -8,
                 sig["distance"] is not None and seconds_left is not None and seconds_left <= 180 and sig["distance"] < 25 and price_change < 0])
        if w >= 2: reversal = True; reversal_text = "UP PERDIENDO FUERZA • POSIBLE REVERSIÓN A DOWN"
        state["opposite_count"] = state.get("opposite_count",0)+1 if score <= FLIP_DOWN_THRESHOLD and sig["mom3"] < 0 else 0
        if state["opposite_count"] >= FLIP_CONFIRMATIONS:
            if not lock: state["active_direction"]="DOWN"; state["active_since"]=n
            state["opposite_count"]=0
    elif active == "DOWN":
        w = sum([score > -3, score_change >= 1.25, sig["mom3"] > .02, sig["mom5"] > 0, price_change > 8,
                 sig["distance"] is not None and seconds_left is not None and seconds_left <= 180 and sig["distance"] > -25 and price_change > 0])
        if w >= 2: reversal = True; reversal_text = "DOWN PERDIENDO FUERZA • POSIBLE REBOTE A UP"
        state["opposite_count"] = state.get("opposite_count",0)+1 if score >= FLIP_UP_THRESHOLD and sig["mom3"] > 0 else 0
        if state["opposite_count"] >= FLIP_CONFIRMATIONS:
            if not lock: state["active_direction"]="UP"; state["active_since"]=n
            state["opposite_count"]=0

    state["reversal_warning"] = reversal; state["reversal_text"] = reversal_text; save_state(state)
    active = state.get("active_direction")
    if active == "UP": decision,signal,icon,color,p = "POSIBLE UP","SEÑAL UP","🚀","#34d399",get_yes_ask(market)
    elif active == "DOWN": decision,signal,icon,color,p = "POSIBLE DOWN","SEÑAL DOWN","🔻","#fb7185",get_no_ask(market)
    elif lock: decision,signal,icon,color,p = "NO NUEVA ENTRADA","FINAL DE RONDA","⏰","#fbbf24",None
    else: decision,signal,icon,color,p = "NO TRADE","ESPERAR","⚪","#fbbf24",None
    q,qc = entry_quality(p,seconds_left)
    return dict(decision=decision,signal=signal,icon=icon,color=color,round_state=state,reversal=reversal,reversal_text=reversal_text,entry_price=p,entry_quality=q,entry_quality_color=qc)


# =========================================================
# MOTOR AUTÓNOMO NUEVO
# =========================================================
BASE_URL = "https://external-api.kalshi.com"
CRED_FILE = Path(".kalshi_credentials.json")
DEFAULT_CFG = {"modo":"SIMULACIÓN","auto_on":False,"max_levels":4,"martingala":True,"monto_inicial":0.50,"multiplicador":2.0,"precio_limite":0.45,"take_profit":90,"riesgo_max_dia":20.0,"max_operaciones_dia":20,"nivel_actual":1,"direcciones":["Seguir señal"]*12}

def init_new_db():
    c=sqlite3.connect(DB_PATH); c.execute("CREATE TABLE IF NOT EXISTS app_config(k TEXT PRIMARY KEY,v TEXT)"); c.execute("CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY AUTOINCREMENT,ticker TEXT UNIQUE,created_at TEXT,mode TEXT,level INTEGER,direction TEXT,amount REAL,limit_price REAL,contracts REAL,client_order_id TEXT,order_id TEXT,status TEXT,pnl REAL DEFAULT 0,result TEXT,note TEXT)"); c.commit(); c.close()
def cfg_load():
    init_new_db(); d=dict(DEFAULT_CFG); c=sqlite3.connect(DB_PATH)
    for k,v in c.execute("SELECT k,v FROM app_config").fetchall():
        try:d[k]=json.loads(v)
        except:pass
    c.close(); return d
def cfg_save(d):
    init_new_db(); c=sqlite3.connect(DB_PATH)
    for k,v in d.items(): c.execute("INSERT OR REPLACE INTO app_config(k,v) VALUES(?,?)",(k,json.dumps(v)))
    c.commit(); c.close()
def creds_load():
    if not CRED_FILE.exists(): return {"key_id":"","pem":""}
    try:return json.loads(CRED_FILE.read_text())
    except:return {"key_id":"","pem":""}
def creds_save(key_id,pem):
    CRED_FILE.write_text(json.dumps({"key_id":key_id.strip(),"pem":pem.strip()}))
    try:os.chmod(CRED_FILE,0o600)
    except:pass
def creds_delete():
    try:CRED_FILE.unlink(missing_ok=True)
    except:pass
def auth_headers(method,path,key_id=None,pem=None):
    cr=creds_load(); key_id=key_id or cr.get("key_id"); pem=pem or cr.get("pem")
    if not key_id or not pem: raise ValueError("Faltan las credenciales de Kalshi.")
    private_key=serialization.load_pem_private_key(pem.encode(),password=None); ts=str(int(time.time()*1000)); clean=path.split("?")[0]; msg=(ts+method.upper()+clean).encode()
    sig=private_key.sign(msg,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.DIGEST_LENGTH),hashes.SHA256())
    return {"KALSHI-ACCESS-KEY":key_id,"KALSHI-ACCESS-TIMESTAMP":ts,"KALSHI-ACCESS-SIGNATURE":base64.b64encode(sig).decode(),"Content-Type":"application/json"}
def kreq(method,path,params=None,payload=None,key_id=None,pem=None,timeout=10):
    r=requests.request(method,BASE_URL+path,headers=auth_headers(method,path,key_id,pem),params=params,json=payload,timeout=timeout)
    if not r.ok: raise RuntimeError(f"Kalshi {r.status_code}: {r.text[:240]}")
    return r.json() if r.content else {}
def verify_kalshi(key_id=None,pem=None):
    t=time.perf_counter(); data=kreq("GET","/trade-api/v2/portfolio/balance",key_id=key_id,pem=pem); ms=round((time.perf_counter()-t)*1000); raw=data.get("balance",0); balance=float(raw)/100 if isinstance(raw,(int,float)) and raw>100 else float(raw or 0); return balance,ms
def create_order_v2(ticker,direction,count,limit_price):
    side="bid" if direction=="UP" else "ask"; yes_price=limit_price if direction=="UP" else 1-limit_price; cid=str(uuid.uuid4())
    body={"ticker":ticker,"side":side,"count":f"{count:.2f}","price":f"{yes_price:.4f}","time_in_force":"good_till_canceled","self_trade_prevention_type":"taker_at_cross","client_order_id":cid}
    data=kreq("POST","/trade-api/v2/portfolio/events/orders",payload=body); oid=data.get("order_id") or (data.get("order") or {}).get("order_id"); return cid,oid,data
def trade_for_ticker(ticker):
    init_new_db(); c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; r=c.execute("SELECT * FROM trades WHERE ticker=?",(ticker,)).fetchone(); c.close(); return dict(r) if r else None
def add_trade(**x):
    init_new_db(); c=sqlite3.connect(DB_PATH); cols=list(x); c.execute(f"INSERT OR IGNORE INTO trades({','.join(cols)}) VALUES({','.join(['?']*len(cols))})",[x[k] for k in cols]); c.commit(); c.close()
def recent_trades(n=25):
    init_new_db(); c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; rows=[dict(r) for r in c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?",(n,)).fetchall()]; c.close(); return rows
def today_stats():
    rows=recent_trades(200); today=utc_now().date().isoformat(); rr=[r for r in rows if str(r.get('created_at','')).startswith(today)]; return len(rr),sum(float(r.get('pnl') or 0) for r in rr)
def effective_direction(signal,level,cfg):
    rule=cfg["direcciones"][max(0,min(11,level-1))]; return "UP" if rule=="Solo UP" else ("DOWN" if rule=="Solo DOWN" else signal)
def autonomous_tick():
    cfg=cfg_load()
    try:
        market=get_kalshi_btc_market()
        if not market:return {"ok":False,"msg":"No hay ronda BTC 15M abierta."}
        df=add_indicators(get_btc_data()); target=get_target_from_market(market); secs=get_seconds_remaining(market)
        try:live=get_kalshi_live_btc_price(market)
        except:live=get_coinbase_live_price()
        sig=build_signal(df,target,secs,live); rs=process_round_signal(market.get("ticker","--"),sig,market,secs,target); out={"ok":True,"market":market,"sig":sig,"rs":rs,"secs":secs,"target":target,"live":live}
        if not cfg.get("auto_on"):return out
        if cfg.get("modo")=="LIVE" and not creds_load().get("key_id"):out["block"]="Faltan credenciales Kalshi"; return out
        direction=(rs.get("round_state") or {}).get("active_direction")
        if direction not in ("UP","DOWN"):return out
        ticker=market.get("ticker")
        if trade_for_ticker(ticker):return out
        nops,pnl=today_stats()
        if nops>=int(cfg["max_operaciones_dia"]):out["block"]="Límite diario de operaciones alcanzado"; return out
        if pnl<=-abs(float(cfg["riesgo_max_dia"])):out["block"]="Límite diario de pérdida alcanzado"; return out
        level=max(1,min(int(cfg["nivel_actual"]),int(cfg["max_levels"]))); direction=effective_direction(direction,level,cfg); ask=get_yes_ask(market) if direction=="UP" else get_no_ask(market)
        if ask is None:out["block"]="Precio de entrada no disponible"; return out
        limit=float(cfg["precio_limite"])
        if ask>limit:out["block"]=f"Precio {ask:.2f} supera límite {limit:.2f}"; return out
        amount=float(cfg["monto_inicial"])*(float(cfg["multiplicador"])**(level-1) if cfg["martingala"] else 1); count=max(1,int(amount/max(ask,.01))); cid=oid=None; status="SIMULADA"; note=f"Señal {direction}; score {sig['final_score']:.2f}"
        if cfg["modo"]=="LIVE":cid,oid,_=create_order_v2(ticker,direction,count,limit); status="ENVIADA"
        add_trade(ticker=ticker,created_at=utc_now().isoformat(),mode=cfg["modo"],level=level,direction=direction,amount=amount,limit_price=limit,contracts=count,client_order_id=cid,order_id=oid,status=status,pnl=0,result=None,note=note); out["executed"]={"direction":direction,"amount":amount,"count":count,"status":status,"order_id":oid}; return out
    except Exception as e:return {"ok":False,"msg":str(e)}

st.markdown("""<style>#MainMenu,header,footer{visibility:hidden}.stApp{background:#07100d;color:#eef7f2}.block-container{max-width:520px;padding:18px 16px 90px!important}[data-testid=stMetric]{background:#0d1814;border:1px solid #1d3a30;border-radius:18px;padding:14px}.hero{border:1px solid #1f5b46;background:linear-gradient(145deg,#0b1914,#09120f);border-radius:22px;padding:18px;margin:8px 0 14px}.ey{color:#69d7a8;font-size:12px;font-weight:800;letter-spacing:1.5px}.big{font-size:34px;font-weight:900}.muted{color:#8fa49b}.pill{display:inline-block;border:1px solid #2a6b53;border-radius:99px;padding:5px 10px;color:#6ee7b7;font-size:12px;font-weight:800}.danger{color:#ff6b72}.warn{color:#f5c451}.good{color:#38d39f}.level{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.dot{border:1px solid #2b4a40;border-radius:10px;padding:7px 10px;font-size:12px}.active{border-color:#39d99f;color:#39d99f;background:#0d241b}.stButton>button{border-radius:14px;min-height:44px;font-weight:800}</style>""",unsafe_allow_html=True)
if "page" not in st.session_state:st.session_state.page="⚡ Bot"
page=st.radio("Navegación",["⚡ Bot","▤ Operaciones","$ Saldo","⚙ Ajustes"],horizontal=True,label_visibility="collapsed",key="page")
if page=="⚡ Bot":
    state=autonomous_tick(); cfg=cfg_load()
    if not state.get("ok"):st.error(state.get("msg","Error de conexión"))
    else:
        m,sig,rs=state["market"],state["sig"],state["rs"]; direction=(rs.get("round_state") or {}).get("active_direction") or "ESPERANDO"; color="good" if direction=="UP" else ("danger" if direction=="DOWN" else "warn")
        st.markdown(f'<div class="hero"><div class="ey">BTC · 15 MIN &nbsp; <span class="pill">KALSHI</span></div><div class="big">${state["live"]:,.2f}</div><div class="muted">Ronda {m.get("ticker","--")} · {format_countdown(state["secs"])} restantes</div></div>',unsafe_allow_html=True)
        a,b=st.columns(2); a.metric("TARGET",f'${state["target"]:,.2f}' if state["target"] else "--"); b.metric("DISTANCIA",f'{sig["distance"]:+.2f}' if sig["distance"] is not None else "--")
        st.markdown(f'<div class="hero"><div class="ey">ALPHA ENGINE v4.6.1</div><div class="big {color}">{direction}</div><div>UP {sig["up_probability"]}% · DOWN {sig["down_probability"]}%</div><div class="muted">EMA {sig["ema"]} · RSI {sig["rsi"]:.1f} · Momentum {sig["momentum"]} · Score {sig["final_score"]:.2f}</div></div>',unsafe_allow_html=True)
        lv=int(cfg['nivel_actual']); mx=int(cfg['max_levels']); dots=''.join(f'<span class="dot {"active" if i==lv else ""}">Nivel {i}</span>' for i in range(1,mx+1)); st.markdown(f'<div class="hero"><div class="ey">AUTO TRADING · {cfg["modo"]}</div><div class="big">{"ENCENDIDO" if cfg["auto_on"] else "APAGADO"}</div><div class="muted">Nivel actual {lv}/{mx} · Monto base ${cfg["monto_inicial"]:.2f} · Límite ${cfg["precio_limite"]:.2f}</div><div class="level">{dots}</div></div>',unsafe_allow_html=True)
        if state.get("block"):st.warning(state["block"])
        if state.get("executed"):st.success(f'Operación {state["executed"]["status"]}: {state["executed"]["direction"]} · ${state["executed"]["amount"]:.2f}')
        if st.button("⏻ APAGAR BOT" if cfg['auto_on'] else "⏻ ENCENDER BOT",use_container_width=True,type="primary"):cfg['auto_on']=not cfg['auto_on']; cfg_save(cfg); st.rerun()
elif page=="▤ Operaciones":
    st.title("Operaciones"); rows=recent_trades(50)
    if not rows:st.info("Todavía no hay operaciones.")
    for r in rows:st.markdown(f'<div class="hero"><div class="ey">{r["ticker"]} · NIVEL {r["level"]}</div><div class="big {"good" if r["direction"]=="UP" else "danger"}">{r["direction"]} · {r["status"]}</div><div class="muted">${r["amount"]:.2f} · {r["contracts"]} contratos · límite {r["limit_price"]:.2f}</div></div>',unsafe_allow_html=True)
elif page=="$ Saldo":
    st.title("Saldo"); cr=creds_load()
    if not cr.get('key_id'):st.info("Conecta Kalshi desde Ajustes → Conexión Kalshi.")
    else:
        try:bal,ms=verify_kalshi(); st.metric("Saldo Kalshi",f"${bal:,.2f}"); st.caption(f"API conectada · {ms} ms")
        except Exception as e:st.error(str(e))
    n,p=today_stats(); a,b=st.columns(2); a.metric("Operaciones hoy",n); b.metric("P&L registrado",f"${p:,.2f}")
else:
    st.title("Ajustes"); tab1,tab2=st.tabs(["🤖 Bot y niveles","🔐 Conexión Kalshi"])
    with tab1:
        cfg=cfg_load(); st.subheader("Estrategia"); modo=st.selectbox("Modo de operación",["SIMULACIÓN","LIVE"],index=0 if cfg['modo']=="SIMULACIÓN" else 1); maxl=st.slider("Máximo de niveles",1,12,int(cfg['max_levels'])); mart=st.toggle("Martingala",value=bool(cfg['martingala'])); monto=st.number_input("Monto inicial ($)",min_value=0.01,value=float(cfg['monto_inicial']),step=0.25); mult=st.number_input("Multiplicador por nivel",min_value=1.0,max_value=5.0,value=float(cfg['multiplicador']),step=0.25); lim=st.slider("Precio máximo de entrada",0.01,0.99,float(cfg['precio_limite']),0.01,format="$%.2f"); tp=st.slider("Tomar profit (%)",1,99,int(cfg['take_profit'])); loss=st.number_input("Pérdida máxima diaria ($)",min_value=1.0,value=float(cfg['riesgo_max_dia']),step=1.0); mop=st.number_input("Máximo de operaciones por día",min_value=1,max_value=100,value=int(cfg['max_operaciones_dia'])); dirs=list(cfg['direcciones']); st.subheader("Dirección por nivel")
        for i in range(maxl):dirs[i]=st.selectbox(f"Nivel {i+1}",["Seguir señal","Solo UP","Solo DOWN"],index=["Seguir señal","Solo UP","Solo DOWN"].index(dirs[i]),key=f"dir{i}")
        if st.button("Guardar cambios",type="primary",use_container_width=True):cfg.update(modo=modo,max_levels=maxl,martingala=mart,monto_inicial=monto,multiplicador=mult,precio_limite=lim,take_profit=tp,riesgo_max_dia=loss,max_operaciones_dia=int(mop),direcciones=dirs); cfg['nivel_actual']=min(cfg['nivel_actual'],maxl); cfg_save(cfg); st.success("Configuración guardada.")
        if modo=="LIVE":st.warning("LIVE envía órdenes reales. Prueba primero en SIMULACIÓN.")
    with tab2:
        st.subheader("Conexión Kalshi"); cr=creds_load(); st.caption("API Key ID + clave privada PEM. La clave se guarda localmente con permisos restringidos cuando el sistema lo permite."); kid=st.text_input("API Key ID",value=cr.get('key_id',''),placeholder="Tu Key ID"); pem=st.text_area("Clave privada PEM",value="",placeholder="Pega aquí la clave para conectar o reemplazarla",height=180); c1,c2=st.columns(2)
        if c1.button("Verificar y guardar",type="primary",use_container_width=True):
            testpem=pem.strip() or cr.get('pem','')
            try:bal,ms=verify_kalshi(kid,testpem); creds_save(kid,testpem); st.success(f"Conectado · ${bal:,.2f} · {ms} ms")
            except Exception as e:st.error(f"No se pudo conectar: {e}")
        if c2.button("Eliminar credenciales",use_container_width=True):creds_delete(); st.success("Credenciales eliminadas."); st.rerun()
        if cr.get('key_id'):
            try:bal,ms=verify_kalshi(); st.markdown(f'<div class="hero"><div class="ey">KALSHI LIVE</div><div class="big good">CONECTADO</div><div class="muted">Saldo ${bal:,.2f} · Latencia {ms} ms</div></div>',unsafe_allow_html=True)
            except Exception as e:st.warning(f"Credenciales guardadas, pero la prueba falló: {e}")
st.caption("Alpha Autónomo · El modo LIVE puede ejecutar operaciones reales. Los límites reducen riesgo, pero no garantizan ganancias.")
