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
    page_title="ALPHA · BTC 15M",
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

LEGACY_ROUND_STATE_DB = 'alpha_experimental_round_state.db'
ROUND_STATE_DB = 'alpha_experimental_round_state_v2.db'
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
    if saved.get('first_direction') in ('UP','DOWN'):
        for key in ('first_direction','first_signal_time','first_signal_seconds','first_signal_price'):
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

LEGACY_HISTORY_DB = "alpha_experimental_history.db"
HISTORY_DB = "alpha_experimental_history_v2.db"

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


@st.cache_data(ttl=5)
def get_btc_data():
    return _fetch_current_btc_candles()


def get_coinbase_whale_flow():
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
    tape = st.session_state.setdefault("whale_flow_tape", [])
    seen = st.session_state.setdefault("whale_seen_ids", {})

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
                tape.append({"id": trade_id, "t": t, "notional": notional, "side": aggressor})
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

    alert = st.session_state.get("whale_flow_alert")
    if qualifies:
        alert = {
            "direction": d10, "time": now,
            "buy": b30, "sell": s30, "total": t30,
            "imbalance": i30, "buy10": b10, "sell10": s10,
        }
        st.session_state["whale_flow_alert"] = alert
    elif alert and now - float(alert.get("time", 0)) > 12:
        alert = None
        st.session_state["whale_flow_alert"] = None

    return {
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
            return _valid_live_observation(value, pd.to_datetime(stamp, unit="s", utc=True), "KALSHI LIVE")
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


def build_presignal(sig, seconds_left):
    """PRESEÑAL INDEPENDIENTE Y REACTIVA.

    No cambia la señal oficial. Usa la lectura ACTUAL y, a medida que se acerca
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

    # El cerebro propone; tres lecturas espaciadas confirman la señal.
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
BACKGROUND_DATA_REVISION = "continuous_history_ia_shadow_v7_active_market_discovery"
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
SHADOW_AI_DB = "alpha_experimental_shadow.db"
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
            sig = build_signal(btc_df, target, seconds_left, live_price,
                               getattr(_BACKGROUND_PRICE_SOURCE, "value", None))
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
    """
    Lector independiente de cierre.
    - La señal principal v4.6.1 NO se modifica.
    - En los últimos segundos, tiempo + distancia al target dominan sobre
      una pequeña contradicción de momentum/microlectura.
    - Nunca llama "confirmado" a un resultado antes del cierre.
    """
    state = round_signal.get("round_state")
    active_direction = state.get("active_direction") if state else None

    if seconds_left is not None and seconds_left <= 0:
        distance = sig.get("distance")
        if distance is None or abs(distance) < 1:
            headline, color = "RONDA FINALIZADA", "#94a3b8"
        elif distance > 0:
            headline, color = "RONDA FINALIZADA • UP", "#00dfb5"
        else:
            headline, color = "RONDA FINALIZADA • DOWN", "#e64b4b"
        return {
            "percent":100, "headline":headline,
            "note":"La ronda terminó. Ya no se muestra una predicción de cierre.",
            "micro":"RONDA CERRADA","color":color,
            "border":"rgba(148,163,184,.45)",
            "bg":"linear-gradient(135deg,rgba(30,41,59,.45),rgba(9,23,34,.72))",
        }

    if active_direction not in ("UP", "DOWN"):
        first_direction = state.get("first_direction") if state else None
        withdrawn = first_direction in ("UP", "DOWN")
        return {
            "percent": 50,
            "headline": "SIN SEÑAL ACTIVA" if withdrawn else "ESPERANDO SEÑAL",
            "note": (f"La señal activa fue retirada. Primera señal de la ronda: {first_direction}. "
                     "Esperando nueva confirmación." if withdrawn else
                     "El motor todavía no confirmó una dirección."),
            "micro": "MICROLECTURA PREPARÁNDOSE",
            "color": "#38bdf8",
            "border": "rgba(56,189,248,.45)",
            "bg": "linear-gradient(135deg,rgba(11,64,91,.30),rgba(9,23,34,.72))",
        }

    distance = sig.get("distance")
    close_direction = active_direction
    terminal_override = False
    terminal_too_close = False

    # En cierre extremo, la posición REAL respecto al target manda.
    # Umbrales deliberadamente conservadores para no llamar un flip por $2-$10.
    if seconds_left is not None and distance is not None:
        abs_d = abs(distance)
        market_side = "UP" if distance > 0 else "DOWN"

        if seconds_left <= 15:
            strong_distance = abs_d >= 30
            too_close = not strong_distance
        elif seconds_left <= 30:
            strong_distance = abs_d >= 45
            too_close = not strong_distance
        elif seconds_left <= 60:
            strong_distance = abs_d >= 70
            too_close = abs_d < 25
        else:
            strong_distance = False
            too_close = False

        if strong_distance:
            close_direction = market_side
            terminal_override = True
        elif too_close and seconds_left <= 30:
            terminal_too_close = True

    direction = close_direction
    base = sig["up_probability"] if direction == "UP" else sig["down_probability"]
    confidence = float(base)

    if distance is not None:
        aligned = distance > 0 if direction == "UP" else distance < 0
        confidence += 6 if aligned else -9

    aligned_momentum = sig["mom3"] > 0 if direction == "UP" else sig["mom3"] < 0
    confidence += 3 if aligned_momentum else -5

    if round_signal.get("reversal") and not terminal_override:
        confidence -= 12

    micro_text = "MICROLECTURA REUNIENDO DATOS"
    strong_contradiction = False

    if micro.get("ready"):
        wanted = 1 if direction == "UP" else -1
        c10 = micro["change_10s"] * wanted
        c30 = micro["change_30s"] * wanted
        slope = micro["slope"] * wanted
        ratio = micro["up_ratio"] if direction == "UP" else 1 - micro["up_ratio"]

        micro_score = 0
        micro_score += 6 if c10 > 8 else (3 if c10 > 2 else (-7 if c10 < -8 else (-4 if c10 < -2 else 0)))
        micro_score += 7 if c30 > 15 else (4 if c30 > 5 else (-9 if c30 < -15 else (-5 if c30 < -5 else 0)))
        micro_score += 4 if slope > 0.45 else (-5 if slope < -0.45 else 0)
        micro_score += 4 if ratio >= 0.62 else (-5 if ratio <= 0.38 else 0)

        # La microlectura pesa menos cuando quedan segundos y la distancia es amplia.
        weight = 1.0
        if seconds_left is not None:
            if seconds_left <= 30:
                weight = 0.45 if terminal_override else 1.20
            elif seconds_left <= 60:
                weight = 0.70 if terminal_override else 1.35
            elif seconds_left <= 120:
                weight = 1.35
            elif seconds_left <= 180:
                weight = 1.20

        confidence += float(np.clip(micro_score * weight, -28, 20))
        strong_contradiction = (c10 < -5 and c30 < -10)

        # Solo limitar por contradicción si tiempo/distancia NO hacen el cierre dominante.
        if strong_contradiction and not terminal_override:
            confidence = min(confidence, 69)

        micro_text = (
            f"MICRO {micro['pressure']} • "
            f"10s {micro['change_10s']:+.1f} • "
            f"30s {micro['change_30s']:+.1f}"
        )

    if seconds_left is not None and seconds_left <= 180:
        confidence += 2

    # Refuerzo específico de tiempo + distancia.
    if terminal_override and distance is not None:
        abs_d = abs(distance)
        if seconds_left <= 15:
            confidence = max(confidence, 90 if abs_d >= 75 else 82)
        elif seconds_left <= 30:
            confidence = max(confidence, 86 if abs_d >= 100 else 78)
        elif seconds_left <= 60:
            confidence = max(confidence, 80 if abs_d >= 120 else 74)

    confidence = int(round(np.clip(confidence, 5, 95)))

    if terminal_too_close:
        # En los últimos segundos NO lo llama simplemente "disputado":
        # muestra qué lado del target está ganando AHORA y la distancia exacta.
        # La confianza se mantiene moderada porque una diferencia pequeña aún puede cruzarse.
        if distance == 0:
            confidence = 50
            headline = "PRECIO EN EL TARGET"
            note = f"Quedan {seconds_left}s y el precio está en el target, sin margen a favor de una dirección."
        else:
            market_side = "UP" if distance > 0 else "DOWN"
            confidence = int(np.clip(confidence, 52, 64))
            headline = f"POSICIÓN ACTUAL {market_side}"
            note = (
                f"Quedan {seconds_left}s y BTC está ${abs(distance):,.0f} "
                f"{'arriba' if distance > 0 else 'abajo'} del target. "
                "El margen es pequeño; no se muestra un apoyo direccional."
            )
    elif terminal_override:
        headline = f"CIERRE MUY FAVORECIDO PARA {direction}"
        note = (
            f"Quedan {seconds_left}s y BTC está ${abs(distance):,.0f} "
            f"{'arriba' if distance > 0 else 'abajo'} del target."
        )
    elif round_signal.get("reversal"):
        headline = "SEÑAL PERDIENDO FUERZA"
        note = round_signal.get("reversal_text") or "Posible cambio de dirección."
    elif strong_contradiction:
        headline = f"{direction} PERDIENDO FUERZA"
        note = "La presión live de 10s y 30s va contra la señal activa."
    elif confidence >= 75:
        headline = ("APOYO FUERTE AL CIERRE UP" if direction == "UP"
                    else "APOYO FUERTE AL CIERRE DOWN")
        note = "Índice de apoyo basado en momentum, volatilidad, presión y distancia. No es una probabilidad de acierto."
    elif confidence >= 60:
        headline = f"VENTAJA MODERADA PARA {direction}"
        note = "La dirección sigue activa, pero la presión inmediata aún puede cambiar."
    else:
        headline = f"CIERRE {direction} SIN VENTAJA CLARA"
        note = "La microlectura no confirma con fuerza la dirección."

    if direction == "UP":
        color = "#00dfb5"
        border = "rgba(0,223,181,.48)"
        bg = "linear-gradient(135deg,rgba(4,86,43,.46),rgba(7,36,25,.78))"
    else:
        color = "#e64b4b"
        border = "rgba(230,75,75,.48)"
        bg = "linear-gradient(135deg,rgba(102,20,31,.48),rgba(43,10,17,.80))"

    return {
        "percent": 0 if terminal_too_close else confidence,
        "direction": None if terminal_too_close else direction,
        "headline": headline,
        "note": note,
        "micro": micro_text,
        "color": color,
        "border": border,
        "bg": bg,
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
      <div style="font-size:13px;font-weight:900;color:#dce7f3">DETECTOR DE REVERSIÓN</div>
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
    return {"rows": rows, "timeframe": timeframe, "price": price or latest,
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

</style>
<section class="panel">
<header class="header"><div><h2>BTC / USD</h2><div class="sub" id="subtitle"></div></div><div><div class="price" id="price"></div><div class="live" id="live"></div></div></header>
<div class="cards"><div class="card signal"><div class="label">SEÑAL OFICIAL DEL BOT</div><strong id="signal"></strong><small>Motor BTC Signal v4.6.1</small></div><div class="card"><div class="label">APOYO DEL MODELO</div><strong class="cyan" id="model"></strong><small>Apoyo calculado · no probabilidad de acierto</small></div><div class="card"><div class="label">ESTADO DE LA GRÁFICA</div><strong class="status" id="status"></strong><small id="updated"></small></div></div>
<details id="whale"><summary>🐋 WHALE FLOW <small>EN VIVO · TOCA PARA ABRIR</small></summary><div class="detail"><h3>🐋 WHALE FLOW — LIVE</h3><div class="note">Operaciones observadas de Coinbase · últimos 30 s</div><div class="watch" id="watch"></div><div class="metrics"><div class="metric"><small>BUY FLOW</small><b class="green" id="buy"></b></div><div class="metric"><small>SELL FLOW</small><b class="red" id="sell"></b></div><div class="metric"><small>DIFERENCIA</small><b id="diff"></b></div><div class="metric"><small>ACTIVIDAD</small><b id="activity"></b></div><div class="metric"><small>FUERZA DEL DESEQUILIBRIO</small><b id="strength"></b></div></div><div class="bars"><div class="bar">BUY<div class="track"><i id="buybar" style="background:#00dfb5"></i></div><b id="buytotal"></b></div><div class="bar">SELL<div class="track"><i id="sellbar" style="background:#e64b4b"></i></div><b id="selltotal"></b></div></div><div class="count"><div class="metric"><small>🐋 BUY WHALES</small><b class="green" id="buys"></b></div><div class="metric"><small>🐋 SELL WHALES</small><b class="red" id="sells"></b></div></div><div class="metric difference"><small>DIFERENCIA DE OPERACIONES</small><b id="countdiff"></b></div><p class="note">«Whales»: operaciones individuales de al menos $10,000, no personas identificadas. Muestra recibida por la API; puede omitir operaciones entre consultas. Actividad: ritmo de los últimos 10 s frente a los 20 s anteriores. En el laboratorio, el flujo puede apoyar una candidatura solo con confirmación técnica; no decide por sí solo.</p></div></details>
<details id="momentum"><summary>⚡ SHORT-TERM MOMENTUM <small>EN VIVO · TOCA PARA ABRIR</small></summary><div class="detail"><h3>MOVIMIENTO RECIENTE DE BTC</h3><div class="metrics" id="momrows"></div><p class="note">Cambio porcentual calculado por el motor en 3, 5 y 15 minutos. La temporalidad de la gráfica no cambia estos valores.</p></div></details>
<div class="tools"><h3>INDICADORES</h3><div class="toggles" id="toggles"></div><div class="legend" id="legend"></div></div>
<div class="floatcounts"><div>🐋 BUY WHALES <b id="floatbuy"></b></div><div>🐋 SELL WHALES <b id="floatsell"></b></div></div>
<div class="tooltip" id="tooltip">Arrastra con un dedo · amplía con dos · AHORA vuelve al precio actual.</div><div class="canvas" id="canvas"></div>
<div class="chartnav"><button id="older" aria-label="Velas anteriores">←</button><button id="newer" aria-label="Velas siguientes">→</button><button id="zoomin" aria-label="Acercar">＋</button><button id="zoomout" aria-label="Alejar">−</button><button id="reset">AHORA</button><span id="viewtf"></span></div>
<div class="footer">COINBASE · BTC/USD · Objetivo de la ronda Kalshi. Soporte/resistencia: extremos de las últimas 20 velas anteriores. VWAP: sesión UTC, con las velas disponibles. Actualización al recibir nuevos datos; intervalo solicitado 2 s.</div></section>
<script>
let D=__PAYLOAD__; const $=id=>document.getElementById(id), fmt=(v,n=2)=>v==null?'—':Number(v).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n}), usd=v=>v==null?'—':'$'+fmt(v), compact=v=>v==null?'—':v>=1e6?'$'+(v/1e6).toFixed(2)+'M':v>=1000?'$'+(v/1000).toFixed(0)+'K':'$'+fmt(v,0);
let saved={};try{saved=JSON.parse(localStorage.getItem('btc-neon-panel-v1')||'{}')}catch(e){}
let toggles=Object.assign({ema9:true,ema21:true,vwap:true,volume:true,rsi:true,},saved.toggles),visible=saved.visible||32,offset=saved.offset||0,pricePan=Number.isFinite(saved.pricePan)?saved.pricePan:0;
function persist(){try{localStorage.setItem('btc-neon-panel-v1',JSON.stringify({toggles,visible,offset,pricePan,whale:$('whale').open,momentum:$('momentum').open}))}catch(e){}}
for(const name of ['whale','momentum']){$(name).open=!!saved[name];$(name).addEventListener('toggle',persist)}
function refreshLabels(){
$('subtitle').textContent=D.timeframe.toUpperCase()+' · COINBASE · BTC SIGNAL';$('price').textContent=usd(D.price);$('live').textContent=D.price==null?'● SIN COTIZACIÓN':'● PRECIO RECIBIDO';$('signal').textContent=(D.signal==='UP'?'▲ ':D.signal==='DOWN'?'▼ ':'')+D.signal;$('signal').className=D.signal==='UP'?'green':D.signal==='DOWN'?'red':'cyan';$('model').textContent=fmt(D.signal==='UP'?D.up:D.signal==='DOWN'?D.down:Math.max(D.up,D.down),1)+'%';$('status').textContent=D.rows.length?'DATOS RECIBIDOS':'SIN VELAS';$('updated').textContent='Actualizado '+D.updated;$('viewtf').textContent=D.timeframe+' · VELAS REALES';
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
let geometry=null;
function draw(){
document.querySelectorAll('.toggle').forEach(x=>x.removeAttribute('data-unused'));
for(const b of $('toggles').children){const k=b.dataset.key;b.className='toggle'+(toggles[k]?'':' off');b.setAttribute('aria-pressed',String(toggles[k]));b.innerHTML=b.dataset.label+'<span>'+(toggles[k]?'ON':'OFF')+'</span>'}
const all=D.rows,n=all.length;visible=Math.max(12,Math.min(visible,Math.max(12,n)));offset=Math.max(0,Math.min(offset,Math.max(0,n-visible)));const end=n-Math.round(offset),start=Math.max(0,end-Math.round(visible)),rows=all.slice(start,end);if(!rows.length){$('canvas').innerHTML='<div class="empty">Esperando velas actuales…</div>';return}
const last=all[n-1];$('legend').innerHTML=['ema9','ema21','vwap'].filter(k=>toggles[k]).map(k=>'<span><i style="color:'+colors[k]+'">●</i> '+k.toUpperCase()+' '+usd(last[k])+'</span>').join('');
const W=720,H=toggles.rsi?780:615,L=10,R=126,T=28,B=580,plot=W-L-R,step=plot/rows.length,body=Math.max(3.8,Math.min(18,step*.84));
let vals=rows.flatMap(r=>[r.low,r.high]);for(const k of ['ema9','ema21','vwap'])if(toggles[k])vals.push(...rows.map(r=>r[k]).filter(v=>v!=null));for(const v of [D.target,D.support,D.resistance,D.price])if(v!=null)vals.push(v);let lo=Math.min(...vals),hi=Math.max(...vals),pad=Math.max((hi-lo)*.12,5);lo-=pad;hi+=pad;lo+=pricePan;hi+=pricePan;const y=v=>T+(hi-v)/(hi-lo)*(B-T),x=i=>L+(i+.5)*step;
let s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Gráfica BTC con velas, indicadores y RSI"><defs><clipPath id="plot"><rect x="0" y="0" width="'+(W-R)+'" height="'+B+'"/></clipPath></defs>';
for(let k=0;k<7;k++){const yy=T+(B-T)*k/6;s+='<line x1="0" y1="'+yy+'" x2="'+(W-R)+'" y2="'+yy+'" stroke="#202039"/><text x="'+(W-R+10)+'" y="'+(yy+5)+'" fill="#9ca6c2" font-size="14">'+fmt(hi-(hi-lo)*k/6)+'</text>'}
for(let k=0;k<=4;k++){const xx=L+plot*k/4;s+='<line x1="'+xx+'" y1="'+T+'" x2="'+xx+'" y2="'+(toggles.rsi?H-30:B)+'" stroke="#191c34"/>'}
s+='<g clip-path="url(#plot)">';if(toggles.volume){const max=Math.max(...rows.map(r=>r.volume),1);rows.forEach((r,i)=>{let h=r.volume/max*105;s+='<rect x="'+(x(i)-body/2)+'" y="'+(B-h)+'" width="'+body+'" height="'+h+'" fill="'+(r.close>=r.open?'#00dfb5':'#e64b4b')+'" opacity=".9"/>'})}
rows.forEach((r,i)=>{const c=r.close>=r.open?'#00dfb5':'#e64b4b';s+='<line x1="'+x(i)+'" x2="'+x(i)+'" y1="'+y(r.high)+'" y2="'+y(r.low)+'" stroke="'+c+'" stroke-width="2.1"/><rect x="'+(x(i)-body/2)+'" y="'+Math.min(y(r.open),y(r.close))+'" width="'+body+'" height="'+Math.max(1.8,Math.abs(y(r.open)-y(r.close)))+'" fill="'+c+'"/>'});
for(const k of ['ema9','ema21','vwap'])if(toggles[k]){let points=rows.map((r,i)=>r[k]==null?'':x(i)+','+y(r[k])).filter(Boolean).join(' ');s+='<polyline points="'+points+'" fill="none" stroke="'+colors[k]+'" stroke-width="3" '+(k==='vwap'?'stroke-dasharray="8 6"':'')+'/>'}
s+='</g>';let levels=[[D.resistance,'RESISTANCE','#e64b4b'],[D.target,'TARGET','#00dfb5'],[D.price,'BTC','#00dfb5'],[D.support,'SUPPORT','#00dfb5']].filter(r=>r[0]!=null).map(r=>({v:r[0],label:r[1],c:r[2],yy:y(r[0]),labelY:y(r[0])})).filter(l=>l.yy>=T&&l.yy<=B).sort((a,b)=>a.yy-b.yy);
let previous=-100;for(const l of levels){l.labelY=Math.max(T+12,previous+42,l.yy);previous=l.labelY}let excess=previous-(B-10);if(excess>0)for(const l of levels)l.labelY-=excess;
for(const l of levels){s+='<line x1="0" y1="'+l.yy+'" x2="'+(W-R)+'" y2="'+l.yy+'" stroke="'+l.c+'" stroke-dasharray="4 5" opacity=".8"/><path d="M '+(W-R-6)+' '+l.yy+' L '+(W-R+5)+' '+l.labelY+'" stroke="'+l.c+'" fill="none"/><rect x="'+(W-R+4)+'" y="'+(l.labelY-17)+'" width="118" height="36" rx="4" fill="'+l.c+'"/><text x="'+(W-R+11)+'" y="'+(l.labelY-3)+'" fill="#06101b" font-size="10" font-weight="850">'+l.label+'</text><text x="'+(W-R+11)+'" y="'+(l.labelY+12)+'" fill="#06101b" font-size="14" font-weight="750">'+fmt(l.v)+'</text>'}
if(toggles.rsi){const rt=620,rh=120,ry=v=>rt+(100-v)/100*rh;s+='<text x="14" y="610" fill="#aa8dc5" font-size="12">RSI 14</text>';for(const v of [30,70])s+='<line x1="0" y1="'+ry(v)+'" x2="'+(W-R)+'" y2="'+ry(v)+'" stroke="#3c284c" stroke-dasharray="5 5"/>';s+='<polyline points="'+rows.map((r,i)=>r.rsi==null?'':x(i)+','+ry(r.rsi)).filter(Boolean).join(' ')+'" fill="none" stroke="#f000ff" stroke-width="3"/>';if(last.rsi!=null)s+='<rect x="'+(W-R+4)+'" y="'+(ry(last.rsi)-12)+'" width="65" height="25" rx="3" fill="#f000ff"/><text x="'+(W-R+11)+'" y="'+(ry(last.rsi)+6)+'" fill="white" font-size="15">'+fmt(last.rsi)+'</text>'}
for(let k=0;k<4;k++){const i=Math.round((rows.length-1)*k/3),tm=new Date(rows[i].t*1000).toLocaleString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit',...(D.timeframe==='1D'?{month:'short',day:'numeric'}:{})});s+='<text x="'+x(i)+'" y="'+(H-7)+'" fill="#95a1bc" font-size="11" text-anchor="middle">'+tm+'</text>'}
s+='<g id="crosshair"></g></svg>';$('canvas').innerHTML=s;geometry={W,H,L,R,T,B,rows,x,y,lo,hi,start,end};
}
$('zoomin').onclick=()=>{visible=Math.max(12,Math.round(visible*.75));persist();draw()};$('zoomout').onclick=()=>{visible=Math.round(visible*1.3);persist();draw()};$('older').onclick=()=>{offset+=Math.max(5,Math.floor(visible/4));persist();draw()};$('newer').onclick=()=>{offset-=Math.max(5,Math.floor(visible/4));persist();draw()};$('reset').onclick=()=>{offset=0;visible=32;pricePan=0;draw();persist()};
const touchPoints=new Map();let gesture=null;
function chartPoint(e){const r=$('canvas').getBoundingClientRect();return {x:(e.clientX-r.left)/r.width*geometry.W,y:(e.clientY-r.top)/r.height*geometry.H}}
function beginGesture(){
 if(!geometry||!touchPoints.size){gesture=null;return}
 const p=[...touchPoints.values()],g=geometry;
 gesture={points:p.map(v=>({...v})),visible:g.rows.length,offset,pricePan,range:g.hi-g.lo,plot:g.W-g.L-g.R,height:g.B-g.T,end:g.end};
 if(p.length>=2){gesture.distance=Math.max(12,Math.hypot(p[1].x-p[0].x,p[1].y-p[0].y));gesture.center=(p[0].x+p[1].x)/2;gesture.anchor=g.start+Math.max(0,Math.min(1,(gesture.center-g.L)/gesture.plot))*g.rows.length}
}
$('canvas').addEventListener('pointerdown',e=>{
 if(!geometry||(e.pointerType==='mouse'&&e.button!==0))return;
 e.preventDefault();touchPoints.set(e.pointerId,chartPoint(e));try{$('canvas').setPointerCapture(e.pointerId)}catch(_){}beginGesture();
});
$('canvas').addEventListener('pointermove',e=>{
 if(!geometry)return;
 if(touchPoints.has(e.pointerId)){
  e.preventDefault();touchPoints.set(e.pointerId,chartPoint(e));const p=[...touchPoints.values()],a=gesture;if(!a)return;
  if(p.length>=2&&a.points.length>=2){
   const distance=Math.max(12,Math.hypot(p[1].x-p[0].x,p[1].y-p[0].y));
   visible=Math.max(12,Math.min(D.rows.length,Math.round(a.visible*a.distance/distance)));
   const center=(p[0].x+p[1].x)/2,fraction=Math.max(0,Math.min(1,(center-geometry.L)/a.plot));
   offset=Math.round(D.rows.length-a.anchor-(1-fraction)*visible);
  }else if(p.length===1&&a.points.length===1){
   offset=Math.round(a.offset+(p[0].x-a.points[0].x)/a.plot*a.visible);
   pricePan=a.pricePan+(p[0].y-a.points[0].y)/a.height*a.range;
  }
  draw();persist();return;
 }
 inspectCandle(chartPoint(e).x);
});
function endGesture(e){
 if(!touchPoints.has(e.pointerId))return;
 const wasTap=gesture&&gesture.points.length===1&&touchPoints.size===1&&Math.hypot(touchPoints.get(e.pointerId).x-gesture.points[0].x,touchPoints.get(e.pointerId).y-gesture.points[0].y)<5;
 const point=touchPoints.get(e.pointerId);touchPoints.delete(e.pointerId);beginGesture();persist();if(wasTap)inspectCandle(point.x);
}
for(const event of ['pointerup','pointercancel','lostpointercapture'])$('canvas').addEventListener(event,endGesture);
$('canvas').addEventListener('dblclick',()=>{$('reset').onclick()});
$('canvas').addEventListener('wheel',e=>{
 if(!geometry)return;e.preventDefault();const p=chartPoint(e),g=geometry,fraction=Math.max(0,Math.min(1,(p.x-g.L)/(g.W-g.L-g.R))),anchor=g.start+fraction*g.rows.length;
 visible=Math.max(12,Math.min(D.rows.length,Math.round(g.rows.length*(e.deltaY>0?1.15:.85))));offset=Math.round(D.rows.length-anchor-(1-fraction)*visible);draw();persist();
},{passive:false});
function inspectCandle(px){if(!geometry)return;const g=geometry,i=Math.max(0,Math.min(g.rows.length-1,Math.floor((px-g.L)/(g.W-g.L-g.R)*g.rows.length))),r=g.rows[i],time=new Date(r.t*1000).toLocaleString('en-US',{timeZone:'America/New_York'});$('tooltip').textContent=time+' · O '+fmt(r.open)+'  H '+fmt(r.high)+'  L '+fmt(r.low)+'  C '+fmt(r.close)+' · Vol '+fmt(r.volume,3);$('crosshair').innerHTML='<line x1="'+g.x(i)+'" x2="'+g.x(i)+'" y1="'+g.T+'" y2="'+g.B+'" stroke="#b8a5e0" stroke-dasharray="4 4"/>'}

window.addEventListener('message', function(event){
  if (!event.data || event.data.kind !== 'alpha-chart-update') return;
  // Only the chart data changes: preserve iframe, zoom, gesture handlers and cards.
  // La lógica y el precio recibido siguen intactos: solo interpolamos la
  // posición VISUAL de la última vela entre dos cotizaciones reales.
  const next = event.data.payload;
  if (!next || !Array.isArray(next.rows)) return;
  const old = D;
  const sameCandle = old && old.timeframe === next.timeframe &&
    old.rows && old.rows.length && next.rows.length &&
    old.rows[old.rows.length-1].t === next.rows[next.rows.length-1].t;
  if (window.__alphaVisualFrame) cancelAnimationFrame(window.__alphaVisualFrame);
  D = next;
  refreshLabels(); // Etiquetas: siempre el dato REAL, nunca interpolado.
  if (!sameCandle || offset > 0 || touchPoints.size > 0 || document.hidden) { draw(); return; }
  const previous = old.rows[old.rows.length-1], current = next.rows[next.rows.length-1];
  const keys = ['open','high','low','close','ema9','ema21','vwap','rsi'];
  const start = performance.now(), duration = 580;
  function frame(now) {
    const u = Math.min(1,(now-start)/duration), f = u*u*(3-2*u);
    if (u >= 1) { D = next; draw(); window.__alphaVisualFrame = null; return; }
    const row = {...current};
    for (const k of keys) {
      if (Number.isFinite(previous[k]) && Number.isFinite(current[k]))
        row[k] = previous[k] + (current[k]-previous[k])*f;
    }
    // El histórico es el real. Solo la vela abierta se anima.
    D = {...next, rows: next.rows.slice(0,-1).concat(row)};
    draw();
    window.__alphaVisualFrame = requestAnimationFrame(frame);
  }
  window.__alphaVisualFrame = requestAnimationFrame(frame);
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


def experimental_model(sig):
    """Índice heurístico propio; no es probabilidad calibrada ni motor Robin."""
    votes = [
        float(np.clip((sig.get('rsi', 50)-50)/12, -1, 1)),
        float(np.clip(sig.get('mom3', 0)/.04, -1, 1)),
        float(np.clip(sig.get('mom5', 0)/.06, -1, 1)),
        float(np.clip(sig.get('vwap_atr', 0)/.5, -1, 1)),
        1.0 if sig.get('macd1', 0)>0 else -1.0 if sig.get('macd1', 0)<0 else 0.0,
        1.0 if sig.get('ema')=='BULL' else -1.0 if sig.get('ema')=='BEAR' else 0.0,
    ]
    edge = sum(votes)/len(votes)
    side = 'UP' if edge >= .30 else 'DOWN' if edge <= -.30 else None
    return side, int(round(50+45*abs(edge)))


def experimental_decision(state, ticker, now, seconds_left, target, price, sig, whale, tape, valid=True):
    """Tres condiciones independientes; una ronda nueva borra toda confirmación."""
    if state.get('ticker') != ticker:
        state.clear()
        state['ticker'] = ticker
    model, support = experimental_model(sig)
    atr = max(float(sig.get('atr', 1)), 1)
    distance = price-target if target is not None and price is not None else None
    position = ('UP' if distance > .10*atr else 'DOWN' if distance < -.10*atr else None) if distance is not None else None
    whale = whale or {}
    # Solo operaciones observadas, sin inferir intenciones ni rellenar huecos.
    recent = [x for x in tape if 0 <= now-float(x['t']) <= 30]
    coverage = bool(recent and now-min(x['t'] for x in recent)>=10 and now-max(x['t'] for x in recent)<=10)
    volume = float(whale.get('buy30', 0))+float(whale.get('sell30', 0))
    flow = whale.get('flow_direction') if coverage and volume>=500000 and float(whale.get('flow_strength',0))>=.18 else None
    flow = flow if flow in ('UP','DOWN') else None
    directions = [model, position, flow]
    count = sum(x==model for x in directions) if model else 0
    ready = valid and ticker not in ('--','',None) and target is not None and seconds_left is not None and seconds_left>0
    aligned = ready and model is not None and count==3
    if not aligned:
        state.update(pending=None, count=0, last=None, since=None, active=None)
        if not ready: reason='Esperando datos actuales y target verificado de la ronda.'
        elif not model: reason='El modelo aún no encuentra una dirección clara.'
        elif position!=model: reason='BTC frente al target todavía no respalda '+model+'.'
        elif not coverage: reason='Reuniendo operaciones recientes para validar el flujo.'
        elif not flow: reason='Flujo comprador/vendedor sin predominio suficiente.'
        else: reason='El flujo va en dirección contraria al modelo.'
    else:
        if state.get('pending')!=model or state.get('last') is None or now-state['last']>15 or now-state['last']<0:
            state.update(pending=model,count=1,last=now,since=now,active=None)
        elif now-state['last']>=2:
            state['count']=min(3,state['count']+1);state['last']=now
        if state['count']>=3 and now-state['since']>=4:
            state['active']=model
            reason='Modelo, BTC frente al target y flujo coinciden con datos recientes.'
        else:reason=f"Tres condiciones alineadas; comprobando continuidad ({state['count']}/3 lecturas)."
    return dict(direction=state.get('active'), model=model, support=support, position=position, flow=flow, count=count if ready else 0, reason=reason)


def render_experimental_panel(result, price, target, seconds_left, ticker, valid):
    import html
    escape=lambda x:html.escape(str(x))
    side=result['direction'];color='#00dfb5' if side=='UP' else '#ef5059' if side=='DOWN' else '#9eafbb'
    def row(label, direction):
        tone='#00dfb5' if direction=='UP' else '#ef5059' if direction=='DOWN' else '#9eafbb'
        return f'<div class="ex-row"><span>{label}</span><b style="color:{tone}">{direction or "NEUTRAL / SIN DATOS"}</b></div>'
    bars=''.join('<i style="background:'+('#00dfb5' if result['model']=='UP' else '#ef5059')+'"></i>' if i<result['count'] else '<i></i>' for i in range(3))
    target_label=f'${target:,.2f}' if target is not None else '—'
    price_label=f'${price:,.2f}' if price is not None else '—'
    model_color='#00dfb5' if result['model']=='UP' else '#ef5059' if result['model']=='DOWN' else '#9eafbb'
    return f'''<style>
    .ex-wrap{{font-family:system-ui,sans-serif;color:#edf5f8;background:#06121a;padding:22px;border:1px solid #20665f;border-radius:20px;max-width:880px;margin:auto}}.ex-head{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #233039;padding:0 0 22px;gap:10px}}.ex-brand{{color:#00dfb5;font-size:12px;font-weight:800;letter-spacing:2px}}.ex-title{{font-size:25px;font-weight:800;margin-top:8px}}.ex-live{{color:#00dfb5;font-size:12px;white-space:nowrap}}.ex-card{{background:#0b1821;border:1px solid #263640;border-radius:20px;padding:24px;margin-top:18px}}.ex-label{{font-size:12px;font-weight:800;letter-spacing:1.6px;color:#8c9faa}}.ex-main{{font-size:44px;line-height:1.2;font-weight:850;margin:16px 0 12px}}.ex-note{{color:#a9bbc5;font-size:14px;line-height:1.5}}.ex-number{{font-size:29px;font-weight:800;margin-top:15px}}.ex-bars{{display:flex;gap:9px;margin-top:22px}}.ex-bars i{{height:9px;border-radius:8px;flex:1;background:#24323b}}.ex-row{{display:flex;justify-content:space-between;gap:12px;padding:19px 15px;margin-top:12px;border:1px solid #263640;border-radius:13px;font-size:13px;color:#a9bbc5}}.ex-row b{{text-align:right}}.ex-small{{margin-top:20px;color:#8295a3;font-size:11px;line-height:1.5;overflow-wrap:anywhere}}@media(max-width:450px){{.ex-wrap{{padding:16px}}.ex-card{{padding:21px}}.ex-main{{font-size:36px}}.ex-title{{font-size:22px}}}}
    </style><div class="ex-wrap"><div class="ex-head"><div><div class="ex-brand">ALPHA · BTC 15M</div><div class="ex-title">Lectura de la ronda</div></div><span class="ex-live">● {'EN VIVO' if valid else 'DATOS INCOMPLETOS'}</span></div>
    <section class="ex-card"><div class="ex-label">SEÑAL OFICIAL</div><div class="ex-main" style="color:{color}">{side or 'ESPERANDO'}</div><div class="ex-note">{escape(result['reason'])}</div></section>
    <section class="ex-card"><div class="ex-label">APOYO DEL MODELO PROPIO</div><div class="ex-main" style="color:{model_color}">{str(result['support'])+'%' if valid else '—'}</div><div class="ex-note">Dirección estimada: <b style="color:{model_color}">{result['model'] or 'NEUTRAL'}</b> · índice de apoyo, no probabilidad de acierto.</div></section>
    <section class="ex-card"><div class="ex-label">CONFIRMACIONES A FAVOR DEL MODELO</div><div class="ex-main">{result['count']}<small style="font-size:23px;color:#8c9faa">/3</small></div><div class="ex-bars">{bars}</div></section>
    <section class="ex-card"><div class="ex-label">TARGET</div><div class="ex-number">{target_label}</div><div class="ex-note">Kalshi · ronda vigente</div></section>
    <section class="ex-card"><div class="ex-label">TIEMPO RESTANTE</div><div class="ex-number">{format_countdown(seconds_left)}</div><div class="ex-note">BTC actual: {price_label}</div></section>
    {row('MODELO ALPHA',result['model'])}{row('BTC / TARGET',result['position'])}{row('FLUJO COMPRADOR / VENDEDOR',result['flow'])}
    <div class="ex-small">{escape(ticker)} · Solo señales<br>El flujo representa operaciones observadas en Coinbase; no identifica personas y puede ser incompleto.</div></div>'''


@st.fragment(run_every="2s")
def live_dashboard():
    errors=[];market=None;btc_df=None;price=None;whale=None;sig={};source='COINBASE'
    try:market=get_kalshi_btc_market()
    except Exception as exc:errors.append('Kalshi: '+str(exc))
    try:btc_df=add_indicators(get_btc_data())
    except Exception as exc:errors.append('Velas: '+str(exc))
    try:price=get_btc_live_price()
    except Exception as exc:errors.append('Precio en vivo: '+str(exc))
    try:whale=get_coinbase_whale_flow()
    except Exception as exc:errors.append('Flujo: '+str(exc))
    ticker=market.get('ticker','--') if market else '--'
    target=get_target_from_market(market);seconds_left=get_seconds_remaining(market)
    now=datetime.now(timezone.utc)
    valid=btc_df is not None and price is not None and market is not None and _KalshiPublicReads._is_current(market,now) and target is not None
    if valid:
        candle_age=(pd.Timestamp(now)-btc_df.iloc[-1]['time']).total_seconds()
        observations=getattr(_PRICE_OBSERVATIONS,'values',{})
        valid=-5<=candle_age<=120 and -5<=now.timestamp()-observations.get('COINBASE',0)<=LIVE_PRICE_MAX_AGE
    if valid:
        try:sig=_signal_engine_without_trace(btc_df,target,seconds_left,price,whale=None)
        except Exception as exc:valid=False;errors.append('Modelo: '+str(exc))
    state=st.session_state.setdefault('alpha_experimental_confirmation_v1',{})
    result=experimental_decision(state,ticker,now.timestamp(),seconds_left,target,price,sig,whale,st.session_state.get('whale_flow_tape',[]) if whale is not None else [],valid)
    if not valid:result.update(model=None,position=None,flow=None)
    sig['up_probability'] = result['support'] if result['model']=='UP' else 100-result['support'] if result['model']=='DOWN' else 50
    sig['down_probability'] = 100-sig['up_probability']
    panel_html=render_experimental_panel(result,price,target,seconds_left,ticker,valid)
    panel_data=json.dumps(panel_html,ensure_ascii=False).replace('<','\\u003c')
    st.html('<script>window.__alphaUpdatePanel('+panel_data+');</script>',unsafe_allow_javascript=True)
    if btc_df is not None:
        chart_timeframe=st.radio('Temporalidad del gráfico',['1m','3m','5m','15m','1h','4h','1D'],horizontal=True,key='chart_timeframe',label_visibility='collapsed')
        try:
            chart_df=btc_df if chart_timeframe in ('1m','3m','5m') else _neon_chart_history(chart_timeframe)
            chart_html=render_neon_chart(chart_df,price,target,result['direction'],chart_timeframe,sig,whale,market,btc_df)
            chart_payload=_neon_payload(chart_df,price,target,result['direction'],chart_timeframe,sig,whale,market,btc_df)
            st.session_state['_alpha_chart_html_initial']=chart_html
            payload_script=json.dumps(chart_payload,ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
            st.html('<script>window.__alphaNextChart='+payload_script+';if(window.__alphaPushChart)window.__alphaPushChart(window.__alphaNextChart);</script>',unsafe_allow_javascript=True)
        except Exception as exc:errors.append('Gráfica: '+str(exc))
    for error in errors:st.caption(error)


import zlib

SIGNAL_TRACE_DB = "alpha_experimental_decisions.db"
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
    result = _confirmation_without_trace(state, candidate, market, seconds_left, now, signal)
    # Solo seguimiento: el resultado de confirmación y su primera señal no cambian.
    if not isinstance(state.get("exit_plan"), dict) and state.get("first_direction") in ("UP", "DOWN"):
        state["exit_plan"] = make_exit_plan(state, signal, seconds_left, now)
    update_exit_plan(state, signal, seconds_left, now)

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
  };
})();
</script>
"""

# Inicia una sola vez el registrador autónomo continuo.


page = "signal"
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
            '<div id="alpha-chart-stable-host" style="width:100%;min-height:1830px"></div>'
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
            'frame.addEventListener("load",function(){'
            'if(window.__alphaNextChart)window.__alphaPushChart(window.__alphaNextChart);'
            '});'
            'if(window.__alphaNextChart)window.__alphaPushChart(window.__alphaNextChart);'
            '})();</script>',
            unsafe_allow_javascript=True,
        )
