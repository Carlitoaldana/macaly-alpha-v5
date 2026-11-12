# Panel informativo de niveles fijos. No altera candidaturas, confirma ni opera por este panel.
import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import sqlite3
import json
import threading
import time
import copy
import random
from email.utils import parsedate_to_datetime

# =========================================================
# MACALY + ALPHA BOT v4.6.1 • MOBILE PRO UI
# BTC 15 MIN • SAME v4.6.1 SIGNAL ENGINE
# =========================================================

st.set_page_config(
    page_title="BTC Signal v4.6.1",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =========================================================
# CONFIGURACIÓN ORIGINAL
# =========================================================

NEW_ROUND_WAIT = 8
NEW_ENTRY_LOCK = 75

# Dos lecturas coherentes, separadas por al menos 2 s (mínimo 2 s).
SIGNAL_CONFIRM_READINGS = 2
SIGNAL_CONFIRM_INTERVAL = 2.0
# Caducidad operativa: una pausa >10s reinicia las lecturas pendientes.
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


UP_THRESHOLD = 4.0
DOWN_THRESHOLD = -4.0

FLIP_UP_THRESHOLD = 4.75
FLIP_DOWN_THRESHOLD = -4.75
FLIP_CONFIRMATIONS = 2

# =========================================================
# DISEÑO MOBILE — BASADO EN LA REFERENCIA APROBADA
# =========================================================

st.markdown(
    """
<style>
#MainMenu, footer, header {visibility:hidden;}
[data-testid="stToolbar"] {display:none;}
[data-testid="stDecoration"] {display:none;}
[data-testid="stStatusWidget"] {display:none;}

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.stApp {
    background:
      radial-gradient(circle at 50% -12%, rgba(31,65,104,.24), transparent 30%),
      #070b11;
    color:#f4f7fb;
}

.block-container {
    max-width:410px !important;
    padding:8px 10px 24px !important;
}

div[data-testid="stVerticalBlock"] {gap:.55rem;}

.topbar {
    position:relative;
    min-height:45px;
    padding:3px 2px 4px;
    text-align:center;
}
.brand {
    color:#f8fafc;
    font-size:13px;
    line-height:1.05;
    font-weight:950;
    letter-spacing:.15px;
}
.version {
    color:#647184;
    font-size:7px;
    font-weight:800;
    margin-top:2px;
}
.live {
    position:absolute;
    right:3px;
    top:27px;
    display:flex;
    align-items:center;
    gap:5px;
    color:#91a0b3;
    font-size:7.5px;
    font-weight:800;
}
.live-dot {
    width:7px;
    height:7px;
    border-radius:50%;
    background:#00dfb5;
    box-shadow:0 0 10px rgba(46,230,123,.8);
}

.hero {
    text-align:center;
    padding:0 4px 8px;
}
.hero-signal {
    font-size:58px;
    line-height:.96;
    font-weight:1000;
    letter-spacing:-3px;
    text-shadow:0 0 28px var(--glow);
}
.hero-wait {
    font-size:31px;
    line-height:1.03;
    font-weight:1000;
    letter-spacing:-1.2px;
    color:#51bff3;
    text-shadow:0 0 22px rgba(56,189,248,.20);
}
.confidence {
    display:inline-block;
    margin-top:10px;
    padding:5px 12px;
    border-radius:7px;
    font-size:10px;
    font-weight:1000;
    letter-spacing:.4px;
    border:1px solid var(--accent);
    color:var(--accent);
    background:var(--soft);
}

.two {
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:8px;
    margin-top:7px;
}
.mini {
    min-height:61px;
    background:linear-gradient(180deg,#101722,#0c121b);
    border:1px solid #1b2735;
    border-radius:10px;
    padding:8px 9px;
}
.mini-label {
    color:#69778a;
    font-size:8px;
    font-weight:900;
    letter-spacing:.8px;
    text-transform:uppercase;
    margin-bottom:5px;
}
.mini-value {
    color:#f4f7fb;
    font-size:18px;
    font-weight:950;
    letter-spacing:-.4px;
}
.mini-sub {
    color:#7e8b9e;
    font-size:9px;
    font-weight:800;
    margin-top:3px;
}
.green {color:#00dfb5;}
.red {color:#ff5363;}
.blue {color:#54c6f5;}
.amber {color:#f7bd4d;}

.section {
    background:linear-gradient(180deg,#0f1620,#0b1119);
    border:1px solid #1b2735;
    border-radius:11px;
    padding:11px;
    margin-top:8px;
}
.section-title {
    color:#8b98aa;
    font-size:9px;
    font-weight:1000;
    letter-spacing:.8px;
    text-transform:uppercase;
    margin-bottom:8px;
}
.prob-row {
    display:flex;
    align-items:center;
    gap:7px;
}
.prob-up, .prob-down {
    height:12px;
    border-radius:4px;
    min-width:2px;
}
.prob-up {
    background:linear-gradient(90deg,#1bcf6a,#53ef8d);
    box-shadow:0 0 10px rgba(46,230,123,.18);
}
.prob-down {
    background:linear-gradient(90deg,#ff3d50,#ff6876);
    box-shadow:0 0 10px rgba(255,76,91,.18);
}
.prob-labels {
    display:flex;
    justify-content:space-between;
    margin-top:7px;
    font-size:10px;
    font-weight:900;
}

.close-reader {
    border-radius:11px;
    padding:12px;
    margin-top:8px;
    border:1px solid var(--reader-border);
    background:var(--reader-bg);
    box-shadow:inset 0 0 25px rgba(0,0,0,.10);
}
.reader-top {
    display:flex;
    justify-content:space-between;
    align-items:center;
    color:#e9eef5;
    font-size:9px;
    font-weight:1000;
    letter-spacing:.7px;
}
.reader-active {
    padding:3px 7px;
    border-radius:8px;
    color:#57ee91;
    border:1px solid rgba(69,231,129,.55);
    background:rgba(28,153,78,.15);
    font-size:8px;
}
.reader-main {
    display:grid;
    grid-template-columns:1fr 70px;
    align-items:center;
    gap:8px;
    margin-top:12px;
}
.reader-text {
    color:#f6f8fb;
    font-size:15px;
    line-height:1.15;
    font-weight:1000;
}
.reader-note {
    color:#8390a2;
    font-size:8px;
    line-height:1.35;
    margin-top:6px;
}
.ring {
    --p:50;
    --ring:#00dfb5;
    width:66px;
    height:66px;
    border-radius:50%;
    display:grid;
    place-items:center;
    background:conic-gradient(var(--ring) calc(var(--p)*1%), #27313e 0);
    position:relative;
}
.ring:after {
    content:"";
    position:absolute;
    width:51px;
    height:51px;
    border-radius:50%;
    background:#0b1119;
}
.ring span {
    position:relative;
    z-index:1;
    color:#f7fafc;
    font-size:15px;
    font-weight:1000;
}

.tech-grid {
    display:grid;
    grid-template-columns:repeat(5,1fr);
    gap:3px;
    text-align:center;
}
.tech-label {
    color:#637084;
    font-size:6.5px;
    font-weight:900;
    letter-spacing:.25px;
    text-transform:uppercase;
}
.tech-value {
    color:#eef3f9;
    font-size:10px;
    font-weight:1000;
    margin-top:5px;
    overflow:hidden;
    white-space:nowrap;
}

.ticker {
    text-align:center;
    color:#4f5c6f;
    font-size:7.5px;
    font-weight:800;
    margin-top:8px;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}

.footer-nav {
    display:grid;
    grid-template-columns:repeat(4,1fr);
    text-align:center;
    padding:10px 2px 1px;
    margin-top:7px;
    border-top:1px solid #182331;
}
.nav-item {
    color:#5f6c7e;
    font-size:8px;
    font-weight:800;
}
.nav-active {color:var(--accent);}

.alert {
    border-radius:10px;
    padding:10px;
    margin-top:8px;
    text-align:center;
    color:#ffd260;
    background:rgba(116,78,7,.18);
    border:1px solid rgba(247,189,77,.42);
    font-size:10px;
    font-weight:900;
}

/* ===== REFERENCE UI OVERRIDES ===== */
.block-container{
    max-width:390px !important;
    padding:5px 9px 20px !important;
}
.topbar{
    min-height:39px !important;
    padding:2px 1px 3px !important;
}
.brand{font-size:12px !important;}
.version{font-size:6.5px !important;color:#536174 !important;}
.live{top:23px !important;font-size:6.8px !important;}

.hero{padding:0 2px 5px !important;}
.hero-signal{
    font-size:55px !important;
    line-height:.90 !important;
    letter-spacing:-4px !important;
}
.confidence{
    margin-top:8px !important;
    padding:4px 9px !important;
    border-radius:6px !important;
    font-size:8px !important;
}

.two{
    gap:6px !important;
    margin-top:6px !important;
}
.mini{
    min-height:57px !important;
    padding:7px 8px !important;
    border-radius:8px !important;
    background:#0d141d !important;
    border-color:#172230 !important;
}
.mini-label{font-size:6.8px !important;margin-bottom:3px !important;}
.mini-value{font-size:15px !important;line-height:1.05 !important;}
.mini-sub{font-size:6.8px !important;margin-top:2px !important;}

.section{
    padding:8px !important;
    margin-top:6px !important;
    border-radius:8px !important;
    background:#0c131c !important;
    border-color:#172230 !important;
}
.section-title{
    font-size:7px !important;
    margin-bottom:6px !important;
}
.prob-row{gap:5px !important;}
.prob-up,.prob-down{height:15px !important;border-radius:3px !important;}
.prob-labels{margin-top:5px !important;font-size:7.5px !important;}

.close-reader{
    padding:9px !important;
    margin-top:6px !important;
    border-radius:8px !important;
}
.reader-top{font-size:7px !important;}
.reader-active{font-size:6px !important;padding:2px 5px !important;}
.reader-main{
    grid-template-columns:1fr 58px !important;
    margin-top:7px !important;
}
.reader-text{font-size:11px !important;line-height:1.08 !important;}
.reader-note{font-size:6.5px !important;margin-top:4px !important;}
.ring{width:54px !important;height:54px !important;}
.ring:after{width:42px !important;height:42px !important;}
.ring span{font-size:12px !important;}

.tech-grid{gap:0 !important;}
.tech-grid > div{
    padding:0 4px !important;
    border-right:1px solid #1c2734;
}
.tech-grid > div:last-child{border-right:none;}
.tech-label{font-size:5.8px !important;}
.tech-value{font-size:8.5px !important;margin-top:3px !important;}

.ref-features{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:4px;
    padding:8px 2px 6px;
    margin-top:6px;
    border-top:1px solid #182331;
}
.ref-feature{
    display:grid;
    grid-template-columns:22px 1fr;
    gap:5px;
    align-items:center;
    color:#66758a;
    font-size:5.6px;
    line-height:1.22;
}
.ref-feature-icon{
    width:20px;height:20px;border-radius:50%;
    display:grid;place-items:center;
    border:1px solid #28dd79;
    color:#00dfb5;
    font-size:10px;font-weight:1000;
}
.ref-feature strong{
    display:block;color:#cfd7e1;
    font-size:5.8px;margin-bottom:1px;
}
.ref-footer{
    display:flex;
    justify-content:space-between;
    gap:8px;
    padding:5px 1px 1px;
    border-top:1px solid #131d29;
    color:#435064;
    font-size:5.2px;
    font-weight:800;
}
.footer-nav{
    padding:7px 2px 1px !important;
    margin-top:4px !important;
}
.nav-item{font-size:6.8px !important;}


/* FINAL REFERENCE MATCH */
.block-container{max-width:430px!important;padding:7px 10px 22px!important}
.topbar{min-height:48px!important;padding:4px 2px 5px!important;text-align:center!important}
.brand{font-size:15px!important}.version{font-size:8px!important}
.live{top:29px!important;right:4px!important;font-size:8px!important}
.hero{padding:2px 2px 7px!important}
.hero-signal{font-size:72px!important;line-height:.86!important;letter-spacing:-5px!important;text-shadow:0 0 12px currentColor,0 0 28px currentColor!important}
.confidence{font-size:10px!important;padding:5px 16px!important;border-radius:18px!important;margin-top:9px!important}
.two{gap:7px!important;margin-top:7px!important}
.mini{min-height:72px!important;padding:9px 10px!important;border-radius:9px!important}
.mini-label{font-size:8px!important}.mini-value{font-size:19px!important}.mini-sub{font-size:8px!important}
.section{padding:9px!important;margin-top:7px!important;border-radius:9px!important}
.section-title{font-size:8px!important;margin-bottom:6px!important}
.prob-up,.prob-down{height:20px!important}.prob-labels{font-size:9px!important}
.close-reader{padding:10px 11px!important;margin-top:7px!important;border-radius:10px!important}
.reader-top{font-size:9px!important}.reader-active{font-size:7px!important}
.reader-main{grid-template-columns:1fr 68px!important;margin-top:8px!important}
.reader-text{font-size:15px!important;line-height:1.08!important}.reader-note{font-size:7.5px!important}
.ring{width:64px!important;height:64px!important}.ring:after{width:50px!important;height:50px!important}.ring span{font-size:15px!important}
.tech-label{font-size:6.5px!important}.tech-value{font-size:10px!important}
.footer-nav{padding:9px 2px 7px!important}.nav-item{font-size:8px!important}
.ref-features{padding:9px 3px 7px!important}.ref-feature{font-size:6px!important}
.ref-feature strong{font-size:6.2px!important}.ref-footer{font-size:5.6px!important}
.ref-icon{font-size:23px;line-height:1;margin-right:8px;display:inline-block;vertical-align:middle}
.ref-btc{color:#ff9f0a}.ref-target{color:#a9c9f3}
.ref-bars{display:inline-flex;gap:2px;align-items:flex-end;height:19px;margin-right:8px;vertical-align:middle}
.ref-bars i{display:block;width:5px;background:var(--accent);border-radius:1px}
.ref-bars i:nth-child(1){height:7px}.ref-bars i:nth-child(2){height:12px}.ref-bars i:nth-child(3){height:18px}
.ref-clock{font-size:23px;color:#b9d5f5;margin-right:8px;vertical-align:middle}
.ref-timebar{height:5px;background:#16324a;border-radius:5px;margin-top:5px;overflow:hidden}
.ref-timebar b{display:block;height:100%;width:58%;background:var(--accent);border-radius:5px}
.tech-head{display:flex;justify-content:space-between;align-items:center}
.tech-chevron{font-size:13px;color:#b6c6da}


/* ===== REBUILT REFERENCE FRONTEND ===== */
.block-container{max-width:430px!important;padding:4px 9px 18px!important}
.refapp{font-family:Arial,sans-serif;color:#eaf2fb}
.rhead{height:54px;position:relative;text-align:center;padding-top:7px}
.rtitle{font-size:15px;font-weight:900}.rver{font-size:9px;color:#9badc3;margin-top:2px}
.gear{position:absolute;right:9px;top:7px;font-size:19px;color:#a9c9ec;text-decoration:none!important;cursor:pointer;z-index:50}
.rlive{position:absolute;right:8px;bottom:1px;font-size:9px;color:#b9c9db}
.rlive i{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--accent);margin-right:5px;box-shadow:0 0 12px var(--accent)}
.rhero{text-align:center;padding:4px 0 8px}
.rsignal{display:flex;align-items:center;justify-content:center;color:var(--accent);font-size:72px;font-weight:1000;line-height:.82;letter-spacing:-5px;text-shadow:0 0 12px var(--glow),0 0 25px var(--glow)}
.rarrow{font-size:79px;margin-right:5px;line-height:.7}.rhero.waiting .rsignal{font-size:39px;letter-spacing:-2px}.rhero.waiting .rarrow{display:none}
.rconf{display:inline-block;margin-top:11px;border:1.5px solid var(--accent);border-radius:18px;padding:5px 17px;color:#fff;font-size:10px;font-weight:900;box-shadow:0 0 10px var(--soft)}
.rgrid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:2px}
.rcard{background:linear-gradient(180deg,#0d1823,#09131c);border:1px solid #203348;border-radius:8px}

/* Acabado visual ALPHA EDGE: franjas dentro de todos los cuadros */
.rcard, .rgrid > div, .finalcard, .analysisbox, .probbox,
.finalclose, .finalanalysis, .weakness-inline, .prebox,
.rnav, .techrow > div, .motionrow > div {
 background-image:
 repeating-linear-gradient(128deg,transparent 0px,transparent 18px,rgba(255,232,173,.12) 19px,rgba(255,232,173,.045) 31px,transparent 40px,transparent 78px),
 linear-gradient(145deg,#0c1c27,#07151e) !important;
 background-blend-mode:screen,normal;
}
.rcard {border-color:rgba(228,190,120,.78)!important;box-shadow:inset 0 1px 0 rgba(255,227,170,.18),0 0 8px rgba(215,166,79,.14);}
.keycard .targeticon,.keycard .clock{width:37px;height:40px;flex:none;display:flex;align-items:center;justify-content:center;filter:drop-shadow(0 1px 3px rgba(249,190,68,.58));}
.keycard .targeticon svg,.keycard .clock svg{width:37px;height:37px;display:block;}

.keycard{height:68px;padding:8px 9px;display:flex;align-items:center;gap:8px}
.bigicon{font-size:31px;font-weight:900;line-height:1}.btcicon{color:#ff9d00}.targeticon{color:#8acfc3}
.rlabel{font-size:8px;color:#b9c9dc;letter-spacing:.4px}.rvalue{font-size:19px;font-weight:900;line-height:1.05;margin-top:2px}.rdelta{font-size:9px;font-weight:900;margin-top:2px}
.green{color:#00dfb5!important}.red{color:#e64b4b!important}
.bars{display:flex;align-items:flex-end;gap:3px;width:31px;height:30px}.bars b{width:7px;background:var(--accent);border-radius:2px}.bars b:nth-child(1){height:11px}.bars b:nth-child(2){height:20px}.bars b:nth-child(3){height:28px}
.clock{font-size:30px;color:#8acfc3}.timecontent{flex:1}.timebar{height:6px;background:#16324a;border-radius:5px;margin-top:5px;overflow:hidden}.timebar b{display:block;height:100%;background:var(--accent);border-radius:5px}
.probs{margin-top:6px;padding:8px}.pbar{display:flex;gap:4px;margin-top:5px}.pup,.pdown{height:21px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:900;border-radius:4px}.pup{background:linear-gradient(90deg,#10d76d,#54ed91);color:#06331d}.pdown{background:linear-gradient(90deg,#ff3548,#ff6472);color:#3d0710}.pleg{display:flex;justify-content:space-between;font-size:10px;font-weight:900;margin-top:6px}
.reader{margin-top:6px;border:1.5px solid var(--rb);background:var(--rbg);border-radius:9px;padding:9px 10px}
.readerhead{display:flex;align-items:center;gap:7px;font-size:9px;color:var(--rr)}.readerhead .pulse{font-size:18px}.readerhead em{margin-left:auto;border:1px solid #24d873;border-radius:12px;padding:3px 8px;font-style:normal;font-size:8px;color:#00dfb5}
.readerbody{display:grid;grid-template-columns:1fr 65px;align-items:center;margin-top:7px}.readerbody strong{display:block;font-size:15px;line-height:1.12}.readerbody small{display:block;color:#aab8c9;font-size:7px;margin-top:5px}
.rring{width:62px;height:62px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--rr) calc(var(--p)*1%),#263342 0);position:relative}.rring:after{content:"";position:absolute;width:48px;height:48px;background:#08121b;border-radius:50%}.rring span{z-index:1;font-size:15px;font-weight:900}
.tech{margin-top:6px;padding:7px 8px}.techhead{display:flex;justify-content:space-between;font-size:9px;color:#c2d0df;padding-bottom:6px}.techrow{display:grid;grid-template-columns:repeat(5,1fr);border-top:1px solid #172737}.techrow>div{text-align:center;padding:7px 2px 2px;border-right:1px solid #172737}.techrow>div:last-child{border:0}.techrow small,.techrow i{display:block;font-size:6px;color:#8d9db0;font-style:normal}.techrow b{display:block;font-size:10px;margin:4px 0}
.rnav{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #203448;border-bottom:1px solid #203448;margin-top:7px;padding:7px 0}.rnav div{text-align:center;color:#9db0c5;font-size:8px}.rnav b{display:block;font-size:17px;margin-bottom:2px}.rnav .active{color:var(--accent)}
.features{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;padding:8px 1px}.features>div{display:flex;gap:5px;align-items:center}.features>div>b{width:25px;height:25px;border:1px solid #00dfb5;border-radius:50%;display:grid;place-items:center;color:#00dfb5;font-size:13px}.features p{margin:0}.features strong{display:block;font-size:5.7px;color:#e1e8f0}.features span{display:block;font-size:5.4px;color:#8c9db0;margin-top:2px}
.refapp footer{border-top:1px solid #182a3a;padding:5px 1px;display:flex;justify-content:space-between;color:#708197;font-size:5.2px}
.ticker{text-align:center;color:#53667d;font-size:6px;margin-top:5px}


/* ===== FINAL PHONE REFERENCE PROPORTIONS ===== */
.block-container{max-width:365px!important;padding:3px 7px 14px!important}
.rhead{height:49px!important;padding-top:4px!important}
.rtitle{font-size:14px!important}.rver{font-size:8px!important}
.gear{right:7px!important;top:4px!important;font-size:18px!important}
.rlive{right:7px!important;bottom:0!important;font-size:8px!important}
.rhero{padding:1px 0 7px!important}
.rsignal{font-size:61px!important;line-height:.80!important;letter-spacing:-4px!important}
.rarrow{font-size:66px!important;margin-right:4px!important}
.rhero.waiting .rsignal{font-size:29px!important;letter-spacing:-1px!important}
.rconf{margin-top:9px!important;padding:4px 14px!important;font-size:9px!important}
.rgrid{gap:5px!important}
.keycard{height:57px!important;padding:6px 8px!important;gap:7px!important}
.bigicon{font-size:27px!important}.bars{width:27px!important;height:26px!important}.clock{font-size:27px!important}
.rlabel{font-size:7px!important}.rvalue{font-size:16px!important}.rdelta{font-size:8px!important}
.timebar{height:5px!important;margin-top:4px!important}
.probs{margin-top:5px!important;padding:7px!important}.pup,.pdown{height:18px!important;font-size:9px!important}
.pleg{font-size:9px!important;margin-top:5px!important}
.reader{margin-top:5px!important;padding:7px 8px!important}
.readerhead{font-size:8px!important}.readerhead .pulse{font-size:15px!important}
.readerbody{grid-template-columns:1fr 58px!important;margin-top:5px!important}
.readerbody strong{font-size:13px!important}.readerbody small{font-size:6.3px!important;margin-top:3px!important}
.rring{width:55px!important;height:55px!important}.rring:after{width:43px!important;height:43px!important}.rring span{font-size:13px!important}
.tech{margin-top:5px!important;padding:6px 7px!important}.techhead{font-size:8px!important;padding-bottom:5px!important}
.techrow>div{padding:5px 1px 1px!important}.techrow small,.techrow i{font-size:5.3px!important}.techrow b{font-size:9px!important;margin:3px 0!important}
.rnav{margin-top:6px!important;padding:6px 0!important}.rnav div{font-size:7px!important}.rnav b{font-size:15px!important}
.features{padding:7px 1px 5px!important;gap:3px!important}.features>div{gap:4px!important}
.features>div>b{width:22px!important;height:22px!important;font-size:11px!important}
.features strong{font-size:5px!important}.features span{font-size:4.8px!important}
.refapp footer{padding:4px 1px!important;font-size:4.7px!important}
.ticker{font-size:5.3px!important;margin-top:4px!important}

/* Make arrows chunky like the reference rather than thin text arrows */
.rarrow{font-family:Arial Black,Arial,sans-serif!important;font-weight:1000!important}


/* ===== TRUE FINAL: CSS ARROW + VISIBLE HEADER ===== */
.rhead{
    display:block!important;
    visibility:visible!important;
    height:58px!important;
    min-height:58px!important;
    padding-top:7px!important;
    overflow:visible!important;
    position:relative!important;
    z-index:20!important;
}
.rtitle,.rver,.gear,.rlive{display:block!important;visibility:visible!important}
.rtitle{font-size:14px!important;line-height:17px!important}
.rver{font-size:8px!important;line-height:11px!important}
.gear{top:7px!important;right:8px!important}
.rlive{bottom:3px!important;right:8px!important}

.rhero{padding-top:4px!important}
.rsignal{gap:9px!important}
.rarrow{display:none!important}

/* Solid arrow matching signal color; no iOS emoji rendering */
.cssarrow{
    position:relative;
    display:inline-block;
    width:42px;
    height:46px;
    background:var(--accent);
    border-radius:3px;
    box-shadow:0 0 12px var(--glow),0 0 24px var(--glow);
    flex:0 0 auto;
}
.cssarrow:before{
    content:"";
    position:absolute;
    left:-17px;
    top:-27px;
    width:0;height:0;
    border-left:38px solid transparent;
    border-right:38px solid transparent;
    border-bottom:34px solid var(--accent);
    filter:drop-shadow(0 0 7px var(--glow));
}
/* DOWN: arrow head below shaft */
.refapp.dir-down .cssarrow{transform:rotate(180deg);}
/* Waiting state: no arrow */
.rhero.waiting .cssarrow{display:none!important}

/* Keep final phone proportions compact */
.block-container{max-width:365px!important;padding-top:3px!important}
.rgrid{margin-top:1px!important}
.reader{min-height:0!important}


/* ===== PRESEÑAL — CAPA VISUAL, NO TOCA EL MOTOR ===== */
.presignal{margin:0 0 6px;padding:9px 10px;border:1px solid var(--precolor);border-radius:10px;background:linear-gradient(135deg,var(--prebg),rgba(8,18,27,.88));box-shadow:0 0 18px var(--preglow)}
.prehead{display:flex;justify-content:space-between;align-items:center;gap:8px}
.pretitle{font-size:8px;font-weight:950;letter-spacing:.55px;color:#b9c9db}
.prebadge{font-size:6.5px;font-weight:900;color:var(--precolor);border:1px solid var(--precolor);border-radius:10px;padding:3px 7px}
.premain{display:flex;justify-content:space-between;align-items:flex-end;margin-top:7px;gap:8px}
.predirection{font-size:17px;font-weight:1000;color:var(--precolor);letter-spacing:-.3px}
.prepercent{font-size:18px;font-weight:1000;color:var(--precolor)}
.prebar{height:5px;background:#1b2938;border-radius:6px;overflow:hidden;margin-top:7px}
.prebar b{display:block;height:100%;background:var(--precolor);border-radius:6px;box-shadow:0 0 9px var(--preglow)}
.prenote{font-size:6.7px;color:#91a2b5;margin-top:5px;line-height:1.25}

/* ===== PANEL FINAL DE CIERRE — EXACTO A LA REFERENCIA ===== */
.finalclose{margin-top:7px;border:1px solid var(--rr);border-radius:9px;padding:7px;background:rgba(5,15,22,.45)}
.finalgrid{display:grid;grid-template-columns:1.65fr .85fr .85fr;gap:4px}
.finalcard{min-height:67px;border:1px solid #29445a;border-radius:8px;background:linear-gradient(180deg,#0b1822,#08121a);padding:6px;text-align:center}
.finalcard.motion{border-color:#25bff2}.finalcard.distance{border-color:#8c4cff}.finalcard.speed{border-color:#ff3f86}
.finaltitle{font-size:6.5px;font-weight:950;color:#e6edf6}.motionrow{display:grid;grid-template-columns:repeat(3,1fr);margin-top:5px}.motionrow>div{border-right:1px solid #203344}.motionrow>div:last-child{border:0}.motionrow small{display:block;font-size:6px;color:#b7c6d7}.motionrow b{display:block;font-size:11px;margin-top:2px}.finalbig{font-size:14px;font-weight:1000;margin-top:8px}.finalsub{font-size:8px;font-weight:900;margin-top:2px}.finalnote{font-size:5.8px;color:#91a3b6;margin-top:4px}
.finalanalysis{display:grid;grid-template-columns:1fr 80px;gap:5px;margin-top:4px}.analysisbox,.probbox{border:1px solid #1fae7a;border-radius:8px;background:#07151a;padding:7px}.analysisbox{display:flex;align-items:center;gap:7px}.analysisicon{font-size:23px;color:#00dfb5}.analysistext small{display:block;font-size:6.3px;color:#d4deea}.analysistext b{display:block;font-size:10px;color:var(--rr);margin-top:2px}.analysistext span{display:block;font-size:6.3px;color:#a3b2c3;margin-top:3px}.probbox{border-color:#ff3f86;text-align:center}.probbox small{display:block;font-size:6.5px;color:#e4ebf3}.probbox b{display:block;font-size:15px;color:var(--rr);margin-top:8px}
.chartbox{margin-top:10px;background:linear-gradient(180deg,#08121d,#060c14);border:1px solid #203a51;border-radius:12px;padding:10px 8px 8px;box-shadow:inset 0 0 28px rgba(20,80,110,.08)}
.charttop{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#eef6ff}.charttop b{font-size:13px}.chartlive{font-size:7px;color:#00dfb5;margin-left:8px}.charttf{border:1px solid #26384b;border-radius:7px;padding:5px 8px;color:#dce8f5;font-size:9px}.ohlc{font-size:7px;color:#8ea0b5;margin-top:5px;white-space:nowrap}.indicators{font-size:7px;color:#aab8ca;margin:7px 0 1px;white-space:nowrap}.ema9dot{color:#df42e7}.ema21dot{color:#32d7ef}.targetdot{color:#23e7c1}.candlesvg{display:block;width:100%;height:265px}.chartfoot{display:flex;align-items:center;gap:10px;border-top:1px solid #18283a;padding:7px 2px 1px;color:#71839a;font-size:6px}.chartfoot .selected{border:1px solid #2a7189;border-radius:7px;padding:4px 8px;color:#e7f5ff;background:#0d2632}.chartempty{height:160px;display:grid;place-items:center;color:#708197;font-size:10px}

/* UNIFIED NEON THEME — visual layer only */
:root{--neon-up:#00dfb5;--neon-down:#e64b4b;--neon-purple:#00dfb5;--neon-cyan:#00eaff}
.stApp,[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse at 50% 0,rgba(0,100,85,.12),transparent 42%),#06121a!important}
.block-container{max-width:720px!important;padding:8px 12px 26px!important}
.refapp{color:#e9eafa;font-family:Inter,Arial,sans-serif}
.rcard,.mini,.section,.close-reader{background:linear-gradient(135deg,#111221,#080d17)!important;border-color:#23685e!important;border-radius:14px!important;box-shadow:inset 0 0 20px #8e48f208,0 0 11px #00dfb50c}
.refapp>section[style]{border-color:#23685e!important;border-radius:15px!important;box-shadow:0 0 13px #00dfb510}
.rtitle{color:#ecedff;text-shadow:0 0 18px #00dfb555}
.gear{color:#00dfb5!important;text-shadow:0 0 12px #00dfb566}
.rlive{color:#00dfb5!important}.rlive i{background:#00dfb5!important;box-shadow:0 0 11px #00dfb555!important}
.green{color:#00dfb5!important;text-shadow:0 0 7px #00dfb5aa,0 0 18px #00dfb555}
.red{color:#e64b4b!important;text-shadow:0 0 7px #e64b4baa,0 0 18px #e64b4b55}
.rconf{box-shadow:0 0 14px var(--soft),inset 0 0 12px var(--soft)!important}
.pup,.prob-up{background:linear-gradient(90deg,#00dfb5,#00dfb5)!important;color:#03281f!important;box-shadow:0 0 18px #00dfb580}
.pdown,.prob-down{background:linear-gradient(90deg,#e64b4b,#e64b4b)!important;color:#320515!important;box-shadow:0 0 18px #e64b4b80}
.timebar b,.ref-timebar b{box-shadow:0 0 11px var(--accent)}
.reader{box-shadow:0 0 14px var(--soft),inset 0 0 20px #9c63ed07!important;border-radius:15px!important}
.readerhead em{border-color:#00dfb5!important;color:#00dfb5!important;box-shadow:0 0 9px #00dfb51a}
.rring{filter:drop-shadow(0 0 6px var(--soft))}.rring:after{background:#080d17!important}
.techrow{border-color:#244047!important}.techrow>div{border-color:#244047!important}
.rnav{border-color:#244047!important}.rnav .active{color:var(--accent);text-shadow:0 0 12px var(--glow)}
.features>div>b{border-color:#00dfb5!important;color:#00dfb5!important;box-shadow:0 0 9px #00dfb521}
.targeticon,.clock{color:#8acfc3!important}.btcicon{filter:drop-shadow(0 0 7px #ff9d0044)}
.stRadio [role="radiogroup"]{gap:8px!important;flex-wrap:wrap;padding:8px 0}
.stRadio label{border:1px solid #23685e;border-radius:18px;padding:6px 10px!important;background:#110e20;color:#ded9f4!important}
[data-testid="stButton"] button{border-color:#23685e;color:#ece3ff;background:#141022;border-radius:12px}
[data-testid="stButton"] button:hover{border-color:#00dfb5;box-shadow:0 0 13px #00dfb533}
[data-testid="stMetricValue"]{color:#00eaff;text-shadow:0 0 10px #00eaff28}
@media(max-width:460px){.block-container{max-width:100%!important;padding:5px 8px 20px!important}}


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

/* Visible only when the already-existing reversal flag is active. */
.weakness-inline{
    margin:2px auto 6px;
    padding:6px 9px;
    width:fit-content;
    max-width:98%;
    border:1px solid #d99a31;
    border-radius:8px;
    background:#3b2b12;
    color:#ffdb8b!important;
    text-align:center;
    font-size:10px;
    font-weight:900;
    line-height:1.35;
    letter-spacing:.1px;
}


/* Solo el emblema original, sin alterar señales, tarjetas ni motor */
.refapp .rhead .jc-real-logo{
  position:absolute!important;left:3px!important;top:0!important;
  width:82px!important;height:89px!important;object-fit:contain!important;
  z-index:4!important;pointer-events:none!important;
  border:0!important;background:transparent!important;
}


/* Fondo sustituido por la imagen aportada, conservando el diseño de app 31. */


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

/* JC ALPHA EDGE: fondo unido al desplazamiento del bot.
   Sin posicion fija ni capas repetidas: no modifica el motor ni el HTML. */
html, body, .stApp, [data-testid="stAppViewContainer"] {
  background-image: none !important;
  background-color: #020919 !important;
}
[data-testid="stMain"], section.main {
  background-image: none !important;
  background-color: #020919 !important;
  background-position: center top !important;
  background-size: 100% auto !important;
  background-repeat: no-repeat !important;
  background-attachment: local !important;
}
[data-testid="stHeader"]{background:transparent!important;}

/* CORRECCION FONDO V3: fondo + bot pertenecen al mismo flujo de scroll.
   Evita el corte de la imagen: el encabezado original se desvanece sobre una
   continuacion azul/dorada que se extiende durante todo el panel. */
[data-testid="stMain"], section.main {
  background: #031024 !important;
}
[data-testid="stMain"] .block-container,
section.main .block-container {
  position: relative !important;
  isolation: isolate !important;
  background-color: #031024 !important;
  background-image:
    radial-gradient(ellipse 20px 42% at 0% 55%, rgba(0,120,255,.32), transparent 100%),
    radial-gradient(ellipse 16px 48% at 100% 55%, rgba(251,160,28,.34), transparent 100%),
    linear-gradient(90deg, #034c98 0%, #03112b 1.7%, #020b1e 10%, #020b1e 88%, #0c1630 97%, #c37b18 100%) !important;
  background-repeat: no-repeat !important;
  background-size: 100% 100% !important;
}
[data-testid="stMain"] .block-container::before,
section.main .block-container::before {
  content: "" !important;
  position: absolute !important;
  display: block !important;
  left: 0 !important;
  top: 0 !important;
  width: 100% !important;
  height: auto !important;
  aspect-ratio: 709 / 1536 !important;
  z-index: 0 !important;
  pointer-events: none !important;
  background: url("data:image/jpeg;base64,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") center top / 100% 100% no-repeat !important;
  -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 72%, transparent 98%) !important;
  mask-image: linear-gradient(to bottom, #000 0%, #000 72%, transparent 98%) !important;
}
/* Tablet únicamente: conservar escala de la ilustración superior.
   El móvil (<=600px) no recibe ningún cambio. */
@media (min-width: 601px) and (max-width: 1199px) {
  [data-testid="stMain"] .block-container::before,
  section.main .block-container::before {
    width: min(94%, 680px) !important;
    /* Compactar verticalmente el fondo en tablet sin cambiar su ancho. */
    aspect-ratio: 709 / 1280 !important;
    background-size: 100% 100% !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
  }
}
[data-testid="stMain"] .block-container > *,
section.main .block-container > * {
  position: relative !important;
  z-index: 1 !important;
}


/* ALPHA EDGE: franjas interiores en TODOS los cuadros del panel.
   La capa es puramente decorativa y no intercepta clics. */
.rcard,
.presignal,
.probs,
.finalclose,
.finalcard,
.finalanalysis,
.probbox,
.ra93-panel,
.chartbox,
.history-stat,
.sq-box,
.panel,
.card,
.metric,
.motionrow > div,
.finalgrid > div,
.metrics > div,
.cards > div,
.rgrid > div,
.history-stats > div,
.sq-item {
  position:relative;
  isolation:isolate;
  overflow:hidden;
}
.rcard::before, .presignal::before, .probs::before, .finalclose::before, .finalcard::before, .finalanalysis::before, .probbox::before, .ra93-panel::before, .chartbox::before, .history-stat::before, .sq-box::before, .panel::before, .card::before, .metric::before, .motionrow > div::before, .finalgrid > div::before, .metrics > div::before, .cards > div::before, .rgrid > div::before, .history-stats > div::before, .sq-item::before {
  content:"";
  position:absolute;
  inset:0;
  z-index:0;
  pointer-events:none;
  border-radius:inherit;
  background:repeating-linear-gradient(128deg,
    transparent 0px,
    transparent 20px,
    rgba(255,232,169,.15) 21px,
    rgba(255,232,169,.085) 30px,
    transparent 39px,
    transparent 79px);
  opacity:.85;
}
.rcard > *, .presignal > *, .probs > *, .finalclose > *, .finalcard > *, .finalanalysis > *, .probbox > *, .ra93-panel > *, .chartbox > *, .history-stat > *, .sq-box > *, .panel > *, .card > *, .metric > *, .motionrow > div > *, .finalgrid > div > *, .metrics > div > *, .cards > div > *, .rgrid > div > *, .history-stats > div > *, .sq-item > * {
  position:relative;
  z-index:1;
}

/* SOLO TABLETS (601–1199px): usar el ancho de pantalla disponible.
   No cambia estilos del teléfono ni lógica del motor. */
@media screen and (min-width: 601px) and (max-width: 1199px) {
  [data-testid="stMain"] .block-container,
  section.main .block-container,
  .stApp .block-container {
    width: 100% !important;
    max-width: 100% !important;
    padding-left: 12px !important;
    padding-right: 12px !important;
    box-sizing: border-box !important;
  }
  [data-testid="stMain"] .block-container::before,
  section.main .block-container::before {
    width: 100% !important;
    left: 0 !important;
    transform: none !important;
  }
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# SESSION STATE ORIGINAL
# =========================================================

if "rounds" not in st.session_state:
    st.session_state.rounds = {}

if "active_ticker" not in st.session_state:
    st.session_state.active_ticker = None

if "micro_prices" not in st.session_state:
    st.session_state.micro_prices = []

if "micro_ticker" not in st.session_state:
    st.session_state.micro_ticker = None


# Informational price plan; never predicts settlement or sends an order.
import math
import html
from datetime import datetime,timezone

def _plan_number(value):
    if isinstance(value,bool):return None
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (TypeError,ValueError,OverflowError):return None

def make_exit_plan(state, signal, seconds_left, now):
    if not signal or signal.get('data_valid') is False:return None
    side=state.get('first_direction');price=_plan_number(signal.get('price'));atr=_plan_number(signal.get('atr'));secs=_plan_number(seconds_left)
    if side not in ('UP','DOWN') or price is None or atr is None or secs is None or min(price,atr,secs)<=0 or atr>=price:return None
    first=state.get('first_signal_time')
    if not isinstance(first,datetime) or first.tzinfo is None or now.tzinfo is None or first>now:return None
    source=signal.get('price_source')
    if source not in ('KALSHI LIVE','COINBASE','COINBASE CANDLE'):return None
    sign=1 if side=='UP' else -1
    return {'rule':'fixed_1atr_reference_v1','direction':side,'reference_btc':price,
        'reference_kind':'confirmation' if first==now else 'resumed',
        'atr_at_confirmation':atr,'target_btc':price+sign*atr,'invalidation_btc':price-sign*atr,
        'source':source,'first_time':first.isoformat(),'created_at':now.isoformat(),
        'terminal_status':None,'terminal_at':None,'terminal_price':None,'last_at':now.isoformat()}

def exit_plan_status(plan, signal, seconds_left, now):
    secs=_plan_number(seconds_left)
    if secs is not None and secs<=0:return 'ROUND_CLOSED'
    if not isinstance(plan,dict):return 'NO_PLAN'
    if plan.get('terminal_status'):return plan['terminal_status']
    if secs is None or not signal or signal.get('data_valid') is False:return 'NO_CURRENT_DATA'
    if signal.get('price_source')!=plan.get('source'):return 'REFERENCE_CHANGED'
    price=_plan_number(signal.get('price'))
    if price is None or price<=0:return 'NO_CURRENT_DATA'
    try:
        last=datetime.fromisoformat(plan['last_at'])
        if now.tzinfo is None or now<last:return 'NO_CURRENT_DATA'
    except (KeyError,TypeError,ValueError):return 'NO_CURRENT_DATA'
    sign=1 if plan['direction']=='UP' else -1
    if sign*(price-plan['invalidation_btc'])<=0:return 'INVALIDATED'
    if sign*(price-plan['target_btc'])>=0:return 'TARGET_REACHED'
    return 'IN_RANGE'

def update_exit_plan(state, signal, seconds_left, now):
    plan=state.get('exit_plan');status=exit_plan_status(plan,signal,seconds_left,now)
    if not plan or plan.get('terminal_status') or status not in ('IN_RANGE','INVALIDATED','TARGET_REACHED'):return status
    updated=dict(plan,last_at=now.isoformat())
    if status!='IN_RANGE':updated.update(terminal_status=status,terminal_at=now.isoformat(),terminal_price=float(signal['price']))
    state['exit_plan']=updated
    return status

def preserve_exit_plan(state, saved):
    old=saved.get('exit_plan')
    if not isinstance(old,dict) or old.get('first_time')!=saved.get('first_signal_time'):return
    current=state.get('exit_plan')
    if not isinstance(current,dict) or current.get('first_time')!=old['first_time'] or old.get('terminal_status'):
        state['exit_plan']=old
        return
    fixed=('reference_kind','rule','direction','reference_btc','atr_at_confirmation','target_btc','invalidation_btc','source','first_time','created_at')
    state['exit_plan']={**current,**{k:old[k] for k in fixed if k in old}}

def plan_bid(market, side):
    market=market or {};prefix='yes' if side=='UP' else 'no'
    value=_plan_number(market.get(prefix+'_bid_dollars'))
    if value is None:
        value=_plan_number(market.get(prefix+'_bid'))
        if value is not None:value/=100
    return value if value is not None and 0<value<=1 else None

def render_exit_plan(state, signal, market, seconds_left, now):
    plan=(state or {}).get('exit_plan');status=exit_plan_status(plan,signal,seconds_left,now)
    titles={'NO_PLAN':'ESPERANDO UNA NUEVA SEÑAL','ROUND_CLOSED':'ESTA RONDA YA TERMINÓ',
        'NO_CURRENT_DATA':'ESPERANDO UN PRECIO ACTUAL','REFERENCE_CHANGED':'NO PUEDO COMPARAR EL PRECIO AHORA',
        'IN_RANGE':'SIGUIENDO LA SEÑAL','TARGET_REACHED':'LLEGÓ AL OBJETIVO · REVISA SALIR',
        'INVALIDATED':'VA EN CONTRA · REVISA SALIR'}
    title=titles[status]
    if status=='NO_PLAN' and (state or {}).get('first_direction') in ('UP','DOWN'):
        title='SEÑAL ACTIVA · ESPERANDO DATOS PARA LA REFERENCIA'
    color='#e64b4b' if status=='INVALIDATED' else '#00dfb5' if status=='TARGET_REACHED' else '#38bdf8'
    if not plan:
        details=('La señal ya está activa. Falta un precio y ATR válidos para iniciar el seguimiento.' if (state or {}).get('first_direction') in ('UP','DOWN') else 'Los precios aparecerán cuando el bot confirme una nueva señal.')
        rows=''
    else:
        if status=='IN_RANGE':title+=' '+plan['direction']
        active_side=(state or {}).get('active_direction')
        if active_side in ('UP','DOWN') and active_side!=plan['direction']:
            title='LA SEÑAL ACTIVA CAMBIÓ A '+active_side+' · REVISA LA REFERENCIA INICIAL'
        bid=plan_bid(market,plan['direction']);bid_text=f'{bid*100:.1f}¢ por contrato' if bid is not None else 'No disponible'
        goal_verb='sube' if plan['direction']=='UP' else 'baja'
        against_verb='baja' if plan['direction']=='UP' else 'sube'
        fields=[('Señal inicial',plan['direction']),('Referencia BTC al reanudar' if plan.get('reference_kind')=='resumed' else 'Precio al dar la señal',f"${plan['reference_btc']:,.2f}"),
            ('Si '+goal_verb+' a esto, revisa salir',f"${plan['target_btc']:,.2f}"),
            ('Si '+against_verb+' a esto, revisa salir',f"${plan['invalidation_btc']:,.2f}"),
            ('Precio orientativo para vender',bid_text)]
        rows=''.join('<div style="display:flex;justify-content:space-between;gap:12px;margin-top:8px"><span>'+html.escape(k)+'</span><strong>'+html.escape(v)+'</strong></div>' for k,v in fields)
        details='Estos precios son una guía; el mercado puede seguir moviéndose.'
        if plan.get('reference_kind')=='resumed':details+=' Referencia fijada al reanudar el seguimiento; no es el precio de la señal original.'
        current_price=_plan_number((signal or {}).get('price'))
        if status=='IN_RANGE' and current_price is not None and (1 if plan['direction']=='UP' else -1)*(current_price-plan['reference_btc'])<0:
            title='RETROCESO CONTRA '+plan['direction']+' · REVISA LA SALIDA'
            details+=' BTC está en contra de la referencia inicial, sin alcanzar aún el límite marcado.'
        if plan.get('terminal_at'):details+=' El aviso ya se activó y seguirá visible aunque el precio regrese.'
    return '<section style="border:1px solid '+color+';border-radius:18px;padding:18px;margin:12px 0;background:#0b1720;color:#cbd5e1"><div style="font-size:13px;color:'+color+'">CUÁNDO REVISAR LA SALIDA</div><h3 style="color:'+color+';margin:10px 0">'+title+'</h3>'+rows+'<p style="font-size:12px;color:#94a3b8;margin:12px 0 0">'+details+' No vende automáticamente. El precio de venta puede cambiar y no asegura ganancias.</p></section>'


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

# =========================================================
# PERSISTENCIA DE RONDA — SOBREVIVE SALIR/ENTRAR A LA APP
# Solo guarda el estado de la ronda; NO cambia el cerebro.
# =========================================================

LEGACY_ROUND_STATE_DB = 'btc_signal_round_state.db'
ROUND_STATE_DB = 'btc_signal_round_state_v2.db'
_ROUND_TRANSACTION = threading.local()


def _round_db():
    conn = sqlite3.connect(ROUND_STATE_DB, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS round_state (ticker TEXT PRIMARY KEY,payload TEXT NOT NULL,updated_at TEXT NOT NULL)')
    return conn


def _decode_round_payload(payload):
    state = json.loads(payload)
    for key in ('detected_at','first_signal_time','active_since'):
        value = state.get(key)
        if isinstance(value, str) and value:
            try:
                state[key] = datetime.fromisoformat(value)
            except ValueError:
                state[key] = None
    state['_restored_from_disk'] = True
    return state


def _load_state_from_connection(conn, ticker):
    row = conn.execute('SELECT payload FROM round_state WHERE ticker=?', (ticker,)).fetchone()
    if row:
        return _decode_round_payload(row[0])
    # La primera lectura conserva la ronda anterior, sin permitir que un trabajador
    # antiguo escriba en la nueva base coordinada.
    try:
        with sqlite3.connect('file:' + LEGACY_ROUND_STATE_DB + '?mode=ro', uri=True, timeout=1) as legacy:
            row = legacy.execute('SELECT payload FROM round_state WHERE ticker=?', (ticker,)).fetchone()
        return _decode_round_payload(row[0]) if row else None
    except Exception:
        return None


def load_round_state(ticker):
    if not ticker or ticker == '--':
        return None
    conn = getattr(_ROUND_TRANSACTION, 'conn', None)
    if conn is not None:
        return _load_state_from_connection(conn, ticker)
    try:
        with _round_db() as conn:
            return _load_state_from_connection(conn, ticker)
    except Exception:
        return None


def _write_state_to_connection(conn, state):
    row = conn.execute('SELECT payload FROM round_state WHERE ticker=?', (state['ticker'],)).fetchone()
    saved = json.loads(row[0]) if row else {}
    # El ticker identifica la ronda y su primera señal ya guardada.
    if saved.get('first_direction') in ('UP','DOWN'):
        for key in ('first_direction','first_signal_time','first_signal_seconds',
                    'first_signal_price'):
            value = saved.get(key)
            if key == 'first_signal_time' and isinstance(value, str) and value:
                value = datetime.fromisoformat(value)
            state[key] = value
    preserve_exit_plan(state, saved)
    keep = {key:value for key,value in state.items() if key != '_restored_from_disk'}
    for key in ('detected_at','first_signal_time','active_since'):
        if isinstance(keep.get(key), datetime):
            keep[key] = keep[key].isoformat()
    conn.execute('INSERT INTO round_state(ticker,payload,updated_at) VALUES(?,?,?) '
                 'ON CONFLICT(ticker) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',
                 (state['ticker'],json.dumps(keep,allow_nan=False),datetime.now(timezone.utc).isoformat()))


def save_round_state(state):
    if not state or not state.get('ticker'):
        return
    conn = getattr(_ROUND_TRANSACTION,'conn',None)
    if conn is not None:
        _write_state_to_connection(conn,state)
        return
    with _round_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _write_state_to_connection(conn,state)


def _run_round_transaction(action):
    if getattr(_ROUND_TRANSACTION,'conn',None) is not None:
        return action()
    conn = _round_db()
    try:
        conn.execute('BEGIN IMMEDIATE')
        _ROUND_TRANSACTION.conn = conn
        try:
            result = action()
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            _ROUND_TRANSACTION.conn = None
    finally:
        conn.close()


def process_round_signal(ticker, sig, market, seconds_left):
    if not ticker or ticker == '--':
        return _process_round_signal_without_coordinator(ticker,sig,market,seconds_left)
    def apply():
        latest = load_round_state(ticker)
        if latest is not None:
            st.session_state.rounds[ticker] = latest
        return _process_round_signal_without_coordinator(ticker,sig,market,seconds_left)
    return _run_round_transaction(apply)


def _background_update_state(state, sig, market, seconds_left):
    def apply():
        latest = load_round_state(state['ticker'])
        current = latest if latest is not None else state
        current.pop('_restored_from_disk',None)
        return _background_update_state_without_coordinator(current,sig,market,seconds_left)
    return _run_round_transaction(apply)




# =========================================================
# HISTORIAL Y RENDIMIENTO — CAPA INDEPENDIENTE
# No modifica build_signal(), preseñal, lector, ballenas ni gráfico.
# =========================================================

LEGACY_HISTORY_DB = "btc_signal_history.db"
HISTORY_DB = "btc_signal_history_v2.db"

def _history_db():
    conn = sqlite3.connect(HISTORY_DB, timeout=5)
    conn.execute('''CREATE TABLE IF NOT EXISTS round_history (
        ticker TEXT PRIMARY KEY, target REAL, final_btc REAL, final_outcome TEXT,
        bot_signal TEXT, result TEXT, first_signal TEXT, first_signal_time TEXT,
        closed_at TEXT NOT NULL)''')
    try:
        conn.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(round_history)")}
        additions = {
            "verification_status": "TEXT NOT NULL DEFAULT 'pending'",
            "observed_outcome": "TEXT", "observed_result": "TEXT",
            "official_result": "TEXT", "settlement_at": "TEXT", "verified_at": "TEXT",
            "last_verification_attempt": "TEXT", "verified_expiration_value": "REAL",
        }
        migrated = False
        for name, spec in additions.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE round_history ADD COLUMN {name} {spec}")
                migrated = True
        if migrated:
            conn.execute('''UPDATE round_history SET observed_outcome=final_outcome,
                observed_result=result,
                result=CASE WHEN first_signal IN ('UP','DOWN') THEN 'PENDIENTE' ELSE 'NO TRADE' END
                WHERE verification_status != 'official' ''')
        conn.execute("CREATE TABLE IF NOT EXISTS history_migrations (name TEXT PRIMARY KEY)")
        migrated_legacy = conn.execute("SELECT 1 FROM history_migrations WHERE name='legacy_import_v1'").fetchone()
        if not migrated_legacy:
            from pathlib import Path
            if Path(LEGACY_HISTORY_DB).exists():
                legacy = sqlite3.connect('file:' + LEGACY_HISTORY_DB + '?mode=ro', uri=True, timeout=1)
                try:
                    legacy.row_factory = sqlite3.Row
                    source_rows = legacy.execute('SELECT * FROM round_history').fetchall()
                    allowed = {'ticker','target','final_btc','final_outcome','bot_signal','result',
                               'first_signal','first_signal_time','closed_at'} | set(additions)
                    for source_row in source_rows:
                        values = dict(source_row)
                        values['observed_outcome'] = values.get('observed_outcome') or values.get('final_outcome')
                        values['observed_result'] = values.get('observed_result') or values.get('result')
                        names = sorted(allowed.intersection(values))
                        conn.execute('INSERT OR IGNORE INTO round_history (' + ','.join(names) +
                                     ') VALUES (' + ','.join('?' for _ in names) + ')',
                                     tuple(values[name] for name in names))
                finally:
                    legacy.close()
            conn.execute("INSERT INTO history_migrations(name) VALUES('legacy_import_v1')")
        conn.commit()
        return conn
    except Exception:
        conn.close()
        raise


def save_round_history(state):
    """Guarda la observación; solamente Kalshi determina la evaluación final."""
    if not state or not state.get("ticker"):
        return
    try:
        latest = load_round_state(state["ticker"])
        canonical_first = bool(latest and latest.get("ticker") == state["ticker"]
                               and latest.get("first_direction") in ("UP", "DOWN"))
        if canonical_first:
            state = dict(state)
            for key in ("first_direction", "first_signal_time"):
                state[key] = latest.get(key)
        target = float(state["last_target"])
        price = float(state["last_live_price"])
        if not np.isfinite(target) or not np.isfinite(price):
            return
        observed = "UP" if price > target else "DOWN" if price < target else "EMPATE"
        first = state.get("first_direction")
        first = first if first in ("UP", "DOWN") else None
        pending = "PENDIENTE" if first else "NO TRADE"
        observed_result = ("EMPATE" if observed == "EMPATE" else "GANADA" if first == observed else "PERDIDA") if first else "NO TRADE"
        fst = state.get("first_signal_time")
        if isinstance(fst, datetime):
            fst = fst.isoformat()
        with _history_db() as conn:
            if canonical_first:
                conn.execute('''UPDATE round_history SET first_signal=?,
                    first_signal_time=COALESCE(?,first_signal_time),bot_signal=?,
                    result=CASE WHEN verification_status='official' AND official_result IN ('yes','no')
                        THEN CASE WHEN official_result=? THEN 'GANADA' ELSE 'PERDIDA' END
                        ELSE result END WHERE ticker=?''',
                    (first,fst,first,'yes' if first == 'UP' else 'no',state['ticker']))
            conn.execute('''INSERT INTO round_history
                (ticker,target,final_btc,final_outcome,bot_signal,result,first_signal,
                 first_signal_time,closed_at,verification_status,observed_outcome,observed_result)
                VALUES(?,?,?,?,?,?,?,?,?,'pending',?,?)
                ON CONFLICT(ticker) DO UPDATE SET
                    target=excluded.target,
                    final_btc=CASE WHEN round_history.verification_status='official' THEN round_history.final_btc ELSE excluded.final_btc END,
                    final_outcome=CASE WHEN round_history.verification_status='official' THEN round_history.final_outcome ELSE excluded.final_outcome END,
                    bot_signal=COALESCE(round_history.first_signal,excluded.first_signal),
                    result=CASE WHEN round_history.verification_status='official' THEN round_history.result ELSE excluded.result END,
                    first_signal=COALESCE(round_history.first_signal,excluded.first_signal),
                    first_signal_time=COALESCE(round_history.first_signal_time,excluded.first_signal_time),
                    observed_outcome=excluded.observed_outcome,
                    observed_result=excluded.observed_result''',
                (state['ticker'], target, price, observed, first, pending, first, fst,
                 datetime.now(timezone.utc).isoformat(), observed, observed_result))
    except Exception:
        pass


def verified_binary_outcome(market, ticker, now=None):
    """Acepta solamente una liquidación binaria fechada y no provisional."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(market, dict) or market.get('ticker') != ticker:
        return None
    if not ticker.startswith('KXBTC15M-') or market.get('market_type') != 'binary':
        return None
    if market.get('is_provisional') not in (None, False):
        return None
    result = str(market.get('result') or '').lower()
    if result not in ('yes', 'no'):
        return None
    try:
        settled = datetime.fromisoformat(str(market['settlement_ts']).replace('Z', '+00:00'))
        if settled.tzinfo is None or settled > now:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return 'UP' if result == 'yes' else 'DOWN'


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


def _kalshi_public_json(path, params=None, ttl=2.0, timeout=6):
    return _kalshi_public_reads().get(path, params=params, ttl=ttl, timeout=timeout)


def reconcile_history_once(limit=4, fetch_market=None):
    """Consulta resultados públicos fuera del motor de señales."""
    with _history_db() as conn:
        tickers = [row[0] for row in conn.execute('''SELECT ticker FROM round_history
            WHERE verification_status != 'official' AND ticker LIKE 'KXBTC15M-%'
            ORDER BY COALESCE(last_verification_attempt,''),closed_at DESC LIMIT ?''', (int(limit),))]
    verified = 0
    for ticker in tickers:
        try:
            with _history_db() as conn:
                conn.execute('UPDATE round_history SET last_verification_attempt=? WHERE ticker=?',
                             (datetime.now(timezone.utc).isoformat(), ticker))
            if fetch_market is None:
                market = _kalshi_public_json(
                    '/markets/' + ticker, ttl=30.0, timeout=5).get('market')
            else:
                market = fetch_market(ticker)
            outcome = verified_binary_outcome(market, ticker)
            if outcome is None:
                continue
            expiration = market.get('expiration_value')
            try:
                expiration = float(expiration)
                if not np.isfinite(expiration) or not 10000 < expiration < 1000000:
                    expiration = None
            except (ValueError, TypeError):
                expiration = None
            with _history_db() as conn:
                conn.execute('''UPDATE round_history SET final_outcome=?,
                    final_btc=COALESCE(?,final_btc),
                    result=CASE WHEN first_signal NOT IN ('UP','DOWN') OR first_signal IS NULL THEN 'NO TRADE'
                                WHEN first_signal=? THEN 'GANADA' ELSE 'PERDIDA' END,
                    verification_status='official',official_result=?,settlement_at=?,verified_at=?,verified_expiration_value=?
                    WHERE ticker=?''',
                    (outcome, expiration, outcome, market['result'], market['settlement_ts'],
                     datetime.now(timezone.utc).isoformat(), expiration, ticker))
            verified += 1
        except Exception:
            continue
    return verified


def _history_verification_loop():
    started = time.monotonic()
    while True:
        try:
            reconcile_history_once()
        except Exception as exc:
            print(f"[ALPHA HISTORY VERIFY] {type(exc).__name__}: {exc}")
        time.sleep(30)


@st.cache_resource(validate=lambda worker: worker.is_alive())
def start_history_verifier():
    worker = threading.Thread(target=_history_verification_loop, name='btc-history-verification-v2', daemon=True)
    worker.start()
    return worker


def load_history(limit=100):
    try:
        with _history_db() as conn:
            # Un registrador antiguo aún activo no puede convertir una observación en resultado oficial.
            conn.execute('''UPDATE round_history SET
                final_outcome=CASE official_result WHEN 'yes' THEN 'UP' WHEN 'no' THEN 'DOWN' ELSE final_outcome END,
                final_btc=COALESCE(verified_expiration_value,final_btc)
                WHERE verification_status='official' ''')
            conn.execute('''UPDATE round_history SET bot_signal=first_signal,
                result=CASE WHEN first_signal NOT IN ('UP','DOWN') OR first_signal IS NULL THEN 'NO TRADE'
                            WHEN verification_status != 'official' THEN 'PENDIENTE'
                            WHEN first_signal=final_outcome THEN 'GANADA' ELSE 'PERDIDA' END''')
            rows = conn.execute('''SELECT ticker,target,final_btc,
                CASE WHEN verification_status='official' THEN final_outcome ELSE 'PENDIENTE' END,
                bot_signal,result,first_signal,first_signal_time,closed_at
                FROM round_history ORDER BY closed_at DESC LIMIT ?''', (int(limit),)).fetchall()
        return pd.DataFrame(rows, columns=['Ronda','Target','BTC final','Resultado oficial','Señal bot','Estado','1ª señal','Hora 1ª señal','Cierre'])
    except Exception:
        return pd.DataFrame()


def history_stats(df):
    if df is None or df.empty:
        return dict(total=0,wins=0,losses=0,no_trade=0,pending=0,decided=0,win_rate=0.0)
    wins = int((df['Estado']=='GANADA').sum())
    losses = int((df['Estado']=='PERDIDA').sum())
    decided = wins + losses
    return dict(total=len(df),wins=wins,losses=losses,
                no_trade=int((df['Estado']=='NO TRADE').sum()),
                pending=int((df['Estado']=='PENDIENTE').sum()),decided=decided,
                win_rate=wins/decided*100 if decided else 0.0)


# =========================================================
# COINBASE — VELAS ORIGINALES DE 1 MINUTO
# =========================================================

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


def get_coinbase_whale_flow(flow_state=None):
    """Lee presión agresiva de Coinbase en ventanas 10s/30s/60s y conserva alertas breves."""
    response = requests.get(
        "https://api.exchange.coinbase.com/products/BTC-USD/trades",
        params={"limit": 100},
        headers={"User-Agent": "MacalyAlphaBot/4.6.1"},
        timeout=6,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list) or not rows:
        raise ValueError("Coinbase no devolvió operaciones recientes.")

    now = pd.Timestamp.now(tz="UTC").timestamp()
    flow_state = st.session_state if flow_state is None else flow_state
    tape = flow_state.setdefault("whale_flow_tape", [])
    seen = flow_state.setdefault("whale_seen_ids", {})

    for row in reversed(rows):
        try:
            trade_id = str(row.get("trade_id", ""))
            if not trade_id or trade_id in seen:
                continue
            price = float(row.get("price", 0))
            size = float(row.get("size", 0))
            notional = price * size
            maker_side = str(row.get("side", "")).lower()
            aggressor = "COMPRA" if maker_side == "sell" else "VENTA" if maker_side == "buy" else ""
            ts = pd.to_datetime(row.get("time"), utc=True, errors="coerce")
            if pd.isna(ts):
                continue
            t = ts.timestamp()
            if (not np.isfinite(price) or not np.isfinite(size) or not np.isfinite(notional)
                    or price <= 0 or size <= 0 or not 0 <= now - t <= 75):
                continue
            if notional > 0 and aggressor:
                tape.append({"id": trade_id, "t": t, "notional": notional, "size": size, "side": aggressor})
                seen[trade_id] = t
        except Exception:
            continue

    tape[:] = [x for x in tape if 0 <= now - x["t"] <= 75]
    for k in [k for k, t in seen.items() if now - t > 90]:
        seen.pop(k, None)

    def window(seconds):
        w = [x for x in tape if 0 <= now - x["t"] <= seconds]
        buy = sum(x["notional"] for x in w if x["side"] == "COMPRA")
        sell = sum(x["notional"] for x in w if x["side"] == "VENTA")
        total = buy + sell
        imbalance = abs(buy - sell) / total if total else 0.0
        direction = "UP" if buy > sell else "DOWN" if sell > buy else None
        return buy, sell, total, imbalance, direction

    b10,s10,t10,i10,d10 = window(10)
    b30,s30,t30,i30,d30 = window(30)
    b60,s60,t60,i60,d60 = window(60)

    # Alert only when flow is materially one-sided AND supported beyond a tiny 4s snapshot.
    burst = t10 >= 750_000 and i10 >= 0.28
    sustained = t30 >= 1_750_000 and i30 >= 0.18
    same_side = d10 is not None and d10 == d30
    qualifies = bool(same_side and (burst or sustained))

    alert = flow_state.get("whale_flow_alert")
    if qualifies:
        alert = {
            "direction": d10, "time": now,
            "buy": b30, "sell": s30, "total": t30,
            "imbalance": i30, "buy10": b10, "sell10": s10,
        }
        flow_state["whale_flow_alert"] = alert
    elif alert and now - float(alert.get("time", 0)) > 12:
        alert = None
        flow_state["whale_flow_alert"] = None

    def traded_price(min_age, max_age):
        trades = [x for x in tape if min_age <= now - x["t"] < max_age and x.get("size", 0) > 0]
        size = sum(x["size"] for x in trades)
        return sum(x["notional"] for x in trades) / size if size else None

    recent_price, previous_price = traded_price(0, 5), traded_price(5, 10)
    move = recent_price - previous_price if recent_price is not None and previous_price is not None else None
    # Usa el último precio ejecutado de cada segundo para medir avance frente a ruido.
    recent_prices = {}
    for trade in tape:
        age = now - trade["t"]
        size = trade.get("size", 0)
        if 0 <= age < 10 and size > 0:
            second = int(trade["t"])
            if second not in recent_prices or trade["t"] > recent_prices[second][0]:
                recent_prices[second] = (trade["t"], trade["notional"] / size)
    price_path = [price for _, price in sorted(recent_prices.values())]

    return {
        "trade_price_move": move,
        "trade_price_path": price_path,
        "detected": alert is not None, "alert": alert,
        "live_buy": b10, "live_sell": s10, "live_total": t10,
        "imbalance": i10, "buy30": b30, "sell30": s30,
        "buy60": b60, "sell60": s60,
        "flow_direction": d10 if same_side else None,
        "flow_strength": max(i10, i30 if same_side else 0.0),
    }


def compact_usd(value):
    value = float(value or 0)
    if value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value/1_000:.0f}K"
    return f"${value:,.0f}"


def render_whale_panel(whale, active):
    base = "margin:8px 0;padding:12px;border:1px solid #26384b;border-radius:13px;background:linear-gradient(180deg,#0c1724,#09111b)"
    if not whale or not whale.get("detected"):
        buy = compact_usd((whale or {}).get("live_buy", 0))
        sell = compact_usd((whale or {}).get("live_sell", 0))
        return f'''<section style="{base}">
          <div style="display:flex;justify-content:space-between;align-items:center"><b style="font-size:10px;color:#e4edf7">🐋 FLUJO BALLENA · EN VIVO</b><span style="font-size:8px;color:#00dfb5">● COINBASE</span></div>
          <div style="margin-top:8px;font-size:13px;font-weight:900;color:#91a2b5">SIN FLUJO EXTREMO AHORA</div>
          <div style="margin-top:6px;font-size:9px;color:#8da0b4">Últimos 10 s · COMPRAS {buy} · VENTAS {sell}</div>
          <div style="margin-top:4px;font-size:8px;color:#6f8195">Confirma presión con ventanas de 10 s y 30 s; no alerta por una operación aislada.</div>
        </section>'''

    a = whale["alert"]
    up = a["direction"] == "UP"
    color = "#00dfb5" if up else "#e64b4b"
    arrow = "↑" if up else "↓"
    label = "COMPRADOR · POSIBLE IMPULSO UP" if up else "VENDEDOR · POSIBLE IMPULSO DOWN"
    dominant = a["buy"] if up else a["sell"]
    relation = ""
    if active in ("UP", "DOWN"):
        relation = " · CONFIRMA SEÑAL" if active == a["direction"] else " · CONTRADICE SEÑAL"
    return f'''<section style="{base};border-color:{color};box-shadow:0 0 20px {color}33">
      <div style="display:flex;justify-content:space-between;align-items:center"><b style="font-size:10px;color:#e4edf7">🐋 FLUJO BALLENA · EN VIVO</b><span style="font-size:8px;color:{color}">● ALERTA</span></div>
      <div style="margin-top:8px;font-size:15px;font-weight:950;color:{color}">⚡ {arrow} FLUJO EXTREMO {label}</div>
      <div style="margin-top:6px;font-size:12px;font-weight:900;color:#f3f7fb">{compact_usd(dominant)} dominantes en ~30 s</div>
      <div style="margin-top:5px;font-size:9px;color:#aab8c7">COMPRAS {compact_usd(a['buy'])} · VENTAS {compact_usd(a['sell'])} · DOMINIO {a['imbalance']*100:.0f}%{relation}</div>
      <div style="margin-top:4px;font-size:8px;color:#7f91a5">Alerta temprana de presión extraordinaria en el flujo real de BTC/USD.</div>
    </section>'''


def get_btc_live_price():
    response = requests.get(
        "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
        headers={
            "User-Agent": "MacalyAlphaBot/4.6.1",
            "Cache-Control": "no-cache",
        },
        params={"_": int(datetime.now(timezone.utc).timestamp())},
        timeout=6,
    )
    response.raise_for_status()
    data = response.json()
    return _valid_live_observation(data.get("price"), data.get("time"), "COINBASE")


# =========================================================
# KALSHI BTC 15 MIN
# =========================================================

def get_kalshi_btc_market():
    return _kalshi_public_reads().current_market()


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
            price = _valid_live_observation(value, pd.to_datetime(stamp, unit="s", utc=True), "KALSHI LIVE")
            _PRICE_OBSERVATIONS.kalshi_points = [(t, p) for t, _, p in timed_points if stamp - 90 <= t <= stamp]
            return price
        except (ValueError, TypeError, OverflowError):
            return None
    # Un precio sin fecha verificable no se anuncia como live.
    return None


def get_kalshi_live_btc(market):
    event_ticker = get_event_ticker_from_market(market)
    if not event_ticker:
        raise ValueError("La ronda no entregó event_ticker.")
    data = _kalshi_public_json(
        "/live_data/events/" + str(event_ticker),
        params={"range": "15min"}, ttl=2.0, timeout=6)
    # Siempre se valida la fecha original, incluso al compartir una respuesta.
    price = extract_kalshi_btc_price(data)
    if price is None:
        raise ValueError("Kalshi live respondió sin precio BTC válido.")
    return float(price)


# =========================================================
# INDICADORES ORIGINALES
# =========================================================

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


def format_countdown(seconds):
    if seconds is None:
        return "--:--"
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


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


# =========================================================
# PROBABILIDAD ORIGINAL
# =========================================================

def estimated_probabilities(
    final_score, distance, seconds_left, mom3, mom5
):
    score = float(np.clip(final_score, -10, 10))
    up_prob = 50 + score * 4.2

    if mom3 > 0.04:
        up_prob += 3
    elif mom3 < -0.04:
        up_prob -= 3

    if mom5 > 0.06:
        up_prob += 2
    elif mom5 < -0.06:
        up_prob -= 2

    if (
        distance is not None
        and seconds_left is not None
        and seconds_left <= 180
    ):
        if distance > 0:
            up_prob += 3
        elif distance < 0:
            up_prob -= 3

    up_prob = float(np.clip(up_prob, 5, 95))
    return round(up_prob), round(100 - up_prob)


# =========================================================
# MOTOR ORIGINAL v4.6.1
# =========================================================

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




def _structure_context(df, price, atr, rvol):
    """Same previous-20-candle levels used by the chart; no look-ahead.

    Distinguish confirmed breaks from rejection, rather than treating every
    touch of a level as a reversal. ATR scales the comparison to volatility.
    """
    candles = df.tail(22)
    if len(candles) < 21:
        return {"available": False, "support": None, "resistance": None,
                "up_blocked": False, "down_blocked": False, "event": "INSUFFICIENT_DATA"}
    prior = candles.iloc[-21:-1]
    last = candles.iloc[-1]
    support = float(prior["low"].min())
    resistance = float(prior["high"].max())
    op, hi, lo, close = (float(last[k]) for k in ("open", "high", "low", "close"))
    span = max(hi-lo, 1e-9)
    body = abs(close-op)
    upper_wick = hi-max(op, close)
    lower_wick = min(op, close)-lo
    # Rejection requires a level test and a meaningful counter-direction candle.
    rejection_up = (hi >= resistance and close < resistance and close < op
                    and upper_wick >= body * 0.7 and upper_wick/span >= .25)
    rejection_down = (lo <= support and close > support and close > op
                      and lower_wick >= body * 0.7 and lower_wick/span >= .25)
    # Confirmed continuation requires closing beyond the level with a body
    # in the breakout direction and volume or a meaningful ATR-sized body.
    break_up = (close > resistance and close > op and
                (rvol >= 1.15 or body >= atr*.45))
    break_down = (close < support and close < op and
                  (rvol >= 1.15 or body >= atr*.45))
    # Near a boundary without breakout confirmation, do not chase into it
    # when the last candle is already turning against the proposed entry.
    near_resistance = 0 <= resistance-price <= atr*.45
    near_support = 0 <= price-support <= atr*.45
    up_blocked = bool(rejection_up or (near_resistance and close < op and not break_up))
    down_blocked = bool(rejection_down or (near_support and close > op and not break_down))
    event = ("RESISTANCE_REJECTION" if rejection_up else
             "SUPPORT_REJECTION" if rejection_down else
             "BREAKOUT_UP" if break_up else "BREAKOUT_DOWN" if break_down else
             "NEAR_RESISTANCE" if near_resistance else
             "NEAR_SUPPORT" if near_support else "NONE")
    return {"available": True, "support": support, "resistance": resistance,
            "up_blocked": up_blocked, "down_blocked": down_blocked,
            "break_up": bool(break_up), "break_down": bool(break_down),
            "event": event}



def _level_decision_context(df, price, atr, seconds_left, target, mom3, rsi, rvol, whale):
    """Unified price-structure decision for the OFFICIAL signal only.

    Look for repeatedly tested zones, current rejection/continuation, and the
    remaining time relative to target distance. No fixed BTC dollar limits.
    """
    ctx = {"event":"NONE", "veto":None, "reversal":None,
           "support":None, "resistance":None, "breakout":None}
    if len(df) < 26 or not np.isfinite(atr) or atr <= 0:
        return ctx
    past = df.iloc[-65:-3]
    recent = df.iloc[-3:]
    if len(past) < 20:
        return ctx
    support = float(past["low"].min())
    resistance = float(past["high"].max())
    tol = float(atr) * .40
    upper_tests = int((past["high"] >= resistance-tol).sum())
    lower_tests = int((past["low"] <= support+tol).sum())
    latest = recent.iloc[-1]
    previous = recent.iloc[-2]
    close = float(latest["close"])
    prev_close = float(previous["close"])
    op = float(latest["open"])
    hi = float(latest["high"])
    lo = float(latest["low"])
    volume_ok = bool(rvol >= 1.05)
    whale = whale if isinstance(whale,dict) else {}
    buy = float(whale.get("buy30") or 0)
    sell = float(whale.get("sell30") or 0)
    bearish_pressure = mom3 < 0 and (rsi < 52 or sell > buy)
    bullish_pressure = mom3 > 0 and (rsi > 48 or buy > sell)
    # Breakout confirmation uses direction, continuation and volume/impulse.
    breakout_up = (close > resistance+tol and prev_close > resistance
                   and close >= prev_close and (volume_ok or mom3 > .04))
    breakout_down = (close < support-tol and prev_close < support
                     and close <= prev_close and (volume_ok or mom3 < -.04))
    ctx.update(support=support,resistance=resistance,
               resistance_tests=upper_tests,support_tests=lower_tests)
    if breakout_up:
        ctx.update(event="BREAKOUT_UP",breakout="UP")
        return ctx
    if breakout_down:
        ctx.update(event="BREAKOUT_DOWN",breakout="DOWN")
        return ctx
    # A rejection may begin with a wick, but requires a counter-move.
    rejected_resistance = (upper_tests >= 2
        and float(recent["high"].max()) >= resistance-tol
        and close < resistance and close < prev_close and bearish_pressure)
    rejected_support = (lower_tests >= 2
        and float(recent["low"].min()) <= support+tol
        and close > support and close > prev_close and bullish_pressure)
    if rejected_resistance:
        ctx.update(event="RESISTANCE_REJECTION",veto="UP",reversal="DOWN")
    elif rejected_support:
        ctx.update(event="SUPPORT_REJECTION",veto="DOWN",reversal="UP")
    else:
        # At an established boundary, don't chase an old trend into a new
        # counter-direction candle; no automatic opposite signal.
        if upper_tests >= 2 and resistance-tol <= price <= resistance+tol and close < op:
            ctx.update(event="RESISTANCE_WARNING",veto="UP")
        elif lower_tests >= 2 and support-tol <= price <= support+tol and close > op:
            ctx.update(event="SUPPORT_WARNING",veto="DOWN")
    # Close to settlement, countertrend calls need plausible target crossing.
    # Use observed recent volatility, not a fixed dollar or seconds cutoff.
    if ctx["reversal"] and seconds_left is not None and target is not None:
        seconds = max(0.,float(seconds_left))
        recent_speed = float(recent["close"].diff().abs().dropna().mean()) / 60.
        travel = max(recent_speed, float(atr)/60.*.35) * seconds
        distance = float(price)-float(target)
        required = max(0.,distance) if ctx["reversal"]=="DOWN" else max(0.,-distance)
        if seconds <= 0 or required > travel:
            ctx["reversal"] = None
            ctx["event"] += "_TARGET_UNREACHABLE"
    return ctx


def _opening_level_gate(df, price, atr, rvol, target=None):
    """Opening protection based on the SAME previous 20 candles as the chart.

    Block chasing a boundary, not a confirmed counter-direction rejection.
    A verified break can authorize continuation. This is an opening-entry
    gate, not a prohibition throughout the entire round.
    """
    result = {"blocked": ["UP", "DOWN"], "reason": "LEVEL_DATA_INSUFFICIENT",
              "support": None, "resistance": None,
              "break_up": False, "break_down": False}
    if (df is None or len(df) < 21 or price is None or target is None
            or not np.isfinite(float(price)) or not np.isfinite(float(target))
            or not np.isfinite(float(atr)) or float(atr) <= 0):
        return result
    ctx = _structure_context(df, float(price), float(atr), rvol)
    if not ctx.get("available"):
        return result
    support, resistance = ctx["support"], ctx["resistance"]
    width = float(atr) * .65
    near_support = abs(float(target)-support) <= width
    near_resistance = abs(float(target)-resistance) <= width
    blocked = []
    if near_resistance and not ctx["break_up"]:
        blocked.append("UP")
    if near_support and not ctx["break_down"]:
        blocked.append("DOWN")
    # When the target is clear, a live approach to the boundary also requires
    # rejection/breakout evidence before chasing through the level.
    if abs(float(price)-resistance) <= width and not ctx["break_up"]:
        blocked.append("UP")
    if abs(float(price)-support) <= width and not ctx["break_down"]:
        blocked.append("DOWN")
    result.update(blocked=list(dict.fromkeys(blocked)),
                  reason="OPENING_LEVEL_CAUTION" if blocked else "NONE",
                  support=support, resistance=resistance,
                  break_up=ctx["break_up"], break_down=ctx["break_down"])
    return result


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
    # One coherent structure evaluation, shared by all official entry routes.
    # PRESEÑAL is computed separately and is not modified.
    structure = _structure_context(df, price, atr, rvol)
    levels = _level_decision_context(
        df, price, atr, seconds_left, target, mom3, rsi1, rvol, whale)
    structure["level_decision"] = levels
    if levels["veto"] in ("UP", "DOWN"):
        eligible[levels["veto"]] = []
    if levels["reversal"] in ("UP", "DOWN"):
        side = levels["reversal"]
        opposite = "DOWN" if side == "UP" else "UP"
        if not eligible[opposite]:
            eligible[side].append({
                "name": "RECHAZO ESTRUCTURAL CONFIRMADO",
                "checks": [("Nivel probado previamente", True),
                           ("Rechazo y presión actual", True),
                           ("Tiempo y distancia al target compatibles", True)],
                "met": 3, "total": 3, "complete": True})
    # Preserve chart-level protection; confirmed breakouts may pass it.
    if structure["up_blocked"] and levels["breakout"] != "UP":
        eligible["UP"] = []
    if structure["down_blocked"] and levels["breakout"] != "DOWN":
        eligible["DOWN"] = []
    # Mandatory boundary gate on the OFFICIAL entry candidate, independent
    # of route scoring or EMA momentum. Presignal is untouched.
    opening_levels = _opening_level_gate(df, price, atr, rvol, target)
    structure["opening_level_gate"] = opening_levels
    for blocked_side in opening_levels["blocked"]:
        eligible[blocked_side] = []
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
    return {"price":price,"candle_price":candle_price,"rsi":rsi1,"rsi3":rsi3,"rsi5":rsi5,"mom3":mom3,"mom5":mom5,"mom15":mom15,"vol_ratio":rvol,"ema":"BULL" if l1["ema9"]>l1["ema21"] else "BEAR","technical_score":evidence,"target_score":target_atr,"final_score":evidence,"distance":distance,"distance_pct":distance_pct,"momentum":momentum,"up_probability":round(up_probability),"down_probability":round(down_probability),"candidate":candidate,"quality":quality,"trend3":d3,"trend5":d5,"adx":adx5,"plus_di":float(l5["plus_di"]),"minus_di":float(l5["minus_di"]),"macd3":float(l3["macd_hist"]),"macd5":float(l5["macd_hist"]),"atr":atr,"vwap":vwap,"vwap_atr":vwap_atr,"target_atr":target_atr,"impulse_internal":impulse,"entry_route_internal":quality,"flow_support_internal":flow_support,"flow_context_internal":flow_context,"structure_internal":structure,"macd1":float(l1["macd_hist"]),"price_ema9_atr":(price-float(l1["ema9"]))/atr}


def build_presignal(sig, seconds_left):
    """PRESEÑAL INDEPENDIENTE Y REACTIVA.

    Usa la lectura ACTUAL y, a medida que se acerca
    el cierre, reduce el peso de señales lentas (3M/5M) y aumenta el peso de la
    posición actual frente al target. Así puede girar UP/DOWN sin quedarse
    pegada a una tendencia vieja.
    """
    bull = 0.0
    bear = 0.0

    ema = sig.get("ema")
    rsi1 = float(sig.get("rsi", 50) or 50)
    rsi3 = float(sig.get("rsi3", 50) or 50)
    rsi5 = float(sig.get("rsi5", 50) or 50)
    mom3 = float(sig.get("mom3", 0) or 0)
    mom5 = float(sig.get("mom5", 0) or 0)
    trend3 = sig.get("trend3", "NEUTRAL")
    trend5 = sig.get("trend5", "NEUTRAL")
    macd3 = float(sig.get("macd3", 0) or 0)
    macd5 = float(sig.get("macd5", 0) or 0)
    plus_di = float(sig.get("plus_di", 0) or 0)
    minus_di = float(sig.get("minus_di", 0) or 0)
    vwap_atr = float(sig.get("vwap_atr", 0) or 0)
    target_atr = float(sig.get("target_atr", 0) or 0)

    secs = 900 if seconds_left is None else max(0, int(seconds_left))
    # Los marcos lentos importan al principio; cerca del cierre mandan menos.
    slow = 1.0 if secs > 300 else 0.70 if secs > 180 else 0.45 if secs > 90 else 0.25

    if ema == "BULL": bull += 0.85
    elif ema == "BEAR": bear += 0.85

    if trend3 == "UP": bull += 1.10 * slow
    elif trend3 == "DOWN": bear += 1.10 * slow
    if trend5 == "UP": bull += 0.90 * slow
    elif trend5 == "DOWN": bear += 0.90 * slow

    if rsi1 >= 52: bull += 0.90
    elif rsi1 <= 48: bear += 0.90
    if rsi3 >= 51: bull += 0.55 * slow
    elif rsi3 <= 49: bear += 0.55 * slow
    if rsi5 >= 52: bull += 0.30 * slow
    elif rsi5 <= 48: bear += 0.30 * slow

    if mom3 > 0.015: bull += 1.15
    elif mom3 < -0.015: bear += 1.15
    elif mom3 > 0: bull += 0.30
    elif mom3 < 0: bear += 0.30
    if mom5 > 0.025: bull += 0.55 * slow
    elif mom5 < -0.025: bear += 0.55 * slow

    if macd3 > 0: bull += 0.70 * slow
    elif macd3 < 0: bear += 0.70 * slow
    if macd5 > 0: bull += 0.35 * slow
    elif macd5 < 0: bear += 0.35 * slow
    if plus_di > minus_di: bull += 0.50 * slow
    elif minus_di > plus_di: bear += 0.50 * slow

    if vwap_atr >= 0.03: bull += 0.70
    elif vwap_atr <= -0.03: bear += 0.70

    # El target gana importancia progresivamente. No inventa dirección:
    # usa únicamente dónde está BTC respecto al target en este instante.
    if secs > 300:
        tw = 0.65
    elif secs > 180:
        tw = 1.40
    elif secs > 90:
        tw = 2.40
    elif secs > 30:
        tw = 3.60
    else:
        tw = 5.00

    # Magnitud: una separación mayor en ATR da más convicción, sin bloquear
    # cambios cuando BTC cruza el target.
    target_strength = min(1.75, 0.55 + abs(target_atr) * 2.25)
    if target_atr > 0:
        bull += tw * target_strength
    elif target_atr < 0:
        bear += tw * target_strength

    total = bull + bear
    edge = bull - bear
    if total < 1.5 or abs(edge) < 0.35:
        return {"direction":"NEUTRAL", "percent":50, "bull":bull, "bear":bear}

    direction = "UP" if edge > 0 else "DOWN"
    dominant = max(bull, bear)
    share = dominant / total if total else 0.5

    # Porcentaje propio de la preseñal. Puede llegar a 100 solo cuando la
    # lectura actual es realmente dominante; no copia la probabilidad oficial.
    percent = int(round(np.clip(50 + (share - 0.5) * 92 + min(abs(edge), 6.0) * 1.8, 52, 100)))

    return {"direction":direction, "percent":percent, "bull":bull, "bear":bear}

def entry_quality(price, seconds_left):
    if price is None:
        return "PRECIO NO DISPONIBLE", "#94a3b8"
    if price <= 0.60:
        return "BUENA", "#00dfb5"
    if price <= 0.70:
        return "PRECAUCIÓN", "#fbbf24"
    return "CARA", "#fb7185"


# =========================================================
# CONTROL DE RONDA — EL CEREBRO MANDA
# =========================================================

def _retention_assessment(state, signal):
    """Use the same evidence families as entry/reversal decisions."""
    side = state.get("active_direction")
    if side not in ("UP", "DOWN"):
        return 0, 0
    families = _direction_evidence(signal)
    return (sum(v == side for v in families.values()),
            sum(v != side for v in families.values()))


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
    """Report weakening without silently withdrawing a confirmed direction.

    Direction changes are handled by the same confirmation path as entries.
    """
    side = state.get("active_direction")
    if side not in ("UP", "DOWN"):
        _reset_withdrawal(state)
        return
    support, contrary = _retention_assessment(state, signal)
    _reset_withdrawal(state)
    if contrary > support and contrary >= 2:
        state["retention_warning"] = side + " PERDIENDO FUERZA • REEVALUANDO RESPALDO"


def _direction_evidence(signal):
    """Independent evidence families; price relative to target is NOT a trend vote."""
    if not isinstance(signal, dict) or signal.get("data_valid") is False:
        return {}
    families = {}
    ema = signal.get("ema")
    if ema in ("BULL", "BEAR"):
        families["trend"] = "UP" if ema == "BULL" else "DOWN"
    # Short and medium trend belong to one family; disagreement abstains.
    trends = [signal.get(k) for k in ("trend3", "trend5")]
    trends = [v for v in trends if v in ("UP", "DOWN")]
    if trends and len(set(trends)) == 1:
        families["structure"] = trends[0]
    rsi = _plan_number(signal.get("rsi"))
    if rsi is not None and abs(rsi - 50) >= 3:
        families["oscillator"] = "UP" if rsi > 50 else "DOWN"
    momentum = [_plan_number(signal.get(k)) for k in ("mom3", "mom5")]
    momentum = [v for v in momentum if v is not None and v != 0]
    if momentum and all(v > 0 for v in momentum):
        families["momentum"] = "UP"
    elif momentum and all(v < 0 for v in momentum):
        families["momentum"] = "DOWN"
    return families


def _direction_consistent(candidate, signal, active=None):
    """Single policy for entry and reversal, using nonduplicated families.

    Reversal requires stronger consensus than first entry; a transient
    oscillation cannot override a previously confirmed signal.
    """
    if candidate not in ("UP", "DOWN"):
        return False
    families = _direction_evidence(signal)
    if len(families) < 3:
        return False
    agree = sum(v == candidate for v in families.values())
    oppose = len(families) - agree
    if active in ("UP", "DOWN") and active != candidate:
        return agree >= 3 and oppose == 0
    return agree >= 3 and agree > oppose


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


def _kalshi_exit_quote(market, side):
    """Best displayed bid in dollars (not a guaranteed execution price)."""
    if not isinstance(market, dict):
        return None
    prefix = "yes" if side == "UP" else "no"
    quote = numeric_kalshi_price(market.get(prefix + "_bid_dollars"),
                                 market.get(prefix + "_bid"))
    return quote if quote is not None and 0 <= quote <= 1 else None


def _update_public_profit_alert(state, signal, market, seconds_left):
    """Round-level advisory; no user entry price, trading, or official signal changes."""
    side = state.get("active_direction")
    if side not in ("UP", "DOWN") or seconds_left is None or seconds_left <= 0:
        state["public_profit_alert"] = None
        return
    quote = _kalshi_exit_quote(market, side)
    if quote is None:
        state["public_profit_alert"] = None
        return
    # No extrapolation from the ask, BTC target, or the engine's support %.
    previous_peak = state.get("public_profit_peak")
    if state.get("public_profit_side") != side:
        previous_peak = None
    peak = max(float(previous_peak or 0), quote)
    state["public_profit_side"] = side
    state["public_profit_peak"] = peak
    try:
        short_momentum = float(signal.get("mom3") or 0)
        vwap_atr = float(signal.get("vwap_atr") or 0)
        probability = float(signal.get("up_probability") if side == "UP" else signal.get("down_probability"))
        direction = 1 if side == "UP" else -1
        weakening = (direction * short_momentum < 0 or direction * vwap_atr < -0.12
                     or probability < 55)
    except (TypeError, ValueError):
        weakening = False
    pullback = peak - quote >= 0.05
    # A high quote is not automatically a profit for every viewer.
    state["public_profit_alert"] = (
        {"side": side, "bid": round(quote * 100), "peak": round(peak * 100),
         "risk": bool(weakening or pullback)}
        if peak >= 0.80 and (weakening or pullback) else None
    )


def _confirmation_without_trace(state, candidate, market, seconds_left, now, signal=None):
    """One confirmation path for foreground and background. Neutral readings
    cancel pending candidates, never erase a confirmed active direction.
    """
    # A candidate is not a confirmation when the available directional
    # evidence contradicts it. Keep the active signal while reassessing.
    if candidate in ("UP", "DOWN") and not _direction_consistent(candidate, signal, state.get("active_direction")):
        candidate = None
    candidate = _round_opening_crosscheck(state, candidate, signal, now)
    level_gate = ((signal or {}).get("structure_internal") or {}).get("opening_level_gate") or {}
    # Opening-only veto. Once the round has a confirmed first direction,
    # subsequent retention/reversal is governed by its separate checks.
    if (state.get("first_direction") not in ("UP", "DOWN")
            and candidate in level_gate.get("blocked", ["UP", "DOWN"])):
        candidate = None

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

    _review_active_retention(state, signal, seconds_left, now)
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


def _process_round_signal_without_coordinator(ticker, sig, market, seconds_left):
    now = datetime.now(timezone.utc)

    if ticker and ticker != "--" and st.session_state.active_ticker != ticker:
        previous_ticker = st.session_state.active_ticker
        if previous_ticker and previous_ticker in st.session_state.rounds:
            save_round_history(st.session_state.rounds.get(previous_ticker))
        st.session_state.active_ticker = ticker
        restored = load_round_state(ticker)
        st.session_state.rounds[ticker] = restored if restored is not None else new_round_state(ticker, seconds_left)
        st.session_state.micro_ticker = ticker
        st.session_state.micro_prices = []

    if not ticker or ticker == "--":
        return {
            "decision":"NO TRADE","signal":"SIN RONDA","icon":"•","color":"#fbbf24",
            "round_state":None,"reversal":False,"reversal_text":"","entry_price":None,
            "entry_quality":"SIN DATOS","entry_quality_color":"#94a3b8",
        }

    if ticker not in st.session_state.rounds:
        restored = load_round_state(ticker)
        st.session_state.rounds[ticker] = restored if restored is not None else new_round_state(ticker, seconds_left)

    state = st.session_state.rounds[ticker]
    restored_from_disk = bool(state.pop("_restored_from_disk", False))
    if sig.get("data_valid") is False:
        confirm_round_candidate(state, None, market, seconds_left, now, sig)
        save_round_state(state)
        return {
            "decision":"ESPERANDO", "signal":"SIN DATOS ACTUALES",
            "icon":"•", "color":"#38bdf8", "round_state":state,
            "reversal":False, "reversal_text":"", "entry_price":None,
            "entry_quality":"SIN DATOS", "entry_quality_color":"#94a3b8",
        }
    score = float(sig.get("final_score", 0.0))
    price = float(sig.get("price", 0.0))
    distance_now = sig.get("distance")
    if distance_now is not None:
        try:
            state["last_target"] = price - float(distance_now)
        except Exception:
            pass

    # Referencia exclusiva de pantalla: el trabajador no consume este delta.
    display_previous = st.session_state.setdefault("weakness_previous", {})
    previous_observation = display_previous.get(ticker, {})
    previous_live_price = previous_observation.get("price")
    state["previous_live_price"] = previous_live_price
    state["last_live_price"] = price
    price_change = price - previous_live_price if previous_live_price is not None else 0.0

    previous_score = float(previous_observation.get("score", score))
    display_previous.clear()
    display_previous[ticker] = {"price": price, "score": score}
    state["previous_score"] = previous_score
    state["last_score"] = score
    score_change = score - previous_score

    # La señal oficial usa la dirección vigente del indicador.
    candidate = sig.get("candidate")
    if restored_from_disk and candidate not in ("UP", "DOWN"):
        # No se mantiene una señal antigua ante una lectura neutral actual.
        pass
    confirm_round_candidate(state, candidate, market, seconds_left, now, sig)

    active = state.get("active_direction")
    reversal = False
    reversal_text = ""

    # Aviso informativo solamente; nunca bloquea ni congela la señal.
    if active == "UP":
        weakness_points = 0
        if sig.get("impulse_internal", {}).get("exhaust_up"): weakness_points += 1
        if score < 0: weakness_points += 1
        if score_change <= -1.25: weakness_points += 1
        if sig.get("mom3",0) < -0.02: weakness_points += 1
        if sig.get("mom5",0) < 0: weakness_points += 1
        if price_change < -8: weakness_points += 1
        if weakness_points >= 2:
            reversal = True
            reversal_text = "UP PERDIENDO FUERZA • PRESIÓN CONTRARIA DETECTADA"

    elif active == "DOWN":
        weakness_points = 0
        if sig.get("impulse_internal", {}).get("exhaust_down"): weakness_points += 1
        if score > 0: weakness_points += 1
        if score_change >= 1.25: weakness_points += 1
        if sig.get("mom3",0) > 0.02: weakness_points += 1
        if sig.get("mom5",0) > 0: weakness_points += 1
        if price_change > 8: weakness_points += 1
        if weakness_points >= 2:
            reversal = True
            reversal_text = "DOWN PERDIENDO FUERZA • PRESIÓN CONTRARIA DETECTADA"

    if active and state.get("retention_warning"):
        reversal = True
        reversal_text = state["retention_warning"]
    state["reversal_warning"] = reversal
    state["reversal_text"] = reversal_text

    if active == "UP":
        decision, signal, icon, color = "UP","SEÑAL UP","⬆","#00dfb5"
        current_entry_price = get_yes_ask(market)
    elif active == "DOWN":
        decision, signal, icon, color = "DOWN","SEÑAL DOWN","⬇","#e64b4b"
        current_entry_price = get_no_ask(market)
    else:
        decision, signal, icon, color = "ESPERANDO",(state.get("opening_conflict") or
            ("CONFIRMANDO " + state["pending_direction"] if state.get("pending_direction") in ("UP","DOWN") else "SIN CONFIRMACIÓN")),"•","#38bdf8"
        current_entry_price = None

    quality, quality_color = entry_quality(current_entry_price, seconds_left)
    save_round_state(state)
    if seconds_left is not None and seconds_left <= 0:
        save_round_history(state)
    return {
        "decision":decision,"signal":signal,"icon":icon,"color":color,
        "round_state":state,"reversal":reversal,"reversal_text":reversal_text,
        "entry_price":current_entry_price,"entry_quality":quality,
        "entry_quality_color":quality_color,
    }


# =========================================================
# REGISTRADOR AUTÓNOMO CONTINUO — SOLO HISTORIAL
# Sigue leyendo las rondas aunque no haya una sesión de Streamlit abierta,
# siempre que el proceso del servidor siga encendido.
# NO modifica el motor, la preseñal, el lector, ballenas ni la interfaz.
# =========================================================

BACKGROUND_RUN_SECONDS = 12 * 60 * 60
BACKGROUND_POLL_SECONDS = 2
BACKGROUND_DATA_REVISION = "continuous_history_ia_shadow_v7_active_market_discovery_recent_support_v1_candle_sources_v2_early_signal_v2_multi_indicator49_v1"
_BACKGROUND_PRICE_SOURCE = threading.local()

def _background_get_btc_data():
    # Misma petición y misma comprobación de fechas para pantalla y fondo.
    return get_btc_data()

def _background_get_market():
    return get_kalshi_btc_market()

def _background_get_live_price(market):
    _BACKGROUND_PRICE_SOURCE.value = None
    try:
        if market:
            price = get_kalshi_live_btc(market)
            _BACKGROUND_PRICE_SOURCE.value = "KALSHI LIVE"
            return float(price)
    except Exception:
        pass
    response = requests.get(
        "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
        headers={"User-Agent": "MacalyAlphaBot/4.6.1", "Cache-Control": "no-cache"},
        params={"_": int(datetime.now(timezone.utc).timestamp())},
        timeout=6,
    )
    response.raise_for_status()
    data = response.json()
    price = _valid_live_observation(data.get("price"), data.get("time"), "COINBASE")
    _BACKGROUND_PRICE_SOURCE.value = "COINBASE"
    return price

# =========================================================
# ALPHA AI SHADOW — observational only; NEVER alters UP/DOWN
# Stores one immutable decision-time snapshot per ticker.
# Training labels must come from official Kalshi settlement.
# =========================================================
SHADOW_AI_DB = "alpha_ai_shadow.db"
SHADOW_FEATURES = ("rsi", "rsi3", "rsi5", "mom3", "mom5", "mom15", "vol_ratio",
                   "technical_score", "target_score", "adx", "macd3", "macd5",
                   "atr", "vwap_atr", "target_atr", "distance_pct")

def _shadow_capture(ticker, sig, state, seconds_left):
    """Read-only capture of existing engine output; no signal writes or model inference."""
    if not ticker or not isinstance(sig, dict) or seconds_left is None:
        return
    try:
        remaining = float(seconds_left)
        if not 0 < remaining <= 900:
            return
        price = float(sig.get("price"))
        target = float(state.get("last_target"))
        if not np.isfinite(price) or not np.isfinite(target) or target <= 0:
            return
        def safe_float(value):
            try:
                number = float(value)
                return number if np.isfinite(number) else None
            except (TypeError, ValueError, OverflowError):
                return None
        features = {name: safe_float(sig.get(name)) for name in SHADOW_FEATURES}
        # Store the engine's original proposal so the training label evaluates
        # the proposal, not the AI-filtered display result.
        signal = sig.get("candidate_raw", sig.get("candidate"))
        if signal not in ("UP", "DOWN"):
            # Wait for the first actual proposal; otherwise a neutral first poll
            # would permanently occupy this ticker's one-snapshot slot.
            return
        with sqlite3.connect(SHADOW_AI_DB, timeout=3) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS snapshots (
                ticker TEXT PRIMARY KEY, observed_at TEXT NOT NULL,
                seconds_left REAL NOT NULL, btc_price REAL NOT NULL,
                target REAL NOT NULL, candidate TEXT, features_json TEXT NOT NULL)""")
            conn.execute("""INSERT INTO snapshots
                (ticker, observed_at, seconds_left, btc_price, target, candidate, features_json)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(ticker) DO UPDATE SET
                    observed_at=excluded.observed_at,
                    seconds_left=excluded.seconds_left,
                    btc_price=excluded.btc_price,
                    target=excluded.target,
                    candidate=excluded.candidate,
                    features_json=excluded.features_json
                WHERE snapshots.candidate IS NULL AND excluded.candidate IS NOT NULL""",
                (str(ticker), datetime.now(timezone.utc).isoformat(), remaining,
                 price, target, signal, json.dumps(features, allow_nan=False)))
    except (sqlite3.Error, TypeError, ValueError, OverflowError):
        return

def _background_update_state_without_coordinator(state, sig, market, seconds_left):
    now = datetime.now(timezone.utc)
    price = float(sig.get("price", 0.0))
    target = get_target_from_market(market)
    if target is not None:
        state["last_target"] = float(target)
    state["previous_live_price"] = state.get("last_live_price")
    state["last_live_price"] = price
    state["last_seconds_left"] = seconds_left
    state["previous_score"] = float(state.get("last_score", 0.0))
    state["last_score"] = float(sig.get("final_score", 0.0))
    confirm_round_candidate(state, sig.get("candidate"), market, seconds_left, now, sig)
    save_round_state(state)
    _shadow_capture(state.get("ticker"), sig, state, seconds_left)
    return state

def _background_history_loop(stop_event=None):
    flow_state = {}
    started = time.monotonic()
    active_ticker = None
    active_state = None
    while not (stop_event and stop_event.is_set()):
        try:
            market = _background_get_market()
            if not market:
                time.sleep(BACKGROUND_POLL_SECONDS); continue
            ticker = str(market.get("ticker") or "--")
            if ticker == "--":
                time.sleep(BACKGROUND_POLL_SECONDS); continue
            if active_ticker and ticker != active_ticker and active_state:
                save_round_history(active_state)
                active_state = None
            if ticker != active_ticker:
                active_ticker = ticker
                restored = load_round_state(ticker)
                if restored:
                    restored.pop("_restored_from_disk", None)
                active_state = restored or new_round_state(ticker, get_seconds_remaining(market))
            seconds_left = get_seconds_remaining(market)
            target = get_target_from_market(market)
            live_price = _background_get_live_price(market)
            btc_df = _background_get_btc_data()
            try:
                background_whale = get_coinbase_whale_flow(flow_state)
            except Exception:
                background_whale = None
            sig = build_signal(btc_df, target, seconds_left, live_price,
                               getattr(_BACKGROUND_PRICE_SOURCE, "value", None),
                               whale=background_whale)
            if stop_event and stop_event.is_set():
                break
            active_state = _background_update_state(active_state, sig, market, seconds_left)
            _shadow_capture(ticker, sig, active_state, seconds_left)
            if seconds_left is not None and seconds_left <= 0:
                save_round_history(active_state)
        except Exception as exc:
            print(f"[ALPHA HISTORY WORKER] {type(exc).__name__}: {exc}")
        if stop_event:
            stop_event.wait(BACKGROUND_POLL_SECONDS)
        else:
            time.sleep(BACKGROUND_POLL_SECONDS)

def _retire_history_workers():
    """Retira solo registradores propios; las versiones antiguas no tenían Event."""
    current = None
    retiring = []
    restore = []
    for worker in threading.enumerate():
        if worker.name not in ("btc-history-canonical-v2", "btc-history-source-v1"):
            continue
        if worker is threading.current_thread() or not worker.is_alive():
            continue
        if getattr(worker, "_btc_data_revision", None) == BACKGROUND_DATA_REVISION and current is None:
            current = worker
            continue
        stop = getattr(worker, "_btc_stop_event", None)
        if stop is not None:
            stop.set()
        else:
            target = getattr(worker, "_target", None)
            context = getattr(target, "__globals__", None)
            if getattr(target, "__name__", None) != "_background_history_loop" or not isinstance(context, dict) or "BACKGROUND_RUN_SECONDS" not in context:
                raise RuntimeError("No se puede retirar el registrador anterior con seguridad. Reinicia la app en Streamlit.")
            if context is globals():
                restore.append((context, context["BACKGROUND_RUN_SECONDS"]))
            context["BACKGROUND_RUN_SECONDS"] = 0
        retiring.append(worker)
    deadline = time.monotonic() + 45
    for worker in retiring:
        worker.join(max(0, deadline - time.monotonic()))
    if any(worker.is_alive() for worker in retiring):
        raise RuntimeError("El registrador anterior sigue ocupado. Reinicia la app en Streamlit antes de continuar.")
    for context, value in restore:
        context["BACKGROUND_RUN_SECONDS"] = value
    return current

@st.cache_resource(validate=lambda worker: worker.is_alive() and getattr(worker, "_btc_data_revision", None) == BACKGROUND_DATA_REVISION)
def start_continuous_history_worker():
    current = _retire_history_workers()
    if current is not None:
        return current
    stop_event = threading.Event()
    worker = threading.Thread(target=_background_history_loop, args=(stop_event,), name="btc-history-source-v1", daemon=True)
    worker._btc_stop_event = stop_event
    worker._btc_data_revision = BACKGROUND_DATA_REVISION
    worker.start()
    return worker

# =========================================================
# LECTOR DE CIERRE PRO — MICRO LECTURA ~2 SEGUNDOS
# Mantiene intacto el motor v4.6.1 y sus señales.
# No inventa velas REST de 1 segundo: construye una cinta
# de muestras del BTC live que ya recibe el dashboard.
# =========================================================

def update_micro_tape(ticker, live_price, price_source=None):
    if not ticker or ticker == "--" or live_price is None:
        return

    # Cada ronda empieza con su propia cinta.
    if (st.session_state.micro_ticker != ticker
            or st.session_state.get("micro_price_source") != price_source):
        st.session_state.micro_ticker = ticker
        st.session_state.micro_price_source = price_source
        st.session_state.micro_prices = []

    now_ts = datetime.now(timezone.utc).timestamp()
    observed_ts = getattr(_PRICE_OBSERVATIONS, "values", {}).get(price_source)
    if (observed_ts is None or not np.isfinite(float(live_price))
            or not -5 <= now_ts - observed_ts <= LIVE_PRICE_MAX_AGE):
        st.session_state.micro_prices = []
        return
    tape = st.session_state.micro_prices

    # Una pausa rompe la ventana micro; volver a reunir datos continuos.
    if tape and observed_ts - tape[-1]["t"] > SIGNAL_CONFIRM_MAX_GAP:
        tape.clear()
    # Evita duplicar muestras dentro del mismo refresco.
    if not tape or observed_ts - tape[-1]["t"] >= 1.0:
        tape.append({"t": observed_ts, "p": float(live_price)})

    # Conserva aproximadamente los últimos 90 segundos.
    cutoff = now_ts - 90
    st.session_state.micro_prices = [
        x for x in tape if x["t"] >= cutoff
    ]


def micro_reading():
    tape = st.session_state.micro_prices
    if (tape and (datetime.now(timezone.utc).timestamp() - tape[-1]["t"] > 6
                  or any(b["t"] - a["t"] > SIGNAL_CONFIRM_MAX_GAP
                         for a, b in zip(tape, tape[1:])))):
        tape = []

    if len(tape) < 4:
        return {
            "ready": False,
            "change_5s": None,
            "change_10s": None,
            "change_30s": None,
            "slope": 0.0,
            "up_ratio": 0.5,
            "pressure": "NEUTRAL",
        }

    now_t = tape[-1]["t"]
    current = tape[-1]["p"]

    def price_ago(seconds):
        target_t = now_t - seconds
        candidates = [x for x in tape if x["t"] <= target_t]
        if candidates and target_t - candidates[-1]["t"] <= SIGNAL_CONFIRM_INTERVAL:
            return candidates[-1]["p"]
        return None

    p5 = price_ago(5)
    p10 = price_ago(10)
    p30 = price_ago(30)

    changes = [
        tape[i]["p"] - tape[i - 1]["p"]
        for i in range(1, len(tape))
    ]
    nonzero = [x for x in changes if x != 0]
    up_ratio = (
        sum(1 for x in nonzero if x > 0) / len(nonzero)
        if nonzero else 0.5
    )

    # Regresión simple precio/tiempo para medir dirección micro.
    xs = np.array([x["t"] - tape[0]["t"] for x in tape], dtype=float)
    ys = np.array([x["p"] for x in tape], dtype=float)
    slope = float(np.polyfit(xs, ys, 1)[0]) if len(xs) >= 3 and xs[-1] > 0 else 0.0

    c5 = current - p5 if p5 is not None else None
    c10 = current - p10 if p10 is not None else None
    c30 = current - p30 if p30 is not None else None

    if slope > 0.35 and up_ratio >= 0.58:
        pressure = "ALCISTA"
    elif slope < -0.35 and up_ratio <= 0.42:
        pressure = "BAJISTA"
    else:
        pressure = "NEUTRAL"

    return {
        "ready": p10 is not None and p30 is not None,
        "change_5s": c5,
        "change_10s": c10,
        "change_30s": c30,
        "slope": slope,
        "up_ratio": up_ratio,
        "pressure": pressure,
    }


def closing_reader(sig, round_signal, seconds_left, micro):
    """Pronóstico independiente UP/DOWN con apoyo derivado de la MISMA decisión.

    El cálculo no lee ni cambia el estado de confirmación/retirada del motor.
    Distancia, tiempo y muestras observadas generan una única puntuación con
    signo: positivo UP, negativo DOWN. El porcentaje expresa intensidad del
    apoyo de este modelo heurístico, NO probabilidad calibrada de acierto.
    """
    from math import isfinite, sqrt, tanh

    def finite(value):
        try:
            result = float(value)
            return result if isfinite(result) else None
        except (TypeError, ValueError, OverflowError):
            return None

    seconds = finite(seconds_left)
    distance = finite(sig.get("distance"))
    price = finite(sig.get("price"))
    if seconds is None or distance is None or price is None or price <= 0:
        return {
            "percent": 0, "direction": None, "headline": "SIN DATOS",
            "note": "Faltan precio, target o tiempo de ronda.",
            "micro": "SIN DATOS", "color": "#94a3b8",
            "border": "rgba(148,163,184,.45)",
            "bg": "linear-gradient(135deg,rgba(30,41,59,.45),rgba(9,23,34,.72))",
        }

    if seconds <= 0:
        return {
            "percent": 0, "direction": None, "headline": "RONDA TERMINADA",
            "note": "El resultado oficial debe verificarse en Kalshi.",
            "micro": "RONDA CERRADA", "color": "#94a3b8",
            "border": "rgba(148,163,184,.45)",
            "bg": "linear-gradient(135deg,rgba(30,41,59,.45),rgba(9,23,34,.72))",
        }

    # Volatilidad observada en velas de un minuto: no supone que el precio
    # puede mantener durante minutos la velocidad de sus últimos 5 segundos.
    atr = finite(sig.get("atr"))
    if atr is None or atr <= 0:
        atr = max(price * 0.0005, 1.0)
    horizon = max(seconds / 60.0, 1.0 / 60.0)
    price_range = max(atr * sqrt(horizon), 1.0)

    # La distancia se evalúa contra el movimiento plausible en el tiempo que
    # resta. Un pequeño retroceso no invalida automáticamente una ventaja amplia.
    score = 1.65 * (distance / price_range)
    observed = 0
    for window, weight in ((5, 0.32), (10, 0.43), (30, 0.25)):
        movement = finite(micro.get(f"change_{window}s"))
        if movement is not None:
            observed += 1
            # Reescala al tamaño normal de un movimiento en esa ventana.
            micro_range = max(atr * sqrt(window / 60.0), 1.0)
            score += weight * tanh(movement / micro_range)

    # Slope solo se usa si hay lecturas suficientes; no se interpreta 0.0
    # (valor por defecto cuando faltan datos) como velocidad real.
    if observed >= 2:
        slope = finite(micro.get("slope"))
        if slope is not None:
            micro_range = max(atr / sqrt(60.0), 0.15)
            score += 0.22 * tanh(slope / micro_range)

    # Si BTC coincide exactamente con el target, el movimiento observado
    # decide. Las velas recientes se usan como desempate, nunca la señal activa.
    if abs(score) < 1e-9:
        momentum = finite(sig.get("mom3")) or 0.0
        score = 0.12 * tanh(momentum / 0.10)
        if abs(score) < 1e-9:
            score = 0.001 if sig.get("ema") == "BULL" else -0.001

    direction = "UP" if score > 0 else "DOWN"
    # Dirección y apoyo están alineados: jamás DOWN con apoyo menor a 50 %.
    percent = int(round(50 + 50 * tanh(abs(score) / 1.75)))

    color = "#00dfb5" if direction == "UP" else "#e64b4b"
    border = "rgba(0,223,181,.48)" if direction == "UP" else "rgba(230,75,75,.48)"
    bg = ("linear-gradient(135deg,rgba(4,86,43,.46),rgba(7,36,25,.78))"
          if direction == "UP" else
          "linear-gradient(135deg,rgba(102,20,31,.48),rgba(43,10,17,.80))")
    return {
        "percent": percent, "direction": direction,
        "headline": direction, "note": "",
        "micro": "LECTURAS DISPONIBLES" if observed else "SIN MICROLECTURA",
        "color": color, "border": border, "bg": bg,
    }


def render_live_candles(df, live_price, target, active, timeframe="1m"):
    # Renderiza velas BTC/USD para visualización sin cambiar el motor v4.6.1.
    # 3m y 5m se construyen agrupando las velas reales de Coinbase de 1 minuto.
    if df is None or len(df) < 5:
        return f'<div class="chartbox"><div class="charttitle">BTC/USD · {timeframe}</div><div class="chartempty">Esperando velas…</div></div>'

    tf_minutes = {"1m": 1, "3m": 3, "5m": 5}.get(timeframe, 1)
    source_df = df.copy().sort_values("time")
    if tf_minutes > 1:
        d = (
            source_df.set_index("time")
            .resample(f"{tf_minutes}min", label="left", closed="left")
            .agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            })
            .dropna()
            .reset_index()
        )
    else:
        d = source_df[["time", "open", "high", "low", "close", "volume"]].copy()

    # Solo actualiza una vela abierta con un precio de la misma fuente.
    bucket_start = pd.Timestamp(datetime.now(timezone.utc)).floor(f"{tf_minutes}min")
    if live_price is not None and len(d) and pd.Timestamp(d.iloc[-1]["time"]) == bucket_start:
        i = d.index[-1]
        d.loc[i, "close"] = float(live_price)
        d.loc[i, "high"] = max(float(d.loc[i, "high"]), float(live_price))
        d.loc[i, "low"] = min(float(d.loc[i, "low"]), float(live_price))

    close = d["close"].astype(float)
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    d = d.tail(42).reset_index(drop=True)
    ema9 = ema9.tail(len(d)).reset_index(drop=True)
    ema21 = ema21.tail(len(d)).reset_index(drop=True)

    W, H = 760, 430
    left, right, top, bottom = 18, 142, 54, 82
    pw, ph = W-left-right, H-top-bottom
    vals = list(d["low"].astype(float)) + list(d["high"].astype(float))
    if target is not None: vals.append(float(target))
    if live_price is not None: vals.append(float(live_price))
    lo, hi = min(vals), max(vals)
    pad = max((hi-lo)*0.10, 8)
    lo, hi = lo-pad, hi+pad
    def y(v): return top + (hi-float(v))/(hi-lo)*ph
    n=len(d); step=pw/max(n,1); body=max(3.2, min(8, step*.58))

    svg=[]
    # horizontal grid + prices
    for k in range(5):
        yy=top+ph*k/4; price=hi-(hi-lo)*k/4
        svg.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{W-right}" y2="{yy:.1f}" stroke="#182536" stroke-width="1"/>')
        svg.append(f'<text x="{W-right+8}" y="{yy+4:.1f}" fill="#8392a7" font-size="12">{price:,.0f}</text>')
    # vertical grid
    for k in range(5):
        xx=left+pw*k/4
        svg.append(f'<line x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{top+ph}" stroke="#121e2d" stroke-width="1"/>')

    # volume scaled into bottom 52 px of plot
    vmax=max(float(d["volume"].max()),1)
    vbase=top+ph
    for i,row in d.iterrows():
        x=left+(i+.5)*step; vh=float(row["volume"])/vmax*48
        col='#16b97a' if float(row['close'])>=float(row['open']) else '#c43d59'
        svg.append(f'<rect x="{x-body/2:.1f}" y="{vbase-vh:.1f}" width="{body:.1f}" height="{vh:.1f}" fill="{col}" opacity=".55"/>')

    # candles
    for i,row in d.iterrows():
        x=left+(i+.5)*step
        o,c,h,l=map(float,[row['open'],row['close'],row['high'],row['low']])
        col='#00dfb5' if c>=o else '#e64b4b'
        svg.append(f'<line x1="{x:.1f}" y1="{y(h):.1f}" x2="{x:.1f}" y2="{y(l):.1f}" stroke="{col}" stroke-width="1.4"/>')
        yy=min(y(o),y(c)); hh=max(2.0,abs(y(o)-y(c)))
        svg.append(f'<rect x="{x-body/2:.1f}" y="{yy:.1f}" width="{body:.1f}" height="{hh:.1f}" rx=".7" fill="{col}"/>')

    # EMA paths
    def path(series,color):
        pts=' '.join(f'{left+(i+.5)*step:.1f},{y(v):.1f}' for i,v in enumerate(series))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
    svg.append(path(ema9,'#df42e7'))
    svg.append(path(ema21,'#32d7ef'))

    # target line
    if target is not None and lo <= float(target) <= hi:
        ty=y(target)
        svg.append(f'<line x1="{left}" y1="{ty:.1f}" x2="{W-right}" y2="{ty:.1f}" stroke="#23e7c1" stroke-width="1.8" stroke-dasharray="7 6"/>')
        # La etiqueta queda en el margen derecho, fuera del área de velas.
        svg.append(f'<rect x="{W-right+18}" y="{ty-12:.1f}" width="96" height="23" rx="3" fill="#20e7bd"/>')
        svg.append(f'<text x="{W-right+25}" y="{ty+4:.1f}" fill="#061510" font-size="10" font-weight="800">TARGET</text>')
    # live price line + label
    if live_price is not None and lo <= float(live_price) <= hi:
        ly=y(live_price); lc='#00dfb5' if active=='UP' else '#e64b4b' if active=='DOWN' else '#38bdf8'
        svg.append(f'<line x1="{left}" y1="{ly:.1f}" x2="{W-right}" y2="{ly:.1f}" stroke="{lc}" stroke-width="1.3" stroke-dasharray="3 4"/>')
        svg.append(f'<rect x="{W-right+18}" y="{ly-12:.1f}" width="96" height="23" rx="3" fill="{lc}"/>')
        svg.append(f'<text x="{W-right+25}" y="{ly+4:.1f}" fill="#061510" font-size="11" font-weight="900">{float(live_price):,.0f}</text>')

    # time labels
    picks=[0, max(0,n//3), max(0,2*n//3), n-1]
    for idx in picks:
        tm=d.iloc[idx]['time'].to_pydatetime().astimezone(ZoneInfo("America/New_York")).strftime('%-I:%M %p')
        xx=left+(idx+.5)*step
        svg.append(f'<text x="{xx:.1f}" y="{H-52}" text-anchor="middle" fill="#8392a7" font-size="11">{tm}</text>')

    last=d.iloc[-1]
    change=float(last['close'])-float(last['open'])
    pct=(change/float(last['open'])*100) if float(last['open']) else 0
    direction_color='#00dfb5' if change>=0 else '#e64b4b'
    target_label=f'${float(target):,.0f}' if target is not None else '--'
    return f'''<section class="chartbox">
      <div class="charttop"><div><b>BTC/USD · {timeframe}</b><span class="chartlive">● LIVE</span></div><div class="charttf">{timeframe}</div></div>
      <div class="ohlc">O {float(last['open']):,.0f} &nbsp; H {float(last['high']):,.0f} &nbsp; L {float(last['low']):,.0f} &nbsp; C {float(last['close']):,.0f} &nbsp; <strong style="color:{direction_color}">{change:+,.0f} ({pct:+.2f}%)</strong></div>
      <div class="indicators"><span class="ema9dot">●</span> EMA9 {float(ema9.iloc[-1]):,.0f} &nbsp;&nbsp; <span class="ema21dot">●</span> EMA21 {float(ema21.iloc[-1]):,.0f} &nbsp;&nbsp; <span class="targetdot">━</span> TARGET {target_label}</div>
      <svg class="candlesvg" viewBox="0 0 {W} {H}" preserveAspectRatio="none">{''.join(svg)}</svg>
      <div class="chartfoot"><span class="selected">{timeframe}</span><span>VELAS REALES COINBASE</span><span>ACTUALIZACIÓN LIVE</span></div>
    </section>'''


# =========================================================
# NAVEGACIÓN REAL — EL ENGRANAJE ABRE AJUSTES
# No muestra botones extra en la pantalla principal.
# =========================================================

def render_history_page():
    st.markdown("""
    <style>
    .settings-back{color:#d7e1ee!important;text-decoration:none!important;font-size:14px;font-weight:900}
    .settings-title{font-size:30px;font-weight:1000;color:#fff;margin:22px 0 4px}
    .settings-sub{font-size:14px;color:#c7d0dc;margin-bottom:20px}
    .history-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}
    .history-stat{background:#0d141d;border:1px solid #1d2b3a;border-radius:10px;padding:10px 5px;text-align:center}
    .history-label{font-size:9px;font-weight:1000;color:#fff!important;opacity:1!important;margin-bottom:7px}
    .history-value{font-size:22px;font-weight:1000;line-height:1}
    .history-note{margin-top:14px;color:#fff!important;opacity:1!important;font-size:10px;font-weight:900}
    
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

</style>""", unsafe_allow_html=True)
    df=load_history(2000); stats=history_stats(df)
    st.markdown(f"""
    <a class="settings-back" href="?page=signal" target="_self">← Señal</a>
    <div class="settings-title">⚙ Ajustes</div>
    <div class="settings-sub">Historial y rendimiento · registro automático por ronda</div>
    <div class="history-stats">
      <div class="history-stat"><div class="history-label">Rondas</div><div class="history-value" style="color:#54c6f5">{stats["total"]}</div></div>
      <div class="history-stat"><div class="history-label">Ganadas</div><div class="history-value" style="color:#00dfb5">{stats["wins"]}</div></div>
      <div class="history-stat"><div class="history-label">Perdidas</div><div class="history-value" style="color:#e64b4b">{stats["losses"]}</div></div>
      <div class="history-stat"><div class="history-label">Acierto</div><div class="history-value" style="color:#f7bd4d">{f"{stats['win_rate']:.1f}%" if stats['decided'] else "—"}</div></div>
    </div>
    <div class="history-note">Pendientes: {stats["pending"]} · NO TRADE: {stats["no_trade"]} · Acierto basado solo en resultados oficiales verificados.</div>
    """, unsafe_allow_html=True)



# =========================================================

# ORDER BOOK + ORDER FLOW: panel independiente, solo informativo.
@st.cache_data(ttl=5, show_spinner=False)
def get_coinbase_order_book():
    r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/book",
                     params={"level": 2}, timeout=6,
                     headers={"User-Agent": "MacalyAlphaBot/4.6.1"})
    r.raise_for_status()
    data = r.json()
    def notional(rows):
        value = 0.0
        for row in rows[:15]:
            price, size = float(row[0]), float(row[1])
            if not np.isfinite(price) or not np.isfinite(size) or price <= 0 or size < 0:
                raise ValueError("Nivel inválido")
            value += price * size
        return value
    bids, asks = data.get("bids", []), data.get("asks", [])
    if not bids or not asks:
        raise ValueError("Libro vacío")
    buy, sell = notional(bids), notional(asks)
    if buy + sell <= 0:
        raise ValueError("Sin liquidez")
    imbalance = (buy - sell) / (buy + sell)
    return {"direction": "UP" if imbalance >= .15 else "DOWN" if imbalance <= -.15 else None,
            "imbalance": imbalance, "reliable": True}


def get_order_flow_advisory(whale):
    if not whale:
        return {"direction": None, "imbalance": 0, "reliable": False}
    buy, sell = float(whale.get("buy30", 0) or 0), float(whale.get("sell30", 0) or 0)
    if buy + sell < 100_000:
        return {"direction": None, "imbalance": 0, "reliable": False}
    imbalance = (buy - sell) / (buy + sell)
    return {"direction": "UP" if imbalance >= .18 else "DOWN" if imbalance <= -.18 else None,
            "imbalance": imbalance, "reliable": True}


def render_intelligent_market_panel(book, flow, active):
    def describe(item):
        if not item or not item.get("reliable"):
            return "SIN DATOS", "—"
        d = item.get("direction")
        return ("PRESIÓN " + d if d else "EQUILIBRADO"), f"{abs(item['imbalance'])*100:.0f}%"
    book_label, book_pct = describe(book)
    flow_label, flow_pct = describe(flow)
    if not book or not flow.get("reliable"):
        headline, color, detail = "DATOS INSUFICIENTES", "#94a3b8", "Esperando lecturas válidas de Coinbase."
    elif book["direction"] and book["direction"] == flow["direction"]:
        direction = book["direction"]
        if active in ("UP", "DOWN"):
            contrary = active != direction
            headline = f"{active} EN RIESGO" if contrary else f"APOYO A {active}"
            color = "#ffb347" if contrary else ("#ef4444" if active == "DOWN" else "#00dfb5")
        else:
            headline, color = f"PRESIÓN CONJUNTA {direction}", ("#ef4444" if direction == "DOWN" else "#00dfb5")
        detail = "Order Book y Order Flow coinciden."
    else:
        headline, color, detail = "LECTURAS MIXTAS", "#e9bb66", "Sin confirmación conjunta entre indicadores."
    def pressure_color(label):
        return "#ef4444" if "DOWN" in label else "#00dfb5" if "UP" in label else "#cbd5e1"
    book_color = pressure_color(book_label)
    flow_color = pressure_color(flow_label)
    return f'''<section style="margin:12px 0;padding:18px;min-height:300px;display:flex;flex-direction:column;justify-content:center;border:1px solid {color};border-radius:18px;background:#0b1520;box-shadow:0 0 18px {color}20">
      <div style="font-size:13px;font-weight:900;color:#dce7f3">ANÁLISIS INTELIGENTE · BTC · COINBASE</div>
      <div style="margin-top:14px;font-size:clamp(25px,5vw,34px);font-weight:950;color:{color};text-shadow:0 0 16px {color}55">{headline}</div>
      <div style="margin-top:12px;font-size:14px;color:#cbd5e1"><b>ORDER BOOK:</b> <span style="color:{book_color};font-weight:900">{book_label} · {book_pct}</span></div>
      <div style="margin-top:9px;font-size:14px;color:#cbd5e1"><b>ORDER FLOW (30 s):</b> <span style="color:{flow_color};font-weight:900">{flow_label} · {flow_pct}</span></div>
      <div style="margin-top:14px;font-size:13px;color:#cbd5e1">{detail}</div>
      <div style="margin-top:15px;font-size:12px;color:#94a3b8">Solo informativo. No predice aciertos ni cambia la señal oficial. Las órdenes pueden cancelarse y el flujo puede ser incompleto.</div>
    </section>'''

# DETECTOR TEMPRANO DE REVERSIÓN (SOLO OBSERVACIÓN)
# Independiente: NO modifica build_signal, preseñal, ni señales oficiales.
# =========================================================

def detect_early_reversal(ticker, micro, whale, price):
    """Detector observacional autónomo: no consulta señal ni estado del cerebro.

    Busca un cambio de dirección entre el movimiento previo y los últimos
    10 segundos. El flujo Coinbase aporta contexto, no impide la lectura.
    """
    empty = {"status": "OBSERVANDO", "direction": None,
             "detail": "Reuniendo movimiento del precio.", "checks": 0}
    if ticker in (None, "--") or price is None:
        return empty
    tape = st.session_state.get("micro_prices", [])
    if len(tape) < 4 or not micro.get("ready"):
        return empty

    now = datetime.now(timezone.utc).timestamp()
    if now - float(tape[-1]["t"]) > 6:
        return {**empty, "detail": "Esperando precio actualizado."}

    last_t = float(tape[-1]["t"])
    current = float(tape[-1]["p"])
    def at_or_before(age):
        cutoff = last_t - age
        earlier = [x for x in tape if float(x["t"]) <= cutoff]
        return (float(earlier[-1]["p"])
                if earlier and cutoff - float(earlier[-1]["t"]) <= SIGNAL_CONFIRM_INTERVAL else None)

    p10 = at_or_before(10)
    p30 = at_or_before(30)
    if p10 is None or p30 is None:
        return {**empty, "detail": "Reuniendo 30 segundos de precio para comparar tendencias."}

    recent = current - p10
    previous = p10 - p30
    direction = None
    if previous < 0 and recent > 0:
        direction = "UP"
    elif previous > 0 and recent < 0:
        direction = "DOWN"

    buy = float((whale or {}).get("live_buy", 0) or 0)
    sell = float((whale or {}).get("live_sell", 0) or 0)
    total = buy + sell
    flow_direction = "UP" if buy > sell else "DOWN" if sell > buy else None
    flow_share = max(buy, sell) / total * 100 if total else 0
    detail = f"Tramo previo {previous:+.0f} USD · últimos 10s {recent:+.0f} USD"
    if total:
        detail += f" · flujo Coinbase {flow_direction} {flow_share:.0f}%"
    else:
        detail += " · flujo Coinbase no disponible"

    if direction:
        return {"status": "POSIBLE REVERSIÓN", "direction": direction,
                "detail": detail + " · cambio de dirección observado, no confirmado",
                "checks": 1}
    return {"status": "SIN REVERSIÓN OBSERVADA", "direction": None,
            "detail": detail, "checks": 0}


def render_early_reversal_panel(result):
    direction = result.get("direction")
    color = "#e64b4b" if direction == "DOWN" else "#00dfb5" if direction == "UP" else "#8fa3b8"
    title = result.get("status", "OBSERVANDO")
    detail = result.get("detail", "")
    return f'''<section style="margin:12px 0;padding:18px;min-height:300px;display:flex;flex-direction:column;justify-content:center;border:1px solid {color};border-radius:18px;background:#0b1520">
      <div style="font-size:13px;font-weight:900;color:#dce7f3">DETECTOR DE REVERSIÓN · EXPERIMENTAL</div>
      <div style="margin-top:14px;font-size:24px;line-height:1.3;font-weight:950;color:{color}">{title}{' → ' + direction if direction else ''}</div>
      <div style="margin-top:14px;font-size:14px;line-height:1.5;color:#cbd5e1">{detail}</div>
      <div style="margin-top:18px;font-size:12px;line-height:1.5;color:#94a3b8">Alerta informativa, no orden de compra ni predicción garantizada. No cambia la señal oficial.</div>
    </section>'''

# Panel visual independiente del motor. Sin envío de órdenes.
import html as _nh

@st.cache_data(ttl=10, show_spinner=False)
def _neon_chart_history(timeframe):
    granularity = {"15m": 900, "1h": 3600, "4h": 3600, "1D": 86400}[timeframe]
    response = requests.get(
        "https://api.exchange.coinbase.com/products/BTC-USD/candles",
        params={"granularity": granularity}, timeout=8,
        headers={"User-Agent": "BTCSignal/4.6.1-chart"},
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list) or not rows:
        raise ValueError("Sin velas para esta temporalidad")
    frame = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    return frame.sort_values("time").drop_duplicates("time")


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
    typical = (frame["high"] + frame["low"] + close)/3
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
    return {"rows": rows, "candle_source": df.attrs.get("candle_source", "COINBASE"), "timeframe": timeframe, "price": price or latest,
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

def render_neon_chart(df, live_price, target, active, timeframe, sig, whale, market=None, round_df=None):
    payload = _neon_payload(df, live_price, target, active, timeframe, sig, whale, market, round_df)
    return _NEON_HTML.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c"))

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
#rsi-pane{position:relative;overflow:hidden}
@media(max-width:480px){#canvas{height:375px!important}}
</style>
<section class="panel">
<!-- Panel BTC/USD y tarjetas visuales retirados. Se conservan los nodos que usa el JavaScript para actualizar datos. -->
<div style="display:none!important" aria-hidden="true"><span id="subtitle"></span><span id="price"></span><span id="live"></span><span id="signal"></span><span id="model"></span><span id="status"></span><span id="updated"></span></div>
<details id="whale"><summary>🐋 WHALE FLOW <small>EN VIVO · TOCA PARA ABRIR</small></summary><div class="detail"><h3>🐋 WHALE FLOW — LIVE</h3><div class="note">Operaciones observadas de Coinbase · últimos 30 s</div><div class="watch" id="watch"></div><div class="metrics"><div class="metric"><small>BUY FLOW</small><b class="green" id="buy"></b></div><div class="metric"><small>SELL FLOW</small><b class="red" id="sell"></b></div><div class="metric"><small>DIFERENCIA</small><b id="diff"></b></div><div class="metric"><small>ACTIVIDAD</small><b id="activity"></b></div><div class="metric"><small>FUERZA DEL DESEQUILIBRIO</small><b id="strength"></b></div></div><div class="bars"><div class="bar">BUY<div class="track"><i id="buybar" style="background:#00dfb5"></i></div><b id="buytotal"></b></div><div class="bar">SELL<div class="track"><i id="sellbar" style="background:#e64b4b"></i></div><b id="selltotal"></b></div></div><div class="count"><div class="metric"><small>🐋 BUY WHALES</small><b class="green" id="buys"></b></div><div class="metric"><small>🐋 SELL WHALES</small><b class="red" id="sells"></b></div></div><div class="metric difference"><small>DIFERENCIA DE OPERACIONES</small><b id="countdiff"></b></div><p class="note">«Whales»: operaciones individuales de al menos $10,000, no personas identificadas. Muestra recibida por la API; puede omitir operaciones entre consultas. Actividad: ritmo de los últimos 10 s frente a los 20 s anteriores. En el laboratorio, el flujo puede apoyar una candidatura solo con confirmación técnica; no decide por sí solo.</p></div></details>
<details id="momentum"><summary>⚡ SHORT-TERM MOMENTUM <small>EN VIVO · TOCA PARA ABRIR</small></summary><div class="detail"><h3>MOVIMIENTO RECIENTE DE BTC</h3><div class="metrics" id="momrows"></div><p class="note">Cambio porcentual calculado por el motor en 3, 5 y 15 minutos. La temporalidad de la gráfica no cambia estos valores.</p></div></details>
<div class="tools"><h3>INDICADORES</h3><div class="toggles" id="toggles"></div><div class="legend" id="legend"></div></div>
<div class="floatcounts"><div>🐋 BUY WHALES <b id="floatbuy"></b></div><div>🐋 SELL WHALES <b id="floatsell"></b></div></div>
<div class="tooltip" id="tooltip">Arrastra velas y escala de precios · pellizca para zoom · AHORA regresa al presente.</div><div class="canvas" id="canvas"></div><div id="rsi-pane" style="height:110px;display:none;background:#06121a;border-top:1px solid #294c69"></div>
<div class="chartnav"><button id="older" aria-label="Velas anteriores">←</button><button id="newer" aria-label="Velas siguientes">→</button><button id="zoomin" aria-label="Acercar">＋</button><button id="zoomout" aria-label="Alejar">−</button><button id="reset">AHORA</button><span id="viewtf"></span></div>
</section>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
let D=__PAYLOAD__; const $=id=>document.getElementById(id), fmt=(v,n=2)=>v==null?'—':Number(v).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n}), usd=v=>v==null?'—':'$'+fmt(v), compact=v=>v==null?'—':v>=1e6?'$'+(v/1e6).toFixed(2)+'M':v>=1000?'$'+(v/1000).toFixed(0)+'K':'$'+fmt(v,0);
let saved={};try{saved=JSON.parse(localStorage.getItem('btc-neon-panel-v1')||'{}')}catch(e){}
let toggles=Object.assign({ema9:true,ema21:true,vwap:true,volume:true,rsi:true,},saved.toggles),visible=saved.visible||32,offset=saved.offset||0,pricePan=Number.isFinite(saved.pricePan)?saved.pricePan:0;
function persist(){try{localStorage.setItem('btc-neon-panel-v1',JSON.stringify({toggles,visible,offset,pricePan,whale:$('whale').open,momentum:$('momentum').open}))}catch(e){}}
for(const name of ['whale','momentum']){$(name).open=!!saved[name];$(name).addEventListener('toggle',persist)}
function refreshLabels(){
$('subtitle').textContent=D.timeframe.toUpperCase()+' · '+(D.candle_source||'COINBASE')+' · BTC SIGNAL';$('price').textContent=usd(D.price);$('live').textContent=D.price==null?'● SIN COTIZACIÓN':'● PRECIO RECIBIDO';$('model').textContent=fmt(D.signal==='UP'?D.up:D.signal==='DOWN'?D.down:Math.max(D.up,D.down),1)+'%';$('status').textContent=D.rows.length?'DATOS RECIBIDOS':'SIN VELAS';$('updated').textContent='Actualizado '+D.updated;$('viewtf').textContent=D.timeframe+' · VELAS REALES';
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
 if(!newN){applyingData=false;return;}
 candleSeries.setData(newC);
 for(const k of ['ema9','ema21','vwap']){overlays[k].setData(seriesRows(k));overlays[k].applyOptions({visible:!!toggles[k]});}
 volumeSeries.setData((D.rows||[]).filter(r=>Number.isFinite(r.t)&&Number.isFinite(r.volume)).map(r=>({time:r.t,value:r.volume,color:r.close>=r.open?'#00dfb573':'#e64b4b73'})));
 volumeSeries.applyOptions({visible:!!toggles.volume});
 rsiSeries.setData(seriesRows('rsi'));
 $('rsi-pane').style.display=toggles.rsi?'block':'none';
 for(const l of levelLines)candleSeries.removePriceLine(l);levelLines=[];
 for(const [value,label,color] of [[D.target,'TARGET','#f1c46b'],[D.support,'SUPPORT','#00dfb5'],[D.resistance,'RESISTANCE','#e64b4b']]){
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


def signal_requirement_view(sig, seconds_left):
    return _entry_route_checks(sig, seconds_left)


def render_signal_requirements(sig, round_signal, market, seconds_left, now=None):
    """One visual box for individual conditions; never changes confirmation."""
    view = signal_requirement_view(sig, seconds_left)
    state = round_signal.get('round_state') or {}
    now = now or datetime.now(timezone.utc)
    end = pd.to_datetime((market or {}).get('close_time'), utc=True, errors='coerce')
    closed = seconds_left is not None and seconds_left <= 0
    if not pd.isna(end):
        closed = closed or end <= pd.Timestamp(now)
    ready = view['valid'] and bool(state) and not closed and not pd.isna(end)
    side = sig.get('candidate')
    if side not in ('UP', 'DOWN'):
        # La dirección histórica no decide qué requisitos se inspeccionan.
        # Sin candidatura válida, mostrar el lado de mayor evidencia ACTUAL,
        # sin convertirlo en señal oficial.
        current_score = sig.get('final_score')
        if current_score is not None:
            try:
                value = float(current_score)
                if np.isfinite(value) and value != 0:
                    side = 'UP' if value > 0 else 'DOWN'
            except (TypeError, ValueError):
                pass
    if side not in ('UP', 'DOWN') and view['valid']:
        side = max(('UP', 'DOWN'), key=lambda d: max(r['met']/r['total'] for r in view['sides'][d]))
    checks = []
    if view['valid'] and side in ('UP', 'DOWN'):
        routes = view['sides'][side]
        # Mostrar solo rutas de tendencia y entrada temprana.
        complete = [r for r in routes if r['complete']]
        route = complete[0] if complete else max(routes, key=lambda r: r['met']/r['total'])
        checks = route['checks']
    total = len(checks)
    met = sum(bool(ok) for _, ok in checks) if ready else 0
    # Cada nombre corresponde al mismo booleano que controla su barra.
    bars = ''.join(
        '<div class="sq-item"><i' + (' class="sq-on"' if ready and ok else '') +
        ' title="' + html.escape(label, quote=True) + '"></i>' +
        '<span>' + html.escape(label) + '</span></div>'
        for label, ok in checks
    )
    label = 'REQUISITOS ' + side if side in ('UP','DOWN') else 'REQUISITOS DE LA SEÑAL'
    note = 'RONDA TERMINADA' if closed else 'ESPERANDO DATOS' if not ready else 'Cada barra representa un requisito.'
    number = str(met) + '<small>/' + str(total) + '</small>' if total else '—'
    return '<style>.sq-box{margin:12px 0;padding:18px;border:1px solid #23685e;border-radius:18px;background:linear-gradient(125deg,#0c2026,#0a151e);color:#eef5f8}.sq-title{font-size:11px;font-weight:800;letter-spacing:1.5px;color:#8ca1ab}.sq-number{font-size:38px;font-weight:900;margin:14px 0;line-height:1.1}.sq-number small{font-size:20px;color:#81949f}.sq-bars{display:flex;gap:7px;margin:14px 0}.sq-bars .sq-item{flex:1;min-width:0;text-align:center}.sq-bars i{display:block;height:7px;width:100%;background:#1d3038;border-radius:9px}.sq-bars .sq-item span{display:block;margin-top:7px;font-size:9px;line-height:1.25;color:#a5b6be;overflow-wrap:anywhere}.sq-bars .sq-on{background:#00dfb5;box-shadow:0 0 10px #00dfb54d}.sq-note{font-size:11px;color:#a5b6be}.sq-down .sq-bars .sq-on{background:#e64b4b;box-shadow:0 0 10px #e64b4b4d}</style><section class="sq-box' + (' sq-down' if side == 'DOWN' else '') + '"><div class="sq-title">' + label + '</div><div class="sq-number">' + number + '</div><div class="sq-bars">' + bars + '</div><div class="sq-note">' + note + '</div></section>'


@st.fragment(run_every="2s")
def live_dashboard():
    btc_error = ""
    live_price_error = ""
    kalshi_error = ""
    kalshi_live_error = ""

    try:
        btc_df = add_indicators(get_btc_data())
        btc_ok = True
    except Exception as error:
        btc_ok = False
        btc_error = str(error)
        btc_df = None

    try:
        market = get_kalshi_btc_market()
        kalshi_ok = market is not None
        if market and market.get("_round_refresh_error"):
            kalshi_error = market["_round_refresh_error"]
    except Exception as error:
        kalshi_ok = False
        kalshi_error = str(error)
        market = None

    try:
        coinbase_live_price = get_btc_live_price()
        coinbase_live_ok = True
    except Exception as error:
        coinbase_live_ok = False
        live_price_error = str(error)
        coinbase_live_price = (
            float(btc_df.iloc[-1]["close"]) if btc_ok else None
        )

    kalshi_live_price = None
    kalshi_live_ok = False

    if market:
        try:
            kalshi_live_price = get_kalshi_live_btc(market)
            kalshi_live_ok = True
        except Exception as error:
            kalshi_live_error = str(error)

    if kalshi_live_price is not None:
        live_btc_price = kalshi_live_price
        source = "KALSHI LIVE"
    else:
        live_btc_price = coinbase_live_price
        source = (
            "COINBASE"
            if coinbase_live_ok else
            "COINBASE CANDLE" if live_btc_price is not None else "SIN DATOS"
        )

    if market:
        ticker = market.get("ticker", "--")
        target = get_target_from_market(market)
        seconds_left = get_seconds_remaining(market)
    else:
        ticker = "--"
        target = None
        seconds_left = None

    # Una sola lectura de Whale Flow por ciclo; la misma alimenta el panel.
    try:
        whale = get_coinbase_whale_flow()
    except Exception:
        whale = None

    if btc_ok:
        sig = build_signal(
            btc_df, target, seconds_left, live_btc_price, source, whale=whale
        )
    else:
        _TRACE_CONTEXT.build_id = None
        _TRACE_CONTEXT.build_payload = None
        sig = {
            "data_valid": False,
            "data_error": btc_error,
            "price": live_btc_price if live_btc_price is not None else 0,
            "candle_price": 0,
            "rsi": 50,
            "mom3": 0,
            "mom5": 0,
            "mom15": 0,
            "vol_ratio": 0,
            "ema": "N/A",
            "technical_score": 0,
            "target_score": 0,
            "final_score": 0,
            "distance": None,
            "distance_pct": None,
            "momentum": "NEUTRAL",
            "up_probability": 50,
            "down_probability": 50,
        }

    round_signal = process_round_signal(
        ticker, sig, market, seconds_left
    )
    # Cinta live de segundos para el Lector de Cierre.
    update_micro_tape(ticker, live_btc_price, source)
    micro = micro_reading()
    # El panel permanece visible; solo la predicción se activa en los últimos 90 segundos.
    # La cinta de precios y las métricas continúan actualizándose durante toda la ronda.
    reader_active = seconds_left is not None and 0 < seconds_left <= 90
    reader = closing_reader(sig, round_signal, seconds_left, micro)
    if not btc_ok:
        reader = {**reader, "percent":0, "headline":"SIN DATOS ACTUALES",
                  "note":"No se puede validar la señal hasta recuperar las velas."}
    reader_percent_label = f"{reader['percent']}%" if reader.get("direction") and btc_ok else "—"
    if seconds_left is not None and seconds_left <= 0:
        # El reloj y el precio instantáneo no prueban la liquidación oficial.
        reader = {**reader, "percent": 0,
                  "headline": "RONDA TERMINADA · RESULTADO PENDIENTE",
                  "note": "Esperando verificación del resultado oficial de Kalshi."}
        reader_percent_label = "—"

    # Whale Flow: panel visual y apoyo opcional a candidatura en el laboratorio.
    # No se consulta por segunda vez ni modifica las confirmaciones temporales.

    state = round_signal.get("round_state")
    active = (
        state.get("active_direction")
        if state and btc_ok
        else None
    )

    # Read-only notices. These do not alter the official UP/DOWN or trading.
    # Render del panel de ballenas. Solo visual; no altera el motor v4.6.1.
    try:
        order_book = get_coinbase_order_book()
    except Exception:
        order_book = None
    order_flow = get_order_flow_advisory(whale)

    if active == "UP":
        accent = "#00dfb5"
        glow = "rgba(0,223,181,.46)"
        soft = "rgba(0,223,181,.10)"
        hero = "↑ UP"
        confidence = sig["up_probability"]
    elif active == "DOWN":
        accent = "#e64b4b"
        glow = "rgba(230,75,75,.45)"
        soft = "rgba(230,75,75,.10)"
        hero = "↓ DOWN"
        confidence = sig["down_probability"]
    else:
        accent = "#38bdf8"
        glow = "rgba(56,189,248,.30)"
        soft = "rgba(56,189,248,.09)"
        hero = None
        confidence = max(
            sig["up_probability"], sig["down_probability"]
        )

    market_live = kalshi_ok and live_btc_price is not None

    distance = sig["distance"]
    distance_pct = sig.get("distance_pct")
    up = int(sig["up_probability"])
    down = int(sig["down_probability"])
    target_text = f"${target:,.0f}" if target is not None else "--"
    countdown = format_countdown(seconds_left)

    if distance is None:
        distance_text, distance_sub = "--", "SIN TARGET"
        distance_color = "#94a3b8"
    else:
        distance_text = f"${abs(distance):,.0f}"
        distance_sub = f"{abs(distance_pct):.2f}%"
        distance_color = "#00dfb5" if distance > 0 else "#e64b4b" if distance < 0 else "#94a3b8"
    first_signal, first_time = "--", "--"
    first_display = st.session_state.get("first_signal_display")
    if first_display is not None and first_display[0] != ticker:
        st.session_state.pop("first_signal_display")
        first_display = None
    if first_display is None and active in ("UP", "DOWN") and state.get("ticker") == ticker:
        side = state.get("first_direction")
        signal_dt = state.get("first_signal_time")
        if side in ("UP", "DOWN") and signal_dt is not None:
            if signal_dt.tzinfo is None:
                signal_dt = signal_dt.replace(tzinfo=timezone.utc)
            clock = signal_dt.astimezone(ZoneInfo("America/New_York")).strftime("%-I:%M %p")
            first_display = (ticker, side, clock)
            st.session_state["first_signal_display"] = first_display
    if first_display is not None:
        _, first_signal, first_time = first_display
    first_color = {"UP": "#00dfb5", "DOWN": "#e64b4b"}.get(first_signal, "#38bdf8")

    # Etiqueta visual en español; el motor conserva internamente BULL/BEAR.
    ema_display = "ALCISTA" if sig.get("ema") == "BULL" else "BAJISTA" if sig.get("ema") == "BEAR" else sig.get("ema", "N/A")

    # PRESEÑAL independiente: permanece visible toda la ronda y NO copia
    # las probabilidades oficiales.
    ut = sig.get("ut_signal") or {}
    pre = sig.get("presignal") or build_presignal(sig, seconds_left)
    pre_direction = pre["direction"]
    pre_percent = pre["percent"]

    if pre_direction == "UP":
        pre_color, pre_bg, pre_glow = "#00dfb5", "rgba(18,91,57,.26)", "rgba(0,223,181,.20)"
        pre_label = "POSIBLE UP"
    elif pre_direction == "DOWN":
        pre_color, pre_bg, pre_glow = "#e64b4b", "rgba(104,25,37,.28)", "rgba(230,75,75,.20)"
        pre_label = "POSIBLE DOWN"
    else:
        pre_color, pre_bg, pre_glow = "#38bdf8", "rgba(24,73,101,.24)", "rgba(56,189,248,.18)"
        pre_label = "NEUTRAL"

    pre_badge = "COINCIDE CON LA SEÑAL" if active in ("UP", "DOWN") and pre_direction == active else "DIFIERE DE LA SEÑAL" if active in ("UP", "DOWN") and pre_direction in ("UP", "DOWN") else "OBSERVANDO"

    pre_html = f'''<section class="presignal" style="--precolor:{pre_color};--prebg:{pre_bg};--preglow:{pre_glow}">
      <div class="prehead"><span class="pretitle">PRESEÑAL</span><span class="prebadge">{pre_badge}</span></div>
      <div class="premain"><span class="predirection">{pre_label}</span><span class="prepercent">{pre_percent}%</span></div>
      <div class="prebar"><b style="width:{pre_percent}%"></b></div>
    </section>'''

    if active == "UP":
        hero_arrow, hero_word = "", "UP"
        btc_delta = f"{sig['mom3']:+.2f}%"
    elif active == "DOWN":
        hero_arrow, hero_word = "", "DOWN"
        btc_delta = f"{sig['mom3']:+.2f}%"
    else:
        hero_arrow, hero_word = "•", "ESPERANDO"
        btc_delta = f"{sig['mom3']:+.2f}%"

    ema_class = "green" if sig["ema"] == "BULL" else "red"
    rsi_class = "green" if sig["rsi"] >= 55 else "red" if sig["rsi"] <= 45 else ""
    mom_class = "green" if sig["mom3"] > 0 else "red" if sig["mom3"] < 0 else ""
    time_pct = max(0, min(100, int((seconds_left or 0) / 900 * 100)))

    # Panel de cierre de últimos segundos — solo lectura; NO cambia la señal principal.
    c30 = float(micro.get("change_30s", 0.0) or 0.0)
    c10 = float(micro.get("change_10s", 0.0) or 0.0)
    c5 = float(micro.get("change_5s", 0.0) or 0.0)
    motion_labels = {}
    for window in (5, 10, 30):
        value = micro.get(f"change_{window}s")
        motion_labels[window] = "—" if value is None else f"{'↑' if value > 0 else '↓' if value < 0 else '→'}<br>{value:+.0f}"
    speed_ready = micro.get("change_10s") is not None
    speed10 = c10 / 10.0
    speed_word = "SUBIENDO" if speed10 > 0.15 else "BAJANDO" if speed10 < -0.15 else "ESTABLE"
    speed_arrow = "↑" if speed10 > 0.15 else "↓" if speed10 < -0.15 else "→"
    speed_value = f"{speed10:+.1f}/s" if speed_ready else "—"
    if not speed_ready:
        speed_word, speed_arrow = "REUNIENDO DATOS", ""
    speed_color = "#00dfb5" if speed10 > 0.15 else "#e64b4b" if speed10 < -0.15 else "#94a3b8"
    market_side = "UP" if (distance or 0) > 0 else "DOWN" if (distance or 0) < 0 else "NEUTRAL"
    abs_final_distance = abs(distance or 0)

    # En el tramo final, tiempo + posición REAL frente al target mandan en este cuadro.
    # Así no muestra "CIERRE MUY DISPUTADO" solo porque la señal vieja o la velocidad
    # contradigan el lado que realmente está ganando a segundos del cierre.
    if seconds_left is not None and seconds_left <= 60 and market_side != "NEUTRAL":
        final_status = f"VENTAJA ACTUAL {market_side}"
        final_note = (
            f"Quedan {seconds_left}s · BTC está ${abs_final_distance:,.0f} "
            f"{'arriba' if distance > 0 else 'abajo'} del target · "
            f"ahora favorece {market_side}."
        )
    elif active in ("UP", "DOWN"):
        if market_side == active and ((active == "UP" and speed10 >= -0.15) or (active == "DOWN" and speed10 <= 0.15)):
            final_status = f"AÚN FAVORABLE A {active}"
            final_note = f"El precio se mantiene {'sobre' if active == 'UP' else 'bajo'} el target, con presión inmediata controlada."
        elif market_side != "NEUTRAL" and market_side != active and abs_final_distance >= 5:
            final_status = f"POSICIÓN ACTUAL {market_side}"
            final_note = f"BTC está al otro lado del target y la lectura actual favorece {market_side}."
        else:
            final_status = f"AÚN FAVORABLE A {market_side}" if market_side != "NEUTRAL" else "SIN VENTAJA CLARA"
            final_note = "La lectura sigue el lado actual del target y el movimiento reciente."
    else:
        final_status = f"VENTAJA FINAL {market_side}" if market_side != "NEUTRAL" else "SIN VENTAJA FINAL"
        final_note = "Lectura independiente basada en distancia, tiempo restante y movimiento de los últimos segundos."
    if seconds_left is None or seconds_left > 60:
        # Fuera del tramo final, esto describe posición, no pronostica cierre.
        final_status = f"POSICIÓN ACTUAL {market_side}" if market_side != "NEUTRAL" else "SIN VENTAJA ACTUAL"
        final_note = "Posición actual frente al target; todavía no es una lectura del cierre final."
    if seconds_left is not None and seconds_left <= 0:
        final_status = "RESULTADO OFICIAL PENDIENTE"
        final_note = "El precio mostrado al terminar no confirma la liquidación del contrato."
    final_distance_label = f"${abs(distance):,.0f}" if distance is not None else "—"
    final_dist_pct_label = f"{abs(distance_pct):.2f}%" if distance_pct is not None else "SIN TARGET"
    final_panel = f'''<div class="finalclose">
      <div class="finalgrid">
        <div class="finalcard motion"><div class="finaltitle">▥ &nbsp; MOVIMIENTO ÚLTIMOS SEGUNDOS</div><div class="motionrow">
          <div><small>30s</small><b style="color:{'#00dfb5' if c30>=0 else '#e64b4b'}">{motion_labels[30]}</b></div>
          <div><small>10s</small><b style="color:{'#00dfb5' if c10>=0 else '#e64b4b'}">{motion_labels[10]}</b></div>
          <div><small>5s</small><b style="color:{'#00dfb5' if c5>=0 else '#e64b4b'}">{motion_labels[5]}</b></div>
        </div></div>
        <div class="finalcard distance"><div class="finaltitle">▥ &nbsp; DISTANCIA AL TARGET</div><div class="finalbig" style="color:{distance_color}">{final_distance_label}</div><div class="finalsub" style="color:{distance_color}">{final_dist_pct_label}</div></div>
        <div class="finalcard speed"><div class="finaltitle">VELOCIDAD</div><div class="finalbig" style="color:{speed_color}">{speed_arrow} {speed_word}</div><div class="finalsub" style="color:{speed_color}">{speed_value}</div></div>
      </div>
      <div class="finalanalysis">
        <div class="analysisbox"><div class="analysisicon">◎</div><div class="analysistext"><small>POSICIÓN ACTUAL</small><b>{final_status}</b></div></div>
        <div class="probbox"><small>{'APOYO A ' + reader['direction'] if reader_active and reader.get('direction') else 'APOYO CALCULADO'}</small><b>{reader_percent_label}</b></div>
      </div>
    </div>'''

    # Advertencia compacta únicamente visual; usa el aviso existente del motor.
    ut_warning = active in ("UP", "DOWN") and ut.get("ut_short") in ("UP", "DOWN") and ut["ut_short"] != active
    profit_notice = state.get("public_profit_alert") if state else None
    # Independent notices: neither hides the other or modifies the signal.
    weakness_html = (
        '<div class="weakness-inline" role="status">⚠ ' +
        html.escape(f"{active} PERDIENDO FUERZA" if ut_warning else round_signal.get("reversal_text") or "SEÑAL PERDIENDO FUERZA") +
        '</div>'
        if (ut_warning or round_signal.get("reversal")) and active in ("UP", "DOWN") else ""
    )
    if active in ("UP", "DOWN") and isinstance(profit_notice, dict):
        weakness_html += '<div class="weakness-inline" role="status">💰 ASEGURAR GANANCIAS</div>'

    reader_html = f'''
  <section class="reader jcclose" style="--rb:{reader['border']};--rbg:{reader['bg']};--rr:{reader['color']}">
    <div class="jcclose-title"><span><span class="jcclose-symbol">◎</span> LECTOR DE CIERRE</span><em>{"● ACTIVO" if reader_active else "● LEYENDO"}</em></div>
    <div class="jcclose-main">
      <div class="jcclose-signal" style="--signal:{reader['color']};visibility:{'visible' if reader_active else 'hidden'}">
        <span class="jcclose-double">{'❯❯' if reader.get('direction') == 'UP' else '❮❮' if reader.get('direction') == 'DOWN' else '◌'}</span>
        <strong>{reader.get('direction') or '—'}</strong>
      </div>
      <div class="jcclose-dial" style="--p:{reader['percent']};--dial:{reader['color']}"><span>{reader_percent_label}</span></div>
    </div>
    {final_panel}
  </section>

'''

    panel_html = f"""
<style>
/* app 31: conserve el encabezado dibujado en el fondo; solo un logo y titulo. */
.refapp .rhead.jc-bg-header {{
  display:block!important;visibility:visible!important;position:relative!important;
  height:154px!important;min-height:154px!important;max-height:154px!important;
  padding:0!important;margin:0!important;overflow:visible!important;
  background:transparent!important;box-shadow:none!important;
}}
.refapp .rhead .jc-bg-gear-hitbox {{
  position:absolute!important;display:block!important;z-index:70!important;
  top:24px!important;right:0px!important;width:43px!important;height:43px!important;
  background:transparent!important;border:0!important;text-decoration:none!important;
  opacity:0!important;cursor:pointer!important;
}}
.refapp .rhero {{margin-top:2px!important;}}
/* Solo tablet: separar la señal del título y la versión del encabezado.
   No modifica móvil, escritorio ni el motor de señales. */
@media screen and (min-width:601px) and (max-width:1199px) {{
  .refapp .rhero {{margin-top:42px!important;}}
}}
@media(max-width:400px){{
  .refapp .rhead.jc-bg-header{{height:145px!important;min-height:145px!important;max-height:145px!important}}
}}
/* Lector de cierre: diseño compacto, sin reglas sobre otros paneles. */
.refapp .reader.jcclose {{
 padding:9px 10px!important; background:linear-gradient(145deg,#031323,#06283b 72%,#02121e)!important;
 border:1px solid #d9af60!important;border-radius:16px!important;
 box-shadow:inset 0 0 11px rgba(0,223,181,.12),0 0 10px rgba(236,181,71,.28)!important;
}}
.refapp .jcclose-title {{display:flex;justify-content:space-between;align-items:center;color:#f6fbff;font-size:clamp(12px,3vw,15px);font-weight:800;font-style:italic;gap:8px}}
.refapp .jcclose-symbol {{color:#e8b84d;font-size:21px;vertical-align:middle;text-shadow:0 0 7px #ffd16e}}
.refapp .jcclose-title em {{font-style:normal;font-size:9px;color:#00dfb5;border:1px solid #08b88e;border-radius:25px;padding:4px 9px;white-space:nowrap}}
.refapp .jcclose-main {{display:grid;grid-template-columns:minmax(0,1fr) 99px;align-items:center;gap:9px;margin:8px 0 10px}}
.refapp .jcclose-signal {{height:82px;min-width:0;border:1px solid var(--signal);border-radius:15px;background:linear-gradient(155deg,#032034,#061729);box-shadow:0 0 12px color-mix(in srgb,var(--signal) 36%,transparent),inset 0 -9px 20px color-mix(in srgb,var(--signal) 12%,transparent);display:flex;align-items:center;justify-content:center;gap:11px;color:var(--signal)}}
.refapp .jcclose-signal strong {{font-size:clamp(30px,8vw,44px)!important;line-height:1!important;font-weight:950!important;font-style:italic;letter-spacing:.5px;color:#f4fbff;text-shadow:0 0 12px var(--signal)}}
.refapp .jcclose-double {{font-size:clamp(21px,5.7vw,32px)!important;line-height:.9;letter-spacing:-10px;padding-right:10px;transform:rotate(-90deg);color:var(--signal);text-shadow:0 0 10px currentColor}}
.refapp .jcclose-dial {{width:95px;height:95px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;position:relative;background:conic-gradient(var(--dial) calc(var(--p)*1%),#203a4b 0);box-shadow:0 0 14px color-mix(in srgb,var(--dial) 45%,transparent)}}
.refapp .jcclose-dial:before {{content:"";position:absolute;inset:12px;border-radius:50%;background:#041625}}
.refapp .jcclose-dial span {{z-index:1;font-size:24px;font-weight:900;color:#f1f9ff}}
.refapp .jcclose .finalnote {{display:none!important}}
.refapp .jcclose .analysistext span {{display:none!important}}
@media(max-width:380px){{.refapp .jcclose-main{{grid-template-columns:minmax(0,1fr) 80px}}.refapp .jcclose-dial{{width:78px;height:78px}}.refapp .jcclose-dial span{{font-size:19px}}.refapp .jcclose-signal{{height:72px}}}}
</style>
<div class="refapp dir-{active.lower() if active in ("UP","DOWN") else "wait"}" style="--accent:{accent};--glow:{glow};--soft:{soft};">
  <!-- El fondo ya incluye logo, título, mercado y engranaje. -->
  <header class="rhead jc-bg-header" aria-label="Encabezado JC Alpha Edge">
    <a class="jc-bg-gear-hitbox" href="?page=settings" target="_self" aria-label="Abrir ajustes" title="Ajustes"></a>
  </header>

  <section class="rhero {'waiting' if active not in ('UP','DOWN') else ''}" data-official-signal="{hero_word}">
    <div class="rsignal"><span class="cssarrow"></span><span>{hero_word}</span></div>
    <div class="rconf">{'APOYO DEL MOTOR ' + str(confidence) + '%' if active in ('UP','DOWN') else round_signal["signal"]}</div>
  </section>

  {weakness_html}

  {pre_html}

  <div class="rgrid">
    <div class="rcard keycard">
      <div class="bigicon btcicon">₿</div>
      <div><div class="rlabel">BTC</div><div class="rvalue">${sig["price"]:,.0f}</div>
      <div class="rdelta {'green' if sig["mom3"] >= 0 else 'red'}">{btc_delta}</div></div>
    </div>
    <div class="rcard keycard">
      <div class="bigicon targeticon"><svg viewBox="0 0 64 64" aria-label="Target dorado" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="tgGold" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff4b5"/><stop offset=".45" stop-color="#ffc84e"/><stop offset="1" stop-color="#9b5b12"/></linearGradient></defs><circle cx="29" cy="36" r="23" fill="none" stroke="url(#tgGold)" stroke-width="5"/><circle cx="29" cy="36" r="14" fill="none" stroke="url(#tgGold)" stroke-width="4"/><circle cx="29" cy="36" r="5" fill="#ffcf59"/><path d="M29 36L51 13M45 8l7 5 6-1-6 7-1 7-5-7" fill="none" stroke="#ffd36a" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/></svg></div>
      <div><div class="rlabel">TARGET</div><div class="rvalue">{target_text}</div></div>
    </div>
    <div class="rcard keycard">
      <div class="bars" style="--accent:{distance_color}"><b></b><b></b><b></b></div>
      <div><div class="rlabel">DISTANCIA AL TARGET</div><div class="rvalue" style="color:{distance_color}">{distance_text}</div>
      <div class="rdelta" style="color:{distance_color}">{distance_sub}</div></div>
    </div>
    <div class="rcard keycard">
      <div class="clock"><svg viewBox="0 0 64 64" aria-label="Cronómetro dorado" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="clGold" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff4b5"/><stop offset=".5" stop-color="#ffca50"/><stop offset="1" stop-color="#99580e"/></linearGradient></defs><path d="M26 4h13v6H26zM44 14l6-6 6 6-6 6" fill="#f4b83c"/><circle cx="32" cy="37" r="23" fill="#14232c" stroke="url(#clGold)" stroke-width="5"/><path d="M32 19v18l-9 7" stroke="#ffd469" stroke-width="4" stroke-linecap="round" fill="none"/><circle cx="32" cy="37" r="4" fill="#ffe49b"/></svg></div>
      <div class="timecontent"><div class="rlabel">TIEMPO RESTANTE</div><div class="rvalue">{countdown}</div>
      <div class="timebar"><b style="width:{time_pct}%"></b></div></div>
    </div>
  </div>

  <section class="rcard probs">
    <div class="rlabel">APOYO CALCULADO · UP / DOWN</div>
    <div class="pbar"><div class="pup" style="width:{up}%">{up}%</div><div class="pdown" style="width:{down}%">{down}%</div></div>
    <div class="pleg"><span class="green">● &nbsp;UP&nbsp; {up}%</span><span class="red">● &nbsp;DOWN&nbsp; {down}%</span></div>
  </section>

  {reader_html}



  <section class="rcard tech">
    <div class="techhead"><span>DETALLES TÉCNICOS</span><span>⌃</span></div>
    <div class="techrow">
      <div><small>1ª SEÑAL</small><b style="color:{first_color}">{first_signal}</b><i>{first_time}</i></div>
      <div><small>KALSHI · PRECIO</small><b>{f"{round_signal['entry_price'] * 100:.0f}¢" if round_signal['entry_price'] is not None else "—"}</b><i>{round_signal["entry_quality"]}</i></div>
      <div><small>EMA</small><b class="{ema_class}">{ema_display}</b><i>9 / 21</i></div>
      <div><small>RSI</small><b class="{rsi_class}">{sig["rsi"]:.0f}</b><i>14</i></div>
      <div><small>MOMENTUM</small><b class="{mom_class}">{sig["mom3"]:+.2f}</b><i>3 MIN</i></div>
    </div>
  </section>

  <footer><span>BTC SIGNAL v4.6.1 &nbsp; | &nbsp; DISEÑADO PARA TRADERS REALES</span><span>MENOS RUIDO. MÁS RESULTADOS.</span></footer>
</div>
<div class="ticker">{ticker} • SCORE {sig["final_score"]:+.2f}</div>
"""
    # Cambia solo texto y atributos, manteniendo nodos existentes.
    # La UI vive fuera del fragmento; este fragmento sigue calculando cada 2 s.
    panel_data = json.dumps(panel_html, ensure_ascii=False).replace("<", "\\u003c")
    st.html(
        "<script>window.__alphaUpdatePanel(" + panel_data + ");</script>",
        unsafe_allow_javascript=True,
    )

    # Panel neón: capa visual independiente. No altera el motor de señales.
    if btc_ok:
        # Selector de temporalidad: mismo acabado dorado y franjas que las tarjetas.
        # Mantener el control nativo para preservar el estado y el ancho distribuido.
        st.markdown("""
        <style>
        @media (max-width: 1199px) {
          .st-key-chart_timeframe,
          .st-key-chart_timeframe [data-testid="stSegmentedControl"],
          .st-key-chart_timeframe [data-testid="stSegmentedControl"] > div,
          .st-key-chart_timeframe [role="group"],
          .st-key-chart_timeframe [data-baseweb="button-group"] {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
          }
          .st-key-chart_timeframe [role="group"],
          .st-key-chart_timeframe [data-baseweb="button-group"],
          .st-key-chart_timeframe [data-testid="stSegmentedControl"] > div {
            display: flex !important;
            width: 100% !important;
            gap: 6px !important;
            justify-content: space-between !important;
          }
          .st-key-chart_timeframe button {
            flex: 1 1 0 !important;
            min-width: 0 !important;
            min-height: 47px !important;
            padding: 8px 2px !important;
            margin: 0 !important;
            background-image:
              repeating-linear-gradient(128deg,transparent 0px,transparent 18px,rgba(255,232,173,.12) 19px,rgba(255,232,173,.045) 31px,transparent 40px,transparent 78px),
              linear-gradient(145deg,#0c1c27,#07151e) !important;
            background-color: #09151f !important;
            background-blend-mode: screen,normal !important;
            color: #f2e7d6 !important;
            border: 1px solid rgba(228,190,120,.78) !important;
            border-radius: 9px !important;
            box-shadow: inset 0 1px 0 rgba(255,227,170,.18),0 0 8px rgba(215,166,79,.14) !important;
            font-size: 14px !important;
            font-weight: 800 !important;
            opacity: 1 !important;
          }
          .st-key-chart_timeframe button * {
            color: inherit !important;
            opacity: 1 !important;
          }
          .st-key-chart_timeframe button[aria-pressed="true"],
          .st-key-chart_timeframe button[aria-checked="true"],
          .st-key-chart_timeframe button[data-state="active"] {
            background-image:
              repeating-linear-gradient(128deg,transparent 0px,transparent 18px,rgba(255,180,180,.10) 19px,rgba(255,180,180,.035) 31px,transparent 40px,transparent 78px),
              linear-gradient(145deg,#43212b,#1a1821) !important;
            border-color: #f47786 !important;
            color: #ffc3c9 !important;
            box-shadow: inset 0 1px 0 rgba(255,195,195,.2),0 0 7px rgba(244,119,134,.35) !important;
          }
        }
        @media (max-width: 599px) {
          .st-key-chart_timeframe [role="group"],
          .st-key-chart_timeframe [data-baseweb="button-group"],
          .st-key-chart_timeframe [data-testid="stSegmentedControl"] > div {
            gap: 3px !important;
          }
          .st-key-chart_timeframe button {
            min-height: 40px !important;
            font-size: 12px !important;
            padding: 6px 0 !important;
          }
        }
        </style>
        """, unsafe_allow_html=True)
        chart_timeframe = st.segmented_control(
            "Temporalidad del gráfico",
            ["1m", "3m", "5m", "15m", "1h", "4h", "1D"],
            default="1m", key="chart_timeframe", label_visibility="collapsed",
            selection_mode="single", width="stretch",
        )
        try:
            chart_df = btc_df if chart_timeframe in ("1m", "3m", "5m") else _neon_chart_history(chart_timeframe)
            chart_html = render_neon_chart(
                chart_df, coinbase_live_price if coinbase_live_ok else None,
                target, active, chart_timeframe, sig, whale, market, btc_df,
            )
            # Keep the chart in its permanent host outside this 2-second fragment.
            # Send only new JSON payload; never recreate the iframe on each refresh.
            chart_payload = _neon_payload(
                chart_df, coinbase_live_price if coinbase_live_ok else None,
                target, active, chart_timeframe, sig, whale, market, btc_df,
            )
            st.session_state["_alpha_chart_html_initial"] = chart_html
            payload_script = json.dumps(chart_payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
            st.html(
                "<script>window.__alphaNextChart=" + payload_script + ";"
                "if(window.__alphaPushChart)window.__alphaPushChart(window.__alphaNextChart);</script>",
                unsafe_allow_javascript=True,
            )
        except Exception:
            st.warning("No se pudo cargar esta temporalidad. Prueba 1m o vuelve a seleccionarla.")

    if target is None and kalshi_ok:
        st.warning(
            "Kalshi está conectado, pero esta ronda no entregó un target numérico."
        )
    if btc_error:
        st.error("Error de velas BTC/USD: " + btc_error)
    if live_price_error and live_btc_price is None:
        st.warning("Coinbase live: " + live_price_error)
    if kalshi_live_error and coinbase_live_price is not None:
        st.warning(
            "Kalshi BTC live falló temporalmente; usando Coinbase."
        )
    if kalshi_error:
        if market and market.get("_round_refresh_error"):
            st.warning("Kalshi no pudo refrescar: se conserva el target verificado de esta ronda y se reintentará. Cotización de contrato no disponible.")
        else:
            st.error("Error Kalshi: " + kalshi_error)


    st.session_state['_recent_alert_context'] = {
        'state': copy.deepcopy(state), 'signal': dict(sig),
        'market': dict(market) if market else None,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }


import zlib

SIGNAL_TRACE_DB = "btc_signal_decisions.db"
_TRACE_CONTEXT = threading.local()


def _trace_json(value):
    def encode(item):
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(type(item).__name__)
    return json.dumps(value, default=encode, ensure_ascii=False, allow_nan=False)


def _trace_event(kind, payload, ticker=None):
    """Diagnóstico independiente: un fallo de escritura no altera la decisión."""
    try:
        observed = datetime.now(timezone.utc).isoformat()
        thread_key = str(id(threading.current_thread()))
        packed = zlib.compress(_trace_json(payload).encode("utf-8"))
        # Give a brief competing writer time to finish, while bounding the
        # diagnostic delay. Long locks still fail without changing the signal.
        with sqlite3.connect(SIGNAL_TRACE_DB, timeout=0.2) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, observed_at TEXT NOT NULL, thread_key TEXT NOT NULL, kind TEXT NOT NULL, ticker TEXT, build_id INTEGER, payload BLOB NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS decisions_thread_kind ON decisions(thread_key,kind,id)")
            conn.execute("CREATE INDEX IF NOT EXISTS decisions_time ON decisions(observed_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS decisions_ticker ON decisions(ticker,id)")
            build_id = getattr(_TRACE_CONTEXT, "build_id", None) if kind == "confirmation" else None
            inserted = conn.execute("INSERT INTO decisions(observed_at,thread_key,kind,ticker,build_id,payload) VALUES(?,?,?,?,?,?)", (observed, thread_key, kind, ticker, build_id, packed))
            cutoff = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() - 12*3600, timezone.utc).isoformat()
            conn.execute("DELETE FROM decisions WHERE observed_at < ?", (cutoff,))
            event_id = inserted.lastrowid
        return event_id
    except Exception:
        # La observación nunca cambia señales ni bloquea por errores de diagnóstico.
        return




# =========================================================
# ALPHA AI GATE — supervised, conservative signal filter
# Learns only from official Kalshi settlements. It can BLOCK a
# weak UP/DOWN proposal, but it never invents or reverses a signal.
# =========================================================
AI_GATE_MIN_ROWS = 80
AI_GATE_MIN_HOLDOUT = 15
AI_GATE_MIN_BRIER_GAIN = 0.02
AI_GATE_BLOCK_BELOW = 0.45
_AI_GATE_CACHE = {"at": 0.0, "model": None, "status": "sin datos oficiales"}

def _ai_sigmoid(z):
    z = np.clip(np.asarray(z, dtype=float), -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-z))

def _ai_feature_vector(features, candidate=None):
    values = []
    for name in SHADOW_FEATURES:
        try:
            value = float(features.get(name))
            if not np.isfinite(value):
                value = np.nan
        except (TypeError, ValueError, OverflowError):
            value = np.nan
        values.append(value)
    # Direction matters: the same indicator values can mean different odds
    # for a proposed UP versus DOWN signal.
    values.append(1.0 if candidate == "UP" else 0.0 if candidate == "DOWN" else np.nan)
    return np.asarray(values, dtype=float)

def _ai_fit_logistic(X, y, epochs=900, lr=0.035):
    means = np.nanmean(X, axis=0)
    means = np.where(np.isfinite(means), means, 0.0)
    X = np.where(np.isfinite(X), X, means)
    scales = np.std(X, axis=0)
    scales = np.where(scales < 1e-8, 1.0, scales)
    Z = np.clip((X - means) / scales, -8, 8)
    Z = np.column_stack([np.ones(len(Z)), Z])
    weights = np.zeros(Z.shape[1], dtype=float)
    # Full-batch gradient descent with mild L2 regularization.
    for _ in range(epochs):
        p = _ai_sigmoid(Z @ weights)
        grad = (Z.T @ (p - y)) / len(y)
        grad[1:] += 0.01 * weights[1:]
        weights -= lr * grad
    return {"means": means, "scales": scales, "weights": weights}

def _ai_predict_model(model, X):
    X = np.asarray(X, dtype=float)
    means, scales = model["means"], model["scales"]
    X = np.where(np.isfinite(X), X, means)
    Z = np.clip((X - means) / scales, -8, 8)
    Z = np.column_stack([np.ones(len(Z)), Z])
    return _ai_sigmoid(Z @ model["weights"])

def _ai_official_training_rows():
    """Return only snapshots whose round has an official yes/no settlement."""
    try:
        with sqlite3.connect(SHADOW_AI_DB, timeout=2) as shadow:
            shadow.row_factory = sqlite3.Row
            shadow.execute("""CREATE TABLE IF NOT EXISTS snapshots (
                ticker TEXT PRIMARY KEY, observed_at TEXT NOT NULL,
                seconds_left REAL NOT NULL, btc_price REAL NOT NULL,
                target REAL NOT NULL, candidate TEXT, features_json TEXT NOT NULL)""")
            snapshots = shadow.execute(
                "SELECT ticker, observed_at, candidate, features_json "
                "FROM snapshots WHERE candidate IN ('UP','DOWN') ORDER BY observed_at"
            ).fetchall()
        if not snapshots:
            return []
        with _history_db() as history:
            history.row_factory = sqlite3.Row
            try:
                settled = {r["ticker"]: r["official_result"] for r in history.execute(
                    "SELECT ticker, official_result FROM round_history "
                    "WHERE verification_status='official' AND lower(official_result) IN ('yes','no')"
                ).fetchall()}
            except sqlite3.Error:
                return []
        rows = []
        for row in snapshots:
            outcome = settled.get(row["ticker"])
            if outcome not in ("yes", "no"):
                continue
            candidate = row["candidate"]
            won = (candidate == "UP" and outcome == "yes") or (candidate == "DOWN" and outcome == "no")
            try:
                features = json.loads(row["features_json"])
            except (TypeError, ValueError):
                continue
            rows.append((_ai_feature_vector(features, candidate), 1.0 if won else 0.0, row["observed_at"]))
        return rows
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return []

def _ai_gate_model(force=False):
    now = time.monotonic()
    if not force and now - _AI_GATE_CACHE["at"] < 60:
        return _AI_GATE_CACHE["model"], _AI_GATE_CACHE["status"]
    _AI_GATE_CACHE["at"] = now
    _AI_GATE_CACHE["model"] = None
    rows = _ai_official_training_rows()
    if len(rows) < AI_GATE_MIN_ROWS:
        status = f"IA en aprendizaje: {len(rows)}/{AI_GATE_MIN_ROWS} rondas con resultado oficial"
        _AI_GATE_CACHE.update(model=None, status=status)
        return None, status
    X = np.vstack([r[0] for r in rows])
    y = np.asarray([r[1] for r in rows], dtype=float)
    split = max(int(len(rows) * 0.8), len(rows) - AI_GATE_MIN_HOLDOUT)
    split = min(split, len(rows) - AI_GATE_MIN_HOLDOUT)
    if split < 30 or len(np.unique(y[:split])) < 2 or len(np.unique(y[split:])) < 2:
        status = "IA sin filtro: faltan resultados variados para validar"
        _AI_GATE_CACHE.update(model=None, status=status)
        return None, status
    try:
        validation_model = _ai_fit_logistic(X[:split], y[:split])
        predictions = _ai_predict_model(validation_model, X[split:])
        baseline = float(np.mean(y[:split]))
        model_brier = float(np.mean((predictions - y[split:]) ** 2))
        baseline_brier = float(np.mean((baseline - y[split:]) ** 2))
        gain = baseline_brier - model_brier
        if gain < AI_GATE_MIN_BRIER_GAIN:
            status = f"IA en evaluación: no mejora el modelo base (ganancia Brier {gain:.3f}); no bloquea señales"
            _AI_GATE_CACHE.update(model=None, status=status)
            return None, status
        model = _ai_fit_logistic(X, y)
        status = f"Filtro IA validado en historial: {len(rows)} rondas oficiales; mejora Brier {gain:.3f}"
        _AI_GATE_CACHE.update(model=model, status=status)
        return model, status
    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
        status = f"IA sin filtro por validación: {type(exc).__name__}"
        _AI_GATE_CACHE.update(model=None, status=status)
        return None, status

def _apply_ai_signal_gate(sig):
    """Only block a proposed signal when a validated model estimates weak odds."""
    if not isinstance(sig, dict):
        return sig
    candidate = sig.get("candidate")
    sig["candidate_raw"] = candidate
    sig["ai_gate_active"] = False
    sig["ai_win_probability"] = None
    model, status = _ai_gate_model()
    sig["ai_gate_status"] = status
    if candidate not in ("UP", "DOWN") or model is None:
        return sig
    features = {name: sig.get(name) for name in SHADOW_FEATURES}
    vector = _ai_feature_vector(features, candidate).reshape(1, -1)
    try:
        p_win = float(_ai_predict_model(model, vector)[0])
    except (ValueError, TypeError, FloatingPointError):
        return sig
    sig["ai_win_probability"] = round(p_win * 100, 1)
    if p_win < AI_GATE_BLOCK_BELOW:
        sig["candidate"] = None
        sig["quality"] = "NO TRADE · FILTRO IA"
        sig["ai_gate_active"] = True
        sig["ai_gate_reason"] = f"Probabilidad estimada de acierto {p_win:.1%}, bajo el umbral {AI_GATE_BLOCK_BELOW:.0%}"
    else:
        sig["ai_gate_active"] = True
        sig["ai_gate_reason"] = f"Señal permitida; probabilidad estimada de acierto {p_win:.1%}"
    return sig


def build_signal(df, target, seconds_left, live_price=None, price_source=None, whale=None):
    _TRACE_CONTEXT.build_id = None
    _TRACE_CONTEXT.build_payload = None
    sig = _signal_engine_without_trace(df, target, seconds_left, live_price, whale=whale)
    sig["price_source"] = price_source
    try:
        candles = [[row.time.isoformat(), float(row.open), float(row.high), float(row.low), float(row.close), float(row.volume)] for row in df.itertuples()]
        payload = {"candles":candles, "candle_metadata":dict(df.attrs), "target":target, "seconds_left":seconds_left, "live_price":live_price, "signal":sig}
        _TRACE_CONTEXT.build_payload = payload
        _TRACE_CONTEXT.build_id = _trace_event("build", payload)
    except Exception:
        pass
    return sig


def confirm_round_candidate(state, candidate, market, seconds_left, now, signal=None):
    before = dict(state)
    if state.get("signal_engine_revision") != "unified_evidence_v6":
        # Migrate state without deleting the already confirmed direction.
        state["signal_engine_revision"] = "unified_evidence_v6"
        state.update(pending_direction=None, pending_count=0,
                     pending_since=None, pending_last_at=None,
                     pending_price_source=None)
        state.setdefault("opening_live_tapes", {})
        _reset_withdrawal(state)
    result = _confirmation_without_trace(state, candidate, market, seconds_left, now, signal)
    # Solo seguimiento: el resultado de confirmación y su primera señal no cambian.
    if not isinstance(state.get("exit_plan"), dict) and state.get("first_direction") in ("UP", "DOWN"):
        state["exit_plan"] = make_exit_plan(state, signal, seconds_left, now)
    update_exit_plan(state, signal, seconds_left, now)
    _update_public_profit_alert(state, signal, market, seconds_left)
    _capture_recent_alert(state, signal, market, now)

    try:
        payload = {"candidate":candidate, "seconds_left":seconds_left, "now":now, "before":before, "after":dict(state), "engine_variant":"limited_retention_exit_plan_v1", "quotes":{"yes":get_yes_ask(market), "no":get_no_ask(market)}}
        payload["data_revision"] = BACKGROUND_DATA_REVISION
        payload["price_source"] = signal.get("price_source") if signal else None
        if signal is not None and signal.get("data_valid") is False:
            payload["data_valid"] = False
            payload["data_error"] = signal.get("data_error", "")
        if getattr(_TRACE_CONTEXT, "build_id", None) is None:
            fallback = getattr(_TRACE_CONTEXT, "build_payload", None)
            if fallback is not None:
                payload["input_fallback"] = fallback
        _trace_event("confirmation", payload, state.get("ticker"))
    except Exception:
        pass
    finally:
        _TRACE_CONTEXT.build_id = None
        _TRACE_CONTEXT.build_payload = None
    return result


def export_round_diagnostics(ticker, limit=4000):
    """Exporta lecturas de una ronda y su verificación; no calcula señales."""
    import gzip
    import io
    if (not ticker.startswith('KXBTC15M-') or len(ticker) > 128
            or any(not (ch.isascii() and (ch.isalnum() or ch == '-')) for ch in ticker)):
        raise ValueError('Ronda no válida.')
    history = None
    try:
        with _history_db() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM round_history WHERE ticker=?', (ticker,)).fetchone()
            history = dict(row) if row else None
    except Exception:
        pass
    output = io.BytesIO()
    with sqlite3.connect(SIGNAL_TRACE_DB, timeout=1) as conn:
        total, last_id = conn.execute("SELECT COUNT(*),MAX(id) FROM decisions WHERE kind='confirmation' AND ticker=?", (ticker,)).fetchone()
        rows = conn.execute("SELECT id,observed_at,thread_key,ticker,build_id,payload FROM decisions WHERE kind='confirmation' AND ticker=? AND id<=? ORDER BY id LIMIT ?", (ticker, last_id or 0, int(limit))).fetchall()
        header = dict(schema_version=1,ticker=ticker,engine_variant="limited_retention_v1",
                      exported_at=datetime.now(timezone.utc).isoformat(),
                      available_confirmations=total,exported_confirmations=len(rows),
                      truncated=total > len(rows),history=history)
        # Comprime cada fila por separado para evitar acumular todas las velas en memoria.
        with gzip.GzipFile(fileobj=output, mode='wb') as packed:
            packed.write((json.dumps(header, ensure_ascii=False, allow_nan=False)[:-1] + ',"entries":[').encode('utf-8'))
            for index, (event_id, observed, thread_key, round_ticker, build_id, payload) in enumerate(rows):
                confirmation = json.loads(zlib.decompress(payload))
                fallback = confirmation.pop("input_fallback", None)
                build = conn.execute("SELECT observed_at,payload FROM decisions WHERE id=? AND kind='build'", (build_id,)).fetchone() if build_id else None
                entry = dict(id=event_id,observed_at=observed,thread_key=thread_key,ticker=round_ticker,
                             confirmation=confirmation,build_observed_at=build[0] if build else None,
                             input=json.loads(zlib.decompress(build[1])) if build else fallback)
                if index:
                    packed.write(b',')
                packed.write(json.dumps(entry, ensure_ascii=False, allow_nan=False).encode('utf-8'))
            packed.write(b']}')
    return output.getvalue()


def render_signal_trace_page():
    """Página técnica separada; no cambia la pantalla de señales."""
    st.title("Datos de decisiones")
    ticker = str(st.query_params.get("ticker", ""))
    entries = str(st.query_params.get("view", "")) == "entries"
    if ticker and st.button("Preparar exportación de esta ronda", key="prepare_trace_export"):
        try:
            st.session_state["prepared_trace_export"] = (ticker, export_round_diagnostics(ticker))
        except Exception as error:
            st.info("No se pudo preparar la exportación: " + str(error))
    prepared = st.session_state.get("prepared_trace_export")
    if prepared and prepared[0] == ticker:
        st.download_button("Descargar lecturas de la ronda", prepared[1],
                           file_name=f"diagnostico_{ticker}.json.gz", mime="application/gzip",
                           key="download_trace_export")
    try:
        with sqlite3.connect(SIGNAL_TRACE_DB, timeout=1) as conn:
            if ticker:
                rows = conn.execute("SELECT id,observed_at,ticker,build_id,payload FROM decisions WHERE kind='confirmation' AND ticker=? ORDER BY id DESC LIMIT ?", (ticker, 2000 if entries else 10)).fetchall()
            else:
                rows = conn.execute("SELECT id,observed_at,ticker,build_id,payload FROM decisions WHERE kind='confirmation' ORDER BY id DESC LIMIT 10").fetchall()
            readings = []
            for event_id, observed, round_ticker, build_id, payload in rows:
                confirmation = json.loads(zlib.decompress(payload))
                fallback = confirmation.pop("input_fallback", None)
                if entries:
                    before, after = confirmation["before"], confirmation["after"]
                    changed = any(before.get(key) != after.get(key) for key in ("first_direction", "active_direction"))
                    if not changed:
                        continue
                build = conn.execute("SELECT observed_at,payload FROM decisions WHERE id=? AND kind='build'", (build_id,)).fetchone() if build_id else None
                readings.append({"id":event_id, "observed_at":observed, "ticker":round_ticker, "confirmation":confirmation, "build_observed_at":build[0] if build else None, "input":json.loads(zlib.decompress(build[1])) if build else fallback})
        st.json(readings)
    except Exception as error:
        st.info("Datos todavía no disponibles: " + str(error))



# Raíz visual estable: no se destruye con los ciclos del fragmento.
# Requiere Streamlit con st.html(..., unsafe_allow_javascript=True).
_ALPHA_STABLE_PANEL = r"""
<div id="alpha-stable-panel"></div>
<script>
(function () {
  if (window.__alphaUpdatePanel) return;
  const root = document.getElementById('alpha-stable-panel');
  function reconcile(current, fresh) {
    if (current.nodeType !== fresh.nodeType ||
        (current.nodeType === 1 && current.tagName !== fresh.tagName)) {
      current.replaceWith(fresh.cloneNode(true)); return;
    }
    if (current.nodeType === 3) {
      if (current.nodeValue !== fresh.nodeValue) current.nodeValue = fresh.nodeValue;
      return;
    }
    if (current.nodeType !== 1) return;
    // Preservar nodos existentes evita que Safari pierda altura y posición.
    for (const attr of Array.from(current.attributes))
      if (!fresh.hasAttribute(attr.name)) current.removeAttribute(attr.name);
    for (const attr of Array.from(fresh.attributes))
      if (current.getAttribute(attr.name) !== attr.value)
        current.setAttribute(attr.name, attr.value);
    let i = 0;
    while (i < fresh.childNodes.length) {
      if (!current.childNodes[i]) current.appendChild(fresh.childNodes[i].cloneNode(true));
      else reconcile(current.childNodes[i], fresh.childNodes[i]);
      i++;
    }
    while (current.childNodes.length > fresh.childNodes.length)
      current.lastChild.remove();
  }
  function syncOfficialSignal() {
    const frame = document.querySelector('#alpha-chart-stable-host iframe');
    const label = frame?.contentDocument?.getElementById('signal');
    if (!label) return;
    const side = root.querySelector('.rhero')?.dataset.officialSignal;
    const text = side === 'UP' ? '▲ UP' : side === 'DOWN' ? '▼ DOWN' : 'ESPERANDO';
    if (label.textContent !== text) {
      label.textContent = text;
      label.className = side === 'UP' ? 'green' : side === 'DOWN' ? 'red' : 'cyan';
    }
  }
  window.__alphaSyncOfficialSignal = syncOfficialSignal;
  window.__alphaUpdatePanel = function(html) {
    const template = document.createElement('template');
    template.innerHTML = html;
    const incoming = template.content;
    let i = 0;
    while (i < incoming.childNodes.length) {
      if (!root.childNodes[i]) root.appendChild(incoming.childNodes[i].cloneNode(true));
      else reconcile(root.childNodes[i], incoming.childNodes[i]);
      i++;
    }
    while (root.childNodes.length > incoming.childNodes.length)
      root.lastChild.remove();
    syncOfficialSignal();
  };
})();
</script>
"""

# =========================================================
# ALERTAS RECIENTES — observación de primeras confirmaciones
# No propone, confirma, retira ni cambia una señal del motor.
# Reutiliza los resultados oficiales del historial existente.
# =========================================================
RECENT_ALERTS_DB = 'btc_signal_recent_alerts.db'


def _recent_alert_time(value):
    try:
        value = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _capture_recent_alert(state, sig, market, now):
    """Attach display metrics to the same persisted first-confirmation state."""
    try:
        side = state.get('first_direction')
        first = _recent_alert_time(state.get('first_signal_time'))
        if side not in ('UP', 'DOWN') or first is None or first != now:
            return
        ticker = state.get('ticker')
        if not ticker or (market or {}).get('ticker') != ticker:
            return
        previous = state.get('recent_alert_metrics') or {}
        if previous.get('side') == side and _recent_alert_time(previous.get('first_at')) == first:
            return
        support = _plan_number((sig or {}).get('up_probability' if side == 'UP' else 'down_probability'))
        if support is not None and not 0 <= support <= 100:
            support = None
        # save_round_state(), already called by both existing signal paths,
        # saves this metadata together with the confirmation in one transaction.
        state['recent_alert_metrics'] = {
            'side': side, 'first_at': first.isoformat(), 'support': support,
            'target': _plan_number(get_target_from_market(market)),
            'close_time': market.get('close_time'),
        }
    except Exception:
        pass


def _recent_alert_rows(current_state=None, sig=None, market=None, limit=4, now=None):
    """Read persisted signals and official results, with no API requests."""
    now = now or datetime.now(timezone.utc)
    items = {}
    current_ticker = (market or {}).get('ticker')

    def add_state(state):
        ticker = state.get('ticker')
        side = state.get('first_direction')
        at = _recent_alert_time(state.get('first_signal_time'))
        if not ticker or side not in ('UP', 'DOWN') or at is None:
            return
        metrics = state.get('recent_alert_metrics') or {}
        captured = metrics.get('side') == side and _recent_alert_time(metrics.get('first_at')) == at
        support = _plan_number(metrics.get('support')) if captured else None
        if support is not None and not 0 <= support <= 100:
            support = None
        target = _plan_number(state.get('last_target'))
        items[ticker] = dict(ticker=ticker, side=side, first_at=at.isoformat(),
                             support=support, target=target if target is not None else _plan_number(metrics.get('target')) if captured else None,
                             close_time=metrics.get('close_time') if captured else None, outcome=None, closed=False)

    conn = None
    try:
        conn = sqlite3.connect('file:' + ROUND_STATE_DB + '?mode=ro', uri=True, timeout=0.1)
        for row in conn.execute('SELECT payload FROM round_state ORDER BY updated_at DESC LIMIT 100'):
            try:
                add_state(json.loads(row[0]))
            except (ValueError, TypeError):
                continue
    except sqlite3.Error:
        pass
    finally:
        if conn is not None:
            conn.close()

    # The existing history is the authority for a round's first signal/outcome.
    conn = None
    try:
        conn = sqlite3.connect('file:' + HISTORY_DB + '?mode=ro', uri=True, timeout=0.1)
        conn.row_factory = sqlite3.Row
        for row in conn.execute('SELECT * FROM round_history ORDER BY closed_at DESC LIMIT 100'):
            data = dict(row)
            side = data.get('first_signal')
            at = _recent_alert_time(data.get('first_signal_time'))
            if side not in ('UP', 'DOWN') or at is None:
                continue
            ticker = data['ticker']
            item = items.setdefault(ticker, dict(ticker=ticker, support=None, edge=None, close_time=None))
            item.update(side=side, first_at=at.isoformat(), target=_plan_number(data.get('target')), closed=True,
                        outcome=data.get('official_result') if data.get('verification_status') == 'official' else None)
    except sqlite3.Error:
        pass
    finally:
        if conn is not None:
            conn.close()

    # Include a newly confirmed first signal before its next disk refresh.
    if current_state:
        ticker = current_state.get('ticker')
        if ticker not in items:
            add_state(current_state)
        if ticker in items and ticker == current_ticker:
            items[ticker]['close_time'] = (market or {}).get('close_time')
            current_target = _plan_number(get_target_from_market(market))
            if current_target is not None:
                items[ticker]['target'] = current_target

    # Historical support is only shown when captured at that confirmation.
    conn = None
    try:
        conn = sqlite3.connect('file:' + RECENT_ALERTS_DB + '?mode=ro', uri=True, timeout=0.1)
        conn.row_factory = sqlite3.Row
        for row in conn.execute('SELECT * FROM recent_signal_metrics ORDER BY first_at DESC LIMIT 100'):
            data = dict(row)
            item = items.get(data['ticker'])
            if item and item['side'] == data['side'] and _recent_alert_time(item['first_at']) == _recent_alert_time(data['first_at']):
                if item.get('support') is None:
                    item['support'] = _plan_number(data['support'])
                item['close_time'] = item.get('close_time') or data['close_time']
                if item.get('target') is None:
                    item['target'] = _plan_number(data['target'])
    except sqlite3.Error:
        pass
    finally:
        if conn is not None:
            conn.close()

    for item in items.values():
        end = _recent_alert_time(item.get('close_time'))
        if item.get('outcome') in ('yes', 'no'):
            won = (item['side'] == 'UP') == (item['outcome'] == 'yes')
            item['status'] = 'GANADA' if won else 'PERDIDA'
        elif item.get('closed') or (end is not None and now >= end):
            item['status'] = 'POR RESOLVER'
        elif item['ticker'] == current_ticker and sig and sig.get('data_valid') is not False and end and now < end:
            item['status'] = ('EN VIVO' if (current_state or {}).get('active_direction') == item['side'] else 'RETIRADA')
        else:
            item['status'] = 'SIN DATOS ACTUALES'
    return sorted(items.values(), key=lambda item: item['first_at'], reverse=True)[:limit]


def _recent_alerts_html(rows, live=False, now=None):
    now = now or datetime.now(timezone.utc)
    cards = []
    for item in rows:
        up = item['side'] == 'UP'
        at = _recent_alert_time(item.get('first_at'))
        minutes = max(0, int((now-at).total_seconds() // 60)) if at else None
        age = ('Hora no disponible' if minutes is None else 'Ahora' if minutes < 1 else
               f'Hace {minutes} min' if minutes < 60 else f'Hace {minutes//60} h' if minutes < 1440 else f'Hace {minutes//1440} d')
        support = _plan_number(item.get('support'))
        support_text = f'{support:.1f}%' if support is not None and 0 <= support <= 100 else '—'
        target = _plan_number(item.get('target'))
        target_text = f'${target:,.2f}' if target is not None else '—'
        local_at = at.astimezone(ZoneInfo('America/New_York')) if at else None
        date_label = local_at.strftime('%d/%m/%Y · %I:%M %p') if local_at else 'Hora no disponible'
        status = item['status']
        status_class = {'GANADA':'ra93-is-win', 'PERDIDA':'ra93-is-loss', 'EN VIVO':'ra93-is-live'}.get(status, 'ra93-is-waiting')
        cards.append(f'''<article class="ra93-card">
<div class="ra93-top"><div><span class="ra93-symbol">BTC 15M</span> <b class="ra93-direction {'ra93-up' if up else 'ra93-down'}">{'▲ UP' if up else '▼ DOWN'}</b></div><span class="ra93-status {status_class}">{html.escape(status)}</span></div>
<div class="ra93-grid"><div><div class="ra93-label" title="Apoyo del motor al confirmar; no es probabilidad de acierto">APOYO</div><div class="ra93-value">{support_text}</div></div><div><div class="ra93-label">OBJETIVO</div><div class="ra93-value">{target_text}</div></div></div>
<div class="ra93-bottom"><span title="{html.escape(item.get('first_at') or '', quote=True)}">{age}</span><span title="Primera señal · {html.escape(item['ticker'], quote=True)}">{date_label}</span></div></article>''')
    if not cards:
        cards.append('<div class="ra93-empty">Todavía no hay señales confirmadas guardadas.</div>')
    return f'''<section class="ra93-panel" aria-label="Alertas recientes">
<div class="ra93-heading"><div><h2>Alertas recientes</h2><p>BTC 15M · Señales del bot</p></div><span class="ra93-badge {'ra93-connected' if live else 'ra93-disconnected'}">● {'EN VIVO' if live else 'SIN DATOS ACTUALES'}</span></div>
{''.join(cards)}
</section>'''


def render_recent_alerts(state, sig, market):
    # Render actual HTML directly; no script message or pending browser host.
    now = datetime.now(timezone.utc)
    end = _recent_alert_time((market or {}).get('close_time'))
    live = bool(market and sig and sig.get('data_valid') is not False and end and now < end)
    try:
        content = _recent_alerts_html(_recent_alert_rows(state, sig, market, now=now), live, now)
    except Exception:
        content = '<section class="ra93-panel"><h2>Alertas recientes</h2><p class="ra93-note">No se pudo leer el historial de señales en esta actualización.</p></section>'
    st.markdown('<div id="alpha-recent-alerts">' + content + '</div>', unsafe_allow_html=True)


@st.fragment(run_every="2s")
def recent_alerts_panel():
    context = st.session_state.get('_recent_alert_context') or {}
    sig = dict(context.get('signal') or {})
    updated = _recent_alert_time(context.get('updated_at'))
    if updated is None or not 0 <= (datetime.now(timezone.utc)-updated).total_seconds() < 15:
        sig['data_valid'] = False
    render_recent_alerts(context.get('state'), sig, context.get('market'))


_RECENT_ALERTS_HOST = r'''
<style>
#alpha-recent-alerts{margin:20px 0 24px;color:#e6edf3;font-family:Inter,system-ui,sans-serif}
#alpha-recent-alerts .ra93-panel{padding:22px;border:1px solid #263844;border-radius:22px;background:#04121a}
#alpha-recent-alerts .ra93-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:24px}
#alpha-recent-alerts h2{color:#e6edf3;font-size:25px;font-weight:750;line-height:1.25;letter-spacing:0;margin:0 0 8px;padding:0;border:0}
#alpha-recent-alerts .ra93-heading p{color:#7f909a;font-size:14px;margin:0;line-height:1.5}
#alpha-recent-alerts .ra93-badge{position:static;flex:0 0 auto;font-size:12px;white-space:nowrap;color:#81929e}
#alpha-recent-alerts .ra93-badge.ra93-connected{color:#45edbe}
#alpha-recent-alerts .ra93-card{background:#0b141e;border:1px solid #222d38;border-radius:18px;padding:20px;margin-top:15px}
#alpha-recent-alerts .ra93-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:22px}
#alpha-recent-alerts .ra93-symbol{font-size:15px;color:#889ba5}
#alpha-recent-alerts .ra93-direction{font-size:18px;font-weight:750;white-space:nowrap}
#alpha-recent-alerts .ra93-up{color:#45edbe}#alpha-recent-alerts .ra93-down{color:#ff5c7e}
#alpha-recent-alerts .ra93-status{position:static;flex:0 0 auto;font-size:11px;font-weight:800;letter-spacing:.7px;text-align:right}
#alpha-recent-alerts .ra93-status.ra93-is-win{color:#45edbe}#alpha-recent-alerts .ra93-status.ra93-is-loss{color:#ff5c7e}#alpha-recent-alerts .ra93-status.ra93-is-live{color:#efc864}#alpha-recent-alerts .ra93-status.ra93-is-waiting{color:#81929e}
#alpha-recent-alerts .ra93-grid{display:grid;grid-template-columns:1fr 1.4fr;gap:12px;margin-bottom:23px}
#alpha-recent-alerts .ra93-label{font-size:11px;color:#788c99;margin-bottom:7px}
#alpha-recent-alerts .ra93-value{font-size:22px;line-height:1.3;color:#e5edf2;font-variant-numeric:tabular-nums}
#alpha-recent-alerts .ra93-bottom{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;color:#70838f;font-size:11px;line-height:1.5}
#alpha-recent-alerts .ra93-bottom span:last-child{text-align:right;overflow-wrap:anywhere;min-width:0}
#alpha-recent-alerts .ra93-note{color:#80939f;font-size:11px;line-height:1.6;margin:18px 0 0}
#alpha-recent-alerts .ra93-empty{color:#8b9ca6;padding:22px 0;font-size:13px;line-height:1.6}
@media(max-width:480px){#alpha-recent-alerts .ra93-panel{padding:17px 12px}#alpha-recent-alerts h2{font-size:23px}#alpha-recent-alerts .ra93-heading p{font-size:11px}#alpha-recent-alerts .ra93-badge{font-size:9px}#alpha-recent-alerts .ra93-card{padding:13px 12px}#alpha-recent-alerts .ra93-direction{font-size:16px}#alpha-recent-alerts .ra93-symbol{font-size:12px}#alpha-recent-alerts .ra93-status{font-size:9px;max-width:100px;line-height:1.3}#alpha-recent-alerts .ra93-grid{gap:6px}#alpha-recent-alerts .ra93-value{font-size:16px}#alpha-recent-alerts .ra93-bottom{font-size:9px}#alpha-recent-alerts .ra93-top{margin-bottom:14px}#alpha-recent-alerts .ra93-grid{margin-bottom:15px}#alpha-recent-alerts .ra93-heading{margin-bottom:18px}}

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
</style>
'''


# Inicia una sola vez el registrador autónomo continuo.
start_continuous_history_worker()
start_history_verifier()

page = str(st.query_params.get("page", "signal"))
if page == "signal_trace":
    render_signal_trace_page()
elif page == "settings":
    render_history_page()
else:
    st.html(_ALPHA_STABLE_PANEL, unsafe_allow_javascript=True)
    live_dashboard()
    # Persistent chart host: not within the periodic Streamlit fragment.
    # Initial srcdoc contains the complete original chart markup and controls.
    initial_html = st.session_state.get("_alpha_chart_html_initial")
    if initial_html:
        safe_html = json.dumps(initial_html, ensure_ascii=False).replace("<", "\\u003c")
        st.html(
            '<div id="alpha-chart-stable-host" style="width:100%;min-height:0"></div>'
            '<script>(function(){'
            'const host=document.getElementById("alpha-chart-stable-host");'
            'if(!host)return;'
            'let frame=host.querySelector("iframe");'
            'if(!frame){frame=document.createElement("iframe");'
            'frame.setAttribute("title","Gráfica BTC interactiva");'
            'frame.style.cssText="width:100%;height:1830px;border:0;display:block;background:#06121a";'
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
            'if(window.__alphaSyncOfficialSignal)window.__alphaSyncOfficialSignal();'
            'if(window.__alphaNextChart)window.__alphaPushChart(window.__alphaNextChart);'
            'fitChartHeight();try{const panel=frame.contentDocument.querySelector(".panel");'
            'if(panel)new ResizeObserver(fitChartHeight).observe(panel);}catch(e){}'
            '});'
            'if(window.__alphaNextChart)window.__alphaPushChart(window.__alphaNextChart);'
            '})();</script>',
            unsafe_allow_javascript=True,
        )

    st.markdown(_RECENT_ALERTS_HOST, unsafe_allow_html=True)
    recent_alerts_panel()
