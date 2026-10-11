"""Alpha Lab: señales experimentales. Sin ejecución de órdenes."""
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st


def context_features(candles, price, target, seconds):
    x = candles.sort_values("time").tail(300)
    p = x.close.to_numpy(dtype=float)

    if len(p) < 40:
        raise ValueError("Contexto insuficiente")

    r = np.diff(np.log(p))
    sigma = float(np.std(r[-20:], ddof=1))

    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("Volatilidad inválida")

    travel = float(np.abs(r[-10:]).sum())

    features = [
        np.log(p[-1] / p[-4]) / (sigma * np.sqrt(3)),
        np.log(p[-1] / p[-11]) / (sigma * np.sqrt(10)),
        np.log(p[-1] / p[-11]) / max(travel, 1e-12),
        np.log1p(
            float(x.volume.iloc[-1])
            / max(float(x.volume.tail(30).median()), 1e-8)
        ),
        math.log(sigma),
        math.log(price / target)
        / (sigma * math.sqrt(max(seconds, 60) / 60)),
    ]

    return np.asarray(features, dtype=float)


def predict_round(samples, query):
    if len(samples) < 40:
        return {
            "direction": None,
            "reason": "Menos de 40 rondas anteriores completas",
            "n": len(samples),
        }

    matrix = np.asarray(
        [sample["features"] for sample in samples],
        dtype=float,
    )

    scale = np.maximum(
        np.percentile(matrix, 75, axis=0)
        - np.percentile(matrix, 25, axis=0),
        1e-6,
    )

    distance = np.sqrt(
        np.mean(((matrix - query) / scale) ** 2, axis=1)
    )

    k = min(40, max(12, int(2 * math.sqrt(len(samples)))))
    selected = np.argsort(distance)[:k]

    weights = 1 / (0.25 + distance[selected])
    weights /= weights.sum()

    outcomes = np.asarray(
        [sample["up"] for sample in samples],
        dtype=float,
    )

    up = float(np.dot(weights, outcomes[selected]))
    effective = float(1 / np.sum(weights**2))
    support = max(up, 1 - up)

    # Filtro heurístico; no es un intervalo calibrado.
    z = 1.96
    lower = (
        support
        + z * z / (2 * effective)
        - z
        * math.sqrt(
            support * (1 - support) / effective
            + z * z / (4 * effective * effective)
        )
    ) / (1 + z * z / effective)

    direction = (
        "UP" if up >= 0.65
        else "DOWN" if up <= 0.35
        else None
    )

    if (
        effective < 10
        or float(np.median(distance[selected])) > 2
        or lower <= 0.5
    ):
        direction = None

    return {
        "direction": direction,
        "up": up,
        "n": k,
        "available": len(samples),
        "effective": effective,
        "support_lower_screen": lower,
        "reason": (
            "Candidato"
            if direction
            else "Evidencia insuficiente"
        ),
    }


class Confirmation:
    def __init__(self):
        self.direction = None
        self.count = 0
        self.last_minute = None
        self.first = None

    def update(self, candidate, minute, timestamp, seconds):
        if minute == self.last_minute:
            return self.first

        self.last_minute = minute

        if not candidate or seconds <= 60:
            self.direction = None
            self.count = 0
            return self.first

        if candidate == self.direction:
            self.count += 1
        else:
            self.direction = candidate
            self.count = 1

        if self.count >= 3 and self.first is None:
            self.first = {
                "direction": candidate,
                "time_utc": timestamp,
                "seconds_left": seconds,
            }

        return self.first


st.set_page_config(
    page_title="Alpha Lab · Señales",
    layout="wide",
)

API = "https://external-api.kalshi.com/trade-api/v2"
COIN = "https://api.exchange.coinbase.com"

HEADERS = {
    "User-Agent": "AlphaLab/0.2",
    "Accept": "application/json",
    "Cache-Control": "no-cache",
}


def get_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    return response.json()


