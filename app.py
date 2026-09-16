import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from textwrap import dedent

# =========================================================
# MACALY + ALPHA V5
# BTC / KALSHI 15 MIN
# MULTI-TIMEFRAME MOMENTUM + LIVE TARGET + CHART
# =========================================================

st.set_page_config(
    page_title="Macaly + Alpha V5",
    page_icon="⚡",
    layout="centered"
)

# =========================================================
# CONFIG
# =========================================================

COINBASE_API = "https://api.exchange.coinbase.com"
KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"

UP_THRESHOLD = 3.5
DOWN_THRESHOLD = -3.5

st.markdown(dedent("""
<style>
.stApp {
    background: #070b14;
    color: #f4f7fb;
}

.block-container {
    max-width: 520px;
    padding-top: 1rem;
    padding-bottom: 3rem;
}

.header-box {
    border: 1px solid #2e7df6;
    border-radius: 22px;
    padding: 22px 14px;
    text-align: center;
    margin-bottom: 18px;
    background: #101827;
}

.header-title {
    font-size: 24px;
    font-weight: 800;
    letter-spacing: 3px;
    color: #46c7ff;
}

.card {
    background: #0d1420;
    border: 1px solid #26384d;
    border-radius: 22px;
    padding: 22px;
    margin-bottom: 18px;
}

.card-title {
    color: #9baac0;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 2px;
    margin-bottom: 18px;
}

.signal-up {
    color: #35e3a6;
    font-size: 38px;
    font-weight: 900;
    text-align: center;
}

.signal-down {
    color: #ff5277;
    font-size: 38px;
    font-weight: 900;
    text-align: center;
}

.signal-wait {
    color: #f2c66d;
    font-size: 32px;
    font-weight: 900;
    text-align: center;
}

.row {
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid #26384d;
    padding: 12px 0;
    gap: 10px;
}

.label {
    color: #95a4ba;
}

.value {
    color: #f4f7fb;
    font-weight: 800;
    text-align: right;
}

.green {
    color: #35e3a6;
}

.red {
    color: #ff5277;
}

.yellow {
    color: #f2c66d;
}

.momentum-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}

.momentum-box {
    border: 1px solid #26384d;
    border-radius: 16px;
    padding: 14px;
    background: #090f19;
}

.small-label {
    color: #8494aa;
    font-size: 12px;
    font-weight: 700;
}

.big-number {
    font-size: 19px;
    font-weight: 900;
    margin-top: 5px;
}

.prob {
    font-size: 26px;
    font-weight: 900;
}

.disclaimer {
    color: #718096;
    font-size: 11px;
    text-align: center;
    margin-top: 8px;
}
</style>
"""), unsafe_allow_html=True)

# =========================================================
# DATA
# =========================================================

