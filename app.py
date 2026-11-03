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
    url("data:image/jpeg;base64,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EABZFRkoAEIqIiAyUqKgIioKkCp7MlKAGkRUZpAAgApQEFEUoVFagVYiwwLFRWoFAaCqikNCK0FEFsNO+rCY/ey8/sxhj6e98mWfLthPH3WL79RrPPljlLUWWW1JprkiKNpVSBCqikCpFKURSFAQAUoAIWKipABAqCRUVEQAIQEi1ABBAEBAhKrIKoAIgBCCooi1KEgAIioKRABSpVqMlKAkItRkoACgICJVQJEarIIijNLNRagKicgIAkoBAsBIWA0FajKxqCqoNMqqKUoBByqCCumE471jH5q8t4+vdFbuTPKcjVo0qsqtpYsRYgqpBoNRWVhCxUimBQGgoCAoFAcHBCxYkElAIOQEhFEURaBIAElBAQAEQQEQoECCICBAAJUVAkFRFKKgKAAoipQUACRFoyUABRFAURUCRFKChRGSlRajNaAAgPZSgAhQUoVFIUiNRqBYqRWmQApRFQGpEkXlqQLaici2tNCcqdpVQLKrEWFNCK0yoilNRWYrUZVUUhSIsIUApQCBQKAogAJACIgBIioCIAICBCUAURagIAEgAKAJKlAEQokJVSgoACiNJQUqLUCSgAoVUBRFRkiKlCQAFKiozSiLUZpAAQApQUgBShQIVYitQKAWVEClak9zGc974W1qT5Gy1nkqK1aURQliorUCqimBVjMWNBoRSFVFagVWYpCxplZSFAaCqikCoEKqCS1AKURUgBI9kAJEVARFqAgIEM1UZIACgIkAAiACJVRIEAQogQioCIqAoAEgAKAIoigKIqMpBWQSoqM0oijNKCgKKiwgVFKAUhQCFioNJVQIVrDHnz4MMfVfp71rKzxPEbxnzWbfgt9oxyWorTIqAylWJFKWKkUsiorUCqitBYqRSFgBCgEKsRWgsVFIVYyspgUBoKAkAJKAUIqJAASCoEiVagpEVAURajLSABIACIAIAkJwqBIKiKABCKgKUAFAAkFQFAqAiKgJUAUolWoyhKqUFKACAMlFRSFBSgBoKqRSACFLGscLlfp7014XO8Tx711zyknpx7SOmOPzWLfhnLKSenHwxylqDK7MiiDJUFIIqKUpAMCqikKqQaCqikLFSLGoFgBZVUUpQQhpYitBYAQKikACSiKUIoEIqJJQQISqgaGaqAoFSs0gAQioCgAIgBACKABICIgIEAAiKgQgAoioCIAKVKqM0iKgJUVkEBGU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ASABCKIoAEIqIoFAhFQERUSEVGSIqIlRUZSAApWWmaCAAgCSiKkoBCgsIAChUUhQCFAKURYQqpFaCiKgoQKUAhQCAUKAgQoipKqK0CKkUhQEgAoRRJBUSFRUhFRIRUCAARACAEkABEVAhFEUSqlZKKgkABAgiIqBACKABCACICSAMkRUBQAFAKElZarIMBAFQEhQQUApVQIUApYAQoBAqKULAIWKikCoFKqKQsEUgVFKURSBUCFASWKitQCxFIFQSUBJFAoKCSKCQipQkABEVEgAIASQKAoFARFQIRUBEVEgoBIAiABIACgCKIoEgAIipQkABQAFEVKEMtVkEABAVIVFIAUoVFIAEFAKUAgVFKUQIVpIFKAQNMqQsVFIFRShYikCoEKAolAIVUCBUClEVJRORJQCgQCBBIABQAIARBBIACEAIRUBEoAgCSAgIAEAiIAElQEQEoQACgASAAoAChQoSVmqlBQUBUBIVFIFRShUUgAQUApQCBUUoVIpAqKkoitAWAgqxlWgqp7KUoBAAkoikCopQqBCgICopQIqQURIVFSQVEigAoAEgCIAEIAQCIgASItQEACQoIoqAIAEICSAAiCVEACAQIQARFQESqgKIqMkASFSKkKikCopQqKQKikACSwAgVFKFRSBUVIVFIFRShYikKqQIVUUgAKFRSBUClVAheQEgoJCoEKnuoEgCQAiAJIKgSCoiABAIkVFAUACQAFAQEASQAEBAiotREQAhFQEABQAJAAhARCiAojSBIKAoqKkKBAoFCopAqKQKilAKgAFCopAqKkKkUgAKUAhVRSBUilKIELFRUAFKACFEClASAVBFQSVARARIWIBKIJACKABCVUCEBEQARFQIRUBEVAgEBAEioqUFKAkJVQEACQCgoACgASAIpQQE5ACUBAVFKURShQIBQgVBJVRYQApAAUKipCopAqKUAEKIpShAhQEBUUpQCFEUoICCiKUCCSiKkIKkCKElASAERFRIACEAJKKiKCsgqgBCKlBQAERUCAEUKFCQBIRUBEVAgoAoioCIqAgASItEkF5AUVBJVRSBUUoVAhQEFAKVYgQqpypAAUKBQqKgAFKAQKBSiCDQkUgVApVRSAFSBApQEgQSUBAEEVEElQEgBIASAQIBAVQEhFQERUoSAAoACAVJAAUCoEABJRUBEBERUCEVARFAkBARFQEASAAlVINBVRUgAhQClVmKQoBAoFKAQoipKAQAFKAQoipABCxUClAIURUlAIACgBJQEgESAEgBIACARIURIAREVAgAJAERACQVAUACEVAQBFBUCQVAhFQFAAUACEVEQAJCgCgICCiTKooQqKUKikKECBQKFAgVBJoRSFEUgVApoQIURSlEEFAKUAgVFKFQSVUCFVFKBFQACgBJQRJUVEgBIACQBJUBIBAVQEhABAEkCgQgAiKgQAiIAQgAiUAhFQEQoCgAQioiABIACiLUBAAgRURUUgVFhAqBTQikKIIKAUoikKCFNCKQogUqoqAqBSgQhRBJQCF5EUpYrKkKAkApAAkAJKIFACQCBKIJACIAkIAQioCCKkCAQCAgCQgAgIkAAoAEIoEiKgIiokIAIioCABIAClSrUBAAkVBFVRSAOQhRFKUBBQChYggqopQqKQKgQoBSiKUoioCoFKECAVClioRBoRShUCFASVAIAElEVIASEFRQBIACAEkFRIRUBAAkASAEUFQJAAQESASgqgBAIkIqVkoACgAQioiIqAgASVFQEACQBFYAQoBAqKkoikKIpQAgoBShFIAClAIAElVAhQClAQVAKUAoWI1CEFCABJQEgAoASAEhUEABIABAEkBEgAFBUCEWoiogEAJIACIqBCKgIIJBRAQAIQQEACEBEQARKqUJAQFRAEASUAgipBJVSKQKilBBSABBQClEUhRBJQGgoCSgFKAQKCQAQKilCoqCgEABQqKkAJABQAkAJACQioEAJAIEqAiIASUAFFBJBUBEVKkAUFAAkFQJBUBEUCRFREABQKgQAChQSRFKyUARAElgCAqKUKikCoFKAgoQKAWECopAAkoDQUgqQAUKioABSgEAqJKsRSFEUoVAhRFSAEgAoRUSAAlEElEElQAkARAAkASQAECokqACIqBCKiIAEgAIigSAlSEVAQoAoigSAAiAkiKlZIAiAJKIqAqKURUikABSgqAAUKBAqKQRUUoVFIFQSUAoUCABJQCAUSAClVAhQCBUElASBFSAEhFRIASAEhFQIARKgBACQgAgIkAAiKgQgIiKgQCAqgBCKiIioEAAoAEgAKIqBCKgaAEgBIVFSFRSBUikABSkBBQChUUgVFKUAhQCABJYAUAIKAUoBAAkoKQigUKioABQAkKipAgkKgkAiSiKkCHIJUVAgoJCACAJIACAJIBQkBAVRUSEVAQECVABEBIBAQECEVARKqUEQAQQSUBIVFiCgNAUEgApVRSABBQClAIUApQCBUVIAKFAgASUAgVFSFQIUAoASVUUgRRIQVJBRJAEkFAkUEkFREACQBJAAQBJAARFQIBEQQCVACQBERUCAARACEURRFShCKgIlVAUACAEQBJRFiCgNBQEiKBQCkEAQUApQCFAKURSBUEhUUoVFIFQSUFIQFSACFEVIAKUQSUBAVBJRApUBIORAVEVIQEgESAQEACEAEBElQAhKAKCiSABAgCIqJCKUFAARASEVARFqBCKlBQAEASAElAQUFaAAkoBQqKQAIKAUsVFIAChUVAAKFApRFQAChQIUBIAIFAoBUkASAEgBJQRJQEBCiIIBLyIJACSAIiKgQioCAgKiAQAkVACAEUACEBFKAEJVQEBAQAIQEhFQFBUBAEgBJQCFVFhAAkKilAKQAIKAULAIURUgAhQClAKAEFAKFRSBUEhUElVFIAEgAoCiQqKkIqJKIJAAQiokBUSURQRKokyKgIAkiKAoi1AlBEgAERUCAEkABEVEkFQERUBAAkASQAFAAQBIASUBBVZUpQCBUUgVFKAEBUUpQCABJVRSCAFKIqQAUoBCiCSgEC8IqQAQogkKgkoCQAUABAIkqAkAJACSCoCAJIKgIAkgFBSotQJUoBAioiAEAJIAClCgQgIiKgICBACQioCgqAgCQAkKioCopQqBCqgUoBCgJCopAqKkKikABSiKQKgkqsqQoBQAkKikCoJKAgAFAASiRSgBIBKkqAkAJACQACICQgAgCSABCKiIigSABAIiAgSggQAigAQioiIqAiKgQCBAIiAAgAQAULEVJYIpAAQoBSgIKAUAIKqBSqgQoBQqCSgECgUKggoilACSiBCrygkKgkogkoCAqCSoCQBEgBIARQBIEEgAEASQAERUSAAgQSEVARFAkVAERUSAAhFRERUBAAkRQJEVEQAEACACgBJQCFBUAApQClEUgAQUAoVFIFRUhFCiKkUgVFSAQpQEhQQAClEElQElEVAVApQEhFRIASUESVASQVAQBIRUSAKEIKCgIkogkAAoAEAiIAEIqJAAKAJCKAoAEgqJIACgAIAEAFACSgEKIqCiKUsAKACFASFRSBUUgVFSFQKUAgVBJQEgAoVBBQCgBIASUBAASAEgBIASOTlBJQEhARAEgQCCgkAAolUSRUEgAFBQJEVEgAEQEgEBAAkARAAhACQoIoACCASgFACSiKQKkVIVIpAqBSgEKAkKgQqoqQqBCgFACCgFKiiQAkAFCoIKAUAJACSiKgAJAgiAJAUSVASAQJUBIASEAEASKAklFQIBAVQEhFQEASEBIRQFAEkABEVAgAJAEUABTkUCRUVIAKFBBRFKFAgAKUBBQChUCFVFSACFEElAKFRSBUVIEElAKFQQURUgBIAKAElQEgBIASAEgAJAEgBIARQAIASAQJUBERQJEVEgFRQAJAAgBFBUSEVARFAkACKgIoigKAJAASiKUoioKIpSgEABSgJCopAAgoBQqBSiLEFEUoAIUIJAqJKIqQAUAIACQqKkAFACQAkFBJAAgBIARAEgESVFAkASEWoEAIoAEIqJAAJUWokABCVURAAhAREVAhFQEBKEIqIgASKkVEVBBQClAIUAhQEiKilCoEKAgoilACSgECoqQAQoBQAkKgkoBQAkAIACSiKkAJACQgJAokgCQAiAJIqAQAkAJJQAQQCAEhFEUACEWokABCAiAgIAEgCQCAlBKEIqIqIBIoIgKgAFKAgRUUpQCAApQEBUUoVAhQElAIFQSUApQgQAJACRFQKUBAASAEhUVIBEgBIASAEgBEASEBIACAEgBJAARACAEgBIQARFRIACQBEBAQAIRUSEqpQRFQIRURAAgL2EgFSCAUoKQigkKBAAkKilCopAAgoilKIJKAQKipKIpAAUAJACSiKkAFACQAgAJACIAkAiSgBAgkqAkAJACQioEqAigqBACQAkgAIiokABCFAUFREACARIRUBEVAhFREDkCbyxYerZhxXDLF1zw0zjlthYcDm0AqQAQoCQqKQAJCopQAQoCQAgoilCxFiSiKQAFACAqBSgJACQAkogkoilACQCBKAUgAQAkAJAgEoipIKiQAiIAQAkioArygJCKiQAEAIoACIqJAASAJCKgIAEiKgIAk+11vSXVlbJ9y+/w+fng+r/Df4hj1eE6bqrPtbOMcr+f/AG49b0t05cz8N8V9fl48eTD7nH1/Dw8eeWGXhn2+Vlizw754ueUfOzw09cyc1Ec2liiJKAgKgUoCQqKUAJCopAAgRUUoASUAgVBJRFSACgRUhUUgASAEgFSQBIASUBJBUSAEhACAEQBIASAAhFEmRURA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Ms9eH4b/AGcrFljqqXbKgwQBEEAlASAEgBIAQURSgBIASAEkASAQEVBIASAQJRFSEBIASBFBQBIACQBEASAEgAIRUSAREACEBFFAIASAChUVBRFMCgQpVRfYgAIFRUgBIASVAKAAgBIASAEm9ez0X5xvmNbMJPvY98a5N69np+7l3xrpjlLPGs2fMZsG88eL27y+GFZoyoKjKAEVQAlQEgBIASUBBUApUBJRBIACEBEBElEAlEEgBIBEgAEASAEgECAEQBIASEAIASQAEBEgBEACAEgAoVFQFApSAQoBCgJCpFIBFSBFSAEgBIASAEkASFRUm9efb05eL4+hljcaw64Zyz0Zf0rrjd+qzfXtzRvKcVlmzRRRAVQAgBIASAEgBJUBJQEAAkRUCAEgAIRUSAEgBIABQBIASAQJQEhFREASBAIBElEEQAJAEgBFFCBACQAUoioCoqQqKQKgUqoEKAgogUAJKIqQAkAJACQiokAJKIqTrhfXPTl59qxZxWXSWbJ3/FHSXy/7Z6YCwBAAUACARJQEgBIACFQKVASUQSAAgESAEgQBUQSUESAEkUQJUBFUBIBAlEEgESAEQAIBEl90VEgBEEUIASAChUVAgKkAEKIpQqKgKgUKipABAqCSgJAipIoJIAkAJCoJKc2XmAk6c+uc+8YSWy8xu8ZTmOm/IdMKislBUSAAhFRIACFQSUQSUBIRRJAEgEBVFRIBElASAEgECAEQBIASEAIASEBEACAEkASAEQAIBElEElAKFRUBUElEElVAhQClEVAEUoASXkRUgEIaEElEElRRJBRJAEgAIWW43sgdpuzmcxExy9P6NWe88N9+wyKAoKgQiokABACQIqQAkAJCACAJACQAEAJAIiAJACQAkgqBACSAIgFCCgkgqIgCQCBKAkAiQKJACQAUKggoCSgECoqRAChUEFASAClQEhUElAIAElQEgBIACAEhcbx2vhAy6Tdn/pDC+18LlOG+/cCIqAgAQiiSIoEAJCACAJACQAEAJAioiAkAJACQAkAgSoCQAigqBAIkpQSQBEBEgAIVBJUVElACACgAoBUgBAVApRFQUAoVBBQEgBIAKFSKkAIACQAkChSCokABACQ1jeZxWQy6TVRZee18nDQQVAQVEkACAEkABAEgAIRUSVARAEgBIASAAhFEkASAEgQRAokigEgKkgCIiiSCoEAqSABKAU//2Q==") !important;
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

    Una decisión por ronda: tras confirmar UP/DOWN no se cambia ni se
    retira durante esa misma ronda. Una ronda nueva inicia esperando.
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
    if state.get("first_direction") in ("UP", "DOWN"):
        state["active_direction"] = state["first_direction"]
        state["pending_direction"] = None
        state["pending_count"] = 0
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
    """Presentación del candidato Gemini-Kalshi; no decide otra dirección."""
    state = round_signal.get("round_state") or {}
    active = state.get("active_direction")
    if seconds_left is not None and seconds_left <= 0:
        headline, direction = "RONDA TERMINADA · RESULTADO PENDIENTE", None
    elif active in ("UP", "DOWN"):
        headline, direction = "SEÑAL " + active, active
    else:
        headline, direction = "ESPERANDO SEÑAL", None
    percent = (sig.get("up_probability", 50) if direction == "UP" else
               sig.get("down_probability", 50) if direction == "DOWN" else 50)
    color = "#00dfb5" if direction == "UP" else "#e64b4b" if direction == "DOWN" else "#38bdf8"
    return {"percent": int(percent), "headline": headline,
            "note": "Señal del motor ALPHA EDGE; el porcentaje indica apoyo interno, no probabilidad de acierto.",
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
<div class="cards"><div class="card signal"><div class="label">SEÑAL OFICIAL DEL BOT</div><strong id="signal"></strong><small>Motor BTC Signal v4.6.1</small></div><div class="card"><div class="label">APOYO DEL MODELO</div><strong class="cyan" id="model"></strong><small>Apoyo calculado · no probabilidad de acierto</small></div><div class="card"><div class="label">ESTADO DE LA GRÁFICA</div><strong class="status" id="status"></strong><small id="updated"></small></div></div>
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
$('subtitle').textContent=D.timeframe.toUpperCase()+' · '+(D.candle_source||'COINBASE')+' · BTC SIGNAL';$('price').textContent=usd(D.price);$('live').textContent=D.price==null?'● SIN COTIZACIÓN':'● PRECIO RECIBIDO';$('signal').textContent=(D.signal==='UP'?'▲ ':D.signal==='DOWN'?'▼ ':'')+D.signal;$('signal').className=D.signal==='UP'?'green':D.signal==='DOWN'?'red':'cyan';$('model').textContent=fmt(D.signal==='UP'?D.up:D.signal==='DOWN'?D.down:Math.max(D.up,D.down),1)+'%';$('status').textContent=D.rows.length?'DATOS RECIBIDOS':'SIN VELAS';$('updated').textContent='Actualizado '+D.updated;$('viewtf').textContent=D.timeframe+' · VELAS REALES';
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
    reader = closing_reader(sig, round_signal, seconds_left, micro)
    if not btc_ok:
        reader = {**reader, "percent":0, "headline":"SIN DATOS ACTUALES",
                  "note":"No se puede validar la señal hasta recuperar las velas."}
    reader_percent_label = f"{reader['percent']}%" if reader.get("direction") else "—"
    if round_signal.get("decision") not in ("UP", "DOWN"):
        reader_percent_label = "—"
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

    # En el tramo final, tiempo + posición REAL frente al target mandan en este cuadro.
    # Así no muestra "CIERRE MUY DISPUTADO" solo porque la señal vieja o la velocidad
    # contradigan el lado que realmente está ganando a segundos del cierre.
    if seconds_left is not None and seconds_left <= 60 and market_side != "NEUTRAL":
        if active in ("UP", "DOWN") and market_side != active:
            final_status = f"GIRO FINAL HACIA {market_side}"
        else:
            final_status = f"VENTAJA FINAL {market_side}"
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
            final_status = f"GIRO HACIA {market_side}"
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
        </div><div class="finalnote">Cambio de precio en los últimos segundos.</div></div>
        <div class="finalcard distance"><div class="finaltitle">▥ &nbsp; DISTANCIA AL TARGET</div><div class="finalbig" style="color:{distance_color}">{final_distance_label}</div><div class="finalsub" style="color:{distance_color}">{final_dist_pct_label}</div></div>
        <div class="finalcard speed"><div class="finaltitle">VELOCIDAD</div><div class="finalbig" style="color:{speed_color}">{speed_arrow} {speed_word}</div><div class="finalsub" style="color:{speed_color}">{speed_value}</div><div class="finalnote">En los últimos 10 s.</div></div>
      </div>
      <div class="finalanalysis">
        <div class="analysisbox"><div class="analysisicon">◎</div><div class="analysistext"><small>{'ANÁLISIS DE CIERRE (ÚLTIMOS 60 s)' if seconds_left is not None and 0 < seconds_left <= 60 else 'POSICIÓN ACTUAL FRENTE AL TARGET'}</small><b>{final_status}</b><span>{final_note}</span></div></div>
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
      <div class="bars" style="--accent:{distance_color}"><b></b><b></b><b></b></div>
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
    <div class="readerbody"><div><strong>{reader['headline']}</strong><small>{reader['note']}</small></div>
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
