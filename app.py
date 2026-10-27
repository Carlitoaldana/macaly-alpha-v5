import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="ALPHA EDGE · Maqueta",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    header, footer {
        display: none !important;
    }
    .stApp {
        background: #080e22;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

HTML = r"""
<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alpha Edge · Maqueta visual</title>

<style>
:root {
    --gold: #efc864;
    --text: #edf3ff;
    --muted: #a6b8df;
    --line: #687aa8;
    --green: #45edbe;
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: radial-gradient(
        ellipse at 45% 5%,
        #243e83 0,
        #101b3e 38%,
        #070c1c 100%
    );
    color: var(--text);
    font: 13px Arial, sans-serif;
}

button, input, select {
    font: inherit;
}

button {
    cursor: pointer;
    color: var(--text);
    border: 1px solid #7790c8;
    background: linear-gradient(#294c94, #142958);
    border-radius: 5px;
    padding: 10px 14px;
}

button:hover {
    filter: brightness(1.2);
}

button:focus-visible,
input:focus-visible,
select:focus-visible {
    outline: 2px solid var(--gold);
    outline-offset: 2px;
}

.app {
    max-width: 1600px;
    margin: auto;
    display: grid;
    grid-template-columns: 190px minmax(0, 1fr);
    min-height: 100vh;
    padding: 12px;
    gap: 14px;
}

.sidebar {
    border: 1px solid #6176a6;
    background: linear-gradient(135deg, #142753, #080e23);
    padding: 18px 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-shadow: inset 0 0 20px #263d6f;
}

.brand {
    text-align: center;
    color: var(--gold);
    font-size: 23px;
    font-weight: 900;
    letter-spacing: 1px;
}

.brand small {
    display: block;
    color: var(--muted);
    font-size: 9px;
    letter-spacing: 3px;
    margin-top: 5px;
}

.tag {
    display: inline-block;
    font-size: 10px;
    color: var(--green);
    border: 1px solid #2a9e87;
    padding: 5px 8px;
    border-radius: 3px;
}

.side-state {
    display: flex;
    justify-content: space-between;
    margin: 18px 0 10px;
    font-size: 10px;
}

.nav {
    display: flex;
    flex-direction: column;
    gap: 7px;
}

.nav button {
    text-align: left;
    text-transform: uppercase;
    font-weight: 700;
    font-size: 11px;
    padding: 12px 10px;
}

.nav button.active {
    color: var(--gold);
    border-color: var(--gold);
    background: linear-gradient(100deg, #5a492a, #1e2540);
}

.nav button span {
    color: #90a9da;
    display: inline-block;
    width: 24px;
}

.mini-radar {
    width: 110px;
    height: 110px;
    border: 2px solid var(--gold);
    border-radius: 50%;
    margin: 30px auto 10px;
    display: grid;
    place-content: center;
    background: repeating-radial-gradient(
        circle,
        #15295a 0 20px,
        #476899 21px 22px
    );
    box-shadow: 0 0 30px #183a7e;
}

.mini-radar strong {
    color: var(--gold);
    font-size: 25px;
    text-align: center;
}

.mini-radar small {
    text-align: center;
    font-size: 9px;
}

.sidebar footer {
    margin-top: auto;
    border-top: 1px solid #354975;
    padding-top: 18px;
    color: var(--muted);
    font-size: 10px;
    line-height: 1.8;
}

.topbar {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    border: 1px solid var(--gold);
    background: linear-gradient(100deg, #234483, #131e3d);
    padding: 13px 18px;
    gap: 14px;
    border-radius: 5px;
    box-shadow: 0 4px 15px #020612;
}

.topbar small, .label {
    font-size: 9px;
    letter-spacing: 1px;
    color: var(--muted);
    display: block;
    margin-bottom: 6px;
}

.topbar strong {
    font-size: 12px;
}

.demo {
    margin: 12px 0;
    color: #f9db8e;
    background: #45391f80;
    border: 1px solid #8d7741;
    padding: 9px 13px;
    border-radius: 4px;
    font-size: 11px;
}

.section-title {
    background: linear-gradient(100deg, #254c9b, #131d3d);
    padding: 12px 15px;
    border: 1px solid #788bc0;
    margin: 14px 0 12px;
    border-radius: 5px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.section-title b {
    color: var(--gold);
    margin-right: 15px;
}

.panel {
    border: 1px solid var(--line);
    border-left: 3px solid var(--gold);
    background: linear-gradient(145deg, #1a3472aa, #0b132c 70%);
    border-radius: 8px;
    box-shadow: inset 0 0 24px #112452, 0 4px 12px #0005;
    overflow: hidden;
}

.panel h2 {
    margin: 0;
    padding: 12px 16px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--gold);
    border-bottom: 1px solid #3b5487;
}

.body {
    padding: 17px;
}

.summary {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 240px;
    gap: 12px;
}

.radar-panel {
    text-align: center;
    position: relative;
}

.radar-sub {
    font-size: 10px;
    color: var(--muted);
    margin: 10px;
}

.radar {
    position: relative;
    margin: 25px auto;
    width: min(340px, 76%);
    aspect-ratio: 1;
    border-radius: 50%;
    border: 2px solid var(--gold);
    background:
        repeating-radial-gradient(
            circle,
            transparent 0 17%,
            #6985b3 17.4% 17.8%,
            transparent 18.2% 23%
        ),
        conic-gradient(from 275deg, #1ca4bd77, transparent 60deg),
        radial-gradient(circle, #18316b, #08172e);
    box-shadow:
        0 0 0 6px #09142b,
        0 0 0 7px #5b78ab,
        0 0 30px #0e6abc66;
}

.radar:before, .radar:after {
    content: '';
    position: absolute;
    background: #708bb565;
}

.radar:before {
    width: 1px;
    height: 100%;
    left: 50%;
}

.radar:after {
    height: 1px;
    width: 100%;
    top: 50%;
    left: 0;
}

.sweep {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: conic-gradient(
        from 0deg,
        transparent 290deg,
        #34d7cd22 330deg,
        #9fffea99 359deg,
        transparent 360deg
    );
    animation: sweep 12s linear infinite;
}

.radar.paused .sweep {
    animation-play-state: paused;
}

@keyframes sweep {
    to {
        transform: rotate(360deg);
    }
}

.radar-core {
    position: absolute;
    inset: 35%;
    border: 1px solid var(--gold);
    border-radius: 50%;
    background: radial-gradient(#1a335c, #080d1e);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 2;
    box-shadow: 0 0 25px #071327;
}

.radar-core b {
    font-size: clamp(14px, 2.3vw, 25px);
    color: var(--gold);
    letter-spacing: 1px;
}

.radar-core small {
    font-size: 9px;
    letter-spacing: 2px;
}

.rnum {
    position: absolute;
    color: #dbe5ff;
    font-size: 10px;
    z-index: 3;
}

.n { top: 8px; left: 48%; }
.s { bottom: 8px; left: 48%; }
.e { right: 8px; top: 48%; }
.w { left: 8px; top: 48%; }

.radar-meta {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    padding: 0 16px 15px;
}

.chip {
    border: 1px solid #6889bf;
    padding: 8px 12px;
    background: #102b55;
    font-size: 10px;
    border-radius: 3px;
}

.chip b {
    display: block;
    margin-top: 5px;
    color: var(--green);
}

.position {
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 340px;
}

.position .amount {
    font-size: 42px;
    font-weight: bold;
    margin: 30px 0 4px;
}

.muted { color: var(--muted); }
.gold { color: var(--gold); }
.green { color: var(--green); }

.position hr {
    border: 0;
    border-top: 1px solid #354d79;
    width: 80%;
    margin: 22px auto;
}

.position strong {
    font-size: 12px;
}

.performance {
    margin-top: 12px;
}

.metrics {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
}

.metrics strong {
    font-size: 24px;
}

.controls {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    margin: 13px 0;
}

.controls button {
    padding: 14px;
    font-weight: bold;
}

.danger {
    background: linear-gradient(#c34a55, #78212b);
    border-color: #fc8490;
}

.primary {
    background: linear-gradient(#ddbc6a, #8a682a);
    color: #101a30;
    border-color: #ffe29a;
}

.settings-grid {
    display: grid;
    grid-template-columns: 1.15fr 1fr;
    gap: 12px;
}

.field {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: center;
    padding: 11px 0;
    border-bottom: 1px solid #314369;
}

.field label {
    font-size: 11px;
    color: #e2eaff;
}

.field small {
    display: block;
    color: var(--muted);
    font-size: 10px;
    margin-top: 4px;
}

input[type=number],
input[type=text],
input[type=password],
select {
    width: 110px;
    background: #090f23;
    border: 1px solid #a58d52;
    color: #fff;
    padding: 9px;
    border-radius: 4px;
}

input[type=checkbox] {
    accent-color: #43e7b3;
    width: 19px;
    height: 19px;
}

.wide {
    width: 100% !important;
}

.save {
    width: 100%;
    margin-top: 15px;
}

.table-wrap {
    overflow-x: auto;
}

table {
    border-collapse: collapse;
    width: 100%;
    font-size: 11px;
    white-space: nowrap;
}

th, td {
    text-align: left;
    padding: 14px 12px;
    border-bottom: 1px solid #2c4068;
}

th {
    color: var(--muted);
    font-size: 9px;
    text-transform: uppercase;
}

.empty {
    text-align: center;
    color: var(--muted);
    padding: 50px 20px;
}

.hidden {
    display: none !important;
}

.notice {
    padding: 16px;
    border: 1px solid #4a638d;
    margin-top: 12px;
    line-height: 1.6;
    color: var(--muted);
    font-size: 11px;
    border-radius: 5px;
}

.toast {
    position: fixed;
    right: 20px;
    bottom: 20px;
    background: #163f3b;
    color: #b9ffe6;
    border: 1px solid #4ce4b6;
    padding: 15px 25px;
    border-radius: 6px;
    z-index: 10;
    box-shadow: 0 6px 30px #0008;
}

.strength {
    height: 8px;
    border-radius: 5px;
    background: #0b1630;
    margin: 15px 0;
    overflow: hidden;
}

.strength i {
    display: block;
    height: 100%;
    width: 0;
    background: var(--gold);
}

.top-controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

@media(max-width: 850px) {
    .app {
        grid-template-columns: 145px minmax(0, 1fr);
        gap: 9px;
        padding: 8px;
    }

    .brand { font-size: 18px; }
    .summary { grid-template-columns: 1fr 180px; }
    .position .amount { font-size: 30px; }
    .settings-grid { grid-template-columns: 1fr; }
    .metrics { grid-template-columns: repeat(2, 1fr); }
}

@media(max-width: 600px) {
    .app {
        display: block;
        padding: 8px;
    }

    .sidebar {
        padding: 10px;
        margin-bottom: 10px;
    }

    .brand { font-size: 19px; }

    .side-state,
    .mini-radar,
    .sidebar footer {
        display: none;
    }

    .nav {
        flex-direction: row;
        overflow-x: auto;
        margin-top: 12px;
        gap: 6px;
    }

    .nav button {
        flex-shrink: 0;
        padding: 10px;
        font-size: 10px;
    }

    .nav button span { width: 18px; }

    .topbar {
        grid-template-columns: 1fr 1fr;
        padding: 12px;
        gap: 15px;
    }

    .summary { grid-template-columns: 1fr; }
    .position { min-height: 190px; }
    .position .amount { margin-top: 18px; }
    .position hr { margin: 14px auto; }

    .radar {
        width: 240px;
        max-width: 78%;
        margin: 22px auto;
    }

    .controls { gap: 6px; }
    .controls button { font-size: 10px; padding: 13px 5px; }
    .metrics strong { font-size: 22px; }
    .radar-meta { padding: 0 10px 14px; }
    .chip { padding: 8px; font-size: 9px; }
}

@media(prefers-reduced-motion: reduce) {
    .sweep { animation: none; }
}
</style>
</head>

<body>
<div class="app">

<aside class="sidebar">
    <div class="brand">
        ALPHA EDGE
        <small>PRECISIÓN · CONTROL</small>
    </div>

    <div class="side-state">
        <span class="muted">ESTADO</span>
        <span class="tag" id="sideStatus">PAUSADO</span>
    </div>

    <nav class="nav">
        <button class="active" data-page="resumen">
            <span>◈</span>Resumen
        </button>
        <button data-page="operacion">
            <span>⚙</span>Operación
        </button>
        <button data-page="entradas">
            <span>↗</span>Entradas
        </button>
        <button data-page="registro">
            <span>▤</span>Registro
        </button>
        <button data-page="senal">
            <span>◎</span>Señal
        </button>
        <button data-page="conexion">
            <span>⌁</span>Conexión
        </button>
    </nav>

    <div class="mini-radar">
        <strong>0%</strong>
        <small>OBJETIVO DIARIO</small>
    </div>

    <footer>
        <span class="gold">ENTORNO DE DISEÑO</span><br>
        BTC · Rondas de 15 minutos<br>
        Cuenta de prueba individual<br>
        <span class="green">● Sin conexión al mercado</span>
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
            <strong>VISTA DE DEMOSTRACIÓN</strong>
        </div>
        <div>
            <small>MODO</small>
            <strong class="green">● MAQUETA VISUAL</strong>
        </div>
    </header>

    <div class="demo">
        MAQUETA INTERACTIVA · Los valores son ilustrativos.
        No recibe precios ni envía órdenes.
    </div>

    <div class="section-title">
        <b id="pageNum">01</b>
        <span id="pageTitle">Resumen</span>
    </div>

    <section id="resumen" class="page">
        <div class="summary">
            <article class="panel radar-panel">
                <h2>Radar de sesión</h2>
                <p class="radar-sub">
                    Lectura de mercado · Confirmación · Ejecución
                </p>

                <div class="top-controls body"
                     style="padding-top:0;padding-bottom:0">
                    <span class="chip">
                        MERCADO
                        <span class="gold"> · SIN DATOS</span>
                    </span>
                    <span class="chip">
                        LÍMITE DE ENTRADA
                        <b id="entryLimit">60 ¢</b>
                    </span>
                </div>

                <div class="radar paused" id="radar">
                    <div class="sweep"></div>
                    <span class="rnum n">00</span>
                    <span class="rnum e">15</span>
                    <span class="rnum s">30</span>
                    <span class="rnum w">45</span>

                    <div class="radar-core">
                        <b>ALPHA</b>
                        <small>EDGE</small>
                    </div>
                </div>

                <div class="radar-meta">
                    <span class="chip">
                        DIRECCIÓN
                        <b>ESPERANDO</b>
                    </span>
                    <span class="chip">
                        PRIMERA SEÑAL
                        <b>—</b>
                    </span>
                    <span class="chip">
                        RONDA
                        <b>— / 15:00</b>
                    </span>
                </div>
            </article>

            <article class="panel">
                <h2>Posición</h2>
                <div class="position">
                    <span class="label">GANANCIA NO REALIZADA</span>
                    <div class="amount">
                        $0<span style="font-size:22px">.00</span>
                    </div>
                    <span class="muted">Sin operaciones</span>
                    <hr>
                    <span class="label">CONTRATOS ABIERTOS</span>
                    <strong>0 CONTRATOS</strong>
                    <hr>
                    <strong class="gold">SIN POSICIÓN</strong>
                </div>
            </article>
        </div>

        <article class="panel performance">
            <h2>Performance</h2>
            <div class="body metrics">
                <div>
                    <span class="label">RESULTADO DEL DÍA</span>
                    <strong>$0.00</strong>
                </div>
                <div>
                    <span class="label">GANANCIA REALIZADA</span>
                    <strong>$0.00</strong>
                </div>
                <div>
                    <span class="label">META DIARIA</span>
                    <strong class="gold" id="goalDisplay">$50</strong>
                </div>
                <div>
                    <span class="label">PROGRESO DE LA META</span>
                    <div class="strength"><i></i></div>
                    <small class="muted">0% · Sin operaciones</small>
                </div>
            </div>
        </article>

        <div class="controls">
            <button class="primary" id="start">▶ INICIAR DEMO</button>
            <button id="pause">Ⅱ PAUSAR</button>
            <button class="danger" id="close">□ CERRAR TODO</button>
        </div>

        <div class="notice">
            El radar muestra el diseño y una animación de demostración.
            La dirección, las operaciones y las métricas permanecerán
            sin datos hasta conectar el motor en otra etapa.
        </div>
    </section>

    <section id="operacion" class="page hidden">
        <article class="panel" style="margin-bottom:12px">
            <h2>Plan de operación</h2>
            <div class="body">
                <div class="top-controls">
                    <span>BTC · 15 minutos</span>
                    <span class="gold">CONFIGURACIÓN DE PRUEBA</span>
                </div>
                <div class="strength">
                    <i style="width:100%"></i>
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
                            <label>
                                Saldo de simulación
                                <small>Capital inicial ilustrativo</small>
                            </label>
                            <input type="number" name="balance"
                                   value="1000" min="1"
                                   max="1000000" required>
                        </div>

                        <div class="field">
                            <label>Meta diaria ($)</label>
                            <input type="number" name="goal"
                                   value="50" min="0" required>
                        </div>

                        <div class="field">
                            <label>Límite de pérdida diaria ($)</label>
                            <input type="number" name="loss"
                                   value="25" min="1" required>
                        </div>

                        <div class="field">
                            <label>Contratos por entrada</label>
                            <input type="number" name="contracts"
                                   value="1" min="1"
                                   max="1000" required>
                        </div>

                        <div class="field">
                            <label>Máximo por operación ($)</label>
                            <input type="number" name="maxTrade"
                                   value="10" min="1" required>
                        </div>

                        <div class="field">
                            <label>Máximo de entradas por ronda</label>
                            <input type="number" name="entries"
                                   value="1" min="1"
                                   max="100" required>
                        </div>
                    </div>
                </article>

                <article class="panel">
                    <h2>Precios y protección</h2>
                    <div class="body">
                        <div class="field">
                            <label>Precio mínimo de compra (¢)</label>
                            <input type="number" name="minEntry"
                                   value="10" min="1"
                                   max="99" required>
                        </div>

                        <div class="field">
                            <label>Precio máximo de compra (¢)</label>
                            <input type="number" name="maxEntry"
                                   value="60" min="1"
                                   max="99" required>
                        </div>

                        <div class="field">
                            <label>
                                Take profit (¢)
                                <small>
                                    Subida desde la entrada;
                                    0 desactiva
                                </small>
                            </label>
                            <input type="number" name="tp"
                                   value="12" min="0"
                                   max="98" required>
                        </div>

                        <div class="field">
                            <label>
                                Stop loss (¢)
                                <small>
                                    Caída desde la entrada;
                                    0 desactiva
                                </small>
                            </label>
                            <input type="number" name="sl"
                                   value="10" min="0"
                                   max="98" required>
                        </div>

                        <div class="field">
                            <label>Salida antes del cierre (seg.)</label>
                            <input type="number" name="exitTime"
                                   value="20" min="0"
                                   max="300" required>
                        </div>

                        <div class="field">
                            <label>
                                Cerrar por señal contraria
                                <small>
                                    Ajuste de salida;
                                    no fija la dirección del cerebro
                                </small>
                            </label>
                            <input type="checkbox"
                                   name="reverse" checked>
                        </div>

                        <div class="field">
                            <label>
                                Comisión estimada
                                por contrato (¢)
                            </label>
                            <input type="number" name="fee"
                                   value="2" min="0"
                                   max="20" required>
                        </div>
                    </div>
                </article>
            </div>

            <button type="submit" class="primary save">
                APLICAR AJUSTES DE LA MAQUETA
            </button>
        </form>

        <div class="notice">
            Los ajustes se guardan solo en este navegador.
            No se aplican al bot ni a una cuenta de Kalshi.
        </div>
    </section>

    <section id="entradas" class="page hidden">
        <article class="panel">
            <h2>Entradas de la sesión</h2>
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
                    </thead>
                </table>
            </div>
            <div class="empty">
                Sin entradas. Esta maqueta no ejecuta operaciones.
            </div>
        </article>
    </section>

    <section id="registro" class="page hidden">
        <article class="panel">
            <h2>Registro de interacción visual</h2>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Hora local</th>
                            <th>Acción</th>
                            <th>Detalle</th>
                        </tr>
                    </thead>
                    <tbody id="logs"></tbody>
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
                        <div class="gold"
                             style="font-size:28px;margin-bottom:15px">
                            ESPERANDO CONEXIÓN
                        </div>
                        El motor no está conectado
                        en esta etapa visual.
                    </div>

                    <div class="field">
                        <label>Dirección actual</label>
                        <strong>—</strong>
                    </div>
                    <div class="field">
                        <label>Primera señal de la ronda</label>
                        <strong>—</strong>
                    </div>
                    <div class="field">
                        <label>Precio de BTC</label>
                        <strong>—</strong>
                    </div>
                    <div class="field">
                        <label>Objetivo de la ronda</label>
                        <strong>—</strong>
                    </div>
                </div>
            </article>

            <article class="panel">
                <h2>Indicadores</h2>
                <div class="body">
                    <div class="field">
                        EMA 9 / EMA 21 <strong>—</strong>
                    </div>
                    <div class="field">
                        RSI 14 <strong>—</strong>
                    </div>
                    <div class="field">
                        Momentum <strong>—</strong>
                    </div>
                    <div class="field">
                        Volumen relativo <strong>—</strong>
                    </div>
                    <div class="notice">
                        Espacios reservados para datos reales.
                        La maqueta no genera señales.
                    </div>
                </div>
            </article>
        </div>
    </section>

    <section id="conexion" class="page hidden">
        <article class="panel">
            <h2>Conexión Kalshi · Próxima etapa</h2>
            <div class="body">
                <p class="muted">
                    Vista previa del formulario.
                    No introduzcas credenciales reales.
                </p>

                <div class="field">
                    <label>Entorno</label>
                    <select>
                        <option>Simulación</option>
                    </select>
                </div>

                <div class="field">
                    <label>API Key ID</label>
                    <input class="wide"
                           style="max-width:360px"
                           type="text"
                           placeholder="Deshabilitado en maqueta"
                           disabled>
                </div>

                <div class="field">
                    <label>Clave privada</label>
                    <input class="wide"
                           style="max-width:360px"
                           type="password"
                           placeholder="Deshabilitado en maqueta"
                           disabled>
                </div>

                <div class="notice">
                    SIN CONEXIÓN · No hay solicitudes a Kalshi
                    ni almacenamiento de credenciales.
                </div>
            </div>
        </article>
    </section>
</main>
</div>

<div class="toast hidden" id="toast" role="status"></div>

<script>
const $ = selector => document.querySelector(selector);

const titles = {
    resumen: "Resumen",
    operacion: "Operación y ajustes",
    entradas: "Entradas",
    registro: "Registro",
    senal: "Señal",
    conexion: "Conexión"
};

let logs = [];

function log(action, detail) {
    logs.unshift({
        time: new Date().toLocaleTimeString("es"),
        action,
        detail
    });

    $("#logs").replaceChildren(
        ...logs.map(item => {
            const row = document.createElement("tr");

            [item.time, item.action, item.detail].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.append(cell);
            });

            return row;
        })
    );
}

function toast(message) {
    $("#toast").textContent = message;
    $("#toast").classList.remove("hidden");

    clearTimeout(window.toastTimer);

    window.toastTimer = setTimeout(() => {
        $("#toast").classList.add("hidden");
    }, 3500);
}

document.querySelectorAll("[data-page]").forEach((button, index) => {
    button.onclick = () => {
        document.querySelectorAll(".page").forEach(page => {
            page.classList.add("hidden");
        });

        $("#" + button.dataset.page).classList.remove("hidden");

        document.querySelectorAll("[data-page]").forEach(item => {
            item.classList.remove("active");
        });

        button.classList.add("active");

        $("#pageTitle").textContent = titles[button.dataset.page];
        $("#pageNum").textContent = String(index + 1).padStart(2, "0");
    };
});

function state(label, animate) {
    $("#status").textContent = label;
    $("#sideStatus").textContent = label;
    $("#radar").classList.toggle("paused", !animate);
}

$("#start").onclick = () => {
    state("DEMO VISUAL ACTIVA", true);
    toast("Animación iniciada · No se ejecutan compras");
    log("INICIAR DEMO", "Solo animación visual");
};

$("#pause").onclick = () => {
    state("PAUSADO", false);
    toast("Demostración pausada");
    log("PAUSAR", "Animación detenida");
};

$("#close").onclick = () => {
    state("PAUSADO", false);
    toast("Sin posiciones que cerrar · Maqueta visual");
    log("CERRAR TODO", "Sin operaciones ni conexión al mercado");
};

const form = $("#settings");

function update() {
    $("#entryLimit").textContent =
        form.elements.maxEntry.value + " ¢";

    $("#goalDisplay").textContent =
        "$" + form.elements.goal.value;
}

try {
    const saved = JSON.parse(
        localStorage.getItem("alphaVisualSettings") || "null"
    );

    if (saved) {
        Object.entries(saved).forEach(([key, value]) => {
            const element = form.elements[key];

            if (element) {
                if (element.type === "checkbox") {
                    element.checked = value;
                } else {
                    element.value = value;
                }
            }
        });
    }
} catch (error) {
    // El panel también funciona sin almacenamiento local.
}

update();

form.onsubmit = event => {
    event.preventDefault();

    if (
        Number(form.elements.minEntry.value) >
        Number(form.elements.maxEntry.value)
    ) {
        toast("El precio mínimo no puede superar al máximo");
        return;
    }

    const settings = {};

    Array.from(form.elements)
        .filter(element => element.name)
        .forEach(element => {
            settings[element.name] =
                element.type === "checkbox"
                    ? element.checked
                    : Number(element.value);
        });

    try {
        localStorage.setItem(
            "alphaVisualSettings",
            JSON.stringify(settings)
        );

        toast("Ajustes visuales guardados en este navegador");
    } catch (error) {
        toast("Ajustes aplicados solo a esta vista");
    }

    update();
    log("AJUSTES", "Configuración de la maqueta actualizada");
};

log("DISEÑO", "Maqueta cargada · Sin conexión al bot");
</script>
</body>
</html>
"""

components.html(HTML, height=1500, scrolling=True)