@st.cache_data(ttl=5)
def get_candles():
    url = f"{COINBASE_API}/products/BTC-USD/candles"

    params = {
        "granularity": 60
    }

    r = requests.get(
        url,
        params=params,
        timeout=8,
        headers={"User-Agent": "MacalyAlphaV5"}
    )
    r.raise_for_status()

    data = r.json()

    df = pd.DataFrame(
        data,
        columns=["time", "low", "high", "open", "close", "volume"]
    )

    df = df.sort_values("time").reset_index(drop=True)

    for col in ["low", "high", "open", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["datetime"] = pd.to_datetime(
        df["time"],
        unit="s",
        utc=True
    )

    return df


@st.cache_data(ttl=2)
def get_coinbase_live():
    url = f"{COINBASE_API}/products/BTC-USD/ticker"

    r = requests.get(
        url,
        timeout=6,
        headers={"User-Agent": "MacalyAlphaV5"}
    )
    r.raise_for_status()

    return float(r.json()["price"])


@st.cache_data(ttl=3)
def get_kalshi_market():
    url = f"{KALSHI_API}/markets"

    params = {
        "series_ticker": "KXBTC15M",
        "status": "open",
        "limit": 100
    }

    r = requests.get(
        url,
        params=params,
        timeout=8,
        headers={"User-Agent": "MacalyAlphaV5"}
    )
    r.raise_for_status()

    markets = r.json().get("markets", [])

    if not markets:
        return None

    now = datetime.now(timezone.utc)
    future = []

    for m in markets:
        try:
            close_time = datetime.fromisoformat(
                str(m["close_time"]).replace(
                    "Z",
                    "+00:00"
                )
            )

            if close_time > now:
                future.append(
                    (close_time, m)
                )

        except Exception:
            pass

    if not future:
        return markets[0]

    future.sort(
        key=lambda x: x[0]
    )

    return future[0][1]


def get_target(market):
    if not market:
        return None

    for key in [
        "floor_strike",
        "cap_strike",
        "strike"
    ]:
        value = market.get(key)

        if value is not None:
            try:
                return float(value)
            except Exception:
                pass

    return None


def get_event_ticker(market):
    if not market:
        return None

    event_ticker = market.get(
        "event_ticker"
    )

    if event_ticker:
        return str(event_ticker)

    ticker = market.get("ticker")

    if not ticker:
        return None

    parts = str(ticker).split("-")

    if len(parts) >= 2:
        return "-".join(parts[:-1])

    return None


def extract_live_number(obj):
    preferred = [
        "price",
        "value",
        "index_value",
        "current_price",
        "current_value",
        "last_price",
        "close"
    ]

    candidates = []

    def walk(x):
        if isinstance(x, dict):
            normalized = {}

            for k, v in x.items():
                key = (
                    str(k)
                    .lower()
                    .replace("-", "_")
                )

                normalized[key] = v

            for key in preferred:
                if key in normalized:
                    try:
                        n = float(
                            normalized[key]
                        )

                        if 10000 < n < 1000000:
                            candidates.append(n)

                    except Exception:
                        pass

            for v in x.values():
                walk(v)

        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)

    if candidates:
        return candidates[-1]

    return None


def get_kalshi_live_btc(market):
    event_ticker = get_event_ticker(
        market
    )

    if not event_ticker:
        return None

    url = (
        "https://external-api.kalshi.com/"
        "trade-api/v2/live_data/events/"
        f"{event_ticker}"
    )

    try:
        r = requests.get(
            url,
            params={"range": "15min"},
            timeout=6,
            headers={
                "User-Agent": "MacalyAlphaV5",
                "Cache-Control": "no-cache"
            }
        )

        r.raise_for_status()

        return extract_live_number(
            r.json()
        )

    except Exception:
        return None


# =========================================================
# INDICATORS
# =========================================================

def calculate_indicators(df):
    df = df.copy()

    df["ema9"] = df["close"].ewm(
        span=9,
        adjust=False
    ).mean()

    df["ema21"] = df["close"].ewm(
        span=21,
        adjust=False
    ).mean()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    rs = (
        avg_gain /
        avg_loss.replace(0, np.nan)
    )

    df["rsi"] = (
        100 -
        (100 / (1 + rs))
    )

    df["rsi"] = (
        df["rsi"]
        .fillna(50)
    )

    typical = (
        df["high"] +
        df["low"] +
        df["close"]
    ) / 3

    cumulative_volume = (
        df["volume"].cumsum()
    )

    df["vwap"] = (
        (typical * df["volume"]).cumsum()
        /
        cumulative_volume.replace(
            0,
            np.nan
        )
    )

    df["vol_ma20"] = (
        df["volume"]
        .rolling(20)
        .mean()
    )

    return df


def dollar_momentum(df, bars):
    if len(df) <= bars:
        return 0.0

    return float(
        df["close"].iloc[-1]
        -
        df["close"].iloc[-1 - bars]
    )


# =========================================================
# COUNTDOWN
# =========================================================

def seconds_remaining(market):
    if not market:
        return 0

    try:
        close_time = datetime.fromisoformat(
            str(
                market["close_time"]
            ).replace(
                "Z",
                "+00:00"
            )
        )

        now = datetime.now(
            timezone.utc
        )

        return max(
            0,
            int(
                (
                    close_time - now
                ).total_seconds()
            )
        )

    except Exception:
        return 0


def format_countdown(seconds):
    minutes = seconds // 60
    secs = seconds % 60

    return (
        f"{minutes:02d}:"
        f"{secs:02d}"
    )


# =========================================================
# MODEL
# =========================================================