def candle_frame(rows):
    x = pd.DataFrame(
        rows,
        columns=[
            "time", "low", "high",
            "open", "close", "volume",
        ],
    )

    x["time"] = pd.to_datetime(
        x["time"], unit="s", utc=True
    )

    for column in ["low", "high", "open", "close", "volume"]:
        x[column] = pd.to_numeric(
            x[column], errors="coerce"
        )

    return (
        x.dropna()
        .drop_duplicates("time")
        .sort_values("time")
        .reset_index(drop=True)
    )


@st.cache_data(ttl=900, show_spinner=False)
def history():
    end = pd.Timestamp.now(tz="UTC").floor("h")
    chunks = []

    for block in range(7):
        stop = end - pd.Timedelta(hours=4 * block)
        start = stop - pd.Timedelta(hours=4)

        rows = get_json(
            COIN + "/products/BTC-USD/candles",
            {
                "granularity": 60,
                "start": start.isoformat(),
                "end": stop.isoformat(),
            },
        )

        if not isinstance(rows, list):
            raise ValueError("Respuesta de velas no válida.")

        chunks.extend(rows)

    return candle_frame(chunks)


@st.cache_data(ttl=10, show_spinner=False)
def recent():
    end = pd.Timestamp.now(tz="UTC")

    rows = get_json(
        COIN + "/products/BTC-USD/candles",
        {
            "granularity": 60,
            "start": (
                end - pd.Timedelta(minutes=300)
            ).isoformat(),
            "end": end.isoformat(),
        },
    )

    x = candle_frame(rows)
    now = pd.Timestamp.now(tz="UTC")

    return x[
        x.time + pd.Timedelta(minutes=1) <= now
    ].reset_index(drop=True)


@st.cache_data(ttl=4, show_spinner=False)
def market():
    rows = get_json(
        API + "/markets",
        {
            "series_ticker": "KXBTC15M",
            "status": "open",
            "limit": 100,
        },
    ).get("markets", [])

    now = pd.Timestamp.now(tz="UTC")

    valid = [
        item
        for item in rows
        if item.get("close_time")
        and pd.Timestamp(item["close_time"]) > now
    ]

    if not valid:
        return None

    return min(
        valid,
        key=lambda item: pd.Timestamp(item["close_time"]),
    )


@st.cache_data(ttl=4, show_spinner=False)
def index_data(event):
    data = get_json(
        API + "/live_data/events/" + event,
        {"range": "15min"},
    )

    live = data.get("live_data", {})
    rows = live.get("details", {}).get("timeseries", [])
    points = []

    for row in rows:
        try:
            timestamp = float(row["t"]) / 1000
            value = float(row["v"])

            if math.isfinite(value) and value > 0:
                points.append((timestamp, value))

        except (KeyError, ValueError, TypeError):
            continue

    if not points:
        raise ValueError(
            "Kalshi no entregó una serie con horas identificables."
        )

    return (
        sorted(dict(points).items()),
        bool(live.get("is_historical", False)),
    )


