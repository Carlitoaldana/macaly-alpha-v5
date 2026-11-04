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
    layout="wide",
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
.bars{display:flex;align-items:flex-end;gap:3px;width:31px;height:30px}.bars b{width:7px;background:var(--accent);border-radius:2px;transition:height .35s ease,background .35s ease}.bars b:nth-child(1){height:11px}.bars b:nth-child(2){height:20px}.bars b:nth-child(3){height:28px}
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
.readerbody small,.finalnote,.analysistext span,.features span,.chartfoot{font-size:11px!important;color:#cbd5e1!important;line-height:1.5!important}
.readerhead,.finaltitle,.motionrow small,.analysistext small,.probbox small,.features strong{font-size:10px!important}
.rhero{filter:drop-shadow(0 0 9px var(--accent))}
.note,.footer,.sub,.card small,.metric small,.tooltip,.chartnav span,summary small{color:#cbd5e1!important;font-size:11px!important}
.floatcounts div{border-color:#00dfb5;box-shadow:0 0 9px #00dfb544}.floatcounts div:last-child{border-color:#e64b4b;box-shadow:0 0 9px #e64b4b44}
.canvas svg rect,.canvas svg line{shape-rendering:geometricPrecision}
@media(max-width:460px){.finalgrid{grid-template-columns:1fr 1fr}.finalcard.motion{grid-column:1 / -1}.features{grid-template-columns:1fr}.finalanalysis{grid-template-columns:1fr 90px}}


/* Purple neon outlines, consistent across dashboard and chart cards. */
.rcard,.mini,.section,.close-reader,.reader,.refapp>section[style],
.finalclose,.finalcard,.analysisbox,.probbox,.chartbox,
.panel,.card,.metric,details,.floatcounts div{
 border-color:#23685e!important;
 box-shadow:0 0 4px #00dfb51a,inset 0 0 4px #00dfb508!important;
}
.panel{border:1.5px solid #23685e!important;margin:8px 6px!important}
.rcard,.mini,.reader,.card,.metric,details{border-width:1.5px!important}
.techrow,.rnav,.chartnav{border-color:#23685e!important}


/* Uniform turquoise presentation. Signal values and timing are unchanged. */
.stApp,[data-testid="stAppViewContainer"]{background:#06121a!important}
.refapp .rcard,.refapp .reader,.refapp .finalclose,
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


/* JC ALPHA EDGE — fondo azul oscuro aprobado; cambio exclusivamente visual. */
.stApp, [data-testid="stAppViewContainer"] {
  background-image:
    linear-gradient(rgba(0,5,17,.65), rgba(0,5,17,.76)),
    url("data:image/jpeg;base64,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EABZFRkoAEIqIiAyUqKgIioKkCp7MlKAGkRUZpAAgApQEFEUoVFagVYiwwLFRWoFAaCqikNCK0FEFsNO+rCY/ey8/sxhj6e98mWfLthPH3WL79RrPPljlLUWWW1JprkiKNpVSBCqikCpFKURSFAQAUoAIWKipABAqCRUVEQAIQEi1ABBAEBAhKrIKoAIgBCCooi1KEgAIioKRABSpVqMlKAkItRkoACgICJVQJEarIIijNLNRagKicgIAkoBAsBIWA0FajKxqCqoNMqqKUoBByqCCumE471jH5q8t4+vdFbuTPKcjVo0qsqtpYsRYgqpBoNRWVhCxUimBQGgoCAoFAcHBCxYkElAIOQEhFEURaBIAElBAQAEQQEQoECCICBAAJUVAkFRFKKgKAAoipQUACRFoyUABRFAURUCRFKChRGSlRajNaAAgPZSgAhQUoVFIUiNRqBYqRWmQApRFQGpEkXlqQLaici2tNCcqdpVQLKrEWFNCK0yoilNRWYrUZVUUhSIsIUApQCBQKAogAJACIgBIioCIAICBCUAURagIAEgAKAJKlAEQokJVSgoACiNJQUqLUCSgAoVUBRFRkiKlCQAFKiozSiLUZpAAQApQUgBShQIVYitQKAWVEClak9zGc974W1qT5Gy1nkqK1aURQliorUCqimBVjMWNBoRSFVFagVWYpCxplZSFAaCqikCoEKqCS1AKURUgBI9kAJEVARFqAgIEM1UZIACgIkAAiACJVRIEAQogQioCIqAoAEgAKAIoigKIqMpBWQSoqM0oijNKCgKKiwgVFKAUhQCFioNJVQIVrDHnz4MMfVfp71rKzxPEbxnzWbfgt9oxyWorTIqAylWJFKWKkUsiorUCqitBYqRSFgBCgEKsRWgsVFIVYyspgUBoKAkAJKAUIqJAASCoEiVagpEVAURajLSABIACIAIAkJwqBIKiKABCKgKUAFAAkFQFAqAiKgJUAUolWoyhKqUFKACAMlFRSFBSgBoKqRSACFLGscLlfp7014XO8Tx711zyknpx7SOmOPzWLfhnLKSenHwxylqDK7MiiDJUFIIqKUpAMCqikKqQaCqikLFSLGoFgBZVUUpQQhpYitBYAQKikACSiKUIoEIqJJQQISqgaGaqAoFSs0gAQioCgAIgBACKABICIgIEAAiKgQgAoioCIAKVKqM0iKgJUVkEBGUonICoDQUAhQUoVFIVrXrud4nj3vwa8LnlxP634d8ssdePow/9uuGG/d6Yyy+IznlMJ6cHK0yrKyy2pNAisNAKkKgQqoFKqRSFVlSFVIpAqKQsWIsaCqkVoCxFIUAhVRYQqorUACwgUCkFEkAoQAkiVUBQAFABUlZrTLNagioyRFQIBAQERVACEVARASQAEASShUBEEBVBGSIqUFEWpWSCAQgAiCUEABaVFaZFRSBUWEDpq15bMvTj/X6Jr15bM5jhO/7PXbjo1+jDzfN+Xbj4/L3emMstep2mdx04ejD+t+XmuXJnlzeWDnnv1FjjpUFc2gFSAEhUUgVFKIoEKqKQKBCgEKsSK0FEikKsSK0FixIsIVUUgVFaAqKQoilAipIFEkCgQigKIoEiVUopSs1pms1qIKlZIlAERUCEVEQAJASggCQgAoclQERUCEWpQUBARKqVkoCAiKgICAiVUoQIAugDbKkFhA3rwy2ZzDCc5U168tmcwwnOV8PdMcOl13HG85X8WXz/p24uLy93pzzz16naWYdPr9OPfK+cvl5M8+au3ZcrzXK3lrk5N+p0MMde6UBxdBUUgVBIASUAhoSKQqopCgNBVQKUFMAqLCBUUwKsZajUCqikKA1AqoENCRSAFKAEhFRIRUCAQEASRFRkolWoDERUZaQVGSItSpJRagIigSIqAoACIUCSgAiCAiKgKCoEIAKAAoACgFCRFSikEGS6BFdGSNYY5Z5zDCc5XxDDDLZnMMJcsr2kj6eGrDotfmZbbPvZf4n0d+Hhud3enLPPx9fKY44dJrsllzv4sv8T6PFt2XO8ru23O964WunLyz9uPTOGHze1t5RFjzbdVAKAElEUgVFSFRSFgQMDQikKECFAjSWLEWECopAAU1ADAqosaZagkUhQVoCopAoEAKUiLRJEWoCVFAkABSoqMlEaZoKCpWSgAKIoClRQJAAUSqlBQAFEqoCIAIioEgICAlBAAkABQVAkFSgpUVAQAFuNYY5Z5zHDG5ZW8ST3TCXLKY4y3K3iSebX2On0YdDqtysu/Kfev8ALPiPTwcN5b+I4cnJMJ+WdOrDotVtsu3Kfey+PpHj37rnbV6jdc8vo82Vd+Xlknhj1GOPC/uy7S1AeS13UIIACSoKkRUikAKURQIVUUgVFIFRShQaCqkCFVFIFRSFAKVYixqBVRTGVIDQVUCFVApQCABJKigKABIKgKAgIlVGaYiKjJQAFAAUKASI0lBRFQERUBQVAmSrUDSCoEgqIoijJQAJBQFAFpIjSClkVGSgAL7nS9Nh0Ou558XfZ3v8s+I8fU77sy89l6rqbsysl7PJlk+jzcuOOPhh1Hk48Lb5ZdmVZB47dvQABABSgJCgQKioCgUoKQKikCg0BUVIikGgKioKqDQVUUgVFKWKgQsaZjTUZUQaCqiwpQUhFRYgAFIACgJQQSgQi8oCJVSslkEZIAClRUBAEhKDJRFSggAKIqJFQGSgqIoVUCQoAoig0UFFpIVRaTNRpLGaWalarNZpQAF1uRx6v1Yaxb3tnQOnp9c7fi/dzps0JQFBQUKAEBYKUAEKCkCpFKFRYgKDQFIJCopAqKQLEUpVQIVUVqBSCtAWIENApAsRWgqopAAQAgSoqIoigSIqApQoyRmqUFlFRloKASAAoAEgAIlAFEVERFQIRUBEVAhFEU4OFBpJwljXBwdLbPC8LwvB8VtnhOHThngWLbHBY3wsw59h4nbjwxl9HXOydp/7cq5ZTTWLIow20sSLGozXTG8OmWE2Y8z8fx8uMdMMuHbG/Fc7PmOY9Oev7WerD8fvP5v9vPYMsbiZltAGSLBSkUCFASFhAhQUgBSAApRFKFRUD2VFIUApRFIWKixqBVjKtQVVRSFixIrTI1GVIVUClBCFEAQBJAAkAFKIDLSJVQVIlVGa0JVQIABQVAhKqUFAEUqKgIAEgASCoiAJAKtJF4FjWgcLIRuRqQWpMS4OuGPL0aumy25THGc2uuPFcunPLOY9vHjquV4k5rO3KYy443n5vy9XVbMNcurTeZ+bP+b9Po+fnXPl1h6nbeG8vdc8mK1WXjr0QAYKqitBY3GI1G4zXbXlw3twm37+H4/efP1/VwlddefFd8bLNVzs1dxw4OHr26ptlz1z735sZ7/WPNYxnhca1jltlYDJFOAoVFQFRShUCGhFQAChQIFRUhUUgVFKFRSCKkVqBVRYYFiosaCqitMqAUpAIUQQAERFQJAARKFRRKqMlEaSslEWoCIqBAAIgBIioCAiIigKCoEgqVIACEVSkU4WRqRUOF4XhrQ2SOmGPLOOPd6+m05bMpjjO/zfEnzXbjwuV0555SQ6fTlszmOM5v7O/V9Vrw1Xp+mvON/+Js/n+k+n7uPVdRjjhdPT37n58/fP/TwZZuufJOOeOLnjx3O+VTblzXC1vK8udfOzu3rxmmay1WXCukAAVAIWNRlqNQVqNSsRqNys13153Gyy+GtuuZy7Nc7/AJsZ+8cJXbXncbLK9GOUs8a5WWXccLEerbrmWN2a52/Nj8fX9Hmsc8sLjW8ctooMlFBIBSEUWJCoqAAUsBSABIVFIFRYUKikEUVqAVIpgWLEVqBoSK0yoBQsRSABIBUkRagSFVAUKCKI0jNSJVSgoAyUABQAFKigKIoEiKIoAEgAIiokiipALI1ENRJGpGpGacNTFZi9GjTdl4nE4nNt8SfNdsOO5XTGWWodPouzLjHj5tviT5q9R1OMwunRf+P82Xvn/r6J1PUY+j7HRzNf5r753/r6PFlXTPkmE8cWMcLld5NZ5cuNq2sV4s8noxhaxatrNcbXSM1FqOdaAAVDgIVUVqBqLGYsagajcrEajcrNdtey43mG3CWevCdvefDnHTDO412mW5qudmvccTh22a5x68Pw/Hw5WMZY2NS7ZVUBFFSTgUQAEgFSIAUoBAsRUCKilKrKtBVRSBUUwKqLG4KsVFLKgECgUAJACQggQiiKAAiAzUlSqlBQqoCiVRkoACgJQQECAQERURAAhFEkUUoWEXhuQLGsYYzl6NOq53txOO9t8SOuGFyrnllprRpud47STvbfEnzU6nqMbj9lp5mueb7535v/AEm/dLj9lr5muXvffK/NeTKu2ecxnjixjju7plWLVrFrx5V6JEtYtW1muNrcGatRzrSIqM0oKAtLxykajcZZVqzn9WVrSFiNGBY1GVjcDcajEajcrFdMMuP8psw4+9j+G/2SN4Zcee8vmO0u5qs305WI6Z4cXmd5fFY4YuOjKigyQBIACFQSUAhQCgBJVRSBQIVUitQCopgVYkaagFRWmRUUoVFQACgAJKi1EQAJAKCgASItQFBajJEVAUCgKIqAiKgQgAoKgIAkAJKqRY3IFjWMI668Ob9Pd1wx3WLdNadfqvtJ72+zW3bPT9nr7Ye/zlfms7M5x6cO2P7uNrtcpjNRiTd3TKueVXKsZV58snWRMqxatrNcMq6SIi1HOtREU45ZLKNVms0xAAW1iLG4y3FuPPjyzHTGuk9s305K654eqeqeXIXHSl2RYiqJqVqMRqNwVuNRiNR0jFdMb7XvL5Zzw9P1l8UlbxynHF8fs6TVmqx041HTPHisWOdmm5UAZIAEAJKIqQBCFAKUSKQqpFIVWVagaCDQVYikKAQqsrCFAIAEgBIRUBARIKJQRFQEQGaRKcoCABJQAUqLWWSUBISiUEEUEEVICLDEsakSN4zl0xm2bVwx5reWfbjHx+7GWXbieGOXXy8ZqMa2tyZtS1m1yuTchazaWs1ytbkKlKlrna0ILjj6v0+WeyknP6LfiLe04nhi030krNaqVzrSAAtLBW4ysalZjUbjNdcamzXz97Hz7xJXTC93aaymq5317eeReHo2aeZc8J+scOGcsLj21MtosAFqLGVjUZrpKvLHJy3KNOuNl7Xx+zOU4qSrzzOK1vcZ6YRqxKxY0iLUYKiKkKgkoBCgFLFSKYAFIFiRWoFVFaCxYikKAQoRSAAgARARJUAIQASpQSQEZIIAiACIAIIBFQKCgAKIqAiKBACSrEaxjUFJOa1cu3E8M5ZduIzy3vQ1tq1i0tZtZuTUjXLNolYtOisryjFrQhWteHq73tjPNZktuoukxw9Xe9sZ7tZWeJ2kayvtO0niOdrepiO2alKjlW4gDJQAF0ixjGukjpPbFGoSK6SMjeFYajeLNenVnxZYm/TLjdmudvzY/H+nPGu+nO45Sx6MdZTxrldy7jycMvd1HTy4Xdpn3PzY/wAv+nkuNc8+K43TeOcyYWFiOba8rGeVWw3yM8h2NNy8s0OeTvaQKMlAAlEVJRFKFRUCKikKrKtBWozFagVUUwLAGgqopCqgQqAkApSABCAiIASAAiKgSAUFEqoyQEBKCIiVQJEqpQUAZIAkAsSJ5LfaJlfaMnelpeUtEGyqCDZARkgNa9fr75dsJ/f6QSW3UXRr1+uc5dsJ7/P0jpll7ScSeJPYzy9p2k8Sezna6+sZqM9plWKqVytbiIqMUoAyQQBajphePPhzajePpmu/pLE1Z8dr4/Z2uD04zym4426rlwsa9Jw14raR0wvdzblax9M17Om3XXlzOL7WXxZ8Vrqujn2d6jp5bp57z3134v0+K8uOT3dD1WWnK2SZY5T05Y5eMp8V7MLjnPHJ585ljfLF8rLHisWPp9f0mOvjdo5ujO9ufON/lv8A/d3zso8nLx3C6r0cecym45rF4RwdFGeV5W00JAhpKBSKDKAEhUUpQEAgpAqK0lVFIWKkVqMqA0GhAhVRSABIFEkKCSAAoAEIqIiAyUBAQAJAAUARRFQISgCgoCIokJaIklFqMkQAUORAQGsMPV3y7Yz+4ktuoujXh6u+XbGf3dMsufpJ4nwZZc/Se0c7XX1jNRjsyrNKjna3BKqMlEVGaUFRkoLwItLEWNxluPRpzknpy/D7X4eaOmNduPLxu3PKbj2Za7HPLF26bZLjNey8T8uXx/pduq45WWcV7fGZTcefy1dV5eB1uLFjncdNy7SV1wy4cllWN0rNvdp6j0TLHKerXnOM8b7z/t5eq6f7KzLC+rVl+HL/ABfqkydteyem4ZznDLzP8/q73KZzxycpLjdx4bGK9G/XdeXHPON7zL5cK8WeNxuq9GN3NsgObaryyqCxWVMDSAUABCgUKioCopAqRWkqpFhjKwAhVRWoFCK0ABIVFIARJUBIBARABEAEQAhABEAESqgQCAiLUCEVKCAiSgiIgBIFRkiKgIDeGHP3svw/upLatphh6u+X4f3byy5/T4MryxXT1jNRnstZVmsWtRAGSgrLJEVARFRknICTSpFjUDUajDUdIzXfDJ9DptmO3Gatt4vjDK/tXy8a9GvJ7ODk8a8/JhuPXs05YZXHKcWOGWPD6nR5YdZjNOyybp215383/wBN/wAV5+o6fLXlccpZZ5le3Lilnlj082PJrLxvb59xR3zw4rllOHkyw09Eu2WplwylrG9NadPVMsbhn3xv9r8vPswuGXF/pZ7t8rLMsfTl49r8DL9c1TPThUbyxuN4rNcLNOkQBkqrMaIFiKQApQAgoBSgECosKGkIQ0JGo0yRRSAUaAAkAqSAFAqBAIkgDJRFQEBAQEoQAiVACEAFKFAhFQERURBAIRUBEAERWscO3OXj2nypLVvRhh75ePj5ayy5LWa6epNRntKlBitIlVKyUFQJBUZKItQUiAyQBJWozFagajUYajcZrcdca4xvGuuNYsezVnxw+5o3Y/xPXNW3j/ysZxhl/wDMnxfr+785hk9OjZZZZeOH0ODm16eTm4fKbnb09RouFss44eTPF+gmzD+J9P8Ae4/8vCd//uz5/X93yN+q428x6Objlm45cPLb6y7jwWMV3zjjk+fnNPZjdsgji212ynF/pfhzssvFVq/enF8+wvtT05CpWGhUVJRFIURSlAQUAoiopAsApSCmMrFiRY0KqpBoKqCSgEACSgiQFRJRAJKjVQFkWoCVFAURUCAAUASEAFAARFQIQAUASQEBAbwx98v6RSbRhj75ePhbeVtZb6moO0qLUZpQBkiKJMioCiNIzSzUaqVmlkWoyQQBaVFaZVYixqBqNRiVqV0xrNdJXXDJxlbxrvjdOeUe/RuywymWOVmUvMs9n0s8seu13ZJJuxnOeM/N9Z/l8PDJ6dG/LXnjljlZlLzK9/DzfF6eTl4t+52m/XxXkyj6+/0dRruzXJMp+PGe31n0fO2YcVjn49e43xZ7nt5rGa6ZRivFlHpiCDBW9/1ZUvcX2mVAEUChUVAVFhCgFKAQKilKqRTGViorQFSKQKgUqoIKAUAiQAEAiKoASVABEAERUCEVAQEBEVEgAFAAkAoKAAoDUnvVJtJjj71q0tStdAqCC0gAQAkgqAiKgSIqUUpUVKzWkqLUYKByItAEKsQjUDTUZ5I1GXSVuVylbldJWbHWVuZOMrUrtjkxY9endlhlMsb3jvtxx2Yfaa5295/LXz5k76t1wvM/Sy+708fLueOXTjlh73HPZjw417duOOU9eH4b/b6PJnjxXLlw1W8MtuaNWMvPXWAgyVRRIAQFBJRGiAApRFIVUWECosagVUUhRFIAClisqkKgQqKiQFQFUBISgCgASAAoAEIoCiKAoiiSAgICUEQAgF4CJPcOUaQIAgKkgAQAkIqJCAyUSrUFKVmtM1itJSgyUABVUCFWIsMCrGValDUalc1lblGnSVqVzjXLcrNjpKsyc5V5bmTOno1bbhfmXzPl024SyZY98b4rySu2vZ6e1743zHbDPc8a55Y+9xzyndzejZj7y8y+K42OeeOq3jWBajk2KgEoQIFRUlioEKAUoBCgEKsThWgoBCkRSlEUgVBJRBJRBJQEkACQAFAEhAoJUWoEAgIggKoAQgAiACgKkFEKAAQBAASBBFUBIRUZKIqCkqCM0jNVGaUAZIACisqkqsqQqoRoNLGVMDUqsrG5Q0srKxqUaa5amTmrUo0768/bL8N/sbMeHGV1wylnpy8fs6TLc1WLNe3Oo6Z48VzYymmpUFGSAICoqSiKUKBCiKQoBCqikEVFaQqKgKhCFAKAEgBIASEAIBAQERAGUgCIhUCEVARFQERazQRUAlBElQEgDhIASAEkABARIQASsrUZpQBmlKiozSiKgIACioqQClCoENRWVIVYixqBSVFOwq8s8h2m1jMWNSsu2GUynpv9KxljxeGZXSX1Ti+fZ0l8vTOtOY1Z3ZZsIAEoCSgEKAUKikCopQqLCFipFIFRSBUClAIRRAlASQBEBEigBIACAgQCAlRUqIioykFRESqgKCgSAqSCiQCJACQi0BQBIQAUSgCJRGaRKqAiURkiKgQAyUASVUClEUpYJFLKqgUqoNBVRSFWMrDA0srKtSh1l9U4vlipy1+L9W97HTIASgBCopQAgoBSgELFiK0FVAhQCFEVIVAhQRIARAEkACAQEASEVAhmqAoACgAIiokgqAgIEAJCoBACQIIgCQgAiAEgICVBGSAgIioCgIyVE5AkVBFRFIWKy1ChUUhRFIVWVIUApVSK0FVAhViBDfmfVOEl4rXnu32GVAIVFSAEFAKUgQhVQaCrEVBRFKACFEVIAKAEhFEkACQAERQJEVKCAIoioEAgKoqBACSAAoAEAJCAiABIAiAgQioiIDJRFAURQJEVGSlSqgIACgigiopCrEIQqoEKqBSqg0GlZUhVRWgoikKIqAsvFQMTdnM5iGN4Wz3nhvsIIsCUBAFQpYsSLCFAIURYUoKQAFKIpAAkIqJAKkIUCQAEBEhFQEBARFQIABEVAgBJCgCioBCKiIAkFAIRUREqoEIqAoioCABIipQSoDJRFSggATKooaFRSBYiwhQgQoBSqikCorQUAhVSEIUApQCBZeEUprhCVSARSFEVIWIpCgECwClVFIACFQElEClEVJAEigBILUBQVEkFQERUBAAkABEAIBAhFRFFAEqKJCAkAgSoCKUKBIFAURUBAAkRUBQKAoi1GSCASKihoAIUAhYqRTAoBSqkWECxBoKqKYFioEKqBSgpACoIsApeAg0BYCSgEKIpSiNQgVAhQChUioABQIoSKBSCoEIqIgIEIAIilBQAJAAgBFAAkRQFFQCAERFRIBAQBJAARACRFBSgASVFQFAGSlRUBQXgBZVAFQUgCKQKikKAUqxIpAA0FVFUAqK0lipFIFQIVUVAAKFlRTEqpFaAIIKCwoiopCqikABAAkKgkAJKgJACQAiiLUCQAEBAQECAAgBEQAioqAoVUSAQEACQq1KiCAQAiiKgQAChQCRFQFAKyURUBOQEmVRWWhQIIqKQKQIUApVQIURSFWIrUAqKURUUgVFIFgJKAQKilKIpAAQoilKqRSFisqQoBAAiAIACQAkIqIgASAAoCpIigKABIKgQiiKIqAnIASABCKIoAEIqIoFAhFQERUSEVGSIqIlRUZSAApWWmaCAAgCSiKkoBCgsIAChUUhQCFAKURYQqpFaCiKgoQKUAhQCAUKAgQoipKqK0CKkUhQEgAoRRJBUSFRUhFRIRUCAARACAEkABEVAhFEUSqlZKKgkABAgiIqBACKABCACICSAMkRUBQAFAKElZarIMBAFQEhQQUApVQIUApYAQoBAqKULAIWKikCoFKqKQsEUgVFKURSBUCFASWKitQCxFIFQSUBJFAoKCSKCQipQkABEVEgAIASQKAoFARFQIRUBEVEgoBIAiABIACgCKIoEgAIipQkABQAFEVKEMtVkEABAVIVFIAUoVFIAEFAKUAgVFKUQIVpIFKAQNMqQsVFIFRShYikCoEKAolAIVUCBUClEVJRORJQCgQCBBIABQAIARBBIACEAIRUBEoAgCSAgIAEAiIAElQEQEoQACgASAAoAChQoSVmqlBQUBUBIVFIFRShUUgAQUApQCBUUoVIpAqKkoitAWAgqxlWgqp7KUoBAAkoikCopQqBCgICopQIqQURIVFSQVEigAoAEgCIAEIAQCIgASItQEACQoIoqAIAEICSAAiCVEACAQIQARFQESqgKIqMkASFSKkKikCopQqKQKikACSwAgVFKFRSBUVIVFIFRShYikKqQIVUUgAKFRSBUClVAheQEgoJCoEKnuoEgCQAiAJIKgSCoiABAIkVFAUACQAFAQEASQAEBAiotREQAhFQEABQAJAAhARCiAojSBIKAoqKkKBAoFCopAqKQKilAKgAFCopAqKkKkUgAKUAhVRSBUilKIELFRUAFKACFEClASAVBFQSVARARIWIBKIJACKABCVUCEBEQARFQIRUBEVAgEBAEioqUFKAkJVQEACQCgoACgASAIpQQE5ACUBAVFKURShQIBQgVBJVRYQApAAUKipCopAqKUAEKIpShAhQEBUUpQCFEUoICCiKUCCSiKkIKkCKElASAERFRIACEAJKKiKCsgqgBCKlBQAERUCAEUKFCQBIRUBEVAgoAoioCIqAgASItEkF5AUVBJVRSBUUoVAhQEFAKVYgQqpypAAUKBQqKgAFKAQKBSiCDQkUgVApVRSAFSBApQEgQSUBAEEVEElQEgBIASAQIBAVQEhFQERUoSAAoACAVJAAUCoEABJRUBEBERUCEVARFAkBARFQEASAAlVINBVRUgAhQClVmKQoBAoFKAQoipKAQAFKAQoipABCxUClAIURUlAIACgBJQEgESAEgBIACARIURIAREVAgAJAERACQVAUACEVAQBFBUCQVAhFQFAAUACEVEQAJCgCgICCiTKooQqKUKikKECBQKFAgVBJoRSFEUgVApoQIURSlEEFAKUAgVFKFQSVUCFVFKBFQACgBJQRJUVEgBIACQBJUBIBAVQEhABAEkCgQgAiKgQAiIAQgAiUAhFQEQoCgAQioiABIACiLUBAAgRURUUgVFhAqBTQikKIIKAUoikKCFNCKQogUqoqAqBSgQhRBJQCF5EUpYrKkKAkApAAkAJKIFACQCBKIJACIAkIAQioCCKkCAQCAgCQgAgIkAAoAEIoEiKgIiokIAIioCABIAClSrUBAAkVBFVRSAOQhRFKUBBQChYggqopQqKQKgQoBSiKUoioCoFKECAVClioRBoRShUCFASVAIAElEVIASEFRQBIACAEkFRIRUBAAkASAEUFQJAAQESASgqgBAIkIqVkoACgAQioiIqAgASVFQEACQBFYAQoBAqKkoikKIpQAgoBShFIAClAIAElVAhQClAQVAKUAoWI1CEFCABJQEgAoASAEhUEABIABAEkBEgAFBUCEWoiogEAJIACIqBCKgIIJBRAQAIQQEACEBEQARKqUJAQFRAEASUAgipBJVSKQKilBBSABBQClEUhRBJQGgoCSgFKAQKCQAQKilCoqCgEABQqKkAJABQAkAJACQioEAJAIEqAiIASUAFFBJBUBEVKkAUFAAkFQJBUBEUCRFREABQKgQAChQSRFKyUARAElgCAqKUKikCoFKAgoQKAWECopAAkoDQUgqQAUKioABSgEAqJKsRSFEUoVAhRFSAEgAoRUSAAlEElEElQAkARAAkASQAECokqACIqBCKiIAEgAIigSAlSEVAQoAoigSAAiAkiKlZIAiAJKIqAqKURUikABSgqAAUKBAqKQRUUoVFIFQSUAoUCABJQCAUSAClVAhQCBUElASBFSAEhFRIASAEhFQIARKgBACQgAgIkAAiKgQgIiKgQCAqgBCKiIioEAAoAEgAKIqBCKgaAEgBIVFSFRSBUikABSkBBQChUUgVFKUAhQCABJYAUAIKAUoBAAkoKQigUKioABQAkKipAgkKgkAiSiKkCHIJUVAgoJCACAJIACAJIBQkBAVRUSEVAQECVABEBIBAQECEVARKqUEQAQQSUBIVFiCgNAUEgApVRSABBQClAIUApQCBUVIAKFAgASUAgVFSFQIUAoASVUUgRRIQVJBRJAEkFAkUEkFREACQBJAAQBJAARFQIBEQQCVACQBERUCAARACEURRFShCKgIlVAUACAEQBJRFiCgNBQEiKBQCkEAQUApQCFAKURSBUEhUUoVFIFQSUFIQFSACFEVIAKUQSUBAVBJRApUBIORAVEVIQEgESAQEACEAEBElQAhKAKCiSABAgCIqJCKUFAARASEVARFqBCKlBQAEASAElAQUFaAAkoBQqKQAIKAUsVFIAChUVAAKFApRFQAChQIUBIAIFAoBUkASAEgBJQRJQEBCiIIBLyIJACSAIiKgQioCAgKiAQAkVACAEUACEBFKAEJVQEBAQAIQEhFQFBUBAEgBJQCFVFhAAkKilAKQAIKAULAIURUgAhQClAKAEFAKFRSBUEhUElVFIAEgAoCiQqKkIqJKIJAAQiokBUSURQRKokyKgIAkiKAoi1AlBEgAERUCAEkABEVEkFQERUBAAkASQAFAAQBIASUBBVZUpQCBUUgVFKAEBUUpQCABJVRSCAFKIqQAUoBCiCSgEC8IqQAQogkKgkoCQAUABAIkqAkAJACSCoCAJIKgIAkgFBSotQJUoBAioiAEAJIAClCgQgIiKgICBACQioCgqAgCQAkKioCopQqBCqgUoBCgJCopAqKkKikABSiKQKgkqsqQoBQAkKikCoJKAgAFAASiRSgBIBKkqAkAJACQACICQgAgCSABCKiIigSABAIiAgSggQAigAQioiIqAiKgQCBAIiAAgAQAULEVJYIpAAQoBSgIKAUAIKqBSqgQoBQqCSgECgUKggoilACSiBCrygkKgkogkoCAqCSoCQBEgBIARQBIEEgAEASQAERUSAAgQSEVARFAkVAERUSAAhFRERUBAAkRQJEVEQAEACACgBJQCFBUAApQClEUgAQUAoVFIFRUhFCiKkUgVFSAQpQEhQQAClEElQElEVAVApQEhFRIASUESVASQVAQBIRUSAKEIKCgIkogkAAoAEAiIAEIqJAAKAJCKAoAEgqJIACgAIAEAFACSgEKIqCiKUsAKACFASFRSBUUgVFSFQKUAgVBJQEgAoVBBQCgBIASUBAASAEgBIASOTlBJQEhARAEgQCCgkAAolUSRUEgAFBQJEVEgAEQEgEBAAkARAAhACQoIoACCASgFACSiKQKkVIVIpAqBSgEKAkKgQqoqQqBCgFACCgFKiiQAkAFCoIKAUAJACSiKgAJAgiAJAUSVASAQJUBIASEAEASKAklFQIBAVQEhFQEASEBIRQFAEkABEVAgAJAEUABTkUCRUVIAKFBBRFKFAgAKUBBQChUCFVFSACFEElAKFRSBUVIEElAKFQQURUgBIAKAElQEgBIASAEgAJAEgBIARQAIASAQJUBERQJEVEgFRQAJAAgBFBUSEVARFAkACKgIoigKAJAASiKUoioKIpSgEABSgJCopAAgoBQqBSiLEFEUoAIUIJAqJKIqQAUAIACQqKkAFACQAkFBJAAgBIARAEgESVFAkASEWoEAIoAEIqJAAJUWokABCVURAAhAREVAhFQEBKEIqIgASKkVEVBBQClAIUAhQEiKilCoEKAgoilACSgECoqQAQoBQAkKgkoBQAkAIACSiKkAJACQgJAokgCQAiAJIqAQAkAJJQAQQCAEhFEUACEWokABCAiAgIAEgCQCAlBKEIqIqIBIoIgKgAFKAgRUUpQCAApQEBUUoVAhQElAIFQSUApQgQAJACRFQKUBAASAEhUVIBEgBIASAEgBEASEBIACAEgBJAARACAEgBIQARFRIACQBEBAQAIRUSEqpQRFQIRURAAgL2EgFSCAUoKQigkKBAAkKilCopAAgoilKIJKAQKipKIpAAUAJACSiKkAFACQAgAJACIAkAiSgBAgkqAkAJACQioEqAigqBACQAkgAIiokABCFAUFREACARIRUBEVAhFREDkCbyxYerZhxXDLF1zw0zjlthYcDm0AqQAQoCQqKQAJCopQAQoCQAgoilCxFiSiKQAFACAqBSgJACQAkogkoilACQCBKAUgAQAkAJAgEoipIKiQAiIAQAkioArygJCKiQAEAIoACIqJAASAJCKgIAEiKgIAk+11vSXVlbJ9y+/w+fng+r/Df4hj1eE6bqrPtbOMcr+f/AG49b0t05cz8N8V9fl48eTD7nH1/Dw8eeWGXhn2+Vlizw754ueUfOzw09cyc1Ec2liiJKAgKgUoCQqKUAJCopAAgRUUoASUAgVBJRFSACgRUhUUgASAEgFSQBIASUBJBUSAEhACAEQBIASAAhFEmRURA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Ms9eH4b/AGcrFljqqXbKgwQBEEAlASAEgBIAQURSgBIASAEkASAQEVBIASAQJRFSEBIASBFBQBIACQBEASAEgAIRUSAREACEBFFAIASAChUVBRFMCgQpVRfYgAIFRUgBIASVAKAAgBIASAEm9ez0X5xvmNbMJPvY98a5N69np+7l3xrpjlLPGs2fMZsG88eL27y+GFZoyoKjKAEVQAlQEgBIASUBBUApUBJRBIACEBEBElEAlEEgBIBEgAEASAEgECAEQBIASEAIASQAEBEgBEACAEgAoVFQFApSAQoBCgJCpFIBFSBFSAEgBIASAEkASFRUm9efb05eL4+hljcaw64Zyz0Zf0rrjd+qzfXtzRvKcVlmzRRRAVQAgBIASAEgBJUBJQEAAkRUCAEgAIRUSAEgBIABQBIASAQJQEhFREASBAIBElEEQAJAEgBFFCBACQAUoioCoqQqKQKgUqoEKAgogUAJKIqQAkAJACQiokAJKIqTrhfXPTl59qxZxWXSWbJ3/FHSXy/7Z6YCwBAAUACARJQEgBIACFQKVASUQSAAgESAEgQBUQSUESAEkUQJUBFUBIBAlEEgESAEQAIBEl90VEgBEEUIASAChUVAgKkAEKIpQqKgKgUKipABAqCSgJAipIoJIAkAJCoJKc2XmAk6c+uc+8YSWy8xu8ZTmOm/IdMKislBUSAAhFRIACFQSUQSUBIRRJAEgEBVFRIBElASAEgECAEQBIASEAIASEBEACAEkASAEQAIBElEElAKFRUBUElEElVAhQClEVAEUoASXkRUgEIaEElEElRRJBRJAEgAIWW43sgdpuzmcxExy9P6NWe88N9+wyKAoKgQiokABACQIqQAkAJCACAJACQAEAJAIiAJACQAkgqBACSAIgFCCgkgqIgCQCBKAkAiQKJACQAUKggoCSgECoqRAChUEFASAClQEhUElAIAElQEgBIACAEhcbx2vhAy6Tdn/pDC+18LlOG+/cCIqAgAQiiSIoEAJCACAJACQAEAJAioiAkAJACQAkAgSoCQAigqBAIkpQSQBEBEgAIVBJUVElACACgAoBUgBAVApRFQUAoVBBQEgBIAKFSKkAIACQAkChSCokABACQ1jeZxWQy6TVRZee18nDQQVAQVEkACAEkABAEgAIRUSVARAEgBIASAAhFEkASAEgQRAokigEgKkgCIiiSCoEAqSABKAU//2Q==") !important;
  background-color: #030b1b !important;
  background-position: center top !important;
  background-size: cover !important;
  background-repeat: no-repeat !important;
  background-attachment: fixed !important;
}


/* JC ALPHA EDGE — champagne claro de referencia; solo CSS */
:root{--jc-gold:#e1c99c;--jc-gold-soft:rgba(225,201,156,.92)}
.refapp .rcard,.refapp .reader,.refapp .finalclose,
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

/* ALPHA EDGE PREMIUM · EXCLUSIVAMENTE PRESENTACIÓN · 2026 */
.stApp,[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse at 55% 0%,#092b48 0%,#061222 38%,#020712 100%)!important}
.block-container{max-width:430px!important;padding:5px 9px 24px!important}
.refapp{position:relative;isolation:isolate;color:#f5f8ff!important}
.refapp::before{content:"";position:absolute;inset:0 0 auto;height:265px;z-index:-1;pointer-events:none;background:linear-gradient(132deg,transparent 9%,rgba(0,159,255,.15) 10%,transparent 11%,transparent 28%,rgba(2,175,255,.20) 29%,transparent 30%),radial-gradient(ellipse at 60% 65%,rgba(0,224,167,.10),transparent 65%)}
.refapp .rhead{height:82px!important;padding-top:10px!important}
.refapp .rtitle{font-size:19px!important;letter-spacing:1.5px!important;font-weight:1000!important;color:#f4f8ff!important;font-style:italic;text-shadow:0 2px 0 #61758a,0 0 13px #2ca9ff66!important}
.refapp .rver{font-size:10px!important;color:#d4deec!important}
.refapp .gear{font-size:25px!important;color:#dbe9ff!important;text-shadow:0 0 12px #29aaff88!important}
.refapp .rlive{bottom:0!important;border:1px solid #00d89c!important;background:#021916!important;color:#effffb!important;padding:5px 10px!important;border-radius:24px!important;box-shadow:0 0 12px #00e9a133!important}
.refapp .rhero{min-height:135px!important;position:relative;padding:10px 0 15px!important;background-image:linear-gradient(90deg,transparent 62%,rgba(1,10,24,.10)),url("data:image/webp;base64,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");background-repeat:no-repeat;background-size:auto,110px 112px;background-position:center,right 0 top 0}
.refapp .rsignal{font-size:78px!important;letter-spacing:-4px!important;filter:drop-shadow(0 0 10px var(--accent)) drop-shadow(0 0 18px var(--glow));-webkit-text-stroke:1px #d6fff066}
.refapp .rhero.waiting .rsignal{font-size:31px!important;letter-spacing:-1px!important}
.refapp .rconf{margin-top:13px!important;border:1.5px solid #ffd579!important;background:linear-gradient(100deg,#150f08,#3c2709 50%,#150f08)!important;border-radius:6px!important;padding:7px 17px!important;box-shadow:0 0 0 2px #6e4b1c,0 0 17px #ffb62d55!important;font-size:11px!important}
.refapp .rgrid{gap:9px!important;margin-top:9px!important}
.refapp .rcard,.refapp .reader,.refapp .finalcard,.refapp .finalclose,.refapp .analysisbox,.refapp .probbox,.refapp .tech{background:linear-gradient(145deg,#102e49 0%,#061626 45%,#030d1b 100%)!important;border:1px solid #b9954f!important;border-radius:17px!important;box-shadow:inset 0 1px 0 #b5ecff35,inset 0 -2px 12px #000b19,0 0 10px #00c6ff1e,0 2px 0 #062943!important}
.refapp .keycard{height:83px!important;padding:11px!important;gap:9px!important}
.refapp .rlabel{font-size:10px!important;font-weight:900!important;letter-spacing:.65px!important;color:#e1e8f6!important}
.refapp .rvalue{font-size:23px!important;letter-spacing:-.5px!important;text-shadow:0 0 9px #fff3!important}
.refapp .rdelta{font-size:11px!important}
.refapp .bigicon,.refapp .clock{font-size:35px!important;color:#ffbf48!important;text-shadow:0 0 12px #ffbd4377!important}
.refapp .bars b{box-shadow:0 0 7px var(--accent)!important}
.refapp .timebar{height:8px!important;background:#183249!important}.refapp .timebar b{background:linear-gradient(90deg,#04d7ae,#5affbd)!important;box-shadow:0 0 9px #00ffb3!important}
.refapp .probs{margin-top:11px!important;padding:13px 12px!important;border-color:#47caff!important}
.refapp .pbar{gap:6px!important;margin-top:9px!important}.refapp .pup,.refapp .pdown{height:28px!important;border-radius:10px!important;font-size:12px!important;box-shadow:0 0 16px #00ffb944!important}
.refapp .pdown{box-shadow:0 0 15px #ff526344!important}
.refapp .pleg{font-size:11px!important}
.refapp .reader{margin-top:12px!important;padding:15px 12px!important;border:1.5px solid #e3ad55!important;box-shadow:0 0 12px #ffc25d30,inset 0 0 15px #0098e011!important}
.refapp .readerhead{font-size:13px!important;font-weight:1000!important;font-style:italic;color:#fff4df!important;text-shadow:0 0 8px #ffd36b55!important}
.refapp .readerhead em{font-style:normal!important;border-color:#00eaa4!important;color:#0ff4b3!important;font-size:10px!important}
.refapp .readerbody{grid-template-columns:1fr 108px!important;margin:12px 0!important;min-height:110px!important}
.refapp .readerbody strong{font-size:23px!important;font-style:italic!important;text-shadow:0 0 12px var(--rr)!important}
.refapp .rring{width:104px!important;height:104px!important;box-shadow:0 0 16px var(--rr),inset 0 0 12px #071a25!important}
.refapp .rring:after{width:79px!important;height:79px!important;background:#03111e!important}
.refapp .rring span{font-size:25px!important}
.refapp .finalclose{border-color:#2f9fcb!important;padding:10px!important}
.refapp .finalcard,.refapp .analysisbox,.refapp .probbox{border-color:#2d7596!important;border-radius:13px!important}
.refapp .finalbig{font-size:22px!important;text-shadow:0 0 10px currentColor!important}
.refapp .tech{margin-top:11px!important;border-color:#d6a957!important}
.refapp .techrow,.refapp .techrow>div{border-color:#54718c!important}
.refapp .techrow b{font-size:12px!important}
.refapp .green{color:#00f2ae!important}.refapp .red{color:#ff5967!important}
@media(max-width:380px){.refapp .rvalue{font-size:19px!important}.refapp .readerbody strong{font-size:19px!important}.refapp .rhero{background-size:auto,86px 88px}}


/* PREMIUM REBUILD v2: responsive, integrated artwork, no change to decisions */
.stApp,[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse at 50% 0,#06375d 0%,#05162a 40%,#010710 100%)!important}
.block-container{max-width:440px!important;padding:5px 9px 25px!important}
.refapp{overflow:hidden;isolation:isolate;background:linear-gradient(148deg,rgba(1,23,44,.4),transparent 30%)!important}
.refapp:before{height:320px!important;background:repeating-linear-gradient(134deg,transparent 0 73px,rgba(0,145,244,.14) 75px,transparent 77px),radial-gradient(ellipse at 70% 34%,rgba(0,220,204,.14),transparent 58%)!important}
.refapp .rhead{height:75px!important;padding-top:8px!important}
.refapp .rtitle{font-size:22px!important;font-style:italic!important;text-transform:uppercase!important;letter-spacing:1.4px!important;color:#f4f8ff!important;text-shadow:0 2px 1px #3b526c,0 0 12px #229cff77!important}
.refapp .rver{font-size:11px!important}
.refapp .rlive{bottom:0!important;right:6px!important;border-color:#00eea8!important;background:rgba(0,24,22,.88)!important}
.refapp .rhero{height:166px!important;min-height:166px!important;padding:15px 0 10px!important;background-image:linear-gradient(120deg,rgba(0,159,250,.07),transparent 58%)!important;background-size:cover!important;background-position:center!important;overflow:visible!important}
.refapp .rhero:before{content:"";position:absolute;right:-8px;top:-7px;width:38%;height:125px;background-image:url("data:image/webp;base64,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");background-size:contain;background-repeat:no-repeat;background-position:center;opacity:.92;mix-blend-mode:screen;pointer-events:none;filter:drop-shadow(0 0 8px #d9a12b66);-webkit-mask-image:radial-gradient(ellipse,#000 38%,transparent 78%);mask-image:radial-gradient(ellipse,#000 38%,transparent 78%)}
.refapp .rhero:after{content:"";position:absolute;left:0;bottom:11px;width:44%;height:66px;opacity:.27;pointer-events:none;background:repeating-linear-gradient(90deg,transparent 0 12px,#00d9ff 13px 15px,transparent 16px 23px);-webkit-mask-image:linear-gradient(0deg,transparent,#000,transparent);mask-image:linear-gradient(0deg,transparent,#000,transparent)}
.refapp .rsignal{position:relative;z-index:1;transform:translateX(-7px);font-size:82px!important;letter-spacing:-4px!important;font-style:italic!important;filter:drop-shadow(0 0 12px var(--accent));text-shadow:0 0 9px var(--glow),0 0 28px var(--glow),0 3px 1px #021f23!important}
.refapp .rhero.waiting .rsignal{font-size:32px!important;letter-spacing:-1px!important;transform:none!important}
.refapp .rconf{position:relative;z-index:2;margin-top:15px!important;background:linear-gradient(95deg,#030e19,#1d1b16,#030e19)!important;border:2px solid #e7b44e!important;border-radius:8px!important;padding:8px 15px!important;font-size:12px!important;box-shadow:0 0 16px #eab74a77,0 0 22px var(--soft)!important}
.refapp .rgrid{gap:9px!important;margin-top:8px!important}
.refapp .rcard,.refapp .reader{background:linear-gradient(138deg,#102c45 0%,#04111e 58%,#061c2c 100%)!important;border:1px solid #78b8e7!important;border-radius:16px!important;box-shadow:inset 0 1px 0 #c1e9ff4a,0 3px 15px #00101c99,0 0 6px #008cff38!important}
.refapp .keycard{height:80px!important;padding:10px 11px!important;gap:10px!important;position:relative;overflow:hidden}
.refapp .keycard:after{content:"";position:absolute;right:0;bottom:0;width:38px;height:18px;background:linear-gradient(135deg,transparent 45%,#ffd36b66 95%);pointer-events:none}
.refapp .rlabel{font-size:10px!important;font-weight:800!important;letter-spacing:.35px!important;color:#e4eafa!important}
.refapp .rvalue{font-size:23px!important;color:#f5faff;font-weight:900!important}
.refapp .rdelta{font-size:11px!important}
.refapp .bigicon,.refapp .clock{color:#f9b943!important;text-shadow:0 0 12px #e9a12955!important}
.refapp .bars b{box-shadow:0 0 8px var(--accent)!important}
.refapp .probs{padding:13px!important;margin-top:11px!important}
.refapp .pup,.refapp .pdown{height:29px!important;border-radius:10px!important;font-size:14px!important;box-shadow:0 0 13px var(--glow)!important}
.refapp .pleg{font-size:12px!important;margin-top:7px!important}
.refapp .reader{margin-top:12px!important;padding:12px!important;border-color:#d7a54e!important;box-shadow:inset 0 1px 0 #f7d58e5c,0 0 15px #d7a54e44!important}
.refapp .readerhead{font-size:16px!important;font-weight:900!important;font-style:italic!important;color:#f8faff!important}
.refapp .readerhead em{font-size:10px!important;border-color:#00e9a6!important;color:#00e9a6!important;padding:5px 10px!important}
.refapp .readerbody{grid-template-columns:minmax(0,1fr) 110px!important;min-height:95px!important;margin:4px 0 9px!important;gap:7px!important}
.refapp .readerbody strong{font-size:21px!important;font-style:italic!important;line-height:1.05!important;text-shadow:0 0 13px var(--rr)!important}
.refapp .rring{width:104px!important;height:104px!important;box-shadow:0 0 19px var(--rr)!important}
.refapp .rring:after{width:79px!important;height:79px!important;background:#04121f!important}
.refapp .rring span{font-size:27px!important}
.refapp .finalpanel{margin-top:7px!important}
.refapp .finalcard,.refapp .motionrow,.refapp .analysisrow>div{border-color:#4c9ac7!important;border-radius:12px!important}
.refapp .tech{margin-top:12px!important;padding:11px!important}
@media(max-width:380px){.refapp .rhero{height:147px!important;min-height:147px!important}.refapp .rsignal{font-size:67px!important}.refapp .rvalue{font-size:19px!important}.refapp .readerbody strong{font-size:18px!important}.refapp .readerbody{grid-template-columns:minmax(0,1fr) 92px!important}.refapp .rring{width:88px!important;height:88px!important}.refapp .rring:after{width:65px!important;height:65px!important}.refapp .rring span{font-size:23px!important}}

/* iPad / tablet responsive layout: presentation only. */
@media (min-width: 700px) {
  .block-container,
  [data-testid="stMainBlockContainer"] {
    width: min(94vw, 1050px) !important;
    max-width: 1050px !important;
    padding: 12px 18px 35px !important;
    margin-inline: auto !important;
  }
  .refapp { width:100% !important; max-width:none !important; }
  .refapp .rhead { height:105px !important; padding:14px 20px 0 !important; }
  .refapp .rtitle { font-size:clamp(25px,3vw,36px) !important; }
  .refapp .rhero { height:205px !important; min-height:205px !important; }
  .refapp .rhero:before { width:31% !important; height:178px !important; right:15px !important; }
  .refapp .rsignal { font-size:clamp(92px,12vw,142px) !important; }
  .refapp .rhero.waiting .rsignal { font-size:clamp(34px,5vw,57px) !important; }
  .refapp .rconf { font-size:16px !important; padding:10px 25px !important; }
  .refapp .rgrid { gap:14px !important; margin-top:15px !important; }
  .refapp .keycard { height:112px !important; padding:18px 22px !important; }
  .refapp .rlabel { font-size:13px !important; }
  .refapp .rvalue { font-size:clamp(27px,3.7vw,38px) !important; }
  .refapp .rdelta { font-size:14px !important; }
  .refapp .probs { padding:19px 22px !important; }
  .refapp .pup,.refapp .pdown { height:38px !important; font-size:17px !important; }
  .refapp .reader { padding:20px 24px !important; }
  .refapp .readerhead { font-size:20px !important; }
  .refapp .readerbody { min-height:130px !important; grid-template-columns:minmax(0,1fr) 145px !important; }
  .refapp .readerbody strong { font-size:clamp(27px,3.4vw,38px) !important; }
  .refapp .rring { width:132px !important; height:132px !important; }
  .refapp .rring:after { width:100px !important; height:100px !important; }
  .refapp .rring span { font-size:34px !important; }
  .refapp .tech { padding:16px !important; }
  .refapp .techrow b { font-size:15px !important; }
}
@media (max-width: 699px) {
  .block-container,[data-testid="stMainBlockContainer"] { width:100% !important; max-width:440px !important; margin-inline:auto !important; padding:5px 9px 25px !important; }
}


/* ALPHA EDGE · refinamiento responsive de app 22(1) · SOLO CSS */
/* Señal nítida: reducir halo que ocultaba la flecha y las letras. */
.refapp .rhero{filter:none!important}
.refapp .rsignal{
  filter:drop-shadow(0 0 3px var(--accent))!important;
  text-shadow:0 1px 0 #05261f,0 0 5px var(--glow)!important;
  -webkit-text-stroke:1px rgba(225,255,245,.55)!important;
}
.refapp .cssarrow{
  box-shadow:0 0 5px var(--glow),inset 0 0 2px rgba(255,255,255,.42)!important;
}
.refapp .cssarrow:before{filter:drop-shadow(0 0 3px var(--glow))!important}
/* Toro: disolver los límites de la ilustración sobre el fondo, sin moverla. */
.refapp .rhero:before{
  -webkit-mask-image:radial-gradient(ellipse 83% 82% at 55% 49%,#000 46%,transparent 100%)!important;
  mask-image:radial-gradient(ellipse 83% 82% at 55% 49%,#000 46%,transparent 100%)!important;
}
/* Lector: conservar círculo y dirección, sin bloque vertical vacío. */
.refapp .readerbody{
  min-height:0!important;
  margin:2px 0 6px!important;
  align-items:center!important;
}
.refapp .readerbody strong{line-height:1.08!important}
.refapp .reader{padding-bottom:11px!important}
.refapp .finalclose{margin-top:4px!important}
/* La tablet conserva ancho completo; el teléfono mantiene sus dos columnas. */
@media(max-width:699px){
  .refapp .rhero{height:156px!important;min-height:156px!important}
  .refapp .rsignal{font-size:clamp(62px,11vw,80px)!important}
  .refapp .readerbody{grid-template-columns:minmax(0,1fr) 100px!important}
  .refapp .rring{width:96px!important;height:96px!important}
  .refapp .rring:after{width:73px!important;height:73px!important}
  .refapp .rring span{font-size:23px!important}
  .refapp .finalgrid{grid-template-columns:1fr 1fr!important;gap:6px!important}
  .refapp .finalcard.motion{grid-column:1 / -1!important}
  .refapp .finalanalysis{grid-template-columns:minmax(0,1fr) 92px!important}
}
@media(min-width:700px){
  .refapp .readerbody{grid-template-columns:minmax(0,1fr) 130px!important}
  .refapp .rring{width:122px!important;height:122px!important}
  .refapp .rring:after{width:92px!important;height:92px!important}
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

    if flow_state is None:
        flow_state = st.session_state
    now = pd.Timestamp.now(tz="UTC").timestamp()
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


# Probabilidades orientativas calculadas únicamente por el motor Gemini-Kalshi.

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
    """Muestra únicamente los requisitos producidos por Gemini-Kalshi."""
    decisions = sig.get("decision_checks")
    if not isinstance(decisions, dict):
        return {"valid": False, "sides": {}, "noise_ok": False}
    sides = {}
    for side in ("UP", "DOWN"):
        checks = list(decisions.get(side, []))
        sides[side] = [{"name": "ALPHA EDGE", "checks": checks,
                        "met": sum(bool(ok) for _, ok in checks),
                        "total": len(checks),
                        "complete": bool(checks) and all(bool(ok) for _, ok in checks)}]
    return {"valid": bool(sides["UP"][0]["total"]), "sides": sides,
            "noise_ok": True}

def _signal_engine_without_trace(df, target, seconds_left, live_price=None, whale=None):
    """Motor experimental Gemini + contexto Kalshi. Solo propone UP/DOWN/espera.

    No ejecuta operaciones. Los porcentajes son puntuaciones orientativas,
    no probabilidades calibradas. Mantiene el contrato de salida del panel.
    """
    one = add_indicators(df)
    three = _resample_indicators(df, 3)
    five = _resample_indicators(df, 5)
    l1, l3, l5 = one.iloc[-1], three.iloc[-1], five.iloc[-1]
    candle_price = float(l1["close"])
    price = float(live_price) if live_price is not None else candle_price
    if not np.isfinite(price) or price <= 0:
        price = candle_price

    def number(value, default=0.0):
        v = _plan_number(value)
        return float(v) if v is not None else default

    def direction(row):
        if not np.isfinite(number(row["adx"])) or number(row["adx"]) <= 18:
            return "NEUTRAL"
        if row["ema9"] > row["ema21"] and row["macd_hist"] >= 0:
            return "UP"
        if row["ema9"] < row["ema21"] and row["macd_hist"] <= 0:
            return "DOWN"
        return "NEUTRAL"

    d3, d5 = direction(l3), direction(l5)
    atr = number(l1["atr"], max(price * .0005, 1.0))
    if atr <= 0:
        atr = max(price * .0005, 1.0)
    target_value = _plan_number(target)
    if target_value is not None and target_value <= 0:
        target_value = None
    distance = price - target_value if target_value is not None else None
    distance_pct = distance / target_value * 100 if distance is not None else None
    target_atr = distance / atr if distance is not None else 0.0
    vwap = number(l1["vwap"], price)
    if vwap <= 0:
        vwap = price
    vwap_atr = (price - vwap) / atr
    rsi1, rsi3, rsi5 = (number(row["rsi"], 50.0) for row in (l1, l3, l5))
    adx5 = number(l5["adx"])
    rvol = number(l1["vol_ratio"], 1.0)
    mom3, mom5, mom15 = (number(l1[k]) for k in ("mom3", "mom5", "mom15"))
    impulse = _internal_impulse_context(one, price, atr, mom3, mom5, mom15, rvol)
    ema_side = "BULL" if l1["ema9"] > l1["ema21"] else "BEAR"
    macd1 = number(l1["macd_hist"])
    macd3 = number(l3["macd_hist"])
    macd5 = number(l5["macd_hist"])

    # Base de Gemini: EMA, MACD, VWAP, tendencia 3m y 5m.
    score = (1.0 if ema_side == "BULL" else -1.0)
    score += 1.0 if macd1 > 0 else -1.0
    score += 1.0 if price > vwap else -1.0
    score += 1.5 if d3 == "UP" else -1.5 if d3 == "DOWN" else 0.0
    score += 2.0 if d5 == "UP" else -2.0 if d5 == "DOWN" else 0.0

    # Volumen y agotamiento modulan la evidencia, sin exigirlos siempre.
    # Un volumen bajo reduce la fuerza de la candidatura; volumen alto
    # solo refuerza cuando el momentum reciente confirma el mismo lado.
    if rvol < .65:
        score *= .75
    elif rvol >= 1.2 and mom3 != 0 and score * mom3 > 0:
        score += .5 if score > 0 else -.5
    if impulse.get("reliable"):
        if impulse.get("exhaust_up") and score > 0:
            score -= 1.5
        if impulse.get("exhaust_down") and score < 0:
            score += 1.5

    # ATR y distancia al strike: cuanto más cerca del cierre, más
    # importante es la posición frente al precio objetivo de Kalshi.
    # Sin strike válido no se inventa una ventaja para ninguno de los lados.
    remaining = None if seconds_left is None else max(0.0, min(900.0, number(seconds_left)))
    if distance is not None and remaining is not None:
        time_weight = .25 + .75 * (1.0 - remaining / 900.0) ** 1.5
        score += float(np.clip(target_atr, -2.0, 2.0)) * 1.5 * time_weight

    # Mantener neutralidad si el mercado está sin dirección definida.
    candidate = None
    if score >= 2.0 and rsi1 > 48:
        candidate = "UP"
    elif score <= -2.0 and rsi1 < 52:
        candidate = "DOWN"

    noise = abs(vwap_atr) < .12 and adx5 < 17 and abs(mom3) < .015
    checks_by_side = {}
    for side, sign in (("UP", 1), ("DOWN", -1)):
        exhaustion = bool(impulse.get("exhaust_up" if sign == 1 else "exhaust_down"))
        checks = [
            ("Puntuación y RSI a favor", score * sign >= 2 and (rsi1 > 48 if sign == 1 else rsi1 < 52)),
            ("Movimiento fuera de ruido", not noise),
            ("Sin agotamiento direccional", not exhaustion),
            ("Volumen utilizable", rvol >= .45),
        ]
        # Evitar señalar el lado perdedor con poco margen de recuperación
        # cuando el cierre está próximo. No impide giros tempranos fuertes.
        if distance is not None and remaining is not None and remaining <= 180:
            adverse_atr = -sign * target_atr
            allowed = .20 + .80 * remaining / 180.0
            checks.append(("Strike alcanzable antes del cierre",
                           adverse_atr <= allowed or
                           (score * sign >= 5.0 and mom3 * sign > .04 and
                            not exhaustion)))
        if remaining is not None:
            checks.append(("Ronda abierta", remaining > 0))
        checks_by_side[side] = checks
    if candidate and not all(ok for _, ok in checks_by_side[candidate]):
        candidate = None

    diagnostics = {}
    for side in ("UP", "DOWN"):
        checks = checks_by_side[side]
        diagnostics[side] = {"route": "ALPHA EDGE", "missing": [label for label, ok in checks if not ok],
                             "met": sum(bool(ok) for _, ok in checks), "total": len(checks)}
    quality = "ALPHA EDGE" if candidate else "SIN CONFIRMACIÓN"
    up_probability = float(np.clip(50 + score * 7, 5, 95))
    flow_side = (whale or {}).get("flow_direction") if isinstance(whale, dict) else None
    flow_context = {"direction": flow_side, "valid": False}
    return {
        "price": price, "candle_price": candle_price, "rsi": rsi1,
        "rsi3": rsi3, "rsi5": rsi5, "mom3": mom3, "mom5": mom5,
        "mom15": mom15, "vol_ratio": rvol, "ema": ema_side,
        "technical_score": score, "target_score": target_atr, "final_score": score,
        "distance": distance, "distance_pct": distance_pct,
        "momentum": "ALCISTA" if score > 0 else "BAJISTA" if score < 0 else "NEUTRAL",
        "up_probability": round(up_probability), "down_probability": round(100-up_probability),
        "candidate": candidate, "quality": quality, "route_diagnostics": diagnostics,
        "trend3": d3, "trend5": d5, "adx": adx5,
        "plus_di": number(l5["plus_di"]), "minus_di": number(l5["minus_di"]),
        "macd3": macd3, "macd5": macd5, "atr": atr, "vwap": vwap,
        "vwap_atr": vwap_atr, "target_atr": target_atr,
        "impulse_internal": impulse, "entry_route_internal": quality,
        "flow_support_internal": {"used": False, "direction": None, "reason": "CONTEXTO"},
        "flow_context_internal": flow_context, "macd1": macd1,
        "price_ema9_atr": (price-number(l1["ema9"], price))/atr,
        "decision_checks": checks_by_side,
    }


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

def _reset_withdrawal(state):
    """Compatibilidad de estado; sin reglas de retención del cerebro anterior."""
    state.update(withdraw_direction=None, withdraw_source=None, withdraw_count=0,
                 withdraw_since=None, withdraw_last_at=None, retention_warning=None)


def _confirmation_without_trace(state, candidate, market, seconds_left, now, signal=None):
    """Confirma solo el candidato Gemini-Kalshi; no recalcula su dirección.

    La primera señal se conserva para historial; la señal activa puede
    cambiar tras dos lecturas contrarias confirmadas. Nueva ronda espera.
    """
    close_time = (market or {}).get("close_time")
    if close_time:
        end = pd.to_datetime(close_time, utc=True, errors="coerce")
        if pd.isna(end):
            candidate = None
        else:
            actual_left = (end - pd.Timestamp(now)).total_seconds()
            seconds_left = actual_left if seconds_left is None else min(seconds_left, actual_left)
    if seconds_left is not None and seconds_left <= 0:
        state["active_direction"] = None
        state["active_since"] = None
        state["pending_direction"] = None
        state["pending_count"] = 0
        return
    # La primera señal queda registrada como historial, NO como candado.
    # Una dirección contraria debe superar la misma confirmación de lecturas.
    # Mientras se confirma, se mantiene la última señal validada.
    if state.get("active_direction") == candidate and candidate in ("UP", "DOWN"):
        state["pending_direction"] = None
        state["pending_count"] = 0
        state["pending_since"] = None
        state["pending_last_at"] = None
        return
    if not signal or signal.get("data_valid") is False or candidate not in ("UP", "DOWN"):
        state["pending_direction"] = None
        state["pending_count"] = 0
        state["pending_since"] = None
        state["pending_last_at"] = None
        state["opening_conflict"] = None
        return
    # Confirmación de lecturas independientes; no contiene filtros técnicos viejos.
    last = state.get("pending_last_at")
    if isinstance(last, str):
        last = pd.to_datetime(last, utc=True, errors="coerce")
        last = last.to_pydatetime() if pd.notna(last) else None
    if (state.get("pending_direction") != candidate or last is None
            or (now - last).total_seconds() < 0
            or (now - last).total_seconds() > SIGNAL_CONFIRM_MAX_GAP):
        state["pending_direction"] = candidate
        state["pending_count"] = 1
        state["pending_since"] = now.isoformat()
        state["pending_last_at"] = now.isoformat()
        return
    if (now - last).total_seconds() >= SIGNAL_CONFIRM_INTERVAL:
        state["pending_count"] = int(state.get("pending_count", 0)) + 1
        state["pending_last_at"] = now.isoformat()
    if state.get("pending_count", 0) >= SIGNAL_CONFIRM_READINGS:
        state["active_direction"] = candidate
        state["active_since"] = now
        # Conservar la primera señal para historial y límite de una entrada.
        # Los cambios confirmados posteriores actualizan solo active_direction.
        if state.get("first_direction") not in ("UP", "DOWN"):
            state["first_direction"] = candidate
            state["first_signal_time"] = now
            state["first_signal_seconds"] = seconds_left
            state["first_signal_price"] = (get_yes_ask(market) if candidate == "UP"
                                           else get_no_ask(market))
        state["pending_direction"] = None
        state["pending_count"] = 0
        state["pending_since"] = None
        state["pending_last_at"] = None
        state["opening_conflict"] = None

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

    # Gemini-Kalshi propone; dos lecturas espaciadas confirman la señal.
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
BACKGROUND_DATA_REVISION = "continuous_history_active_market_discovery_recent_support_v1_candle_sources_v2_flow_opening_v3"
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
    return state

# Cinta micro compartida entre sesiones Streamlit del MISMO proceso.
# El trabajador autónomo la alimenta aun cuando el navegador se desconecta.
_MICRO_SHARED_LOCK = threading.RLock()
_MICRO_SHARED = {"ticker": None, "source": None, "prices": []}

def _record_shared_micro(ticker, price, source, observed_ts=None):
    if not ticker or ticker == "--" or not source:
        return
    try:
        p = float(price)
        t = float(observed_ts) if observed_ts is not None else time.time()
    except (TypeError, ValueError):
        return
    if not math.isfinite(p) or p <= 0 or abs(time.time() - t) > LIVE_PRICE_MAX_AGE:
        return
    with _MICRO_SHARED_LOCK:
        shared = _MICRO_SHARED
        if shared["source"] != source:
            shared.update(ticker=ticker, source=source, prices=[])
        else:
            shared["ticker"] = ticker
        tape = shared["prices"]
        if tape and (t - tape[-1]["t"] > SIGNAL_CONFIRM_MAX_GAP or t < tape[-1]["t"]):
            tape.clear()
        if not tape or t - tape[-1]["t"] >= 1.0:
            tape.append({"t": t, "p": p})
        shared["prices"] = [v for v in tape if v["t"] >= time.time() - 90]

def _shared_micro_snapshot(ticker, source):
    with _MICRO_SHARED_LOCK:
        if _MICRO_SHARED["ticker"] != ticker or _MICRO_SHARED["source"] != source:
            return []
        return [dict(x) for x in _MICRO_SHARED["prices"]]

def _background_history_loop(stop_event=None):
    started = time.monotonic()
    active_ticker = None
    active_state = None
    whale_state = {}
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
            background_source = getattr(_BACKGROUND_PRICE_SOURCE, "value", None)
            observed = getattr(_PRICE_OBSERVATIONS, "values", {}).get(background_source)
            _record_shared_micro(ticker, live_price, background_source, observed)
            btc_df = _background_get_btc_data()
            try:
                whale = get_coinbase_whale_flow(whale_state)
            except Exception:
                whale = None
            sig = build_signal(btc_df, target, seconds_left, live_price,
                               getattr(_BACKGROUND_PRICE_SOURCE, "value", None), whale=whale)
            if stop_event and stop_event.is_set():
                break
            active_state = _background_update_state(active_state, sig, market, seconds_left)
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
    observed = getattr(_PRICE_OBSERVATIONS, "values", {}).get(price_source)
    _record_shared_micro(ticker, live_price, price_source, observed)
    st.session_state.micro_ticker = ticker
    st.session_state.micro_price_source = price_source
    st.session_state.micro_prices = _shared_micro_snapshot(ticker, price_source)


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


# Suavizado de volatilidad compartido entre sesiones del mismo proceso.
_CLOSING_SIGMA_LOCK = threading.RLock()
_CLOSING_SIGMA_STATE = {"source": None, "sigma": None, "timestamp": 0.0}

def closing_reader(sig, seconds_left, micro):
    """Lector independiente basado en distancia, tiempo y volatilidad observada.

    El porcentaje es un índice de apoyo NO calibrado, no una probabilidad.
    No lee candidate, round_signal ni up_probability del cerebro principal.
    """
    price = _plan_number(sig.get("price"))
    distance = _plan_number(sig.get("distance"))
    atr = _plan_number(sig.get("atr"))
    remaining = _plan_number(seconds_left)
    direction = None
    percent = 50
    headline = "REUNIENDO DATOS"
    note = "Falta precio, target o tiempo para evaluar el cierre."
    if remaining is not None and remaining <= 0:
        headline = "RONDA TERMINADA · RESULTADO PENDIENTE"
        note = "Esperando el resultado oficial de Kalshi."
    elif price is not None and distance is not None and remaining is not None:
        remaining = max(1.0, remaining)
        # Estimar desplazamiento por segundo con diferencias de la cinta compartida.
        # Usar datos frescos; saltos de sesión no cuentan como movimiento de mercado.
        tape = list(st.session_state.get("micro_prices", []))
        now = time.time()
        tape = [v for v in tape if now - v["t"] <= 65]
        increments = []
        for prev, cur in zip(tape, tape[1:]):
            dt = cur["t"] - prev["t"]
            if 0.8 <= dt <= 6.0:
                increments.append((cur["p"] - prev["p"]) / math.sqrt(dt))
        observed_sigma = float(np.std(increments, ddof=1)) if len(increments) >= 8 else None
        # Respaldo con ATR de 1m: evitar falsa certeza si faltan ticks o la
        # volatilidad reciente parece artificialmente baja.
        atr_sigma = (atr / math.sqrt(60.0)) if atr is not None and atr > 0 else price * 0.0005 / math.sqrt(60.0)
        # Mezcla progresiva: evita el salto al alcanzar la muestra número 8.
        # Mantiene una base conservadora mientras llegan suficientes observaciones.
        if observed_sigma is None:
            sigma = max(atr_sigma, 0.01)
        else:
            weight = float(np.clip((len(increments) - 3) / 24.0, 0.0, 1.0))
            measured = max(observed_sigma, atr_sigma * 0.5, 0.01)
            sigma = (1.0 - weight) * max(atr_sigma, 0.01) + weight * measured
        # Suavizado compartido entre recargas de la página, sin tocar el cerebro.
        global _CLOSING_SIGMA_STATE
        with _CLOSING_SIGMA_LOCK:
            state = _CLOSING_SIGMA_STATE
            now_m = time.monotonic()
            if state["source"] != st.session_state.get("micro_price_source"):
                state.update(source=st.session_state.get("micro_price_source"),
                             sigma=None, timestamp=now_m)
            previous = state["sigma"]
            if previous is not None:
                dt = max(0.0, min(now_m - state["timestamp"], 30.0))
                alpha = 1.0 - math.exp(-dt / 14.0)
                sigma = previous + alpha * (sigma - previous)
            state["sigma"] = sigma
            state["timestamp"] = now_m
        expected_move = max(sigma * math.sqrt(remaining), 1.0)
        # El movimiento actual solo influye parcialmente y nunca garantiza el cierre.
        drift = 0.0
        if micro.get("ready"):
            c10 = _plan_number(micro.get("change_10s"))
            c30 = _plan_number(micro.get("change_30s"))
            if c10 is not None and c30 is not None:
                velocity = 0.65 * (c10 / 10.0) + 0.35 * (c30 / 30.0)
                drift = float(np.clip(velocity * remaining * 0.25, -expected_move, expected_move))
        adjusted = distance + drift
        z = float(np.clip(adjusted / expected_move, -5.0, 5.0))
        # Mostrar siempre la inclinación actual cuando hay datos válidos,
        # incluso cerca del target. Un apoyo cercano a 50% indica incertidumbre.
        # Esto afecta SOLO al lector de cierre, no a la señal principal.
        direction = "UP" if z >= 0 else "DOWN"
        # Índice orientativo, NO probabilidad calibrada.
        percent = int(round(50 + 49 * math.erf(abs(z) / math.sqrt(2.0))))
        percent = max(50, min(99, percent))
        headline = "SEÑAL DE CIERRE " + direction
        note = ""
    color = "#00dfb5" if direction == "UP" else "#e64b4b" if direction == "DOWN" else "#38bdf8"
    return {"percent": percent, "headline": headline, "note": note,
            "micro": "", "direction": direction, "color": color,
            "border": "rgba(56,189,248,.45)",
            "bg": "linear-gradient(135deg,rgba(11,64,91,.30),rgba(9,23,34,.72))"}


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
.readerbody small,.finalnote,.analysistext span,.features span,.chartfoot{font-size:11px!important;color:#cbd5e1!important;line-height:1.5!important}
.readerhead,.finaltitle,.motionrow small,.analysistext small,.probbox small,.features strong{font-size:10px!important}
.rhero{filter:drop-shadow(0 0 9px var(--accent))}
.note,.footer,.sub,.card small,.metric small,.tooltip,.chartnav span,summary small{color:#cbd5e1!important;font-size:11px!important}
.floatcounts div{border-color:#00dfb5;box-shadow:0 0 9px #00dfb544}.floatcounts div:last-child{border-color:#e64b4b;box-shadow:0 0 9px #e64b4b44}
.canvas svg rect,.canvas svg line{shape-rendering:geometricPrecision}
@media(max-width:460px){.finalgrid{grid-template-columns:1fr 1fr}.finalcard.motion{grid-column:1 / -1}.features{grid-template-columns:1fr}.finalanalysis{grid-template-columns:1fr 90px}}


/* Purple neon outlines, consistent across dashboard and chart cards. */
.rcard,.mini,.section,.close-reader,.reader,.refapp>section[style],
.finalclose,.finalcard,.analysisbox,.probbox,.chartbox,
.panel,.card,.metric,details,.floatcounts div{
 border-color:#23685e!important;
 box-shadow:0 0 4px #00dfb51a,inset 0 0 4px #00dfb508!important;
}
.panel{border:1.5px solid #23685e!important;margin:8px 6px!important}
.rcard,.mini,.reader,.card,.metric,details{border-width:1.5px!important}
.techrow,.rnav,.chartnav{border-color:#23685e!important}


/* Uniform turquoise presentation. Signal values and timing are unchanged. */
.stApp,[data-testid="stAppViewContainer"]{background:#06121a!important}
.refapp .rcard,.refapp .reader,.refapp .finalclose,
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
.readerbody small,.finalnote,.analysistext span,.features span,.chartfoot{font-size:11px!important;color:#cbd5e1!important;line-height:1.5!important}
.readerhead,.finaltitle,.motionrow small,.analysistext small,.probbox small,.features strong{font-size:10px!important}
.rhero{filter:drop-shadow(0 0 9px var(--accent))}
.note,.footer,.sub,.card small,.metric small,.tooltip,.chartnav span,summary small{color:#cbd5e1!important;font-size:11px!important}
.floatcounts div{border-color:#00dfb5;box-shadow:0 0 9px #00dfb544}.floatcounts div:last-child{border-color:#e64b4b;box-shadow:0 0 9px #e64b4b44}
.canvas svg rect,.canvas svg line{shape-rendering:geometricPrecision}
@media(max-width:460px){.finalgrid{grid-template-columns:1fr 1fr}.finalcard.motion{grid-column:1 / -1}.features{grid-template-columns:1fr}.finalanalysis{grid-template-columns:1fr 90px}}


/* Purple neon outlines, consistent across dashboard and chart cards. */
.rcard,.mini,.section,.close-reader,.reader,.refapp>section[style],
.finalclose,.finalcard,.analysisbox,.probbox,.chartbox,
.panel,.card,.metric,details,.floatcounts div{
 border-color:#23685e!important;
 box-shadow:0 0 4px #00dfb51a,inset 0 0 4px #00dfb508!important;
}
.panel{border:1.5px solid #23685e!important;margin:8px 6px!important}
.rcard,.mini,.reader,.card,.metric,details{border-width:1.5px!important}
.techrow,.rnav,.chartnav{border-color:#23685e!important}


/* Uniform turquoise presentation. Signal values and timing are unchanged. */
.stApp,[data-testid="stAppViewContainer"]{background:#06121a!important}
.refapp .rcard,.refapp .reader,.refapp .finalclose,
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
.refapp .rcard,.refapp .reader,.refapp .finalclose,
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
<section class="panel">
<header class="header"><div><h2>BTC / USD</h2><div class="sub" id="subtitle"></div></div><div><div class="price" id="price"></div><div class="live" id="live"></div></div></header>
<details id="whale"><summary>🐋 WHALE FLOW <small>EN VIVO · TOCA PARA ABRIR</small></summary><div class="detail"><h3>🐋 WHALE FLOW — LIVE</h3><div class="note">Operaciones observadas de Coinbase · últimos 30 s</div><div class="watch" id="watch"></div><div class="metrics"><div class="metric"><small>BUY FLOW</small><b class="green" id="buy"></b></div><div class="metric"><small>SELL FLOW</small><b class="red" id="sell"></b></div><div class="metric"><small>DIFERENCIA</small><b id="diff"></b></div><div class="metric"><small>ACTIVIDAD</small><b id="activity"></b></div><div class="metric"><small>FUERZA DEL DESEQUILIBRIO</small><b id="strength"></b></div></div><div class="bars"><div class="bar">BUY<div class="track"><i id="buybar" style="background:#00dfb5"></i></div><b id="buytotal"></b></div><div class="bar">SELL<div class="track"><i id="sellbar" style="background:#e64b4b"></i></div><b id="selltotal"></b></div></div><div class="count"><div class="metric"><small>🐋 BUY WHALES</small><b class="green" id="buys"></b></div><div class="metric"><small>🐋 SELL WHALES</small><b class="red" id="sells"></b></div></div><div class="metric difference"><small>DIFERENCIA DE OPERACIONES</small><b id="countdiff"></b></div><p class="note">«Whales»: operaciones individuales de al menos $10,000, no personas identificadas. Muestra recibida por la API; puede omitir operaciones entre consultas. Actividad: ritmo de los últimos 10 s frente a los 20 s anteriores. En el laboratorio, el flujo puede apoyar una candidatura solo con confirmación técnica; no decide por sí solo.</p></div></details>
<details id="momentum"><summary>⚡ SHORT-TERM MOMENTUM <small>EN VIVO · TOCA PARA ABRIR</small></summary><div class="detail"><h3>MOVIMIENTO RECIENTE DE BTC</h3><div class="metrics" id="momrows"></div><p class="note">Cambio porcentual calculado por el motor en 3, 5 y 15 minutos. La temporalidad de la gráfica no cambia estos valores.</p></div></details>
<div class="tools"><h3>INDICADORES</h3><div class="toggles" id="toggles"></div><div class="legend" id="legend"></div></div>
<div class="floatcounts"><div>🐋 BUY WHALES <b id="floatbuy"></b></div><div>🐋 SELL WHALES <b id="floatsell"></b></div></div>
<div class="tooltip" id="tooltip">Arrastra con un dedo · amplía con dos · AHORA vuelve al precio actual.</div><div class="canvas" id="canvas"></div>
<div class="chartnav"><button id="older" aria-label="Velas anteriores">←</button><button id="newer" aria-label="Velas siguientes">→</button><button id="zoomin" aria-label="Acercar">＋</button><button id="zoomout" aria-label="Alejar">−</button><button id="reset">AHORA</button><span id="viewtf"></span></div>
</section>
<script>
let D=__PAYLOAD__; const $=id=>document.getElementById(id), fmt=(v,n=2)=>v==null?'—':Number(v).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n}), usd=v=>v==null?'—':'$'+fmt(v), compact=v=>v==null?'—':v>=1e6?'$'+(v/1e6).toFixed(2)+'M':v>=1000?'$'+(v/1000).toFixed(0)+'K':'$'+fmt(v,0);
let saved={};try{saved=JSON.parse(localStorage.getItem('btc-neon-panel-v1')||'{}')}catch(e){}
let toggles=Object.assign({ema9:true,ema21:true,vwap:true,volume:true,rsi:true,},saved.toggles),visible=saved.visible||32,offset=saved.offset||0,pricePan=Number.isFinite(saved.pricePan)?saved.pricePan:0;
function persist(){try{localStorage.setItem('btc-neon-panel-v1',JSON.stringify({toggles,visible,offset,pricePan,whale:$('whale').open,momentum:$('momentum').open}))}catch(e){}}
for(const name of ['whale','momentum']){$(name).open=!!saved[name];$(name).addEventListener('toggle',persist)}
function refreshLabels(){
$('subtitle').textContent=D.timeframe.toUpperCase()+' · '+(D.candle_source||'COINBASE')+' · BTC SIGNAL';$('price').textContent=usd(D.price);$('live').textContent=D.price==null?'● SIN COTIZACIÓN':'● PRECIO RECIBIDO';$('viewtf').textContent=D.timeframe+' · VELAS REALES';
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
const all=D.rows,n=all.length;visible=Math.max(12,Math.min(visible,Math.max(12,n)));offset=Math.max(-Math.floor(visible*.6),Math.min(offset,Math.max(0,n-visible)));const virtualEnd=n-Math.round(offset),end=Math.min(n,virtualEnd),start=Math.max(0,virtualEnd-Math.round(visible)),rows=all.slice(start,end);if(!rows.length){$('canvas').innerHTML='<div class="empty">Esperando velas actuales…</div>';return}
const last=all[n-1];$('legend').innerHTML=['ema9','ema21','vwap'].filter(k=>toggles[k]).map(k=>'<span><i style="color:'+colors[k]+'">●</i> '+k.toUpperCase()+' '+usd(last[k])+'</span>').join('');
const W=720,H=toggles.rsi?780:615,L=10,R=126,T=28,B=580,plot=W-L-R,freeRight=164,candlePlot=plot-freeRight,step=candlePlot/Math.round(visible),body=Math.max(3.8,Math.min(18,step*.84));
let vals=rows.flatMap(r=>[r.low,r.high]);for(const k of ['ema9','ema21','vwap'])if(toggles[k])vals.push(...rows.map(r=>r[k]).filter(v=>v!=null));for(const v of [D.target,D.support,D.resistance,D.price])if(v!=null)vals.push(v);let lo=Math.min(...vals),hi=Math.max(...vals),pad=Math.max((hi-lo)*.12,5);lo-=pad;hi+=pad;lo+=pricePan;hi+=pricePan;const y=v=>T+(hi-v)/(hi-lo)*(B-T),x=i=>L+(i+.5)*step;
let s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Gráfica BTC con velas, indicadores y RSI"><defs><clipPath id="plot"><rect x="0" y="0" width="'+(W-R)+'" height="'+B+'"/></clipPath></defs>';
for(let k=0;k<7;k++){const yy=T+(B-T)*k/6;s+='<line x1="0" y1="'+yy+'" x2="'+(W-R)+'" y2="'+yy+'" stroke="#202039"/><text x="'+(W-R+10)+'" y="'+(yy+5)+'" fill="#9ca6c2" font-size="14">'+fmt(hi-(hi-lo)*k/6)+'</text>'}
for(let k=0;k<=4;k++){const xx=L+plot*k/4;s+='<line x1="'+xx+'" y1="'+T+'" x2="'+xx+'" y2="'+(toggles.rsi?H-30:B)+'" stroke="#191c34"/>'}
s+='<g clip-path="url(#plot)">';if(toggles.volume){const max=Math.max(...rows.map(r=>r.volume),1);rows.forEach((r,i)=>{let h=r.volume/max*105;s+='<rect x="'+(x(i)-body/2)+'" y="'+(B-h)+'" width="'+body+'" height="'+h+'" fill="'+(r.close>=r.open?'#00dfb5':'#e64b4b')+'" opacity=".9"/>'})}
rows.forEach((r,i)=>{const c=r.close>=r.open?'#00dfb5':'#e64b4b';s+='<line x1="'+x(i)+'" x2="'+x(i)+'" y1="'+y(r.high)+'" y2="'+y(r.low)+'" stroke="'+c+'" stroke-width="2.1"/><rect x="'+(x(i)-body/2)+'" y="'+Math.min(y(r.open),y(r.close))+'" width="'+body+'" height="'+Math.max(1.8,Math.abs(y(r.open)-y(r.close)))+'" fill="'+c+'"/>'});
for(const k of ['ema9','ema21','vwap'])if(toggles[k]){let points=rows.map((r,i)=>r[k]==null?'':x(i)+','+y(r[k])).filter(Boolean).join(' ');s+='<polyline points="'+points+'" fill="none" stroke="'+colors[k]+'" stroke-width="3" '+(k==='vwap'?'stroke-dasharray="8 6"':'')+'/>'}
s+='</g>';let levels=[[D.resistance,'RESISTANCE','#e64b4b'],[D.target,'TARGET','#00dfb5'],[D.price,'BTC','#00dfb5'],[D.support,'SUPPORT','#00dfb5']].filter(r=>r[0]!=null).map(r=>({v:r[0],label:r[1],c:r[2],yy:y(r[0]),labelY:y(r[0])})).filter(l=>l.yy>=T&&l.yy<=B).sort((a,b)=>a.yy-b.yy);
let previous=T-20;for(const l of levels){l.labelY=Math.max(T+14,previous+32,l.yy);previous=l.labelY}let excess=previous-(B-14);if(excess>0)for(const l of levels)l.labelY-=excess;
for(const l of levels){const edge=W-R,priceX=edge+2,labelWidth=l.label==='BTC'?0:(l.label==='RESISTANCE'?146:106),labelX=priceX-labelWidth;s+='<line x1="0" y1="'+l.yy+'" x2="'+edge+'" y2="'+l.yy+'" stroke="'+l.c+'" stroke-width="'+(l.label==='TARGET'?2.5:1)+'" stroke-dasharray="'+(l.label==='TARGET'?'6 5':'3 4')+'" opacity=".9"/><path d="M '+edge+' '+l.yy+' L '+priceX+' '+l.labelY+'" stroke="'+l.c+'" fill="none"/>';if(labelWidth)s+='<rect x="'+labelX+'" y="'+(l.labelY-14)+'" width="'+labelWidth+'" height="28" rx="2" fill="'+l.c+'"/><text x="'+(labelX+labelWidth/2)+'" y="'+(l.labelY+6)+'" text-anchor="middle" fill="#06101b" font-size="18">'+l.label+'</text>';s+='<rect x="'+priceX+'" y="'+(l.labelY-14)+'" width="120" height="28" rx="2" fill="'+l.c+'"/><line x1="'+priceX+'" x2="'+priceX+'" y1="'+(l.labelY-14)+'" y2="'+(l.labelY+14)+'" stroke="#06101b" stroke-width="1"/><text x="'+(priceX+6)+'" y="'+(l.labelY+6)+'" fill="#06101b" font-size="18">'+fmt(l.v)+'</text>'}
if(toggles.rsi){const rt=620,rh=120,rvals=rows.map(r=>r.rsi).filter(Number.isFinite),rmin=rvals.length?Math.min(...rvals):30,rmax=rvals.length?Math.max(...rvals):70,rpad=Math.max((rmax-rmin)*.15,3);let rlo=Math.max(0,rmin-rpad),rhi=Math.min(100,rmax+rpad);if(rhi-rlo<20){const mid=(rhi+rlo)/2;rlo=Math.max(0,mid-10);rhi=Math.min(100,rlo+20);rlo=Math.max(0,rhi-20)}const ry=v=>rt+(rhi-v)/(rhi-rlo)*rh;s+='<text x="14" y="610" fill="#aa8dc5" font-size="12">RSI 14</text>';for(let v=Math.ceil(rlo/10)*10;v<=rhi;v+=10)s+='<line x1="0" y1="'+ry(v)+'" x2="'+(W-R)+'" y2="'+ry(v)+'" stroke="#29243d"/><text x="'+(W-R+10)+'" y="'+(ry(v)+5)+'" fill="#9ca6c2" font-size="14">'+fmt(v)+'</text>';s+='<polyline points="'+rows.map((r,i)=>Number.isFinite(r.rsi)?x(i)+','+ry(r.rsi):'').filter(Boolean).join(' ')+'" fill="none" stroke="#f000ff" stroke-width="3"/>';const shownRsi=rows[rows.length-1].rsi;if(Number.isFinite(shownRsi))s+='<rect x="'+(W-R+4)+'" y="'+(ry(shownRsi)-12)+'" width="65" height="25" rx="3" fill="#f000ff"/><text x="'+(W-R+11)+'" y="'+(ry(shownRsi)+6)+'" fill="white" font-size="15">'+fmt(shownRsi)+'</text>'}
for(let k=0;k<4;k++){const i=Math.round((rows.length-1)*k/3),tm=new Date(rows[i].t*1000).toLocaleString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit',...(D.timeframe==='1D'?{month:'short',day:'numeric'}:{})});s+='<text x="'+x(i)+'" y="'+(H-7)+'" fill="#95a1bc" font-size="11" text-anchor="middle">'+tm+'</text>'}
s+='<g id="crosshair"></g></svg>';$('canvas').innerHTML=s;geometry={W,H,L,R,T,B,rows,x,y,lo,hi,start,end,visible,step,candlePlot};
}
$('zoomin').onclick=()=>{visible=Math.max(12,Math.round(visible*.75));persist();draw()};$('zoomout').onclick=()=>{visible=Math.round(visible*1.3);persist();draw()};$('older').onclick=()=>{offset+=Math.max(5,Math.floor(visible/4));persist();draw()};$('newer').onclick=()=>{offset-=Math.max(5,Math.floor(visible/4));persist();draw()};$('reset').onclick=()=>{offset=0;visible=32;pricePan=0;draw();persist()};
const touchPoints=new Map();let gesture=null;
function chartPoint(e){const r=$('canvas').getBoundingClientRect();return {x:(e.clientX-r.left)/r.width*geometry.W,y:(e.clientY-r.top)/r.height*geometry.H}}
function beginGesture(){
 if(!geometry||!touchPoints.size){gesture=null;return}
 const p=[...touchPoints.values()],g=geometry;
 gesture={points:p.map(v=>({...v})),visible:g.visible,offset,pricePan,range:g.hi-g.lo,plot:g.candlePlot,height:g.B-g.T,end:g.end};
 if(p.length>=2){gesture.distance=Math.max(12,Math.hypot(p[1].x-p[0].x,p[1].y-p[0].y));gesture.center=(p[0].x+p[1].x)/2;gesture.anchor=g.start+Math.max(0,Math.min(1,(gesture.center-g.L)/gesture.plot))*g.visible}
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
 if(!geometry)return;e.preventDefault();const p=chartPoint(e),g=geometry,fraction=Math.max(0,Math.min(1,(p.x-g.L)/g.candlePlot)),anchor=g.start+fraction*g.visible;
 visible=Math.max(12,Math.min(D.rows.length,Math.round(g.visible*(e.deltaY>0?1.15:.85))));offset=Math.round(D.rows.length-anchor-(1-fraction)*visible);draw();persist();
},{passive:false});
function inspectCandle(px){if(!geometry)return;const g=geometry,i=Math.max(0,Math.min(g.rows.length-1,Math.floor((px-g.L)/g.step))),r=g.rows[i],time=new Date(r.t*1000).toLocaleString('en-US',{timeZone:'America/New_York'});$('tooltip').textContent=time+' · O '+fmt(r.open)+'  H '+fmt(r.high)+'  L '+fmt(r.low)+'  C '+fmt(r.close)+' · Vol '+fmt(r.volume,3);$('crosshair').innerHTML='<line x1="'+g.x(i)+'" x2="'+g.x(i)+'" y1="'+g.T+'" y2="'+g.B+'" stroke="#b8a5e0" stroke-dasharray="4 4"/>'}

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
    reader = closing_reader(sig, seconds_left, micro)
    if not btc_ok:
        reader = {**reader, "percent":0, "direction":None,
                  "headline":"SIN DATOS ACTUALES",
                  "note":"No se puede evaluar el cierre hasta recuperar las velas."}
    reader_percent_label = f"{reader['percent']}%" if reader.get("direction") else "—"
    if seconds_left is not None and seconds_left <= 0:
        # El reloj y el precio instantáneo no prueban la liquidación oficial.
        reader = {**reader, "percent": 0, "direction":None,
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
    # Indicador visual independiente: altura de las tres barras según
    # la distancia ABSOLUTA al target, con escala de referencia de $150.
    # No modifica señales, lector de cierre ni porcentajes.
    bar_level = min(1.0, max(0.0, abs(distance) / 150.0)) if distance is not None else 0.0
    bar_heights = [round(10 + bar_level * extra) for extra in (12, 26, 44)]
    # El diseño usa una altura máxima de 30px; se escalan proporcionalmente.
    bar_heights = [round(h * 28 / 54, 1) for h in bar_heights]
    bars_html = ''.join(f'<b style="height:{h}px"></b>' for h in bar_heights)
    first_signal = (state.get("first_direction") if state else None) or "--"
    first_time = "--"
    if state and state.get("first_signal_time"):
        signal_dt = state["first_signal_time"]
        if signal_dt.tzinfo is None:
            signal_dt = signal_dt.replace(tzinfo=timezone.utc)
        first_time = signal_dt.astimezone(ZoneInfo("America/New_York")).strftime("%-I:%M %p")

    # Etiqueta visual en español; el motor conserva internamente BULL/BEAR.
    ema_display = "ALCISTA" if sig.get("ema") == "BULL" else "BAJISTA" if sig.get("ema") == "BEAR" else sig.get("ema", "N/A")

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

    # Estado factual independiente del motor de señales.
    if seconds_left is not None and seconds_left <= 0:
        final_status = "RESULTADO OFICIAL PENDIENTE"
        final_note = "Esperando la liquidación oficial de Kalshi."
    elif distance is None:
        final_status = "SIN POSICIÓN DISPONIBLE"
        final_note = "Esperando precio y target actualizados."
    else:
        final_status = f"POSICIÓN ACTUAL {market_side}" if market_side != "NEUTRAL" else "PRECIO EN EL TARGET"
        final_note = "Posición del precio frente al target; no determina el cierre definitivo."
    final_status_color = "#00dfb5" if market_side == "UP" else "#e64b4b" if market_side == "DOWN" else "#94a3b8"
    final_distance_label = f"${abs(distance):,.0f}" if distance is not None else "—"
    final_dist_pct_label = f"{abs(distance_pct):.2f}%" if distance_pct is not None else "SIN TARGET"
    final_panel = f'''<div class="finalclose">
      <div class="finalgrid">
        <div class="finalcard motion"><div class="finaltitle">▥ &nbsp; MOVIMIENTO ÚLTIMOS SEGUNDOS</div><div class="motionrow">
          <div><small>30s</small><b style="color:{'#00dfb5' if c30>=0 else '#e64b4b'}">{motion_labels[30]}</b></div>
          <div><small>10s</small><b style="color:{'#00dfb5' if c10>=0 else '#e64b4b'}">{motion_labels[10]}</b></div>
          <div><small>5s</small><b style="color:{'#00dfb5' if c5>=0 else '#e64b4b'}">{motion_labels[5]}</b></div>
        </div><div class="finalnote">Cambio de precio en los últimos segundos.</div></div>
        <div class="finalcard distance"><div class="finaltitle">▥ &nbsp; DISTANCIA AL TARGET</div><div class="finalbig" style="color:{distance_color}">{final_distance_label}</div><div class="finalsub" style="color:{distance_color}">{final_dist_pct_label}</div></div>
        <div class="finalcard speed"><div class="finaltitle">VELOCIDAD</div><div class="finalbig" style="color:{speed_color}">{speed_arrow} {speed_word}</div><div class="finalsub" style="color:{speed_color}">{speed_value}</div><div class="finalnote">En los últimos 10 s.</div></div>
      </div>
      <div class="finalanalysis">
        <div class="analysisbox"><div class="analysisicon">◎</div><div class="analysistext"><small>{'ANÁLISIS DE CIERRE (ÚLTIMOS 60 s)' if seconds_left is not None and 0 < seconds_left <= 60 else 'POSICIÓN ACTUAL FRENTE AL TARGET'}</small><b style="color:{final_status_color}">{final_status}</b><span>{final_note}</span></div></div>
        <div class="probbox"><small>{'APOYO A ' + reader['direction'] if reader.get('direction') else 'SIN APOYO DIRECCIONAL'}</small><b>{reader_percent_label if reader.get('direction') else '—'}</b></div>
      </div>
    </div>'''

    # Advertencia compacta únicamente visual; usa el aviso existente del motor.
    weakness_html = (
        '<div class="weakness-inline" role="status">⚠ ' +
        html.escape(round_signal.get("reversal_text") or "SEÑAL PERDIENDO FUERZA") +
        '</div>'
        if round_signal.get("reversal") and active in ("UP", "DOWN") else ""
    )

    panel_html = f"""
<div class="refapp dir-{active.lower() if active in ("UP","DOWN") else "wait"}" style="--accent:{accent};--glow:{glow};--soft:{soft};">
  <header class="rhead">
    <img class="jc-real-logo" src="data:image/jpeg;base64,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" alt="JC ALPHA EDGE" />
    <div class="rtitle">BTC Signal</div>
    <div class="rver">v4.6.1</div>
    <a class="gear" href="?page=settings" target="_self" aria-label="Ajustes">⚙</a>
    <div class="rlive"><i></i>{'Mercado en vivo' if market_live else 'Conexión parcial'}</div>
  </header>

  <section class="rhero {'waiting' if active not in ('UP','DOWN') else ''}">
    <div class="rsignal"><span class="cssarrow"></span><span>{hero_word}</span></div>
    <div class="rconf">{'APOYO DEL MOTOR ' + str(confidence) + '%' if active in ('UP','DOWN') else round_signal["signal"]}</div>
  </section>

  {weakness_html}


  <div class="rgrid">
    <div class="rcard keycard">
      <div class="bigicon btcicon">₿</div>
      <div><div class="rlabel">BTC</div><div class="rvalue">${sig["price"]:,.0f}</div>
      <div class="rdelta {'green' if sig["mom3"] >= 0 else 'red'}">{btc_delta}</div></div>
    </div>
    <div class="rcard keycard">
      <div class="bigicon targeticon">◎</div>
      <div><div class="rlabel">TARGET</div><div class="rvalue">{target_text}</div></div>
    </div>
    <div class="rcard keycard">
      <div class="bars" style="--accent:{distance_color}">{bars_html}</div>
      <div><div class="rlabel">DISTANCIA AL TARGET</div><div class="rvalue" style="color:{distance_color}">{distance_text}</div>
      <div class="rdelta" style="color:{distance_color}">{distance_sub}</div></div>
    </div>
    <div class="rcard keycard">
      <div class="clock">◷</div>
      <div class="timecontent"><div class="rlabel">TIEMPO RESTANTE</div><div class="rvalue">{countdown}</div>
      <div class="timebar"><b style="width:{time_pct}%"></b></div></div>
    </div>
  </div>

  <section class="rcard probs">
    <div class="rlabel">APOYO CALCULADO · UP / DOWN</div>
    <div class="pbar"><div class="pup" style="width:{up}%">{up}%</div><div class="pdown" style="width:{down}%">{down}%</div></div>
    <div class="pleg"><span class="green">● &nbsp;UP&nbsp; {up}%</span><span class="red">● &nbsp;DOWN&nbsp; {down}%</span></div>
  </section>

  <section class="reader" style="--rb:{reader['border']};--rbg:{reader['bg']};--rr:{reader['color']}">
    <div class="readerhead"><span class="pulse">⌁</span><span>LECTOR DE CIERRE</span><em>ACTIVO</em></div>
    <div class="readerbody"><div><strong style="color:{reader['color']}">{reader['headline']}</strong></div>
    <div class="rring" style="--p:{reader['percent']}"><span>{reader_percent_label}</span></div></div>
    {final_panel}
  </section>




  <section class="rcard tech">
    <div class="techhead"><span>DETALLES TÉCNICOS</span><span>⌃</span></div>
    <div class="techrow">
      <div><small>1ª SEÑAL</small><b style="color:var(--accent)">{first_signal}</b><i>{first_time}</i></div>
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
        chart_timeframe = st.radio(
            "Temporalidad del gráfico",
            ["1m", "3m", "5m", "15m", "1h", "4h", "1D"],
            horizontal=True, key="chart_timeframe", label_visibility="collapsed",
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
    _capture_recent_alert(state, signal, market, now)

    try:
        payload = {"candidate":candidate, "seconds_left":seconds_left, "now":now, "before":before, "after":dict(state), "engine_variant":"gemini_kalshi_clean_v1", "quotes":{"yes":get_yes_ask(market), "no":get_no_ask(market)}}
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
        header = dict(schema_version=1,ticker=ticker,engine_variant="gemini_kalshi_clean_v1",
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
.refapp .rcard,.refapp .reader,.refapp .finalclose,
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


# ETAPA GRÁFICA: arte real extraído de la referencia proporcionada.
# Solo se modifica la presentación. Se conserva el motor original.
st.markdown('''<style>
.refapp .rhead {
  min-height: 125px !important;
  background-image: linear-gradient(90deg,rgba(0,10,24,.04),rgba(0,10,24,.04)),
    url("data:image/png;base64,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sA34OMABBGcftBAlay0TFb1MCtl+wYXXXnvtZz79SfF+5cqVP/P2n9LgRfMeour8suXLLr30slar9dJLLz366KOzM532UPPcbecfOXpo5bKV69atvf322/fu2bNi+YprrrlmdGzkyJEjd9xxx5FDh2AsvFx00QXbzj/PmvTBRx54+qlnvTj12mqml26/eMuWLU898eRwuy3OJ8aK93m3t2HDhksuv2xi6bIdu57/0b33584759jaotdLm2ne6QB+6cTEFVdcsWL5yqeeefqxx56YmZlpDQ2deeaZU8eOTUyMb926Ncuy22677dDBw5wk1pjCFUNDQ2eeeWa3M/vMM89I4diYjZs3b9646YEHHnhp1wseyoq3vOXHDx89cv8DD4HUe127es2pp57ywH33e++2X3D+hRdeoE4efuzR+++/3+U5EXNqfe5MYkviLVARQL0CBKEjL72sBlgyjMmeLzJjgvezLw2qLc5xkaIoIMJJoqqaZZu3bjn/gm3j46PLl6/+sTffkufwAqh895vfPnRgP8iSkG22s8KLEhHnDsysxsIqSK2hH97+g594bufqUze4nt94+pn/4Vf+01OPPyZKO3Y999TjjyrJIvytV5pu9c0OavYaKTtRHyrhir5srYyHcv5EqVDOzwWzMlSUURq0BuqIYsWiCKnxnDQbDU8eTpJGg8UZLZaMNbZvP/ctb7nlxte+fsnEGHwBdFHsnXxpx1133nnvvY88u3Pf4RmZypfM5twpKJditld4H4BH58kEJdGpwJO1jZSTp5/bs2vX1FlbLl01tuau2797pj993YZ1EFUvueRNW9AQwyQYa4n3q9avnj3UWD5X+LxonN0YmRj3zFCDmWLL6Wfect2V6zZu+tYd97iZw2Mj6etff+PY2NjOXS90ehk1GxA1NvVFASUNDOQqdRgrkWs2zNlnb37u2afnej00Uq+kRbZi6cjWDeOnLCtWLvGNBArqzPVGx+mXf+mn3njT9sM7n/ijD/7hI0/tVjvsi3yoxWtX0aplnV/+xTf/7L954933PnzHHQ8+8OAzTz+7Z9/h2SzzjWbbifrCgYyKgKhkYTIUMR/G/J7rB3TUozwkVh8JNEyrSmybQGrStksapsmnnbpk+znrv/iJjz171z2UNgleNFfNkc+i2zEckhJaHxCHkKCQtMx6aogMwaohA5IIkLCwIZhQ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IReygNcwWRuBhHmWZGiTCZtTp94tn3jY4Dfe9OKzNh0Y3X1PGe+BIM0f8f3b9r3nH77x0AKk5aIQ4s48i48UncFcALbQA9WSkYr3GlyCOlsvcZ1KcYOIRJTxDjjMrGmaGC4mYld0XT7j1DOecv5TDcbMTz7vKc985rM+9rGPpZTAbmTqtnnrlsHMcN++fXfecIdDZ2dnn/CEM5//3MuOO+6En/u5n/vOd77dNOlZz/qh//Hf33XmGWc5/N57737ggQdm5mbOOvOs5z/3eeeec95v/+f/+5//+Z+/+uWv/cPff+jXf/3XX/CCF1xyySUf/8QnnbB58+bXv/71J5xw0n333fcXf/lX+w8snnLKae985ztf8tIXmfuDD91/17fv2LRp7pxzzrngggvOOeecY48//r/9t/9neXmxaZNqNjPm1GVN0s7ObVLHaLT20AMPjsfjpmmOPPLI5z73+U95ylOfev6F/9d//s2HH37YnZxapxZob731tkcf3dsbPqq7jtcmMAjEDG1qmVLOaBSImdlQa8aqNDBJzjpoZzbNbxGRM05/wjN/6JKbbr41NYNciogcffTRL3rJK7cddhSAJDNMAy+SzS659Dn//b//9yc96Uk559tvuf2xxx7btmPHWWee+epXveap513wX3/vd//+/X9fOr377nuZuXR569atRx11NAi7H921srpERHv3PpqzijQ/8sOv/f3f/287jzgCRDfcdPNj+x876ogjzjzzzB894aRznnTer//6r3/hC19IibuiTTNo2+Hdd9994MCBQdPOzs6eeuqpr3jliUccefRP/+xP3XX3ncSUAWlS7pQpcdOqUS548KHdTZpzaErJ3IX5yKOO2Tw/v2//gQOLyyzNYTuP2Lxl22OP7Xvggfty1pRS0zSPPPKIKsHo5S99xStf/qrPfOrT3/z2t372p3/u1371V6+56ppbbrv13HPPecsb3/TwQw/97fve143XUsMAtIoF1qV/AUhsOPbczYkIVsKvOMpkBkXXq+RukfxG7m7O7DB1JuIiLADbarYm4YZ795178ubBoM2l2333Q1/78Ide9eKXLS2vfuXGu3i41SQJiTNUFRMFQ4RViycJBIU5Fcooioawa/HAp79qLNvPP2MB2jUpDEaXu6W5wcyaKdAhdQSc/fLnjTV/4a/+riyvyoBZ3WFMpF1hSWrZlSIT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JKJqrjaZTl/0ohcdOnRI1d/2tre96U1vIqJ2urZ3794k7Ste/so//MM/PH78eEopODS3337bv/23/049q/rRo0fvueee7a0tkPT94o477njNa15z+PDhZz3rWY899thisZhOmj73cH/6FVfdeOONJLjnnnuOnTjuUDVvWjlx4thstpVzfvzRx2IS5r5X1XvuuUe1v+iii174whfeeeedOWcRIpKc88UXHXrOc57DoFOnTj3yyCPMEGn7voeqixeUDlbzsiwiBk+SXvrSl155xdM2Nzfvu+8+N4uY++zZs3/yJx++5ZZbmMHMkeAQEQAi4k6TyQRGxGi4cfau64PHkJJY1miANhCMVDXn/Ik//eSdX7vr2c981sFDF+Wcb7rppscffzSllFLKXc/MWxtnjx49mnO+/vprr7766i/91W2Bl0TW47rrrrvqqqsAHDnyYN8v4nY4hdq3m+XCtAdSSseOHTt69KirXXPNNZdfetnJk0+00uacU5L5onvBC15w+aWXzWazBx98ELCAZxaLxa//+q+/+93/9Yd/+If/6T/9p8x89OjRhx4+EmtKUgKTlaDF22bSdV3TNKquqpcdvuw1r3ktU7r11lu/8pU7iaht277v+75/6KGHHnzw/pTayWRN+3z77bc/8vDDV1911aFDh1JKBeEQNtXvePl3/tiP/dhnP/vZz372s7/yy/9+7+59//gfv/Pee+/9jd/4jR/5kR/5k4/8yWc++1kCJET1C+xQozciYoSWUMx2joWCiEOcgZipAheCwJmcKCT/nAjMxJTFLbrPNy0W5tn8qiv5H/3sD/3gq2/07snZYjfa/Q88iV/91Xffde+RnnY1k0ledEScnHvNcK6BLNeWBcTOngxgYlDUT6aEex85ddOfH56+cs9VF28AzNxpnxruvWPVVvxJN8pZ1na/5h0/1s76r/zJTZY1FAXALqkxcZ0vqG0099I0ofaImsatG13ZEmukt4Lhe8UAVjPIDHcwcyOFEUlEnKr/4VR7MFuEo9yg7xwEEVjC+t793/KSa2988R133K9nZ8gG75EXbsqWNc9DZ97hZhlqgDGzCPV9h5xJwR5dYt2FQIQug0N6SrNmYinNtDnBM6gJ9uPhZ97Qz2fH7voqLMNy9Xh0BDbYjtGIe2/bydA8eUgSgamUTFIo+Q+6CZG1Ltl/oRTbgruTiJnlnCeTyXStnc/nfd83TaNL9iDVPpw8cBBQq3CZnIa6BTvXGDqgOfed9x1yBpFl76npSQCBJ/LEKlCCkZm5GmlGUB2zUs6RyRj+M4ZKaCAraad5Ae/gHbqt3G1pXkTepLIsdUijkNsgzUkjJ8AJgyZBUGxQMDMHEU2b3XvWd+3a1TRN/YQSuyRKDTeJo9B6cFnO9VqK/QyEJv6L3nFwz9HGcglErJJ66oslg4PRewo4AYpch5XXV77dULssVj2n2E84FjlxL+gSZSYjUSQnIW5YUhIWAF23+PbXfe/rfuGtR9byEd863dg2nNpJ13UCSiLaL9Tzem/d57925t0fw/3HsJVZnYzgHMURntVzDs6sZffsVvonaqUydovc99R+6JOfPzXvr3rGtRunHrt4Pf/o67/tqotBjHYqlMBCbSPujkRE0UoKDdCQN+gb71ugBSbgBtIgJUiilIgTlSrVUqsKZ3iCJ0AIDBdCAsQ9AQkQEDkYDCN2vvjgxa99zevaNJnPO1VfX9+9vr6bQd180S0W3/Gyl73oW77Vspr20U34sUe//qef/PjHPvrhT9z0sa/e8WWzvLY+TUKau1v+8jPHTzx66aWXvOlH/t6Bi/aDsOh7NV/bNf25n//Zl3zbi89ubtzyub88ffYUSVTrzSdTYebJZAJYN5+FUjXMPn/rLffee/fBg/t/9M1vesb11wHW9/1stj2ZNK9//etf+PwXMOjzt97y9YePJCHtOyG0Tcr9Aq4EczVXy532vS4WfSPtD/7gG3/iJ36KKd1z93133XV3kpaI5vN5krbKUVvf9yLihtwrQ9o0adOEOam6G+bbi8X2wnqDcqIGmWDESI6UlUANqNme9ZLaBx488rGbPtHlfs++vY8cffjDH/1QNHBd9HMStG2aL+af+MRNTzxx/Oqrr37LW96y/8A+UzWznLu9e3e//e1vu/TSS1T7T9/8qY3N0yzG5KamfWYQQ/pFB3PXrLnrF4vPfOYzW1tb11xzzY/+6I/u3b1vMessezfvn3H9M3/mrW/fu3vffHt286f/zNSFUuLGFY8+evy++x74g9//r7fe8sX19d1vfevPPP95LzQFcdIum4EoGpSKqrftFGDmxJxe9d2vfu5zn7c1m//+7/+X7a35pF1bzPtJu3b99c/4x7/wT/7hz/8CQ7p5b9kPX3zp5ZdeBvPZ1lx7g1HihpwP7L/obT/9M2uT9d9+1+/0i3zddTfcf/+DN3/6M7f8xa233PK5g/svuv6a6021sNyIGCKQREkgkYUlMEGImCBCIoSG0BA3Ti1hQt6QNwSGCEiYGvFGvEk+TZgmX0u6xrZ/F08brLXYM0272a/Yj3/yjlf+nb99+Oyjtz52363bZ4/e/8gj/+uv/u5Ntx3pZEptk91dzeE5Z6gS4NmQFVmhQHYEpV3hvcGkkZbBjTSYEz53z7E/+mT79dO7FyqqICU2stwkzPvtBfVnmv4h2ty8eP1N7/y5b/6+16BJxiztRLjRfgHKSIrUO2VEAzga6A3LY2VnjqYP4z122D9HOzCAks4mIiJ1D6oxyNhd3AgWSqwcRQw8SW0LYqzv2v2cF1z7rG/+q1tvW5w8idyjX2A2Q78wK3L95qZmlYdn5EYw0kx9tOSx6NBCJERJRMAqSdsJN03D3DpaIoAUxZVxOB98znPafbuP3XMXts/CFQ4xYYsilCg3pSpUVbLkwTZwp67rSvq1aVLTsAiIYJErMWiGZqox2NDf3EHRJA8sYDHEKBGYsmkkHFMNwqlQ5n1sLj00bep/6UL5p6jBi6ciDqmyXBrxTa3bZK/glAO9elYSgnq0gTHWVWGHGAkDfJJtH3ESW6iZ9WS2Jozcbw8UznEQP4Tv57vUlbxC5EIsuhoLgL7vF9r3XYfo0RKPoU5T7PBwR2m5kWWvDMr4upIZwWx7u++6EiJjRGtYoQ5Vrm8kRFBpE4Prs4NieGGEA4gmvKHIko2QACeDODFcyNkQyY5sPexbvuflP/wP3/rEPnp488SszbM8T2uNaZ4Cpqba74ekTNt3PXDqPR/DPUcx3SUGZBASKLk6cpRcwjyafUcmv+L80YmL2cxYpvOu/9Nb7nzjK77p0GUHTz7x0DMPr7/x1Te+/+N3HN9SJagjJYGbuEd7IOJwk0t30ORQRx/CE/DI+zrcyAWhhl8GokBb5SH4MGYlCxXgGqhNaXsxf+HzX3Djjc/f2pr9+q//+vvf/34iX1tbyzlfeeWV/8v/8kvPetazXv7y7/zIRz4C57ZtNedgJwRNSS1aMgQkgL+89S/+5E8+8JM//VM//MM/3Pf9e97znpMnTx48ePANb3jDj//4j3OS2279q/f9t/e6a0rCjK6PDhHUL7pgT/fZiIhFvvKVr/zxH3/gne+89m+//GX/+3/8D+/6rd86cuTIdH3tVa961Vt/6m179uw7evToe97zno3NM03TsKDrshvaaSMkXdeR8N79B17xilf2mg8dOvTCF77wLW95y/79e+ez+W/+5m8ePfpI1m6xmInIfL5144035pz37t1NUaxhfvvtt5944sRisSDGZDL523/7ZVdefUXTNO6+trZ24sSJL3zhc4tFN2lbgiQGWmaQZU1Cwuxm7/2jP/ze17z6ec977m998IN33/U1AOQmQoCZ56aRD3/4o6997ff94Bt/6Md+7C2q/sd//McbZ84ePLj/zW9+89/9u29sGvn0pz/9qU99MiUBPKia7p6zhbEnEoIxsZl9/OMff/Ob3/zS7/iOn/mZd0yn6x/4wAfOnj176SWH3/72t7/0277dLN9000233norgGyacybh+XwO8OOPH/uDP/iD5z3/uVdcccVP/9RPvfMXf7Hve4jAHAKoBftK+2xmAO/fv//Hf/zHL77k0Ac+8Cef+exnOVG2PrVCgp/8yZ/8n/6nX3zkkUeOH3/i9ttvP3To0D/6R//oaU972unTp7/0pS/l0GzQDOA7X/nyV7ziFe9973s//vGPHzp0cGNj49ChQ5dccskjX3900q7N5vNjx46RuYBUTUSogvQU6WaKOePuIHYp8a2Hg08AMxKMOQEuTImt+NmChtEwhNAIyC01SKldLLrLLsJbf/pV3/fdzz77xFdtfjpNptu29nt//Kmbb390JmvcrnmvUI16Ue9zBLWE2NKoQr9U+t0oW6dAalJrWUnJtzM+d+fX2+aaN35Pc+l+aXxra2N9MrV+Pk0TeM6gRZOO91vXXXLZ3/+f3/n7bfPnH7pJNbdgkKSUFjZzNVmb6GwOagrngNhrcnjnbl8wfir76uhvO6wGpcTMUYXHzGbRkJM4cq7xLVyY66aUc0Yz4eu/6frnveQrd96LrR6SkDvkDtpFKJi9h2sp2UCUqIDcvc+9BbfPokOeOZsDiFR31l5ZJ8zJjdxz2eeSuBokXXTdNXt27X7oji9hc2MZcErgEOIDCdPtPPbBHURFF9jMmSJzChHPPRH5io0bcfKI4K5uMCpaJtFNkTjnnLNNJ5PpdDqPrr51Ay58RxDOqU9NKBkpAmicgKJKFxC4uCWzqAlKadLAahcWB9XbMy/+LBiOYGKwejg8A40ZVXA9H39iazKZubXrawTbPHUmcfJTZ6CR9hkpnZyH1F+uMbahZTPPYnUBIUgTAE6/6Cy6/nEIRjo0m2armafqqSy9AQ+xthj2MW+2IjuBJ21vbljO4QbCDCkheMtl3FdhCRo6fnkRKR/lPiqyZzshknPE4ULEFdSANJNT2WaEExs7T5kTmS++9Tte/JO/9AvNpYef0GO0Zrtbhk23PWcNRQ+fEcmmzu+4/+z7PoKHnoBPMM8aXV4psbNmR/ROUagWDAge4l4j18ogRLlfdKDHt/xTX7j7jS+7dm2fzk7e/4xnPPtHvve57/nQV05sQ6jp+n4qSI7kHN3pvYE6m0V6FxKdmSwbJJrT29KHC6/NQdHzuujcBVG3iIw4hzBZkKjdbG0y/f7vf/2+vXuPH3/yve997xe/+MWSXwbdKvJ3vufV11973Wte85r3ve99d955J0sjqc3qDjYnYTGCsxC59kqCja3NX/6Vf7f/4EWvec1r3vGOn339638wqP4XX3xx13Wfv/UL/+pf/L8efuiRxBLUzjaV9O1kspaziTR934kkM+Sc3/Ubv3Xl0694/etf/93f9T3f/tLvOH36dDudHDhwILE8+OCRX/7lf3PzzTenlNRMzVLDqt51uUnStFNzuv6GZ/7u7/1B27ZNK22TADzwwL3/6T/+6h+//719XjSNMIPId+1a+5f/8p+j+qPTadt13Vvf+tYPfOBP1nZN1RcHD+79D//h36ubiBghpfSJT3zibT/10/P5tpkBptnNTNiETftutrXZJrn7a3f+2q/+76961Xf91rt+w7Rvm6Q5e0Xusnremv3Kr/xvl172tJe97GV//x0/96a/9yMbZ88ePLh///79TdP8xV989p/9s3/22KOPRiYlNW3XLXo14uSqXa/m1KSm73sRvu+B+3/pn/2v//aXf+VFL/rmn/sH/+Atb3nLxsaZvXv37t27t+/7T9/8Z7/8K//u9NlTLEQCg84W86ZtQQDTe977Rz/w/d/72te+9o0/+IaPfORDH//4x90VDpaGQvkZRu6NcM76fa99zQte+LyzW5sf+NAHTp45OZlMNKuwbC+2P3rTR173/a+97rpr/tOv/9qDDz64b9++yy+/3Mze99/e+6ef/mRqxd2heuWVV/7MO972+PHH/tOv/1q2/omTJz5600fe+c53/qv/97+8+577XvHKl9/25dtu+/JtlChQ9uAMRQ+4SBEH6ZGpVBVW2wmJLlEEITQM5kwkUd2XyJOgZTRCDWEqjeZuut70fW9kuw/QT/zUq7//tc+fPXkH+jOpmdrkit95/53v+dTRRWrATbfIBCryeb0BSJyst2UPVXghKZHBSKYNkaNHQ8mIGWSCfrHAn93+sKdnvOnV6eL1PdPpdrdILMlkSmu7uJkY9u7aBaSLD176s/+Pf9z3s8996k+7xTavtTkbTyaWVT1jwugcJU+ASIGtuBQDrwwgEsBt2edoqLIr+y+Yd+/eDSCaRae2tb4HNYQSoIPJSEBCRGyGJKA9zbOee83zXnzHnffrqQ0Y0Cu6RdnpLIMc2kvbaJ/BpQWra3aNctBcOm/HBRmTqedcLJ9Zn7vS6I+JkJTcswHcXnPl7kMXPXTbl3DqSUBhOXRKshicRFkArb1IPBi7tKwZBFEYu1K8yuTMLMLM7WQC99qqbkmL9uGzzA7OusR1NLp0Esi8z1mkSSl1pQ8VhgSzO7Baj0BUmrGe/yBmd9K+3zx1BkxY3zPdvXt+9mwmyGwRWrAEOAzusGzaW+4dCcRgBbPnWDLDMBROn7t3Dx3pHn0MQH/NFY0kvfeeDadQSTwvXnLhqxzlGtwhIiJElLNpznCnoQuCWfBa6/Wswh6D9qp7NfznwCFWUlYxca3rKoRjBW8gWpnQo4F2HxIjVKEiG/11pQ7bR8yJ4U/1DVbGnAnwSKIGqbZZb4mMJ/SyV77iR/+Hn36gO3rHl7/w6PbWPPGZzdlCzYnNTFz6ftHlHqc3tm/+Iu49ii41xv28QyKzbK5whiLSWLU9MOAKG1JRjmhCbF5jvpRF73lM//yOe3/itS9pzhzZfPKhF3/TN5M9+3fffxdR1zZQgDUEP8ApMpDB7IESzJEJQug9Ou9qaGtoOOXFxQ4OK1dkokr6gEAQsJmlJmm2fjG/9vpnXX7p4bu+9rXbbrvt7rvvCnI1M2Awz3/2Z3/2zGc+U5r2uc997gMP3Hfy5Mm777772LFjWLZ1dXc31aD+QPHwkUd+8Rd/8bYv3f6617726muu2b2+Z75Y3H7bl2+++ebf/d3fvfPOr4hI04hl5dLSxY8fP37ffffNt7eIKKWQWMgi8vjjj/7iL/7iLbfc8vrXv/7G5z9v165d7WRy5MiRz91y62//9rv+8i//0qFt2867eTtpZtudh48ueOTRo3fffbe7t+3UtG+EN7fOfu5zt7z//e//wuduZebd65Ozm7NTp5/88pf/en193d01am1d3b3vuu2tDQJOn3ri3rvvjiZ8RDybz3POTTM5+vAjgbXmrk9JmsRdZ5tbpx75+oOPP/pwYoN1qv5f3/37H/3wB0+dOjVt2q2t2WJ7dvSRI48/+miwPlPi22+//Wd/9md//Md//FWvevXTnnbZRRddlHP3ta997WMf+8hv/8677r33vsmkcXfVniSxoOu6hx56aN7n2WwWtFMAzELEf/7nn/nRH33zT//0297whjccuujA3r17u67767/+6/e9731/9Ed/dN9994mQuvf94tHHH5tMTm5tbwBmpotF99u/864rrnzarl27fuAHfuC22247dvxYapq8WEiKO4e7Wfb9e/d+20tefPbs6du+fNtf3PoZbhyibSOWVcj/7LN/9o53/MzP/dzPfcu3fMvhyy5hyJ133vnBD37wt37rt7a2NmJ4p9Ppq179PZdddtm//tf/+q67vppY+tz///6PX7vyqstf+Z3ffePzn3vXXXf/q3/5z489erRNYmZJWNXgliS5eyKAjIkSlS7LvIwhSRghRtEIJEUzRItkR8tIjGnCNNFEuAG4bcDWMajhH3vLD3zv654937xPeM7r+2xy5Xv++Iu/98E7NjHtjaMJGxFBzfrw2N1yzBaOymGPAlZ2kEAcC0IiAy0oUyuc3LSHZjTQz9x2F/kl3/rsRYI30hE6lhk1XTOZMbtMt3n9SLt+xf5Db/+ld1Da+uLNt3jnBiKHUNLFAgAkBSoR7RhRo7iyVQ4xZHCIVtUIh70UAJgnk0mk+WK/6vs+Nn9CdLgyDd4l4MQqDGVc+6zrnvOie+97WE+cBjdQbYBe+8SU+x5QThG06J69u93Vcl7MtrU3aA94EfMMMLsoHHNs+HBAJMIoZnYm02KJ9l595b7DFx/56y/h9ClSdWgpVdsJzvCgW0ij+41ftKZ1IFJKElU9KxhN06ytrZnZYrEY3mZW+7oGJS0GTRJMwSmiYZKUs+W8iG41ywh/aah4Z4cpuea57h4V50aWAD11xjc3AuGyiP4lAY59B9b3Hdx+4hhU2cj7ubgbGWDGju98xd5vevZWl71pLAmIQemydu2xD3wYd98DIuTMQOiGIzXGDRqB+drVT5+2k1P33gMHcibANY/rbYYEAYBzbqhQfoszwcSVWJdzhjuyUkoAPLrvlVN5xctKBOlWq8gQndNXshtAkbIuUhQQj+SyRIv6EKdQMEdt45gmA0R+Z5gbEeaPOCIjD2TwGEZ3F2HKMgXD5E6mQR9oCKxIQANuwA2mTfuS7/r2n/gf337rw7d9+Isfffz0iW7b/OQ2Osd2xswwz+gjW+FYKJSwcGhDCyMT63t4VA9QdJSHVsVPIuwQ63QGGTObZcBTEvZuYr5L8ebvftpbXv3s+bGv0bw/dNkNH/3Lh9/7sYctoZcoyKKGiSV4Z65qqlBDNuoUaqwODRQOcGMtxaJuTtF50W2gvKwONSAi875nEjCldm3//v0szcbGxoknn2Dm3CkLkqSuz3t377rkkktEZHt7+8yZM4cPX7y+vn52c+P48eMhn5q1J0k59549+toSKNIfF1906JnPftallxw+efrUww89cuTIkWL/BES+a601MiEXbi49fIW0k9OnT584cYKYw9y6uxT5Jt+/f+811157xRVXOOHhh44ceeiBxWIOQBqOxb9YZDByDyK4Ye++PQf3HyCi4JASbGvj7NbWRt/3UsqryZkm0/VDhy4G0Pe9FgvhbdOQ6anTJ2ez2SWXHDq4/0AIOi0WPae0tbXVtpPZbHbyxBOqGvqBgEFw+aWX7tm9z1SPHTu2vb0dt6CKtmlERB0XHTy0trbW9/roscc3N7dZKDqWpZSuuOKq66+/ds+u3ZtbZx955MiRIw+1kzSfB9midde+19xj3/4Dhw5dCuCxo4+eOXOGCU0TwriIJllts37ppZfecMMNk0kzn3f33Xff0aOP9f3CCQFx7d6964ornpazPfHEE6dPn2WQmbYNX3fddUSUmsn999+/Ndt2Q7PW5pyJvGmaxbxrhNu2verKK9d37dqcbT32+NHcl+r8xWyWUtJsfW979uy+7robLr74YlU9evToQw89tJjPaZnAxGVPu/zAgQMP3Hf/optLIJHM+/btu/766/cd2H/nnXcdP34MsKiAJcCNzHPDDWAMEnIij+LZ6O5ARMlJyCEBWgszmqRJrAleBfOUvE0+bbDe0jTxhD2l1Dljwt/52le+8U3fNd+8YzY72jLx2hV/+JEj/+Y/f/yxbfSTCXE7255Tatxi1xIissCYiRgCMov04+BPsEMEnjklElfKQEbDaAUNkAxs2L2GSUJitEAitISk2NOiRbtvur5nfd++A697yXf/rQPPevf/93c+/am/8CycMd+YwxrK7Aun7DAic5gE7ujukRuNPTA0AiheH2Pqy1yHc5K2bbuus8UC3MI9MuDsXBB1JlAqoSG3oCldcf1zX/KKr37tPjt9GpLQZ3RZCK49FbavM8NyD1eeTEBmuUffoe/gBoYQghQMTgWlMCeLHvQZAjIFGKl1YyjQJhw+dMP11zzwxS/o48eYYP1cmkath9Rbcxat3L4L9x/fEZEO+XzT3t1FZDKZNI0wczff3tzclKYpxGem0iMl5rE6NULuZpmjtYQ5EYmkoEqYRaX/0EtsVa/5XH8inzyNzY2CdwBIjNTCgD37du/es3X6pC8WbAo3d3UyEnYGXvbtu5/9rK1O0TbODYggzaXt5PEPfgz33AsQchZ2mKk7p8YoxdTc8/SntW3z5P0PRK82hptqlHie60/wqvHAON8BkPAS9skZtcdg8RgGZ2Jp6WUg+1QIn8tUG83RKPQAIlm29CfSpM05w6zhpPCo0Y/a5RWXYulPVBpLRa6o5jjiTorPREvV8Av5Ey6whpAcYmiIW7RTVuq/4+Uv/el/8o5bHv3yR7/4yaOnHl5sbeCsyoz1TEedYO5Q8g7IoGzorVC4exIT74hi6GxgSCTyMuajYR+0UNnKsGhqJu49e56w7xbaY/73f+CKH3zFs/Kph8kwvegZf/ihWz/86RM8hREgaASJhchh1iuyYt5Fxix1iuxmCEVTmMONjeDuaq6RtHMaPInYa8Y7isGZREHzRTZQzu4EEep7bxpSdZHSZ0gVjUCW0yYzMzfJ3fucU2p7zWbGoK6zaZu6Ltdpx1Q1/700J3Nib4UlMZE3bdT7FMZI3/dru3bN54tesxCpGhGiaiKbmzmx5KypobVGmEq9EqWisa/ZDbW7BoEcIlBFO6FWmICmES+a9DCzrN6p9bl40UysakwgwkR40pCImOWmiZxCo/Dc26Btkah4e2DnhtSsSUmIAOScKTTQHdIwQ7Jpksm879yo77OFS9cpM4ikbK8AGVgwaVgaBsAN55xZiEzdad45nPtcFkIg/CJIpT5MVJ2kWSw6LZL0AkSa0ZqmCWcOkZ11JIYZptM2516IumxE6BXCpO5wsJAI5Wwpha1yIkos2bIkpCbxUGAFATCfdzlDmFVdRHLOYIJ5KHICkVAukd7aJPV9boSaRhhE7GbmAHMKvkTO2cxN0SQxs5A8DJEXZpYS2VrQLVMwJ7jQD1nQJG/FpskbwoQxIawlrLXYNeFpY+sTdhJtd734ld/2ujd+t9KJ7c17GZqml330U/f+P3/lk0fP0kLEuYGRZjOQqjKlISlMxlz3vQKiFn+CYmNkESJHQ0oZntEKWNEI2FOb3B3s1EhuGZIxAdpMa+RTo4MN7W5l166nH7j8773otS+++vn/9V1/eNMHP7HYyt3cqE+2ndEZKbk6nGBEzrX14KiioTTXZriTjDBmHzZVRK1NCQt7R6g2laiSa9zIIAEIPMXlNzznRS+/76GvL06dRu6RO7gKwfosTNr1RfawaFyGZIWhpDmMyGHqqsziVDtYRW2vkYCKFpMtQASZwIBmin17b3j+jfd95XZ/8L5EyF3fTlI377lh8zyYIfKiXDtYE5xjB8dHmSrMzNwvFhG+EpEITafTtUnj7pubm71qjKm7k0QBl4OksjjhaoClUvCVAOSKCREnnM+fKPmOmomJazRQKLAZMbk5cgYL+p4QqgVs5Q2CKAt2A7O7u2X25MjR/YOQYAoQXMGuIUEQayNQQstm6p7AXJQQi3bpMjO0/Dlce+UchNM+wAnunoeCaRDUYrB4lHMLrl89Z4BfQM3H+6idRiGSxhY+0gYJzD1WeJI2e1ZVH54982B9hRyV17Esf402sACi/7mPjaEN7x8p4K2mBY04JWeYBXmREgvBcqcv++6X/oP/+ef+6uE7PvzpDxzbPLk4u40twya0I3Rr1BHPXXtAFdFeTYmslDKbOkXxSqFHSDXS5AV4HBqjcJ0ojoqY5ZwbogRhQwYtuP8vH3nk4ksPv+7bnnHqsa+ldPwnfuRlZxYf+9Lts7UGVGp4k1rvDmeaZ18kzDr0ZA1TVo42DQr0GcqlY5sysoU6pwdtd6h/qpMCRJDI95o3ItkciQzuRkkI8JQ4RMcY3DQQUYFxUJ+lVC06nIXdNFGUziG15G4Nl0EgjuWaUHFXVeNCnTGJ8r2QcIMBSJIszxshFiHzNHjADhKGwEBJWiKDqzDaJHDq1cQjPiS10u6NCcRgxrQhEWqKS2zEZT6rw8gFjkSJg6jKSYQdRD5JXmoJkhB5WpNgxWSgZ9coYfPQa3QmiKMVMJDIicgSw1XjStiE4AluPTdu6g1TVjfTaSr3Hn5JSolcmSFCLMHNQkrJyUCi2RPczCeS3N3VmD2xS4oCYwfImbIrGjaIO4UutQHqnHslMGDMSAAnYjg3SMjTVrJBCBYNLkLKkCm2uiSlbD82XyGkJKkBh6SUcDhnmr1lCqmHpm2ZuU2NullW0/CtkTjYyRCAVNcaToxELvVp1f3HVTOTW+woplJzpBI+HEOCLkjEIBYThzBC/TixM3xCNEk0bbkRnSRMGVPGnkmzZz1NW1+fmE/aG17yolf/8N8BPT7bfkwm02Z6+Na/OvMrv/bJrz8OWeOUSckCpHQ1JiYLmoJ4LrL2VJPkzFQ2SCYEJdMNxMiRjWT0BgZF1XefiQgCzxkdIzktyIVoi2hCvmG0q/d9s8dPPvL+7Q/t2rP+jp/7Kcy7D3/0ZuRsi0VqG40VXvc8r4WzHuKtvmpH695YNdaHDbPq/RTcGoDDQvEPMA0zzw2bOWSKQ1fe8Pxvv++Bo4snngSMoqZFs7qSw7LCLeoIS3BlymVXR0kWWHD+GK5kTCgNOuOS1MHSoO8hEySmfuGpwf5dz/5bL3noy7f7ww+BNYtDczYnGJtQcDmJSNhYgZj08AFf2Zldr1FoRb6jupuYXAnExFDNmxsblie7d+++6KKDGxsb3XwR0vNkpWiFmD26yYd6KzE4mS56VaDU0xkTqlUoo1uPpR5DVRQsAbzDEXXP5RIDYEIVgByifIIDzOgUvQYaBbOgUERD8+JwuNUPu2rPEDcAxuZuVqiLT8Gc8KUfMPBQxqmbnW/+hocX2c2xV1uGIjzc6iKEoGMRnKBBa6ZwGqgyJ2IE3Vae8fCzvIKVlMFT+JgXOkjQ556bBswi5Elz3k6T9MJvufEd//BtX3nkzvd/9L89evyRrss4kzEnzBnZkd17eEfcuypBDdldHQZ2UhCi1VphS1RZUo+ntwMRolgtVJKsDi9lrNGbwJh74HTuf+f9X7z88Ld/67OfsfHkI8JPvuPtb3jXb/1fD9+9vXsKgTYt2rZZZPTZthfYAiaERUKv1KtnMzNkQ9tQD5jC4NkgDDVYkb2CO+nY2XI0zHBSgC2KYTwbnBhcmq2BjJ1jGSRG2wiLcfQ6jKDIzMgFpGTsg+49kZGyq4bonoOtqHwCRC4MEo9qPw5GKweUogQxqDupO4WQPNCwoOArZGZad6aWIVxEixogg4jJoqcvOeDCJQMpQpICYVuBOjWCLw9Ju2C3AQAzC+kkUWJL4vF1RORQA5oGLZMGhAwgTCNBkjMg4okFZO7wDBUIgQQc4u5OaqTqajTrPUfbo9LBGUSeOAdpJnH0DIwOhDB308LEIXK4usPJmBBOj7BHyb4xsYIdC80hVes1+SmF6Y1ESIkaCXDFGQ42IbbIL2jIOoc/WDbDkukmMCExEaEhYjaiyHqTAZkdElbUYJ0VQRonhrCnihzEiRmeODotcLh6QGi/ZnZWVyleZkVCq98pXKYNUUhKEJExoU1gQnIXwppwEkyE1xqatjqd0FR8vcHuttnd0PpE27VE0/VrX/Ccl77xe9HO+8UZT9RMLv3qXaf/P//m3Q88jOmUjURDJK1MKCcPknWMTU2SV9SvPEKvhpOoiGnFEBpATAJEQpAY7CaAggTew9lYiGeEJnlD2CbMc7fbHu4ffvf7/nDva+Unf+YtDz527LYvflUXyJtz4mZHmn6M5C/TxBfeQitcgR2FcuV1NTCLk4tYdrQTHL76mhtffPTrxxanN9Erk4OyqSLqOIwsMAlXIoIbOZEbO7lb5IZL4Vvd76Xk5VmNnaxEN31uptM+91D1RjBtrnvh8+7+6u12/92wHsLQLvouURK3kJ9nB8EC5/CosPSR+RuPzHgH2Dl0BS8n5mTI3SKfzqen7eTQoYtY8MQTT2xuboaUKoM0O8tERCIyJ+bc9yzN0JnSfTk/djgTCHzCSwHGeQpAYoYtqzNQt4Ga6E8gdygE2cTBBusySGjSuKGfzd2sSHNQVXsD4E5RbGPuatDBnxiH4hd0CwKd8DqOy0nG9BSfKrdznmFfOag6CuEdRkf68MQodBg9ol9zM3bUTmOo/MoBfkCdYo46t+uXLzGrFT9muLsdl03D/ZoJuA3NWvMkJhniV91w+C0//3dvuevmP/7UR5/c2OAFyTZ0RpgZughE2DOjB3dO6q5QdXeHhTMRElGhVVoed6ikAij5y+HCauoHAMihIGIiI09AMiCZOlhFHj6p/+5df/kv/sfXfeuzn3Pyya/v2Zd//h/+0Ht+4//aPL7RkE9aFXbitL1tZ+c4vWlbTNvqHXyhmhWmlBXZOJv3ZGowphzzxRGNDgoeixr/RTtRIDuUmM3hzhSNXerDJY8O9UlYBJyUyAUwInZkN1PXqneK4k6EeKxFWa5RKCsWDJjChDOcPRFYSNiThLIQgZgI6lSQwpq6SnWWKEwz5ZDcgQV9q+Bj7qU+mCApOlebsAexXxIaBrwPwLyczakqfoWwPRBVDETCnNh2TUQ4elZSne3kTqqqTKECPWDbkXdIjJRMShGVQsJlQegKRjWxsil5NiRGbzCFxkJ0sKAp4rsuRbA+fA43QJlhQCKrQjMARKhtmMUiecQhAsPGQtY7hSwtSCRy6BRrpxGkxhshYWchjpwRWJ1UqTHVbFrdYwtUACCGEJjDHEJYuXSD0uKtigNOpdGcF8CJAtWA1ObOFZIMZ4IadmFUeL5UXRM8GwEk1S6IUCIi9sTE5IldOIQoA6UAMRKjIbTsa8kn5NPk663tW6Pd67xvXdbF1tnXW927DuyarD/jeS9+/fdhTbU/s2Ca7rnsoQcW/+Jf/d5dd2YiIm/7hbaS3HPv1md1apbpAq94WkyMIcTjyigs6t7GSiBzp1KoVZuAgqK8zosgDAdVnOCMBEuOzrBQbJFu9EdOPvifHv/PP/S6H3rbz//Ev/nn//6hLz9C0ym2q47wqoGMyoJlEAsUOtfI1Rj4izbeSX3nSRJTXmyhXYesYf9lV37Ttzzy+Mn8xCn0PZyGOUpq8OxGKF2EYgSMjEJgqppYX0bXrk6i7sXLhzk49ksS6xfbcEAIu/Ze/7decvyB++2eu9Btc9vYPMOAxKYZzAwO7ggBVkR4AYKVws/BjPIQVq/6E0McGzACO8yjQQ9TVkOXATz88MOXXX746iuvOn788eMnHgeo4QYGd9WcieBIbgCJWamq8FXzXH3y5THSi9wx9sBO0zv2DWMoLeYawanhhC7DM1JiSp57MBELTAGDuzNVn5FQBDAVcNfeNZWzjRuOn3sMEEW5PBpHBuPXz+tSrCRQLvDXkSdQvAEfzjZ46x6NhslVFQpT82J6QTbwJ7x6GRfyYIbLXkJE38jXAQlMTQj9Iu1qcp4h2cHL9v/Am37gc3/9+Y/d/PEzfTZnPa0tWu8IndEiXGy4mmVCBnVgdzP2ukcQUFpghPNjSy20uAtbiQPKBgqgqkU4c9TAspHD3Mn7jGZK933d//PvffSXfuEHbrju+rOLUxcdvugn3vqGP/vYp7dPHtu33qKfN5DZTI49Od+d5EznZzufZVsosiF33mfqHQtFZjILyRRkg4VEO5E7NCZFACXEgCu8MWSy3sEEC4l2ZsDqw3RiNKwpSWoEEq25AUV2yu69FvXbgQEtCOoKeipBcXlePqS3GDBiEHlDiIZbxEOMRwZozJsQMRQPwp0BSuhrIwNwELDhXNDF6H5DZKE9J4kSkSRiNiZjsBQVRURapyf0IGfS0lW3zMdGKCWaijVkzCB2hkQQ4XBlmJlJdSPC0DIaQpOQEqV44iaBsbkjSqPVyczVRNV7983eOoMJBv2aUs4jpSQyqLQ9XB3m6GFBa1AiLzlyboRSgjAlKhBZAxghk3siIdJsBWcoK5UYLowkaAXCJOSRWFE3dhYCKZMbG8WYRPVEoPoJztCS3yGK5M5Q0KmRe6SgTIAiMufiggih1Ag4CNHPhcoF1GUSnWjCLRdhBzgR4AIK9YhIZCT2REhcCt7Dv0mC1KBlTBLWxNfFdyfbNcHBXdi3h/at6549snstMWN9sp4OXX79q1+F/Xtt66gR1qcXPXZs/r/9yu9/5ct5MmXr20U2WHXQhEW4L9TwAKF5R7zvw/+8kPViPURHbgKZRSEIiNjJQGTmJWNgFB1E4W5OlBkCqKMDLdw7zDe3Hzix9Zu/+dt/57te89rv+97fPfruraOnI4c+iiwjYTcqvhtvlBVdHl+0u5PvMHPxISIHmHOXeW239cBFh6/+pm9+9NiT+YlTiMbX0fc9yG6aSYOvVV0tj90ltsVKpYryxioSFTGiLQNIq1uEgQBhpPT0F7zg1BNPnv3a3egXJER9j+xoGnCQRjl4sExVUrp4TiiA+gUsygoQ7iVu8TJcJc/gRszJifpOUyOPPXqsmy+uuuJpB/btefjhh+bzRWrXosOyk6hmQDiAnKK7SFh1EnYY3zR6bACCbwgdrjkuBUBtiIvo2VEwAtJwZ5nFbUpwlpkbEYy8aZpJVEAwwxXQ8CRABI+8JcPhap5LL1eGLdMF5/UqhheXiYa41cEkk9tOv8gudLYLPhWtI4HaKmY5SqXSRrjUHyNS1zHxQ2WiYkJDzuh8x9LnGH31EGmee7llcsgEpjxZzzbHGmGNrn7ODTd/4fN3fvWr81lHk6nNlTHtFsoZ3oGyuCPaBrm7ZkBBGiuHaeCFuIfGQ+kbAB18UQu3dLgJqn5x4ZoUsXZnApsT3JnMWTxnn05wx136O//l5nf+whsPHj44nz+x6znXvmrPK+++7c/tzIlDk10+67bO5It2y9dP9Ce36eTMNzMWClOyTuY9byt3qousZqSGbJ7NzckM6kMzOK92EUrsBDP0CiXvyYxYSzgYu5JxZCiEUyIWBLU9hE6zW0bu2awqscUsK+C0+9SLO0VEYKoNppGzepU9Ewa7JhYZcYUz2FI8Ymcm5tCmBcAKVyHTqKpZlnBbxOZwIjJTIUgiETQSOX5hWOjOxrUBcEbj3keJvbBz9F0jZmobmgivJWsiHQJnGEp/Ydfsg5oNCxIRMxr2RjBNaNvBn4B7ICVscFPqsvVq2dwUHahNMo8C4FKDU0SGmYu3bc5maMgVlh3iKPqChXhNRJSEExOLpaWYi5tZNiRNnSOnsVguCC4ijZAIkgQjpUjWKbGBTJHElJtsy0lTN1sXZiISEBPIjcEpAnUiJWioPqQKdUfPDHIWMJPUjTI2eommz4xEErCQuRtBVZUIBDWLx8FMwtYIC1NiEkdiT0KJQx3TE7EwkumkoabFWuvrre9ucHANB6ZyYB0XHUjr++e7Dtj0wHTBu3ftfe7Fz34JrnzafOPJNGmbtOvsY1vv+o/v/cpfP7F/H07PLGMh0hrRXPvsZj0biIxKI4shXPTiHi3XewGPK1MtmtgX6S22aI5pAEdzAoEaQpKfwy0ykLkZZafeqIVneM/OTtKeOT37b3/0sRtuuOHpN1x595NPIgvy4CgMm0410AGqeWmhXPerZWXlkAgYNk2g1vOVQIAVbDnhossvvu55jx0/0506WQxTcU6dDJQXlfVpxWMoDRoiyihvZi9AV6UBFPjWmBD5Tyf3XIwwM5gPXntdf/yJJ+++C10Giy96Y+ZJYyBkBTeAwTOIHTKIO5UWRUTDrlTnPmDL2643PUoPBTOMGNGXvCTkWZrkpsx8/IkTGxtnrr36ymc/+9mPPfbY448fl9Rmc2JPqcmazYAksDzcYdEpr0OO0ZEGyL1mgEZPgqopLMbRbYAkregADO/QU6fmj671jUBkusc3trdE0tlsmM3KGQbHqkyU8HfcLO9gFZz/eGrUYRjiwe6e+3EAq/mF4W/DB89v+sNdWY7S8rtRoiSU4V0Cz+dJ7J3voi4Mxlzo8AC+DJpBtP/gRfc/8PDZrbPUO6y1zQxpzIHOBZI79b50XhmwBxiRJwt5EivUkIDWKdyD8ubRxNiJpdXbD2wcEb5EQtGDVSoipiaTtm36v/rCk//nu2/6B7/w2uneBtq1z7r2xkPrZx+8J586IfO+3b/Ix89eus7tlqfNxdrMZvO86NHNJfVAtqTc9Nabakaf0RvcPBvca1BRoxl3JDIDMkAehW9QimapQREeUhhIUCaVQVvTS5gR5HYLr7qk/50oar2QSy7AKbag4mmX2uEYDXZnQCzX+BVWnOzSspegXIqVAWgJ3KkIsQ6Y7jDviFwaMCOxM7vUzKQ7GqlTGxWOpIiySkoiyBSJ0U5smiJ8D3NbjQkBQDTkSQQRNAki3iZOgmnCetu0bSuFX+qVf6pq6HtfdDbv0GfvDWQOR+vQ8phKEpAK8l96HsSD6AUMoAdgTtCQkaPgtWhhIdQZF0OdAbKeHMnKljHEqwkQYMIQDipPmRQx7DGwWo1jGdXAigBypRpACIFdWUNcF4mghKawdjw7ENwwgqDEFONlQVCOQDRoGbb89gT3KFEkF7Hid7JJZDQkSlo8slFCYLaGMG3SpKF2QtMJ7V7jvWtycPfagXW+aHezex/2HUKzr/H1Xfv3Xb3/spfiaTfk2ck0nSSWxZOb7/2DD3751gfXU7Ox1Xvku81UAQJxAyUm1iD/n8OSwhDgOgCnQhQC4GAKQRg4nL00X0KQMIbd1AkgdosaCgmat4McypaBDDSN9m7wfmPr9idu23vxvvX9B7Y3t8u3j/wJ951R2XnB5hHQu7TvqwfnSMMcOHz4mmedPD3vz2zAFdqVplwkgHvOHgL8BKiWeV88CRuBNojpasDShJW/GkZxrIPhAqPpZZctZlsnH3igTL6sLCG8TUVFkwRqkBAJjZxqRQWKQtJOpwHntXfDOBAKEEBE4VLACQLibBnWC6d519/5tXsuv/SSZ9xw/b69e+67/wFhdvK+X0g70VyRRhLozppVWjWL59GzuuDVxd0Qw4gtMHJyuACq3t//cH/k62Dg8CV0+DDuub9TPemEWYdsVIpMlgyO0kMT5O45am8KFACAV6QORgO3ciXF1zJyDOUVha8wvHEH7LXDfvvSXTqfn2EAkwNMFbbW4qqX7bx4r0NCiwa8YTyzfYjzMbxt+fvKhYQQnY3Xw9icE4xs4WRuwKSRSbvYovmpLQeFWEN00Yt+7v32dqJGNbx4qyxLIiNyiEZcWHrQweopUO0qSr0wFbxSrKD6Qbgoz3G4cKdI+mkwFOaLvHtN2HQqza6Uv/zFhz7ziS+/4g2v6MVZGzl84971G/ozZzCf8cbpy+ezfZuLwzOdz3TWoettodYZZ/Wcc2+q2VU9q2UlMxix5hCXXYlI2BGqTWas2VWtVy9sR1OngBtFRFLiRkSEmGKbXZrJnHOfreu6ognKlIiJAgYAR8kB07CQDO7Rqts9MunMTOyJmJmzZyJxIyu5o1IGJ4nZDTBFKIq4GUwhiK6JSqRedjFjQSMpOhNGJA3A1cwjhTLMfFK4KbJp8EWJPWDzNnHbpqaVpmkiBxHBJVc6YRSMCbEIJ3ERahMx83QymaQ2mhrHPDWzXPqmW8666LXrtVfqVTV77AuqbuYB3kS5Ws59YAxqbvFkLWqvyuPTIonrAhLixMLMiQGYQ6NPmBkWWdRQBDBKQtIj+yAiraTEhQYZU8Kg5u5Oqq45+DF1NbETEXssNxtsKjNLlISxAzCFOrpFH+WpQ1YralWibQfqPkJc0lju7q4CMUItzQGTEBDzLzWSEqeUUmIRcWgU+DGlINByJBFhbaLUWDuRaTtZn7brk+n6VPaskzR5fc96s75Xm4OTi67GrsvRbTvNGmZsb3/mQzfffsuXG4N2YDQET0SdORFDyRW9mhSuAEpaNpr6VveUqqsNR9GKiVyHOphDY6DoHdMQoVPh2hIcRkYCcYLnwHXcWWKZwBgLi8txcpCfffjkRKbBjvYdOs42+Bc2bDqlBfFQWu/j4rxwJWmZwI48NRHQ4MAll1x348bM+tNnAG6M3Mgpm2WQELtphgem4lS+OVLaVt1RlFAAOw8xIPoDEJx6wOEpHv6uQxdPICcfeKDmAo2kiRXsWZE4ehfAEhE5lMRJO7g7MUXDLIDYzsFghsspUMzYlRK4RdToXhp9E0BQVU7JDWaZiRw4ceLJ2fbmtdde9cxnXHfPAw91fd9O17vZAs0ERFAMehj13I7KQxqOtBxuInhNJFNN26LgRR4wTo3jPAQcQwk/sLKuR++Ap43t9b3d2c1NGJBzERAodstqm+qBGOoEE7flcNjoMZ1j41eQnAIPeJi88Zv/b8f9Fcots3DlT4X46sV8lUxL4VMN+aDx8RRfPZoK5/NgvvHhUEmSYZJa6zE7uyBn9pKkE4YBnjMAQWu9wioZ2zRcCneDMZclyzUXguIreDEJCDJRoRXXjOTgTdXYDxTRQKnjj/DFgLZpiIhdSW0ynYjnz33m9quvu/bqv/W8zhP3B2jPvmZXC+sazGDzA94j98HIKdr4iQGD9kGXiMDWzUqRjcYOEjmaEoojmsYFK9tc1U2L7SGEq6FRGRgH15IllL+6u6tGv+zIlKJs8kQS2vIkzsTRebNmrEqlvjmVMIArb4ANEWVQZdBHjlq55CPLxHMnze4KLn6HBWHAXOtcM2ZuRLC0NDAzrfcSXM84Va/KqXEyZnZ2gUvitm2lbSBtqG7FAKD0KCv5TEIpP0UoyZLAWqQWlJZQAADrQFpSn54jWQm4m1IRL6khptdnV/w8U9V4V/EF8yJex2jZCrFARIQRvD8zy6YacJRH60Eqj2xwJqJHohDTsuqFwFaHN3rYIdfOikQDL7I23vPQjGKR2uczhE/KZ5fCqcaeSiFjre+g4dGXozg0BNPY4Kq7wEyJijKpAJxY4MH5LRzO0c9EwWoEM2QCF6CBAL4AJ1AL2p3oENIBWON4skkb0O6vbvrMlz7zJd92MUmU4NH0jXpVB8EbZjRANl/ijVawhRiZHVHliGMe6z5Cl0jwRgQiwBDWOELOnKhkDZg4wBw3NwYczmBiZusU7MxinXWUJzzJyDkAjx0bPqKB0bCFnrt/8nANY3NQCkaJQC3WD152/XPOznX7xCm4wbOpEbS0sWR1BVSD/4Kca54l6hNL4gM1soorq19X2MwA2EObZwgFfXpwn6udPPIgYHCDLiJvEEXmJeLMHZyYkoWw9/gobZvAlJzUFNHCvt61gQJQHS6qxEJFmQwDW84BCtTQNOpg4WDiVt02Nud33vm1w4cvvvqKK7/+2OMbm1vN2nru+1iUcLK6V+4c+Jo9SADcDE7sBIdbVs8QghKxuBcMv9ywZbhGhRa5MbF5MSkFTnYXEAUFPzJP5GAEZZHcSShacg48R+pyn7dKNoTq7k5LTzlmlRtGObO6DGiwcRhcihU7TSMDGO+P85RZMrwORAZ+pHEa5yGO7aaQdAtOVX01AqE0a4lLsB1j7V7Nxng7JsFoHe94NBU4jTUwuNwEcjA5p8yg1HhP0OI1e73TwhHyBHdVABJPCJVCEWdzh0bL2upy+gDYVWAlrpOISgMaX44JICPvOB4nEwgUTqyWp6TarrXMptqTW7/d3/KpW/YfPrz/2m9CugTdXqQDGb3b2eQb0JOETdhCbUttbphZNyfvvO/g2dXMO9es2mvuoOaWKRuMyMidXD26ErN3nntVt6xm5ory5rBKlskhITdY3AdUe1bYcw51ILSqYotnTvEbmJTYhMJ6EdHA41FVoBiV+FzYGngl8tX5EI4cu9V/62DL3N07C+sGMi4VzT50cyjjH/tEJOpRyprUndyjuQmYwMRNkpTiMkSkaRpuprJrr3NDwhAOIMApeUqSpsQNaMrUkDfEDUHcpyT7QROmhjh062CWHTPY3G3T/Kzblum22ZZ5T9qh69lUA01Stdy79pRNc+9qrr2rqSrUTNU1s3mFlArORxRSGURLV4/Msqu6u3ULBDZRFqYXmKX4fdEvmAEmErBbbTEQdbnuy0hjGM+V8KOowQYCR6GDAnAIcw1uh5EFShQaJIUIw4kk9MvjhLaUpYn7YQInTiIpURJOQkmIkycQJwhTKDITUZKUUiBFLMLNNPEa8QSyS3jq1oAa97jH1l2g1Mg60QLqxz//hds+c0t/dpG80dy7e4YpcSY2lqyhKQiLwMGH1T0ywGaDsnV5JpUmUrenwFhH6fwC7MerhFpsHqgHAa4WWYsgtIMdFFKLhKgV8eROvXdwZmJDUYVkYudSZTbaX6kmzw21w1MEuexUNiWOTJmDGE6QCdLuS69/zqnTs/n2NqAgJ1fzPgIqolLiTARXK8w/80Imq9nt6lO5D/+sG6YzUcjbU6Q2JcLytT17W/IzTz6Ofo6GgVwgXQrVuxqcg0Aw1yAAu3rACaWKyYY8DpOwEyNqJ4mkabXvEImTyK0WQxPJKQ78qcz26Oxo1euyQgNkiIJd9cgjxy65+NDlhy89Tsc3t+cMIk7RhgvGNY3ncGXaGbcnaLVn5oALKMelsCDSNl4zOLBaO20loeNVR4bq6wFJ2ciIBnmzgvYBhIxWr3WLOYFLm/aCvFXWbqX1uo/D49VjFZbAGAj6Gx4lVFvyM8YeybjudvDf8d8Bgfx3HbR6y8utMGIuI1Bgkbb0lyv0VyGcSgkrziko/ojionhxXM89omSAx/DZjlv26ocRYvNMoFyjPbhTVu8JXfJeaXsrnz52+qu3fv7bpvv5ysvBGTpLBAghK6pXJk6CBEwQ8zE18EApWsudWme5dcvs5k6uYA9Mhi1ST7ow13AmyNzVPH6xTOZxaURCpQOzMaWaiVCgdHNzd5GyCpiZwBGFOpibFkRhM0oYyksvdkThpKGQdQhSqGL7QDQOLNcTIxYXTIFfuI7l8NxLj9PhtMM3mg39h2wZ5RNSSiTCSUTEWZiZU0KaIjUI+VoiJygRcXJqpGnBDfEUHK3jBdQALXgCtEADB9CASKgpiTmryQADlM0XbhOZKMxh6mauZtp7Vlcjd9fsZtBc63MM5uXplCP29GXkV+iuigps9GwKz8OgxY0TBUUv/ANG9UsQQhYrydC6siKeXsE72VenN/HOmT+8wVCQnHK1wsxMUWkqHHWUJSFa5qVTlOFKIuHydApEwc5OzEaoMrrGwdhMAiaSJDyBJFADDpZHbNoZOoMlEIEMlNFvbH31jls+efPmqe1FppNbi63MMzUnKdw3QzgIRhXFj32MlrvfOQu83j7VLBIVPLhuibbcIWi0vZcfVjDu2MtiHZnBrDpziEAUxdQhfADUmNHrbjKy6MunUmpvyrfbeCfzyIeTFCCn2f20Zz7/9Ea3WPRQhSlB3XKUZS9tVrnHysGMrxjKBOoFnHfzd3c14yaFngzUQbxr756U5MzJJ9EvQMFV1hgFt8hBYPWc41lHwxz1MsUlErOo0wmmWlUcY19YhoSD91yTWFHpN9xFbYM04DeWlZjS8RNP5K6/6sqnP/roo1vb814NBHVGOEg5g5lFMG7uCgBI8KEjqFJsDBGuBfujXI0XStVyWM8dS0TsXieTY3AmlymnAgyWI6rXs0YhKRFHbzSMBnh5fhpcUpRyg1GOY2ecsZr+GK52OX9jeCOpVC0xVZCtuOt1Ni+fTvUtArHZAbfVJ4dzIYflNYQoyvjl8b/CBUV1vZYYitXSNgCAkhsg5gOAcd6vc5CTm3Ns/Uv3upweAFUJt/P7Rt/IYRpGzIvIkyPwDGGFOzibzPs8F8wyn53pk0+eeviOL111YPr0rdNIu8AtSIAOeQGbW+5yzl3W3HufkXPO5mpshhwCVxY63GZORo1bsD4ISBYsBDP3tubazZ0o+PxWwv3qC4q7Wwh71ya/5S6COMIuQwscpkHfgiDqRjQkBUBURIhpPBWrHqIT4DK8XkK8yk0ZHIoy/uHruAWBJhEzF6ID7ajjcyrUAYsArrwc5i9oAaEdHj0+RJrIBTC72Zwo1Kmjr7GXJp8pMXNT/KdyOwxqGQ2LSDIkQgOm3jTnDuzmWfsua6+qZqbZPIpz2UfeLZmKe+r73qw1M7NUI09X95xz+MbjuytuQSW1LP0Jm/R9X/WDwxULcRZikeEb4xETxJmQGh/N8GKcgLH/PX591eeg8WNdeQRc7AA5okeqRCfCSHIRoFGnrKoa2hpxtniTJI62hYExEbm7cQgPek8eeiFgRtOyiDSyaCU1KbUJjXASI1eiQB0beANvTaWbdbf++V8eue/x42fmR0/OThqdJd5UXyhBwQZxVh9AZxqWeCzjlR2PIncALAPw+q/AQ0dxXDxnj1HdsWd4hMgAByTtTgO04GWNoFoKL7FQIRKH+rKV1PaO4CoWdc3LC+CAgqCxUlVT0zjglKCEtfVLn/H8zQVvbW7DSlbU3aDm5GQ24rRFBmd0B1E/T7YyN4KeWe5lNJeIrO+5acwU6mv79yWmM6dOYj5HIrCUDlbF3cnLUtjlaNp4HtZwLdy/0tuvmD93kIciMzSvnKQyMcMUVlxz5JmN3jlcD5xIxNyF6MzG5uL+h57xzOufOHHy6GOPU2pg6iaUBNy4uxV1nxVzlsTJY4sEmQ20hsjGcp1ocYEY1Pjr1w+OraGQGKIXalWnqB5lrEZatfHDZobaX2Q8Hufe8CpssJR5QPXdzh2m8w7cjnEfvOClhTiffR2/cn7rC9Qi3ZWPPcV54grOvcKy6HzF2wjXh7xIzpT6ZxocIBr/dAS3IBTa6kY53jHP2T3PvbzxUJx3eMthQwFJ0RUxJ1NS5s6IHJsLJFYWmm7qxun+7tu+8vgDR7lJTKnwHzXPZotFr9uzbjbP23OdzXV7Zn32efbOkHPuct/12mWoIgdJz9FHIzGHGlQRnoN7+d2H3H0ttgLKzhPCGaFbBZT+C3F/QWDU5Z3W9wNA1S2g5aOjon9Tfi9/5YKyqa68k6r3WoMOGFDxIrgv/0qF/19/l2ExlRkWqsFxPRwOf6k9AZWu1khMLBBuWMDMAhKuLmjxWiCJhdBOUsM0aVPb8ERYhBphJl1LmCRJqXViJzZwzjbvO1Xvcu66ftFZt9BF1twjm6pQ9IM1uGowNz0b+t7U0K8+JgPyaoaw7nsAyrYfD8gs1EGG+lsQlRhHwt0efTBimXguvWGohYyNiQwKSK33ifEffvLo9WArDr/veGcAWKWOL2Dg1T3MDI7S1Xh4pk2CIKQ/4wGVgpRUqkwRKhqNICUIY22CtuFpO1lvZddksj6h9Qma5Lum1DbEjFYSkQCsmTa39Ohjm4+f6R47O3tygdOKM13f+6RTL5dhNFB5gi8WXsJ5V/3OyCdihlEwveMNw2axYviJgr9gVv2ECHSC4RkU8OXaGhTfHObsAwQCnG+zGlgFJVpa+jROzDmbTNY1A2nXZdc9r9fmzIkT8No93C3aWYeWdqD546eHWJ1h3WjYNnf0RNwRuEatl1jOUJ3u3d9IOnPyJLo5mgYwWIabCEfMcx4GyDc6lsPuABlHAODo89KfWAbtRMs0h0cRxDkYz/jkcDdEN4E+L3wxv//++592+RWXX3r48SeeFAYxR8OXSpsTXx2QxJodHNXh7hr0gkAOEOWgg3Nklrsgx10oJnbAA2QegyrkoGUQFQBVwJgGLorXIUgBDAH7yIcIpG0lELcaFqP4hnWulZDinKhiaarLQIyO4LsVF7gib+dMXyLayTo+3zE+dT3DN/5UhbVXvUVUr4vgRTbGyYZYuTyhYvFG/gR7/T3itxHmQu47RhjAUoUCqw5QcYUrVlbIcWW4qOBVgXBqBP3uUCKYKVGfg/VJ4gA5M0+b5ugTaT6fTdJMSJk8eIgL9U7Rq3dZF6pZvcvoM/VKHVwNOVuXkZVC5yCDstWcj4fuUPwOzeROITNQGAm+bAjAHBcutSzUtZSBBfcgkAOiYCeMBmG0P0aFi4Q4jlPAFR6Z4kImdTY3Mqq6F2UMw9kIOcu4MPJBM7M8cS5KWQSYOS1hYaPSYKw6glY1J4ioEA6KDiaxl6i3YWFBoiZAC8BLb1tz9wKONkxMPmk8MTUpt4kaNmZwtPCACSXC3OBFltSsc9Xs6uiDJmHsztk4oAmjMvKGFLUYoRqSQwjXKvva2ciqkjMAeAjSuANsAx41bCNEWlLX5Yi6Gyvq1CGnXVmf8ICT3WW8bVuVYDNnry47FSTJS0VjbAbxxLismPKKh8K6ecVqvRbeMjMVyg0h+hsH1yTmaKTIQKRQIgaLgQXZQqBTWUOs3cmdBYkQ0MVaJ0m4TT5JeZowEZsmTkmbRG0tznMjd1Kn2Vy3t/TY2cXpHhuEU3NfKPedGZpsqgZzVy/8Jg8/ggoD/5wtyUemy4c9c2WvGO9sfu4ZhpkMABzFMla9MNQi6dF7MRAyEGlZghXbYW5UCm6GJRDfK4CDDIzQkg1DSySurtmQ9u6//ptnPj194kR0JyoMYtNQcQMQDO7VSshiBeADsDtQcTBsgzFwRVN0uHIid2/W15PQ2dMnkXu0CabVO3anFA4186qe5IXbhy7fIsGszABYUmIBTHPGDsCtjiihtGi3SoG+0JlrQirBrM+9cAPvtzZnDz/0wKWXP/3QwYOnzmzMe40iOjioie7TKydJebZwAqeWmTV3Tma5C6RhCffFZ9R02W1rx7WEMXSQFb5ViQ1XaiNX7nSEwASi5RhZ+hrujYCHpRzCEGrv9A1HAANGgfWFRnD00QEC8h2vjz++E/N8yhP+Td523g+eGxaAGMUCFMmp5a2RRSeeYihreLDiyxVI0KluHOf/lgtf+Y4hHT2UGooM3C5TJlcQk3QWFabSMXHfn1kAm9arPnlme9q4UGYrqY3e0an07hFHuUOdskJdslt2qHm08zAVA8zJWaLxS3Zzh7q5uynM2Y3dSUFU+p/C4CFDhELq5+Dbuzu8CftqSGFd2MWjVwcZefwcfDAXlLx7RbNS8VDdK3RZfno9xmNYfd14lAg8b4wD+QJAxLvRfrzkVoh9eRhhuX0N2TqvPa+JYBLVK0VeaXjc4V354O0TsQBMmLYcqk2NuLALOaBMZAoKT8DMjcAl1WJOGqy1oswu5cHlAE1CbztYsKxuGpxfMy1EYxAEtFpuFh1PSjaEfHwg3PlSQTNAiVF7Y6GBwACSQV1h0FLXAa6UQrK65cS3jJ/LudO+fMvOcDRGbbnvU7DTsbN2kDxaGZDXOkZmMFEXaiJUwNkIFoh4qS5HRcw7CpPbOZLopEFiaqVr2ZtEiQHP0RTX3bMaAAN3vc8WNlec7jB3bGcYN/NOiT1gvFKiUDxTIDxGnG87Xb3l8gRWJ/P4DcMrQ7Ay3snDxHv1KuqXhps2rj8cLHigrDt3Y2DHNZAPfFKypS442MyQ1mGTA1c/S6k9e/wkVEEKz7AMU2iOjaRsl8uJuBK41hhy+cSDnrnj9pe3zux9366vt227efYsujnaFpqjWzoR3MwjN/GU1uS8toaogM2lp6ZDVb30QK7XQwSmwUWO89iA0y6Hrli9FUNAQGjtejLLBGeiRa9Hjhw5fNnlu3btss3tLudGmuxmXU8iXp94XG3y+QwEawmJsJgbHH1ePsxRu1oDluTN8Wh6JcV4VELUB1YmIg1DPa4PXlneFR8uEdSwVwaSgfhD7L9e7pnqtRUCfIxR8KyHUauLgZYMifGKOfdh7tjcgR0bzYUe/2i2nWeK8PCec9dh/ceITVnPNrYBsVm6R5zqRYwnauIqgO10nkURRrT4/uDY3QgrNcqj+pSVKKPunuOZPQgWojBFonISzgXBLvBmdiRIdurgrBSFF0qYWc/QNfaGidR7RR/q2lClQa+T3T24Eb3CjcI4RedLdQpSujq5azFvgDvc0IcZ8YLlDJMNwRRRtggy474pAjsefC7zaJAGAVtoCBf1zCoxrsv4eBio4sjVGT52vyrNc0j8LZ/NaFTrL84kCSgPqFa+GQDqUR9ioR+UrwZxnTAlF8NOXjpfsxOZMxUMoOAhvlzW5U4cW4aGuVEIgyWEiKgy58zDI4vca2nJSTnifwriR6ehiEZcHLWqxhJDUDqeOUr5SsUQhdPS3ju8FHrETkM+5Cm8aJgK0VJoLxRUPJY9R2rEmcnJqHQe9lzN4XKPplhRZcht2C4IQ9RbwSQsZ8t4YSxXq9V1Pbg4q6cVh3NteROS3nCXOH9cLwjkDCkFhzT4TC6EaUMty1w9sQtM4MLGHG6oujuYQsnDCX32BbjrbbsDc7Iei5yJm3ln0e86k6uX0rTVVhBlQl4ozBiOYWYDdZsuv54/bFt+fjWNUs9MY2Bjue2X90dNh40X1PiqwisDinAGvLoHIKQpfDK9+psWmG6fOI7cQwi5A0V3mUq9tKIys3IBqKcsnKT65pWBGHvCI2jAwO1URDY3NpA7tC36DFNEJ/roIjji+K8MePAiodhhKeqKg1O0CIwjtFzgIJKi3snjEYztwGHGPlaeHj0FQjWvxdqW/ByBRODI1jOxux87duzARRfv27fvzMbZvs8MBMUaFH1GSgubUlbOMEYyCyzIy84aPuQQCqBik8sKjDqEoVQw+LCRExlcl/PN1OhKW7gkXngYy7fFTD9njtLARsbAzsR4JdOAJI/+OX7bzmNwzKmWPP33Qgv/dw8a25bzHSPH33esQ6/YABVxq3AsCv9l+GsE4XW6s/8NbvBcj2oAfs53MCwy1Rz7vxSbQdqpp6AxGTmM4cxG2HZKLNtMbApjIukd85yzcVAXUAGWCKPMeAjwwo3IJV4VhVvlh7iHC+JuZMTkpF593JgqWnzWpSoXsSGq2qr+AaSef+jq5kSkKM1miSqbKP6rEbOTSwUQ4kKLsl3gR0xs1V9B6Nl7IxIVnmEj61/Jsw++ijtxWSZhd5wRfQ0js0vx2LWYN4uW0jALVlWmYFZy8WULa4QsqI4In6t8WJwSuzglAjFRCA2F+6JkZkSM4ltQ2DMrafFIyVHg+tDIdsAQqI8PwzLMJkCs5gY0c511JV41pYBCagDqJbZyJqLelSncMx98OtOSySoDU+Z5KUtz98CZuKBNbKSlq5uzU/krGS0zIDHaLk4WaBY5RngVG7T8TsHfCNGU6BFVfhJ5nEfDYSoep4fxrUgVSUkAF0Qq3Dvm8BRdO+/IJZOwofRVISIUoWsvmWRzZ+aF6sK9z0Lgbq5MrZsaWE2VYOResTaLy6HqM9UH81SbwypEcZ6/7jjO65o4+RjVD6BiOKzElMvPuu+4pmE6DQ9/CdEVR4SBBjrZffUzNO3ePn0G3QxCUIdwcCYoPGw3L2pPO/a3Ja2DcI43eZ4br0YEIJGmaWazWRRBQDMzObO7q+rYB9mBQCx/H0Kgcx6HEzg1lrOrejy7kVUrNb5MgC/LFW30WMfZhnOPsIAMkMA1ioqFm2ivnQ0nnji5d+/evbv3nNnY6LoupZRzLma6xlGJYKGJWulDkelwj/q0EZphliNHHs94xxNwdya2aBYaxZ+IOuMRT3j8GebRK6XQgrz4brFT2EBkwpBqGj2AEo5bKdyqNIFKzhqFj8UrcgDqY5yAVyYuFVqoj6AhjGeb1xG/0OGjBzk8pPi/y+obvdK0xq9HHLOsBizZ7vAcMQqAypqk4RuqD0HL1315yjoOy89eaF9Y4pZDTHDBm0XBipbPAhWJJ2Y2cyPqoxMopVnW3iFKQlhU4NPgvZtBYs9lJyrUhhJyaXYrS8scgxmjQi8zhDXdYbdK8rX4DdHBxEOC2rAyklZUYCpPLIZxHHwUHcABNJK63Xm1PdXNr5uqFaeqbjVWNFqqNw5z77KDiIkdyFE4Vtx3rgFT6DYSANfo6GkcooOxDEFwZx5QYSotR5wLBwRERbAoxjbuxt0gxAYwLPokMrMrTI2NcghbEAFkVKgGFqiYM4KBFWIMBCD8Nh+8NFeP7zJCdHqudZjV3wpNDiqmc5nhrCU2CgKxlcRXnblDCENwt2jTVPRbg41YxHwK0uRFWCE0i0MQCmrD8yIvkTEZooMJMch88O04uGtWKj8pdB+X74wGLFTmmI8gQCs+X1j9Kh7pXjnSPBRBxL4U8SaTc+no6yHZSUTEMBIlJ3MaaoZK5QU7IUqNygC6K2Tulg2kgIuqq0tvrkTqBucoYLJYtuQgMtUdK/y8lqyuhZWw8BuEHOWvoecx2H7Az91Ai41YGogw97HSRie2cHFrJObhx5rFKvCcKTXODbTdfc2NvbWLUyexWFDj7KRZwQyLUlmDK8wJQWC2893vcp8sYepK3B8K2VwYTxGQiIjIYj4vQlju8FoTOsI5SmhHAC2L90e3yWXhBkzpHsJfRGT1W4qPELEcAuxfhs3u7NGWXUi7LpKOy/FHccrOeVLxu6LkG+r+MQyH++mzZ3fv3r1/796NjY3t2XbbtL2qkzgJAIalOIW7cslpjW9shaUzcGi8/r7ytzpe54cBVo/RvBk9IY9s5/i0NPziS5JtCbbiHhNz6EjHTmFRGk8SQ8ioi6e6sQwa6tFpkHMZf9f4qLN56UsuHZfzHcXYj1yK+suqjxEO0FPhE75jkoUBqVNqlZ06HDsXqp9T9hIv73jT+MouGH+cH91Z+puoxnjQnHcqmcbsUc2ZHFBzhmcQFX0LV5CVQJ/Ja9FjKWNhLVyHuEwDeAgVzcmMEBBiKfjyUltU9iyKiHy4S6t+pBPIQNfM4AAAE9dJREFUgupORsOM9HP8ZFQDL2GkEWyVJc29/LQdPuzo87HCEXOTyk8r4oHxioBKo8YR8Bdef+k3hJIiDudlIJiSLld8MESJgkxQ7rTgdF5U5CBI7m4OYqizu4bbwurELhnKzuqDh64cQX8weFDqISpBz61kLQ0lER694PMy2GUtO3JBhqjYeUJ4FvWxDsvBa9xQYIYBM4jUZ9EZi6cV2YMKR1cIPW62xsNcE/I0/hnTIBIOy59A+LWxaZSfiBtUOKs7oom5l2kT3861DAWAu5aqkMBLinMa3yvj+sIAcYhiH6Lik5EJhEBw44ATwjcsyk/FfsTXVpCDw2k1IHNSq/XEIAX17gY3RF4FZf57Lbk/nzPxFMd59oenBnRji9hpMnd8ti5wB5jO94YLfEux8R6STdJOVAGf7Hr6dWaTxcY2LLcN931nZCxNwDSx6xQWElD4EGW6DN9i4x1v510vbUGVZuYSmqr20MD4h/AB7n8DnOPckRnZkSFY8nNcgQHBoSDjRNkIh4hwEXcZ3r4E+C8UT8Y2s9zeluGiCMxsc3PTVadrrTC25zPmpMtH5Indamcdp53uRDVIFFAKk1f1LgpWHFaxppLJxCgleW5NxBKTGD4+QikQRm0HMERle4htBChd5Qne1AWmKxyEIhpONZQcHi2quHTcXSSHRldb5/dgHQpMWRyec8b/PC7UOZPvXP99jPgtCwrHPP8hv7Vy3gGh+Ua7wHIS2TkWcsmBKPvvkl924a3hvNuMx9kcUSReh8jhZKWOzh3QshJUjIVAHhnl+FI2p4Lrl9kc12AGqW9alo15qewcGH9xEQSwG3moRAYQUFZ7ABIlHVo9OdZAuo2JB/Mcu9O5/sQwwqx1IHR1zHdgOWOfuEZ7oz/X6Ra7OUVxSNgKYizXvy2dzhWAd8dzKeaZIrHhkBC9rRu4wyqBn81VuTjEhd2AoqQSXUlitZfTBlJqZgWiDpeR6nTgmoYvnRSi4q6whYNpMXaYDe5xp2XjQ5W6Hm4zLtu91iQVAAlMSwBaSIZUAYgH9oMvPVqszFYb7mnlsKeCGctR6AFlKNlXV/Gwa6Dcdn1zMMPGG1917dire1IOAeDsgOiSLkNGUT/FQeVhOEWVL1OkiupJnc3juQ+ujRrcWd3M2d0zXN3UqUg9lkxR0Ke/4QCc51iJ98Z73fmmqBFWahYutLuM18vIOA3fOPy+wzSG/y0Nac5ESXtH2t1ccq01++ZnNkh70k4DZ3cmzdB+iV3HaXeUVCxxFBpb1pU9uaziom4ZoZSIIBADLdrzqPYU5jsKCkt9ou/40tFY+dDJKr5+ScB399rYrjjpcTGQekYzMAuLu1lWuO+scUVlj42/erixEf3cUcT4ATiTmhLg7rPZjDBpWCZN22c3V3cXERDXkiMar0YUwH8AvggV7XEAY0EDsCHkPIc7RMhUxGMbBQN/gyNizmWOgOrW5sbMDJRsCDyE95mY6v1HyR4DEcIOu4DRMIKBti3nvKOmZgfCZjStGCF+O8zGsNdXzGPncR5nYudhK/udYxQ3rJ6n1m7QOWM4Rtoj8IleA0NG/9xz7rgwLrUMsL/ZTxpxAqKTRfy+BJgG73PlJ2mYdnOAQ34FROx1SVRAuGYczM2M4EQWvSxs9CzK0LEDbhZOf/EePAhC4dDGlK3s3NjxR9h6VB3VYhcCpIxkHfGSvuHiYEbjAfIKP5aZMHocywdaZtton63/qwmN4nZTeQil7DcMrFPtWgoUcMwqGZrhJVs/xtsonkWZzEzk2QtrAyjoQciAB0JRKiYBFGW1GrFwRd4Gx734B1VwfZDGGGgKFfCPm408KxGXFFIwKpaIo3udyOQMRwx1ZWGXWsDi+Lv7UJW0WjlhxEX0Ph5uYXpZpYmM1wlXn6x0UKGSvGcAgtAm59XxXCbjh1W2/OcF0LsYf6tOQ2jRejWD43ClpmJ5bJVtadhjF49SZBIng4XAKrsAVSO5fg8AcwZMwlUxd3C4EeoU4xbIRAHVaRnpIZii8eDG6xpPtQ+Mj/MOxY4Xg1j6N9xhduwzsTuNg+vzfiNHZzJmzw6etAcuk3bP7MwMs82mFYNrl6Vt3KH9gnhYgu7QEbYa+o01HwaqUCaN8ACrqiV1VXrhZHHBh6iUoQ7cbUKtIxpPoxWcklA4OiueTcXf6g26RwTDHn1w4AZzgsQ+VWoVYn4KEchNS7fBkXDDU8HP44cYI+BLZ6IcZiTUSOr7bmtrazKZpJRA8IxQtGPmFK50zHzy1SU0di8ofI4KK8fD8JU4qGy15ppXtbpWb2H5FRaAXEkq7LhXj42AIg3pwoBHbyswXMhrRqm6coTYC6xK7jvBXYmwkrGrdSUopjwezvKbbVleUS9yfPFlWq+ko3z0nh2+SPEvV+jPPoYPuKy3UWJiqZ0SM9elZKmX569Z4qW1KVUfEf8Vpfwlx9DPwfHDLC9/ApW48I1/ItjxRT2plJRznQg1PVyANXd3JydSA4jVOVowAjmwx6jALDoQZCGrFu2eAK605CECLv9fVrWUBW8xeQPdHqIKqvSUWJbl/atAQXww5vio9oXdC4Mz0qwonLvKgxg/8fP4kGW8+ZwFXFWcYx0t3Y44z8rJi5seuaEShcYr8Z+TlcrsYTaFjXSTIDo4AcZeLKVHt/pIwLOXnDw5AFWrKY7RTSwnS0FoAJBzYRbU8KJ+Qh0wSEDrQ/Bny8cU9xKgVZmrFhlsFlCp2xn4lwMkOTg+4b8ahWRXrGoDHAGg7gRDfYAYgFLXVITogwcQXM8CMcaqrGt/ICjVLc6X4RLGi6m0711ulsN+t7LtUYVJ81COUIcl7kNGTmngVepGlNR7ipnhiP4pPki/lKS5KRGZhz9mJUZiHaJCH4BD+IABm8NNAAMvVzfGa/ycVX/OTvg3OsoODOaBGsU7dxXY8tvrTwr0bmUMV5yzYvNARGJ9h2avHLxSeXd35gxp5uR9PwMLN0zaQXNxvwFyp+UjtDJRrVr6JcmgPqmyLYd2bQkIEGsJYCE2VzPSeL/GV6BailhkXud8ra2KBxMmdWXpLePY4jC7VwQw5Iw9Sh/g7ioxpUto5EWY1+A5Iyrmhz0PFfP7xi4FFQ2jOkRlyBkAVCMQkT5b1n66vt4y932fc9acl/3Kva54ABf6ylWzVH15qh4Gyvd1XTc8//Nf74VBi4rzlx2E2AVgIqZSDpegTEgMhhGRMQ12IqJZAQpLZ1j8ZI7CYAJMyu4CUC3NCT8d7KWBcvgiw8XviGBK9DWsqSXcvWr1By+mvmEcXizdp7FIy+oQOUoMu3SIikWtnypE9ygwq33BBi+heuLF9zvXpVj+9P/OnwSwlQ03ls3IoyK3KOGpUbEDgJYxZAIEwS1AWEeDe8G/CDYw5gbmo1SPYohi4a5Gg1eBSDcbnCCoPAej5bPAeMVWYzEaDS9Wo4DWdZu3yqQp7x9GtMy+qMEYv15/7pgDg03auTQGJ3J0hUP/mpXTBhwey9E5sHapyfviuUbHZCoWPdIFWihuECY3A3MKKW8AVmgitmMOj/6J6IBlborou1VNFsJAKZw1vstoHB9Q2R29BsTk7qWVsbOXs0VTxuWuuhzcejECQti/2G+DFVAwEgMGOL6GAj78s9C+wu0wcgLHyvICj+x4ZCFSFv7jzqhuBdUfZYB2PE4ab5gDrFXY0LzDxXeve2LErIj6GyPigvuAtKx3AsysjEpIG8Oj3WRJFCm7ja6Zqkc8gs2KYkHtM1xgzuLhjtZ4oc18Ixt0QdQBsKKPGQOyjHxKVsuXq6z49T7kqb/R4QQSdUGarB241Nu98805tGcYkRJ7NOE07YmcOZkpCqKH6tVZJYNGsmnYomv+1Udq98OuV+eSoCD7FHhANG4O1JTK9ZVHQDSSkiwubFkU4QIMD6vavvGNVmjVWMiMKhrtAJFHSg9ORsQMclOzTE6VoDR69N/QmfBxnUS9VJibC4u7q2mh2wOmivlcRFJKgaHUfuV/E3+zGqagYAPn/4xl7fse7pHdPE9q/5x/8OqfCu+bCBRpDmJCyCk2hIaZ4VzqJUIrdah3L4lSDVSVlqtUUfev8k1F14VqGB0n89rAlQpdyZlQo5byM1Yc78CCUAZkhI9hKQY7foo1blnNuY+HOTCYYh+WBPjiNp37nQAKB50dulp3EITmglg85VzaYT++8REUFpewvkPrYy/KkhTREswsDACQyEHdsHTY2Zxr+Z86k5GUxtkGNgFgbEbGwXgoAG/Z4sOWOSja/rC7EbToV7IWAYJCL7dq+NzrOMTcG2HIJd3rvMNgxJSMzLczwnCOEcvCQsQyH1Gw0JEtpNHcA1D3r/FwLvftIRV6jlHf+YzYGHGbBDgTE6z8jlp1Aiw7bil6AolLqXGgpdcCgAph1TC6lOGrtTR/WNbIFOsTGF9A7CWhS0NwGQ+Kaj3XkPLxsr6ie1adEVQ6gmpwcOpMAhAioKE/LnCqHRpLrY97IP/lPO4oHSRLTA+iIFG6e2RMbHxyDO5u+c74vSRRaEUmYXyIR6/gUU4m3HobTjD6C9mATvmSJLZDM8tK9i4mT6ymqCrFwBcxWJTquTM5lj3PosWvacF3CxbjAyct8C+tsIzxjktEtSi+MvhPdRQq2wq6sIJ20OrPERox+tJ6sqLpdf70ynAxMUsNAprA0vqhp7FMtzc2w9CCKKunhuF97hfRvCpkUBgVBaThGzFGjIYvoJjVBZUsFzG+Hi5VJVFtrhw7kHtYHhuDK+XiKYCXIQNYSF3nG9ShL0ZkfJljxzNXL95owE4ovgSCZ+OhCmxCAT56aTwYGOaKZ8g77qh8HWF4MrSE62LFBgeYDa5Ba+LUd52KRPcfIkqouT9CzbEBNZ3z1JQlHl3WIMOcHUJqI2X1OEKqZdi7fdCwkMJfNi8bRPHFItyVkAokF7gwWubE1BAYtUCGJVtU8rtzoWePHJTo10gMcG0Yb4AjGxzE2foSkDrHXKhZ1fh4fMd4wUcYCrcdJBegxGHn9ayHl8oIxGiM0NklLXRYSJWgsPIgzrX3dWCFQhAZAEEcQPnJo99HKMvybMV8Vt9uGQifex/LwyqzLAOosBCIKFrolor/MhYOgFmcFJSpRCzszlFpqAMqF4rKUdIV4v6eAVipql4OLYcVjwryMPlACsNCBDeGlDJ/gFxsWfBpjKXbtyyKKqTjkSkFlr6FR/iMipRGiswqKEqAGYHNjCwCba79KkvstRogDnzvShJa5j6WQX+80XkgO5x71JpJKt6MmtUYm2u2gUIGworINgFOQl4bWhFFw3ry8mB86XkPFrokJgCN/GJx1pfMKqJlRqYOHqFa+rgcj8IRdkMIkoPYF0WsutgIL+1DLQOoKQ9iYnYmEHlP5ImZLPKz4TBYsHLq8yr+ExM5SvIPAEJxBF5jCdeCNXKF1lBBFAsqEura8wuthjJLvbr7uqpIzeNfIuViAENHUAGHx1+3x7KzFWEPdYIUfa9ohFbcYgMP0YbWqhnnQKYGSMWjDBVUKqdY4YRagj2ah8PFxOiN73bYDc79OYwA6lfsyMNiFNWPfwZP4twjvNsBsh36NIw8tkK0iWZ2fbY9hy5p2vXNrRlrR+SRQW/YPXfwPrGbKywKGJflY0syVQz60GelfJcFWJJqt78BBI1Y19yERIhy7tgsQDNH2cIASIQ9VLReKqKwTK1H3rEC4aM8S/zJCUwwV48e4QRE/w2rWBdCub+Cr8GegloPN2GOjmVMbESmY74wakr6qY/BmTAiYqbIdNQcfnC9DMxm1vd98SfcCO4cqU/2IdEQi6pEV8vuGwFFDzcffAYNG03EnhzIcI1wQigZmVmmkI03Y5gwRFgk8vpqZgxPDM0QAaQMHhFE4qlAEhAtc4D1tUmoZbSpyTmaq7M5mVlvqsUcsBcmH4HIoyRIbVj2FUqX6F0Url+w/6ITRF2OK3XJXuoSfVhvMavPFe0ZPlCsBUtvS9UzLjLyHvjDgI6NI9TQHXMLUV4UqoiZh2bhELgA2Z0oPFYdiABc3Roa2ab6SiFjDBZq+MW9eJfnMrD8Qr8DBKSls1u9EtVgC1WbDkRnDxTWxYh9Uq+BomdEPb8BwYAnFBmq5ctAOIIoe2WwJ4ppSQBBKTNaIzMnYkis2+hKXKVZyYpRHQS7qfbfsoEW7OHIEEjChaHa3WNkEsBVr2XAeuGh01hKfLmQFQCAeVzHgfrBmnyDR5I/MNLRbCxe9ti1GLbA4ahdRkdUDIUZ2MBANlCCqoKVyImZmE2dmC0rRccs4qy9JyZi02jVHtFawH1BXPJwwZZx43KnJiJRqFIXOCJTNDwo6SrPEUJ3DGXylsEkwqLZkrBZ7rXQ5FN0RHNwTfA7gRLYIUSTpjGzJBSIa3yvAwo3M3UzM46tIIqIg7BjFJwLX9qo5QhbjROoVoUY4O4kvOwnMngMFP1pdVj9ZoDpGFomig0zmBhkGs8UlX/K6rU7ljl5Dh+MKr7DnECx6C0khmo2uzx+ZyQKTl6ZfMVmx2SoDa0cyIECepgioLIDhukzUNeXRpfLjNIa3tBSw6N+ES1vFnVJSlFc2Ln5LH8/b4ENg0jLVwPu1eMbTXAWU0AVrSB7v2v/JUkw2zjhXW6Y3FziJshgscY0NIVR8BILiREah1IlCW6xLOHFnwA5Z6uY1pKMA6CRmGcqgenV+3TSAq6Xy2bi8Ygt/xSQUpk3Iz5mpN7K+3k5zjE+KxFg+UAxUiQgh1Ifu64q+gXcwjkCKJl7dLVVNZLWsjGxmYKZGK4hwStjz6bGK3CARFDTX+MykHi00Sv0/w/JYFIaNoNXwgAAAABJRU5ErkJggg==") !important;
  background-size: 100% auto !important;
  background-position: center top !important;
  background-repeat: no-repeat !important;
  border: 0 !important;
}
.refapp .rhead .jc-real-logo,
.refapp .rhead .rtitle,
.refapp .rhead .rver {
  visibility: hidden !important;
}
.refapp .rhead .gear, .refapp .rhead .rlive {
  position: relative !important;
  z-index: 3 !important;
}
@media (max-width: 720px) {
 .refapp .rhead { min-height: 105px !important; }
}
</style>''', unsafe_allow_html=True)