def build_model(
    df,
    btc_price,
    target,
    time_left
):
    last = df.iloc[-1]

    ema9 = float(last["ema9"])
    ema21 = float(last["ema21"])
    rsi = float(last["rsi"])
    vwap = float(last["vwap"])

    mom1 = dollar_momentum(
        df,
        1
    )

    mom5 = dollar_momentum(
        df,
        5
    )

    mom10 = dollar_momentum(
        df,
        10
    )

    mom30 = dollar_momentum(
        df,
        30
    )

    volume = float(
        last["volume"]
    )

    vol_ma = last["vol_ma20"]

    if (
        pd.isna(vol_ma)
        or vol_ma <= 0
    ):
        volume_ratio = 1.0

    else:
        volume_ratio = (
            volume /
            float(vol_ma)
        )

    technical_score = 0.0

    # EMA trend
    if ema9 > ema21:
        technical_score += 1.5

    elif ema9 < ema21:
        technical_score -= 1.5

    # Price vs VWAP
    if btc_price > vwap:
        technical_score += 1.0

    elif btc_price < vwap:
        technical_score -= 1.0

    # RSI
    if rsi >= 55:
        technical_score += 1.0

    elif rsi <= 45:
        technical_score -= 1.0

    # Momentum 1m
    if mom1 > 15:
        technical_score += 0.75

    elif mom1 < -15:
        technical_score -= 0.75

    # Momentum 5m
    if mom5 > 30:
        technical_score += 1.0

    elif mom5 < -30:
        technical_score -= 1.0

    # Momentum 10m
    if mom10 > 50:
        technical_score += 1.0

    elif mom10 < -50:
        technical_score -= 1.0

    # Momentum 30m
    if mom30 > 80:
        technical_score += 0.75

    elif mom30 < -80:
        technical_score -= 0.75

    # Volume confirmation
    if volume_ratio >= 1.25:
        if mom1 > 0:
            technical_score += 0.5

        elif mom1 < 0:
            technical_score -= 0.5

    distance = 0.0
    target_score = 0.0

    if target is not None:
        distance = (
            btc_price - target
        )

        if distance > 0:
            target_score += 2.0

        elif distance < 0:
            target_score -= 2.0

        abs_distance = abs(
            distance
        )

        if time_left <= 60:
            weight = 3.0

        elif time_left <= 180:
            weight = 2.5

        elif time_left <= 300:
            weight = 2.0

        else:
            weight = 1.25

        if distance > 0:
            target_score += weight

        elif distance < 0:
            target_score -= weight

        # Close to target = reduce confidence
        if abs_distance < 15:
            target_score *= 0.55

        elif abs_distance < 30:
            target_score *= 0.75

    score = (
        technical_score +
        target_score
    )

    # Estimated probabilities
    up_probability = (
        50 +
        (score * 6.5)
    )

    if target is not None:
        distance_boost = np.clip(
            distance / 15,
            -15,
            15
        )

        up_probability += (
            distance_boost
        )

    up_probability = float(
        np.clip(
            up_probability,
            5,
            95
        )
    )

    down_probability = (
        100 -
        up_probability
    )

    if score >= UP_THRESHOLD:
        signal = "UP"

    elif score <= DOWN_THRESHOLD:
        signal = "DOWN"

    else:
        signal = "WAIT"

    if (
        mom5 > 0
        and mom10 > 0
    ):
        momentum_bias = "UP"

    elif (
        mom5 < 0
        and mom10 < 0
    ):
        momentum_bias = "DOWN"

    else:
        momentum_bias = "MIXED"

    # Simple projected close based on recent momentum
    projected_move = (
        mom1 * 0.30
        +
        mom5 * 0.20
        +
        mom10 * 0.10
    )

    projected_close = (
        btc_price +
        projected_move
    )

    if target is not None:
        projected_gap = (
            projected_close -
            target
        )

    else:
        projected_gap = 0.0

    return {
        "signal": signal,
        "score": score,
        "technical_score": technical_score,
        "target_score": target_score,
        "up_probability": up_probability,
        "down_probability": down_probability,
        "distance": distance,
        "ema9": ema9,
        "ema21": ema21,
        "rsi": rsi,
        "vwap": vwap,
        "volume_ratio": volume_ratio,
        "mom1": mom1,
        "mom5": mom5,
        "mom10": mom10,
        "mom30": mom30,
        "momentum_bias": momentum_bias,
        "projected_close": projected_close,
        "projected_gap": projected_gap
    }