@st.cache_data(ttl=900, show_spinner=False)
def labelled_history():
    rows = get_json(
        API + "/markets",
        {
            "series_ticker": "KXBTC15M",
            "status": "settled",
            "limit": 100,
        },
    ).get("markets", [])

    rows = sorted(
        [
            item
            for item in rows
            if item.get("result") in ("yes", "no")
            and item.get("floor_strike") is not None
        ],
        key=lambda item: item["close_time"],
    )[-80:]

    if len(rows) < 40:
        raise ValueError(
            "Faltan 40 rondas cerradas para el nuevo motor."
        )

    def fetch(item):
        data = get_json(
            API + "/live_data/events/" + item["event_ticker"],
            {"range": "1hour"},
        )
        return item, data

    prices = {}

    with ThreadPoolExecutor(max_workers=6) as pool:
        downloaded = list(pool.map(fetch, rows[::-4]))

    for item, data in sorted(
        downloaded,
        key=lambda pair: pair[0]["close_time"],
    ):
        series = (
            data.get("live_data", {})
            .get("details", {})
            .get("timeseries", [])
        )

        for point in series:
            prices[int(point["t"]) // 1000] = float(point["v"])

    return rows, prices


def round_model(
    hist, live, price, target,
    seconds, close_time, labelled,
):
    rows, prices = labelled

    end = pd.Timestamp(close_time)
    start = end - pd.Timedelta(minutes=15)

    elapsed = max(0, min(839, 900 - int(seconds)))
    offset = (elapsed // 60) * 60

    samples = []

    for item in rows:
        prior_end = pd.Timestamp(item["close_time"])

        if prior_end > start:
            continue

        stamp = (
            prior_end
            - pd.Timedelta(minutes=15)
            + pd.Timedelta(seconds=offset)
        )

        historical_price = prices.get(
            int(stamp.timestamp())
        )

        if historical_price is None:
            continue

        candles = hist[
            hist.time + pd.Timedelta(minutes=1) <= stamp
        ].tail(300)

        if len(candles) < 40:
            continue

        if not (
            candles.time.diff()
            .dropna()
            .eq(pd.Timedelta(minutes=1))
            .all()
        ):
            continue

        samples.append({
            "features": context_features(
                candles,
                historical_price,
                float(item["floor_strike"]),
                900 - offset,
            ),
            "up": float(item["result"] == "yes"),
        })

    query = context_features(
        live, price, target, seconds
    )

    return predict_round(samples, query)


st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');

.stApp {
    background: #0a101b;
    color: #e5edf8;
    font-family: 'DM Sans', sans-serif;
}
.block-container {
    max-width: 1180px;
    padding: 28px 28px 45px;
}
h1,h2,h3,p,[data-testid="stCaptionContainer"] {
    color: #dce6f3;
}
[data-testid="stSidebar"] {
    background: #101a29;
    border-right: 1px solid #213048;
}
[data-testid="stSidebar"] * {
    color: #dce6f3;
}
#MainMenu,footer {
    visibility: hidden;
}
.brandrow {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 0 24px;
    border-bottom: 1px solid #243044;
}
.wordmark {
    font: 800 22px Manrope,sans-serif;
    letter-spacing: 4px;
    color: #f5f7fc;
}
.brandtag {
    font-size: 10px;
    color: #8494ad;
    letter-spacing: 2px;
    margin-top: 5px;
}
.modepill {
    font-size: 10px;
    color: #83cfc4;
    border: 1px solid #2b4948;
    border-radius: 30px;
    padding: 8px 12px;
    letter-spacing: 1px;
}
.signalstage {
    position: relative;
    padding: 34px 0 28px;
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 28px;
    align-items: center;
}
.eyebrow {
    font-size: 10px;
    letter-spacing: 2.5px;
    color: #8394af;
    text-transform: uppercase;
}
.signalword {
    font: 800 clamp(44px,8vw,90px) Manrope,sans-serif;
    line-height: 1.04;
    letter-spacing: -4px;
    margin: 12px 0;
    color: var(--signal);
}
.signaldesc {
    font-size: 13px;
    line-height: 1.6;
    color: #98aac3;
    max-width: 470px;
}
.signalmark {
    font-size: 12px;
    font-weight: 600;
    color: var(--signal);
    letter-spacing: 1px;
    margin-top: 17px;
}
.contextstrip {
    display: grid;
    grid-template-columns: repeat(3,1fr);
    gap: 22px;
    border-top: 1px solid #243044;
    border-bottom: 1px solid #243044;
    padding: 21px 0;
    margin-bottom: 25px;
}
.contextvalue {
    font: 600 24px Manrope,sans-serif;
    color: #edf3fd;
    margin-top: 7px;
    letter-spacing: -0.7px;
}
.contextnote {
    font-size: 11px;
    color: #8fa3bc;
    margin-top: 5px;
}
.balance {
    padding: 24px 0 15px;
    border-bottom: 1px solid #243044;
}
.balancehead {
    display: flex;
    justify-content: space-between;
    color: #b8c7dd;
    font-size: 11px;
    letter-spacing: 1px;
}
.balancebar {
    display: flex;
    gap: 4px;
    height: 9px;
    margin: 15px 0;
    border-radius: 10px;
    overflow: hidden;
}
.balancelabels {
    display: flex;
    justify-content: space-between;
    font: 600 27px Manrope,sans-serif;
}
.scenario {
    display: flex;
    gap: 20px;
    justify-content: space-between;
    padding: 17px 0;
    color: #8da1bc;
    font-size: 11px;
}
.scenario b {
    display: block;
    color: #dce7f6;
    font: 500 17px Manrope,sans-serif;
    margin-top: 7px;
}
.sessionline {
    border-top: 1px solid #243044;
    padding-top: 17px;
    margin-top: 22px;
    display: flex;
    justify-content: space-between;
    gap: 15px;
    font-size: 11px;
    color: #8ca0bb;
    flex-wrap: wrap;
}
@media(max-width:650px) {
    .block-container {
        padding: 18px 17px 35px;
    }
    .signalstage {
        grid-template-columns: 1fr;
        gap: 10px;
        padding-top: 27px;
    }
    .signalword {
        font-size: 58px;
        letter-spacing: -3px;
    }
    .contextstrip {
        gap: 12px;
    }
    .contextvalue {
        font-size: 18px;
    }
    .wordmark {
        font-size: 17px;
    }
    .modepill {
        font-size: 8px;
        padding: 7px;
    }
    .scenario {
        gap: 8px;
    }
    .scenario b {
        font-size: 15px;
    }
}
</style>

<div class="brandrow">
    <div>
        <div class="wordmark">ALPHA / LAB</div>
        <div class="brandtag">
            BITCOIN · 15 MINUTE SIGNAL RESEARCH
        </div>
    </div>
    <div class="modepill">SOLO SEÑALES</div>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Motor corregido · candidato")

    st.write(
        "Analogías con resultados oficiales de rondas anteriores. "
        "Umbral fijo del 65% y filtro conservador de evidencia."
    )

    st.write(
        "Confirma con tres velas de contexto distintas; "
        "refrescar los mismos datos no agrega una confirmación."
    )

    st.caption(
        "Prueba histórica: 2 señales acertadas, 0 fallidas "
        "y 8 sin señal en 10 rondas. No equivale a precisión "
        "futura ni a rentabilidad."
    )


def render_round_chart(points, target, end, now):
    start = end.timestamp() - 900

    current = [
        (timestamp, value)
        for timestamp, value in points
        if start <= timestamp <= min(end.timestamp(), now)
        and math.isfinite(value)
        and value > 0
    ]

    if not current:
        st.info("Esperando puntos de precio de la ronda actual.")
        return

    rows = []

    for timestamp, value in current:
        stamp = pd.Timestamp(
            timestamp, unit="s", tz="UTC"
        ).isoformat()

        rows.append({
            "time": stamp,
            "price": value,
            "series": "Índice Kalshi",
        })

        if target is not None:
            rows.append({
                "time": stamp,
                "price": target,
                "series": "Target",
            })

    values = [value for _, value in current]

    if target is not None:
        values.append(target)

    low = min(values)
    high = max(values)
    padding = max((high - low) * 0.15, 1)

    chart = pd.DataFrame(rows)

    spec = {
        "height": 300,
        "background": "#0a101b",
        "mark": {
            "type": "line",
            "strokeWidth": 2.5,
        },
        "encoding": {
            "x": {
                "field": "time",
                "type": "temporal",
                "title": None,
                "axis": {
                    "format": "%H:%M",
                    "tickCount": 5,
                },
            },
            "y": {
                "field": "price",
                "type": "quantitative",
                "title": None,
                "scale": {
                    "zero": False,
                    "domain": [
                        low - padding,
                        high + padding,
                    ],
                },
                "axis": {
                    "format": "$,.2f",
                    "tickCount": 5,
                },
            },
            "color": {
                "field": "series",
                "type": "nominal",
                "scale": {
                    "domain": ["Índice Kalshi", "Target"],
                    "range": ["#69d9bf", "#91a2c4"],
                },
                "legend": {
                    "title": None,
                    "orient": "bottom",
                },
            },
            "strokeDash": {
                "field": "series",
                "type": "nominal",
                "scale": {
                    "domain": ["Índice Kalshi", "Target"],
                    "range": [[1, 0], [7, 5]],
                },
                "legend": None,
            },
            "tooltip": [
                {
                    "field": "time",
                    "type": "temporal",
                    "title": "Hora",
                    "format": "%H:%M:%S",
                },
                {
                    "field": "series",
                    "type": "nominal",
                    "title": "Serie",
                },
                {
                    "field": "price",
                    "type": "quantitative",
                    "title": "Precio",
                    "format": "$,.2f",
                },
            ],
        },
        "config": {
            "view": {"stroke": None},
            "axis": {
                "labelColor": "#9aabc3",
                "titleColor": "#9aabc3",
                "gridColor": "#243044",
                "domainColor": "#243044",
                "tickColor": "#243044",
            },
            "legend": {
                "labelColor": "#a8b9d1",
                "titleColor": "#a8b9d1",
            },
        },
    }

    st.vega_lite_chart(
        chart,
        spec,
        use_container_width=True,
    )


def render_signal(direction, model, item, reason=None):
    label = {
        "UP": "ALCISTA",
        "DOWN": "BAJISTA",
        "SIN VENTAJA": "EN ESPERA",
        "CIERRE": "CIERRE",
    }[direction]

    ink = (
        "#69d9bf" if direction == "UP"
        else "#f5a68a" if direction == "DOWN"
        else "#b1bce8"
    )

    up = model.get("up") if model else None
    evidence = ""

    if up is not None:
        percent = up * 100

        evidence = f"""
<div class="balance">
    <div class="balancehead">
        <span>DISTRIBUCIÓN DE ANALOGÍAS</span>
        <span>{model['n']} CASOS</span>
    </div>
    <div class="balancebar">
        <div style="
            width:{percent}%;
            background:#69d9bf">
        </div>
        <div style="flex:1;background:#f5a68a"></div>
    </div>
    <div class="balancelabels">
        <span style="color:#69d9bf">{percent:.0f}% UP</span>
        <span style="color:#f5a68a">{100-percent:.0f}% DOWN</span>
    </div>
</div>
<div class="contextnote">
    Frecuencia histórica ponderada; no es precisión validada.
</div>
"""

    description = reason or (
        "Contexto actual comparado con rondas anteriores. "
        "La primera señal se conserva durante la sesión."
    )

    return f"""
<div class="signalstage" style="--signal:{ink}">
    <div>
        <div class="eyebrow">Perspectiva del mercado</div>
        <div class="signalword">{label}</div>
        <div class="signaldesc">{description}</div>
        <div class="signalmark">
            RONDAS OFICIALES · CANDIDATO
        </div>
    </div>
    <div>{evidence}</div>
</div>
"""


@st.fragment(run_every="10s")
def dashboard():
    current_market = None
    points = []
    price = None
    index_error = None
    model = None

    try:
        current_market = market()

        if not current_market:
            st.info("No hay ronda abierta disponible.")
            return

        end = pd.Timestamp(current_market["close_time"])
        now = datetime.now(timezone.utc).timestamp()
        seconds = max(0, int(end.timestamp() - now))

        target = (
            float(current_market["floor_strike"])
            if current_market.get("floor_strike") is not None
            else None
        )

        state = st.session_state.setdefault("lab_rounds", {})

        item = state.setdefault(
            current_market["ticker"],
            {
                "first": None,
                "time": None,
                "confirmation": Confirmation(),
            },
        )

        age = None
        is_historical = False

        try:
            points, is_historical = index_data(
                current_market["event_ticker"]
            )
            timestamp, price = points[-1]
            age = now - timestamp

        except (
            requests.RequestException,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as error:
            index_error = str(error)

        signal_box = st.empty()

        signal_box.markdown(
            render_signal(
                "SIN VENTAJA",
                None,
                item,
                "Preparando datos para evaluar esta ronda.",
            ),
            unsafe_allow_html=True,
        )

        price_text = (
            f"${price:,.2f}"
            if price is not None
            else "Sin datos"
        )

        target_text = (
            f"${target:,.2f}"
            if target is not None
            else "Pendiente"
        )

        difference = (
            f"{price-target:+,.2f} USD frente al target"
            if price is not None and target is not None
            else "Esperando precio o target"
        )

        age_text = (
            f"Índice actualizado hace {max(0,age):.0f} s"
            if age is not None
            else "Índice no disponible"
        )

        st.markdown(
            f"""
<div class="contextstrip">
    <div>
        <div class="eyebrow">Índice Kalshi</div>
        <div class="contextvalue">{price_text}</div>
        <div class="contextnote">{difference}</div>
    </div>
    <div>
        <div class="eyebrow">Target oficial</div>
        <div class="contextvalue">{target_text}</div>
        <div class="contextnote">Referencia de esta ronda</div>
    </div>
    <div>
        <div class="eyebrow">Tiempo restante</div>
        <div class="contextvalue">
            {seconds//60:02d}:{seconds%60:02d}
        </div>
        <div class="contextnote">{age_text}</div>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

        miami_now = datetime.now(
            ZoneInfo("America/New_York")
        ).strftime("%I:%M:%S %p")

        miami_close = end.tz_convert(
            "America/New_York"
        ).strftime("%I:%M %p")

        st.markdown(
            f"""
<div class="sessionline" style="
    margin-top:0;
    border-top:0;
    padding-top:0;
    margin-bottom:20px">
    <span>MIAMI · {miami_now}</span>
    <span>CIERRE · {miami_close}</span>
    <span>{current_market['ticker']}</span>
</div>
""",
            unsafe_allow_html=True,
        )

        if points:
            st.markdown(
                '<div class="eyebrow">'
                "Trayectoria publicada por Kalshi"
                "</div>",
                unsafe_allow_html=True,
            )
            render_round_chart(points, target, end, now)
        else:
            st.info(
                "Esperando la serie de Kalshi para mostrar el gráfico."
            )

        footer = st.empty()

        footer.markdown(
            f"""
<div class="sessionline">
    <span>
        PRIMERA SEÑAL · {item['first'] or 'SIN CONFIRMAR'}
    </span>
    <span>
        CONFIRMACIÓN · {item['confirmation'].count}/3
    </span>
</div>
""",
            unsafe_allow_html=True,
        )

        def blocked(message, detail=None):
            signal_box.markdown(
                render_signal(
                    "SIN VENTAJA",
                    None,
                    item,
                    "Señales en pausa hasta recibir datos válidos. "
                    "El panel sigue disponible.",
                ),
                unsafe_allow_html=True,
            )

            item["confirmation"].direction = None
            item["confirmation"].count = 0

            footer.markdown(
                f"""
<div class="sessionline">
    <span>
        PRIMERA SEÑAL · {item['first'] or 'SIN CONFIRMAR'}
    </span>
    <span>CONFIRMACIÓN · 0/3</span>
</div>
""",
                unsafe_allow_html=True,
            )

            st.warning(message)

            if detail:
                with st.expander("Detalle de datos"):
                    st.write(detail)

        if target is None or target <= 0:
            blocked("Esperando el target oficial de esta ronda.")
            return

        if (
            index_error
            or is_historical
            or age is None
            or age > 15
            or age < -5
        ):
            blocked(
                "El índice de Kalshi no está actualizado; "
                "las señales están en pausa.",
                index_error,
            )
            return

        with st.spinner("Cargando contexto y rondas oficiales…"):
            hist = history()
            live = recent()

        if live.empty:
            blocked("Coinbase no entregó velas terminadas.")
            return

        now_after = datetime.now(timezone.utc).timestamp()

        candle_end = (
            live.time.iloc[-1] + pd.Timedelta(minutes=1)
        ).timestamp()

        candle_age = now_after - candle_end

        if candle_age > 120 or candle_age < -5:
            last_time = pd.Timestamp(
                candle_end, unit="s", tz="UTC"
            ).tz_convert(
                "America/New_York"
            ).strftime("%I:%M:%S %p")

            blocked(
                "Las velas de Coinbase están atrasadas; "
                "el panel permanece visible.",
                f"Última vela terminada: {last_time} · "
                f"atraso {max(0,candle_age):.0f} segundos.",
            )
            return

        with st.spinner(
            "Comparando con rondas oficiales anteriores…"
        ):
            labelled = labelled_history()

        updated_points, updated_historical = index_data(
            current_market["event_ticker"]
        )

        decision_now = datetime.now(timezone.utc).timestamp()
        updated_timestamp, updated_price = updated_points[-1]
        seconds = max(0, int(end.timestamp() - decision_now))

        if (
            updated_historical
            or seconds == 0
            or decision_now - updated_timestamp > 15
            or decision_now - updated_timestamp < -5
        ):
            blocked(
                "La ronda cerró o el índice quedó atrasado "
                "durante la carga."
            )
            return

        if decision_now - candle_end > 120:
            blocked(
                "Actualizando velas después de la carga inicial."
            )
            return

        model = round_model(
            hist,
            live,
            updated_price,
            target,
            seconds,
            current_market["close_time"],
            labelled,
        )

        if "up" not in model:
            blocked(model["reason"])
            return

        candidate = model["direction"]
        minute = live.time.iloc[-1].isoformat()

        first = item["confirmation"].update(
            candidate,
            minute,
            datetime.now(timezone.utc).isoformat(),
            seconds,
        )

        if first and item["first"] is None:
            item.update(
                first=first["direction"],
                time=first["time_utc"],
            )

        suggested = (
            candidate
            if candidate and item["confirmation"].count >= 3
            else "SIN VENTAJA"
        )

        if seconds <= 60:
            suggested = "CIERRE"

        signal_box.markdown(
            render_signal(suggested, model, item),
            unsafe_allow_html=True,
        )

        footer.markdown(
            f"""
<div class="scenario">
    <div>
        RONDAS DISPONIBLES
        <b>{model['available']}</b>
    </div>
    <div>
        CASOS EFECTIVOS
        <b>{model['effective']:.0f}</b>
    </div>
    <div>
        CONFIRMACIÓN
        <b>{item['confirmation'].count}/3</b>
    </div>
</div>
<div class="sessionline">
    <span>
        PRIMERA SEÑAL · {item['first'] or 'SIN CONFIRMAR'}
    </span>
    <span>REFRESCO · 10 SEGUNDOS</span>
</div>
""",
            unsafe_allow_html=True,
        )

        with st.expander("Qué está midiendo"):
            st.json({
                "evidencia": model,
                "edad_indice_segundos": round(
                    decision_now - updated_timestamp, 1
                ),
                "historico_velas": len(hist),
                "primera_senal_hora": item["time"],
            })

            st.write(
                "Solo señales. Primera señal conservada "
                "durante la sesión. Los porcentajes "
                "no son precisión validada."
            )

    except (
        requests.RequestException,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
    ) as error:
        if "signal_box" in locals():
            signal_box.markdown(
                render_signal(
                    "SIN VENTAJA",
                    None,
                    item,
                    "Señales en pausa por un problema con los datos.",
                ),
                unsafe_allow_html=True,
            )

        st.warning(
            "No se pudo completar la lectura. "
            "Se reintentará en el próximo refresco."
        )

        with st.expander("Detalle del error"):
            st.write(str(error))


dashboard()