# =========================================================
# CHART
# =========================================================

def make_chart(df, target):
    chart = (
        df.tail(60)
        .copy()
    )

    chart = chart.set_index(
        "datetime"
    )

    data = pd.DataFrame(
        {
            "BTC": chart["close"],
            "EMA9": chart["ema9"],
            "EMA21": chart["ema21"],
            "VWAP": chart["vwap"]
        }
    )

    if target is not None:
        data["TARGET"] = target

    return data


# =========================================================
# DASHBOARD
# =========================================================

def dashboard():

    st.markdown(
        dedent("""
        <div class="header-box">
            <div class="header-title">
                ⚡ MACALY + ALPHA V5
            </div>
        </div>
        """),
        unsafe_allow_html=True
    )

    try:
        df = calculate_indicators(
            get_candles()
        )

        market = (
            get_kalshi_market()
        )

        target = get_target(
            market
        )

        coinbase_price = (
            get_coinbase_live()
        )

        kalshi_price = (
            get_kalshi_live_btc(
                market
            )
        )

        if kalshi_price is not None:
            btc_price = (
                kalshi_price
            )

            source = (
                "KALSHI LIVE 🟢"
            )

        else:
            btc_price = (
                coinbase_price
            )

            source = (
                "COINBASE LIVE 🟡"
            )

        time_left = (
            seconds_remaining(
                market
            )
        )

        model = build_model(
            df,
            btc_price,
            target,
            time_left
        )

        signal = model["signal"]

        if signal == "UP":
            signal_html = (
                '<div class="signal-up">'
                '🚀 POSIBLE UP'
                '</div>'
            )

        elif signal == "DOWN":
            signal_html = (
                '<div class="signal-down">'
                '🔻 POSIBLE DOWN'
                '</div>'
            )

        else:
            signal_html = (
                '<div class="signal-wait">'
                '⏳ ESPERAR'
                '</div>'
            )

        # =================================================
        # MAIN SIGNAL
        # =================================================

        st.markdown(
            dedent(f"""
            <div class="card">
                <div class="card-title">
                    BTC • KALSHI 15 MIN
                </div>

                {signal_html}

                <div style="
                    text-align:center;
                    font-size:25px;
                    margin-top:14px;
                ">
                    BTC ${btc_price:,.2f}
                </div>
            </div>
            """),
            unsafe_allow_html=True
        )

        # =================================================
        # PROBABILITY
        # =================================================

        st.markdown(
            dedent(f"""
            <div class="card">
                <div class="card-title">
                    PROBABILIDAD ESTIMADA
                </div>

                <div class="row">
                    <span class="label">
                        🚀 UP
                    </span>

                    <span class="prob green">
                        {model["up_probability"]:.0f}%
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        🔻 DOWN
                    </span>

                    <span class="prob red">
                        {model["down_probability"]:.0f}%
                    </span>
                </div>

                <div class="disclaimer">
                    Estimación interna del modelo.
                    No representa certeza de resultado.
                </div>
            </div>
            """),
            unsafe_allow_html=True
        )

        ticker = (
            market.get(
                "ticker",
                "N/A"
            )
            if market
            else "N/A"
        )

        if target is not None:
            target_text = (
                f"${target:,.2f}"
            )

            if model["distance"] >= 0:
                distance_text = (
                    f'+${model["distance"]:,.2f} ARRIBA'
                )

                distance_class = (
                    "green"
                )

            else:
                distance_text = (
                    f'-${abs(model["distance"]):,.2f} ABAJO'
                )

                distance_class = (
                    "red"
                )

        else:
            target_text = "N/A"
            distance_text = "N/A"
            distance_class = "yellow"

        # =================================================
        # CURRENT ROUND
        # =================================================

        st.markdown(
            dedent(f"""
            <div class="card">
                <div class="card-title">
                    RONDA ACTUAL
                </div>

                <div style="
                    text-align:center;
                    border:1px solid #35bdf4;
                    border-radius:14px;
                    padding:12px;
                    margin-bottom:15px;
                    color:#79d7ff;
                    font-weight:800;
                ">
                    {ticker}
                </div>

                <div class="row">
                    <span class="label">
                        Target
                    </span>

                    <span class="value">
                        {target_text}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        BTC referencia
                    </span>

                    <span class="value">
                        ${btc_price:,.2f}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        Fuente BTC
                    </span>

                    <span class="value">
                        {source}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        Distancia
                    </span>

                    <span class="value {distance_class}">
                        {distance_text}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        Tiempo restante
                    </span>

                    <span class="value">
                        {format_countdown(time_left)}
                    </span>
                </div>
            </div>
            """),
            unsafe_allow_html=True
        )

        # =================================================
        # MOMENTUM
        # =================================================

        def momentum_html(value):
            if value > 0:
                return (
                    '<span class="green">'
                    f'▲ +${value:,.2f}'
                    '</span>'
                )

            if value < 0:
                return (
                    '<span class="red">'
                    f'▼ -${abs(value):,.2f}'
                    '</span>'
                )

            return (
                '<span class="yellow">'
                '$0.00'
                '</span>'
            )

        st.markdown(
            dedent(f"""
            <div class="card">
                <div class="card-title">
                    ⚡ IMPULSO A CORTO PLAZO
                </div>

                <div class="momentum-grid">

                    <div class="momentum-box">
                        <div class="small-label">
                            1M
                        </div>

                        <div class="big-number">
                            {momentum_html(model["mom1"])}
                        </div>
                    </div>

                    <div class="momentum-box">
                        <div class="small-label">
                            5M
                        </div>

                        <div class="big-number">
                            {momentum_html(model["mom5"])}
                        </div>
                    </div>

                    <div class="momentum-box">
                        <div class="small-label">
                            10M
                        </div>

                        <div class="big-number">
                            {momentum_html(model["mom10"])}
                        </div>
                    </div>

                    <div class="momentum-box">
                        <div class="small-label">
                            30M
                        </div>

                        <div class="big-number">
                            {momentum_html(model["mom30"])}
                        </div>
                    </div>

                </div>

                <div class="row">
                    <span class="label">
                        Momentum bias
                    </span>

                    <span class="value">
                        {model["momentum_bias"]}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        Projected close
                    </span>

                    <span class="value">
                        ${model["projected_close"]:,.2f}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        Projected gap
                    </span>

                    <span class="value">
                        ${model["projected_gap"]:,.2f}
                    </span>
                </div>
            </div>
            """),
            unsafe_allow_html=True
        )

        # =================================================
        # INDICATORS
        # =================================================

        st.markdown(
            dedent(f"""
            <div class="card">
                <div class="card-title">
                    INDICADORES
                </div>

                <div class="row">
                    <span class="label">
                        EMA9
                    </span>

                    <span class="value">
                        ${model["ema9"]:,.2f}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        EMA21
                    </span>

                    <span class="value">
                        ${model["ema21"]:,.2f}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        VWAP
                    </span>

                    <span class="value">
                        ${model["vwap"]:,.2f}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        RSI 14
                    </span>

                    <span class="value">
                        {model["rsi"]:.1f}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        Volume ratio
                    </span>

                    <span class="value">
                        {model["volume_ratio"]:.2f}x
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        Score técnico
                    </span>

                    <span class="value">
                        {model["technical_score"]:+.2f}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        Score target
                    </span>

                    <span class="value">
                        {model["target_score"]:+.2f}
                    </span>
                </div>

                <div class="row">
                    <span class="label">
                        Score total
                    </span>

                    <span class="value">
                        {model["score"]:+.2f}
                    </span>
                </div>
            </div>
            """),
            unsafe_allow_html=True
        )

        # =================================================
        # CHART
        # =================================================

        st.markdown(
            dedent("""
            <div class="card-title">
                📈 GRÁFICA BTC + INDICADORES
            </div>
            """),
            unsafe_allow_html=True
        )

        chart_data = make_chart(
            df,
            target
        )

        st.line_chart(
            chart_data,
            height=380,
            use_container_width=True
        )

        st.caption(
            "BTC + EMA9 + EMA21 + VWAP + target de la ronda."
        )

    except Exception as e:
        st.error(
            f"Error cargando datos: {e}"
        )


# =========================================================
# AUTO REFRESH
# =========================================================

@st.fragment(run_every=2)
def live_dashboard():
    dashboard()


live_dashboard()
