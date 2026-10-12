import streamlit as st
# requirements.txt: streamlit>=1.40, requests>=2.31, pandas>=2.0,
# numpy>=1.26, cryptography>=42
# Secrets opcionales para reconectar tras reiniciar:
# KALSHI_KEY_ID = "tu API Key ID"
# KALSHI_PRIVATE_KEY = PEM multilinea de tu cuenta (nunca subirlo al repositorio).
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import sqlite3
import json
import threading
import time
import base64
import math
import uuid
import hashlib
import fcntl
from concurrent.futures import ThreadPoolExecutor

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

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

# Confirmación original v4.6.1: tres lecturas con separación mínima de 2 s.
SIGNAL_CONFIRM_READINGS = 3
SIGNAL_CONFIRM_INTERVAL = 2.0

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
    background:#2ee67b;
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
.green {color:#36e985;}
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
    --ring:#36e985;
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
    color:#34e982;
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
.bigicon{font-size:31px;font-weight:900;line-height:1}.btcicon{color:#ff9d00}.targeticon{color:#a9cff5}
.rlabel{font-size:8px;color:#b9c9dc;letter-spacing:.4px}.rvalue{font-size:19px;font-weight:900;line-height:1.05;margin-top:2px}.rdelta{font-size:9px;font-weight:900;margin-top:2px}
.green{color:#32e981!important}.red{color:#ff4c5d!important}
.bars{display:flex;align-items:flex-end;gap:3px;width:31px;height:30px}.bars b{width:7px;background:var(--accent);border-radius:2px}.bars b:nth-child(1){height:11px}.bars b:nth-child(2){height:20px}.bars b:nth-child(3){height:28px}
.clock{font-size:30px;color:#b9d8f7}.timecontent{flex:1}.timebar{height:6px;background:#16324a;border-radius:5px;margin-top:5px;overflow:hidden}.timebar b{display:block;height:100%;background:var(--accent);border-radius:5px}
.probs{margin-top:6px;padding:8px}.pbar{display:flex;gap:4px;margin-top:5px}.pup,.pdown{height:21px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:900;border-radius:4px}.pup{background:linear-gradient(90deg,#10d76d,#54ed91);color:#06331d}.pdown{background:linear-gradient(90deg,#ff3548,#ff6472);color:#3d0710}.pleg{display:flex;justify-content:space-between;font-size:10px;font-weight:900;margin-top:6px}
.reader{margin-top:6px;border:1.5px solid var(--rb);background:var(--rbg);border-radius:9px;padding:9px 10px}
.readerhead{display:flex;align-items:center;gap:7px;font-size:9px;color:var(--rr)}.readerhead .pulse{font-size:18px}.readerhead em{margin-left:auto;border:1px solid #24d873;border-radius:12px;padding:3px 8px;font-style:normal;font-size:8px;color:#45ec8e}
.readerbody{display:grid;grid-template-columns:1fr 65px;align-items:center;margin-top:7px}.readerbody strong{display:block;font-size:15px;line-height:1.12}.readerbody small{display:block;color:#aab8c9;font-size:7px;margin-top:5px}
.rring{width:62px;height:62px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--rr) calc(var(--p)*1%),#263342 0);position:relative}.rring:after{content:"";position:absolute;width:48px;height:48px;background:#08121b;border-radius:50%}.rring span{z-index:1;font-size:15px;font-weight:900}
.tech{margin-top:6px;padding:7px 8px}.techhead{display:flex;justify-content:space-between;font-size:9px;color:#c2d0df;padding-bottom:6px}.techrow{display:grid;grid-template-columns:repeat(5,1fr);border-top:1px solid #172737}.techrow>div{text-align:center;padding:7px 2px 2px;border-right:1px solid #172737}.techrow>div:last-child{border:0}.techrow small,.techrow i{display:block;font-size:6px;color:#8d9db0;font-style:normal}.techrow b{display:block;font-size:10px;margin:4px 0}
.rnav{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #203448;border-bottom:1px solid #203448;margin-top:7px;padding:7px 0}.rnav div{text-align:center;color:#9db0c5;font-size:8px}.rnav b{display:block;font-size:17px;margin-bottom:2px}.rnav .active{color:var(--accent)}
.features{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;padding:8px 1px}.features>div{display:flex;gap:5px;align-items:center}.features>div>b{width:25px;height:25px;border:1px solid #28e57f;border-radius:50%;display:grid;place-items:center;color:#35e986;font-size:13px}.features p{margin:0}.features strong{display:block;font-size:5.7px;color:#e1e8f0}.features span{display:block;font-size:5.4px;color:#8c9db0;margin-top:2px}
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
.finalanalysis{display:grid;grid-template-columns:1fr 80px;gap:5px;margin-top:4px}.analysisbox,.probbox{border:1px solid #1fae7a;border-radius:8px;background:#07151a;padding:7px}.analysisbox{display:flex;align-items:center;gap:7px}.analysisicon{font-size:23px;color:#2ee98a}.analysistext small{display:block;font-size:6.3px;color:#d4deea}.analysistext b{display:block;font-size:10px;color:var(--rr);margin-top:2px}.analysistext span{display:block;font-size:6.3px;color:#a3b2c3;margin-top:3px}.probbox{border-color:#ff3f86;text-align:center}.probbox small{display:block;font-size:6.5px;color:#e4ebf3}.probbox b{display:block;font-size:15px;color:var(--rr);margin-top:8px}
.chartbox{margin-top:10px;background:linear-gradient(180deg,#08121d,#060c14);border:1px solid #203a51;border-radius:12px;padding:10px 8px 8px;box-shadow:inset 0 0 28px rgba(20,80,110,.08)}
.charttop{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#eef6ff}.charttop b{font-size:13px}.chartlive{font-size:7px;color:#28e69a;margin-left:8px}.charttf{border:1px solid #26384b;border-radius:7px;padding:5px 8px;color:#dce8f5;font-size:9px}.ohlc{font-size:7px;color:#8ea0b5;margin-top:5px;white-space:nowrap}.indicators{font-size:7px;color:#aab8ca;margin:7px 0 1px;white-space:nowrap}.ema9dot{color:#df42e7}.ema21dot{color:#32d7ef}.targetdot{color:#23e7c1}.candlesvg{display:block;width:100%;height:265px}.chartfoot{display:flex;align-items:center;gap:10px;border-top:1px solid #18283a;padding:7px 2px 1px;color:#71839a;font-size:6px}.chartfoot .selected{border:1px solid #2a7189;border-radius:7px;padding:4px 8px;color:#e7f5ff;background:#0d2632}.chartempty{height:160px;display:grid;place-items:center;color:#708197;font-size:10px}
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
    }

# =========================================================
# PERSISTENCIA DE RONDA — SOBREVIVE SALIR/ENTRAR A LA APP
# Solo guarda el estado de la ronda; NO cambia el cerebro.
# =========================================================

ROUND_STATE_DB = "btc_signal_round_state.db"

def _round_db():
    conn = sqlite3.connect(ROUND_STATE_DB, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS round_state (ticker TEXT PRIMARY KEY,payload TEXT NOT NULL,updated_at TEXT NOT NULL)')
    return conn


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


# =========================================================
# HISTORIAL Y RENDIMIENTO — CAPA INDEPENDIENTE
# No modifica build_signal(), preseñal, lector, ballenas ni gráfico.
# =========================================================

HISTORY_DB = "btc_signal_history.db"

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
            t = ts.timestamp() if not pd.isna(ts) else now
            if notional > 0 and aggressor:
                tape.append({"id": trade_id, "t": t, "notional": notional, "side": aggressor})
                seen[trade_id] = t
        except Exception:
            continue

    tape[:] = [x for x in tape if now - x["t"] <= 75]
    for k in [k for k, t in seen.items() if now - t > 90]:
        seen.pop(k, None)

    def window(seconds):
        w = [x for x in tape if now - x["t"] <= seconds]
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
          <div style="display:flex;justify-content:space-between;align-items:center"><b style="font-size:10px;color:#e4edf7">🐋 FLUJO BALLENA · EN VIVO</b><span style="font-size:8px;color:#35e986">● COINBASE</span></div>
          <div style="margin-top:8px;font-size:13px;font-weight:900;color:#91a2b5">SIN FLUJO EXTREMO AHORA</div>
          <div style="margin-top:6px;font-size:9px;color:#8da0b4">Últimos 10 s · COMPRAS {buy} · VENTAS {sell}</div>
          <div style="margin-top:4px;font-size:8px;color:#6f8195">Confirma presión con ventanas de 10 s y 30 s; no alerta por una operación aislada.</div>
        </section>'''

    a = whale["alert"]
    up = a["direction"] == "UP"
    color = "#35e986" if up else "#ff5367"
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
    price = response.json().get("price")
    if price in [None, ""]:
        raise ValueError("Coinbase ticker no devolvió precio.")
    return float(price)

# =========================================================
# KALSHI BTC 15 MIN
# =========================================================

@st.cache_data(ttl=2)
def get_kalshi_btc_market():
    response = requests.get(
        "https://external-api.kalshi.com/trade-api/v2/markets",
        params={
            "limit": 100,
            "status": "open",
            "series_ticker": "KXBTC15M",
        },
        headers={"User-Agent": "MacalyAlphaBot/4.6.1"},
        timeout=10,
    )
    response.raise_for_status()
    markets = response.json().get("markets", [])
    if not markets:
        return None
    markets.sort(key=lambda m: str(m.get("close_time") or "9999"))
    return markets[0]

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
    candidates = []

    preferred_keys = {
        "price", "value", "index_value", "indexvalue",
        "current_price", "currentprice", "current_value", "currentvalue",
        "last_price", "lastprice", "close",
    }

    def walk_preferred(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                normalized_key = str(key).lower().replace("-", "_")
                if normalized_key in preferred_keys:
                    try:
                        number = float(value)
                        if 10000 < number < 1000000:
                            candidates.append(number)
                    except (TypeError, ValueError):
                        pass
                walk_preferred(value)
        elif isinstance(obj, list):
            for item in obj:
                walk_preferred(item)

    walk_preferred(details)
    if candidates:
        return float(candidates[-1])

    pair_candidates = []

    def walk_pairs(obj):
        if isinstance(obj, list):
            if len(obj) >= 2:
                try:
                    possible_price = float(obj[-1])
                    if 10000 < possible_price < 1000000:
                        pair_candidates.append(possible_price)
                except (TypeError, ValueError):
                    pass
            for item in obj:
                walk_pairs(item)
        elif isinstance(obj, dict):
            for value in obj.values():
                walk_pairs(value)

    walk_pairs(details)
    return float(pair_candidates[-1]) if pair_candidates else None

def get_kalshi_live_btc(market):
    event_ticker = get_event_ticker_from_market(market)
    if not event_ticker:
        raise ValueError("La ronda no entregó event_ticker.")

    response = requests.get(
        "https://external-api.kalshi.com/trade-api/v2/live_data/events/"
        f"{event_ticker}",
        params={
            "range": "15min",
            "_": int(datetime.now(timezone.utc).timestamp()),
        },
        headers={
            "User-Agent": "MacalyAlphaBot/4.6.1",
            "Cache-Control": "no-cache",
        },
        timeout=6,
    )
    response.raise_for_status()
    price = extract_kalshi_btc_price(response.json())
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

def build_signal(df, target, seconds_left, live_price=None):
    _TRACE_CONTEXT.build_id = None
    _TRACE_CONTEXT.build_payload = None
    sig = _signal_engine_without_trace(df, target, seconds_left, live_price)
    try:
        candles = [[row.time.isoformat(), float(row.open), float(row.high), float(row.low), float(row.close), float(row.volume)] for row in df.itertuples()]
        payload = {"candles":candles, "candle_metadata":dict(df.attrs), "target":target, "seconds_left":seconds_left, "live_price":live_price, "signal":sig}
        _TRACE_CONTEXT.build_payload = payload
        _TRACE_CONTEXT.build_id = _trace_event("build", payload)
    except Exception:
        pass
    return sig


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
        return "BUENA", "#34d399"
    if price <= 0.70:
        return "PRECAUCIÓN", "#fbbf24"
    return "CARA", "#fb7185"


# =========================================================
# CONTROL DE RONDA — EL CEREBRO MANDA
# =========================================================

def confirm_round_candidate(state, candidate, market, seconds_left, now):
    before = dict(state)
    result = _confirmation_without_trace(state, candidate, market, seconds_left, now)
    try:
        payload = {"candidate":candidate, "seconds_left":seconds_left, "now":now, "before":before, "after":dict(state), "quotes":{"yes":get_yes_ask(market), "no":get_no_ask(market)}}
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



def process_round_signal(ticker, sig, market, seconds_left):
    if not ticker or ticker == '--':
        return _process_round_signal_without_coordinator(ticker,sig,market,seconds_left)
    def apply():
        latest = load_round_state(ticker)
        if latest is not None:
            st.session_state.rounds[ticker] = latest
        return _process_round_signal_without_coordinator(ticker,sig,market,seconds_left)
    return _run_round_transaction(apply)


# =========================================================
# REGISTRADOR AUTÓNOMO 12 HORAS — SOLO HISTORIAL
# Sigue leyendo las rondas aunque no haya una sesión de Streamlit abierta,
# siempre que el proceso del servidor siga encendido.
# NO modifica el motor, la preseñal, el lector, ballenas ni la interfaz.
# =========================================================

BACKGROUND_RUN_SECONDS = 12 * 60 * 60
BACKGROUND_POLL_SECONDS = 2

def _background_get_btc_data():
    return _fetch_current_btc_candles()

def _background_get_market():
    response = requests.get(
        "https://external-api.kalshi.com/trade-api/v2/markets",
        params={"limit": 100, "status": "open", "series_ticker": "KXBTC15M"},
        headers={"User-Agent": "MacalyAlphaBot/4.6.1"},
        timeout=10,
    )
    response.raise_for_status()
    markets = response.json().get("markets", [])
    if not markets:
        return None
    markets.sort(key=lambda m: str(m.get("close_time") or "9999"))
    return markets[0]

def _background_get_live_price(market, with_source=False):
    try:
        event_ticker = get_event_ticker_from_market(market)
        if event_ticker:
            response = requests.get(
                "https://external-api.kalshi.com/trade-api/v2/live_data/events/" + str(event_ticker),
                params={"range": "15min", "_": int(datetime.now(timezone.utc).timestamp())},
                headers={"User-Agent": "MacalyAlphaBot/4.6.1", "Cache-Control": "no-cache"},
                timeout=6,
            )
            response.raise_for_status()
            price = extract_kalshi_btc_price(response.json())
            if price is not None:
                return (float(price), "KALSHI") if with_source else float(price)
    except Exception:
        pass
    response = requests.get(
        "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
        headers={"User-Agent": "MacalyAlphaBot/4.6.1", "Cache-Control": "no-cache"},
        params={"_": int(datetime.now(timezone.utc).timestamp())},
        timeout=6,
    )
    response.raise_for_status()
    price = response.json().get("price")
    if price in (None, ""):
        raise ValueError("Sin precio BTC live.")
    return (float(price), "COINBASE") if with_source else float(price)

def _background_update_state(state, sig, market, seconds_left):
    def apply():
        latest = load_round_state(state['ticker'])
        current = latest if latest is not None else state
        current.pop('_restored_from_disk',None)
        return _background_update_state_without_coordinator(current,sig,market,seconds_left)
    return _run_round_transaction(apply)


def _background_history_loop():
    started = time.monotonic()
    active_ticker = None
    active_state = None
    while time.monotonic() - started < BACKGROUND_RUN_SECONDS:
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
            sig = build_signal(btc_df, target, seconds_left, live_price)
            active_state = _background_update_state(active_state, sig, market, seconds_left)
            if seconds_left is not None and seconds_left <= 0:
                save_round_history(active_state)
        except Exception:
            pass
        time.sleep(BACKGROUND_POLL_SECONDS)

@st.cache_resource
def start_12h_history_worker():
    worker = threading.Thread(target=_background_history_loop, name="btc-history-12h", daemon=True)
    worker.start()
    return worker

# =========================================================
# LECTOR DE CIERRE PRO — MICRO LECTURA ~2 SEGUNDOS
# Mantiene intacto el motor v4.6.1 y sus señales.
# No inventa velas REST de 1 segundo: construye una cinta
# de muestras del BTC live que ya recibe el dashboard.
# =========================================================

def update_micro_tape(ticker, live_price):
    if not ticker or ticker == "--" or live_price is None:
        return

    # Cada ronda empieza con su propia cinta.
    if st.session_state.micro_ticker != ticker:
        st.session_state.micro_ticker = ticker
        st.session_state.micro_prices = []

    now_ts = datetime.now(timezone.utc).timestamp()
    tape = st.session_state.micro_prices

    # Evita duplicar muestras dentro del mismo refresco.
    if not tape or now_ts - tape[-1]["t"] >= 1.0:
        tape.append({"t": now_ts, "p": float(live_price)})

    # Conserva aproximadamente los últimos 90 segundos.
    cutoff = now_ts - 90
    st.session_state.micro_prices = [
        x for x in tape if x["t"] >= cutoff
    ]

def micro_reading():
    tape = st.session_state.micro_prices

    if len(tape) < 4:
        return {
            "ready": False,
            "change_5s": 0.0,
            "change_10s": 0.0,
            "change_30s": 0.0,
            "slope": 0.0,
            "up_ratio": 0.5,
            "pressure": "NEUTRAL",
        }

    now_t = tape[-1]["t"]
    current = tape[-1]["p"]

    def price_ago(seconds):
        target_t = now_t - seconds
        candidates = [x for x in tape if x["t"] <= target_t]
        if candidates:
            return candidates[-1]["p"]
        return tape[0]["p"]

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

    c5 = current - p5
    c10 = current - p10
    c30 = current - p30

    if slope > 0.35 and up_ratio >= 0.58:
        pressure = "ALCISTA"
    elif slope < -0.35 and up_ratio <= 0.42:
        pressure = "BAJISTA"
    else:
        pressure = "NEUTRAL"

    return {
        "ready": True,
        "change_5s": c5,
        "change_10s": c10,
        "change_30s": c30,
        "slope": slope,
        "up_ratio": up_ratio,
        "pressure": pressure,
    }

def closing_reader(sig, round_signal, seconds_left, micro):
    """Lector de cierre adaptativo y conectado al reloj.

    No toca la señal oficial. Estima qué lado tiene ventaja usando la distancia
    REAL al target comparada con el movimiento que BTC todavía podría recorrer
    en el tiempo restante. Esa capacidad de movimiento se recalcula con ATR,
    momentum y la cinta live; no depende de una tabla fija de "$X con Ys".
    """
    state = round_signal.get("round_state")
    active_direction = state.get("active_direction") if state else None
    distance = sig.get("distance")
    secs = 900 if seconds_left is None else max(0, int(seconds_left))

    if seconds_left is not None and seconds_left <= 0:
        if distance is None or abs(distance) < 1:
            headline, color = "RONDA FINALIZADA", "#94a3b8"
        elif distance > 0:
            headline, color = "RONDA FINALIZADA • UP", "#34e982"
        else:
            headline, color = "RONDA FINALIZADA • DOWN", "#ff4e5f"
        return {
            "percent":100, "headline":headline,
            "note":"La ronda terminó. Ya no se muestra una predicción de cierre.",
            "micro":"RONDA CERRADA","color":color,
            "border":"rgba(148,163,184,.45)",
            "bg":"linear-gradient(135deg,rgba(30,41,59,.45),rgba(9,23,34,.72))",
            "direction":"UP" if (distance or 0) > 0 else "DOWN" if (distance or 0) < 0 else None,
        }

    if distance is None:
        return {
            "percent":50, "headline":"ESPERANDO TARGET",
            "note":"Falta la referencia del target para estimar el cierre.",
            "micro":"MICROLECTURA PREPARÁNDOSE","color":"#38bdf8",
            "border":"rgba(56,189,248,.45)",
            "bg":"linear-gradient(135deg,rgba(11,64,91,.30),rgba(9,23,34,.72))",
            "direction":None,
        }

    market_side = "UP" if distance > 0 else "DOWN" if distance < 0 else None
    direction = market_side or active_direction
    if direction not in ("UP", "DOWN"):
        direction = "UP" if float(sig.get("mom3", 0) or 0) >= 0 else "DOWN"

    # Movimiento restante esperado: ATR de 1 minuto escalado por sqrt(tiempo).
    # Se adapta solo a la volatilidad actual de BTC y se afina con la cinta live.
    atr1 = max(float(sig.get("atr", 0) or 0), 1.0)
    remaining_sigma = atr1 * np.sqrt(max(secs, 1) / 60.0)

    micro_text = "MICROLECTURA REUNIENDO DATOS"
    micro_drift = 0.0
    micro_noise = None
    if micro.get("ready"):
        c5 = float(micro.get("change_5s", 0) or 0)
        c10 = float(micro.get("change_10s", 0) or 0)
        c30 = float(micro.get("change_30s", 0) or 0)
        slope = float(micro.get("slope", 0) or 0)
        ratio = float(micro.get("up_ratio", .5) or .5)

        # Drift reciente amortiguado: cuanto menos tiempo queda, más relevante.
        observed_drift = (0.45*c5/5.0 + 0.35*c10/10.0 + 0.20*c30/30.0)
        time_focus = 1.0 - min(1.0, secs / 180.0)
        micro_drift = observed_drift * secs * (0.20 + 0.80*time_focus)

        # Ruido observado por segundo, convertido al horizonte restante.
        local_scale = max(abs(c5)/np.sqrt(5), abs(c10)/np.sqrt(10), abs(c30)/np.sqrt(30), abs(slope)*1.5, 1.0)
        micro_noise = local_scale * np.sqrt(max(secs, 1))
        # Cerca del cierre la cinta manda más; lejos, ATR manda más.
        blend = 1.0 - min(1.0, secs / 180.0)
        remaining_sigma = (1.0-blend)*remaining_sigma + blend*micro_noise

        micro_text = f"MICRO {micro.get('pressure','NEUTRAL')} • 10s {c10:+.1f} • 30s {c30:+.1f}"

    # Distancia proyectada al cierre. Positiva = UP, negativa = DOWN.
    projected_distance = float(distance) + micro_drift

    # Convierte colchón/volatilidad restante a probabilidad sin umbrales de dólares.
    # logistic evita reglas rígidas y permite que una ronda prácticamente definida
    # llegue naturalmente a 100% al redondear.
    risk_scale = max(remaining_sigma * 0.72, 0.75)
    z = projected_distance / risk_scale
    up_close_prob = 100.0 / (1.0 + np.exp(-np.clip(z, -12, 12)))
    side_prob = up_close_prob if direction == "UP" else 100.0 - up_close_prob

    # Si la dirección estimada por la proyección cruzó el target, el lector gira.
    projected_side = "UP" if projected_distance > 0 else "DOWN" if projected_distance < 0 else market_side
    if projected_side in ("UP", "DOWN") and projected_side != direction:
        direction = projected_side
        side_prob = up_close_prob if direction == "UP" else 100.0 - up_close_prob

    # Antes de los últimos 3 minutos conserva algo del contexto técnico;
    # al acercarse el cierre, tiempo+target dominan progresivamente.
    if secs > 180 and active_direction in ("UP", "DOWN"):
        tech_prob = float(sig.get("up_probability", 50) if direction == "UP" else sig.get("down_probability", 50))
        clock_weight = max(0.15, min(0.55, (900-secs)/720.0))
        side_prob = tech_prob*(1-clock_weight) + side_prob*clock_weight

    confidence = int(round(np.clip(side_prob, 0, 100)))

    # Texto coherente con reloj + colchón dinámico, no con una distancia fija.
    cushion = abs(projected_distance) / max(remaining_sigma, 1.0)
    if confidence >= 99:
        confidence = 100
        headline = f"CIERRE PRÁCTICAMENTE DEFINIDO • {direction}"
        note = (f"Quedan {secs}s · BTC está ${abs(distance):,.0f} "
                f"{'arriba' if distance > 0 else 'abajo'} del target. "
                "La distancia domina ampliamente el movimiento restante estimado.")
    elif secs <= 60 and cushion >= 1.35:
        headline = f"CIERRE MUY FAVORECIDO PARA {direction}"
        note = (f"Quedan {secs}s · BTC está ${abs(distance):,.0f} "
                f"{'arriba' if distance > 0 else 'abajo'} del target; "
                "el colchón supera el movimiento restante estimado.")
    elif secs <= 60:
        headline = f"VENTAJA FINAL {direction}"
        note = (f"Quedan {secs}s · BTC está ${abs(distance):,.0f} "
                f"{'arriba' if distance > 0 else 'abajo'} del target. "
                "La cinta de segundos pesa cada vez más en la estimación.")
    elif market_side in ("UP", "DOWN"):
        headline = f"AÚN FAVORABLE A {direction}"
        note = "La ventaja se recalcula con distancia, volatilidad y tiempo real restante."
    else:
        headline = f"CIERRE {direction} SIN VENTAJA CLARA"
        note = "La lectura todavía no tiene colchón suficiente frente al movimiento esperado."

    if direction == "UP":
        color = "#34e982"; border = "rgba(52,233,130,.48)"
        bg = "linear-gradient(135deg,rgba(4,86,43,.46),rgba(7,36,25,.78))"
    else:
        color = "#ff4e5f"; border = "rgba(255,78,95,.48)"
        bg = "linear-gradient(135deg,rgba(102,20,31,.48),rgba(43,10,17,.80))"

    return {"percent":confidence,"headline":headline,"note":note,"micro":micro_text,
            "color":color,"border":border,"bg":bg,"direction":direction}

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

    d = d.tail(42).reset_index(drop=True)
    # La última vela se mantiene visualmente al precio live recibido por el dashboard.
    if live_price is not None and len(d):
        i = d.index[-1]
        d.loc[i, "close"] = float(live_price)
        d.loc[i, "high"] = max(float(d.loc[i, "high"]), float(live_price))
        d.loc[i, "low"] = min(float(d.loc[i, "low"]), float(live_price))

    close = d["close"].astype(float)
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()

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
        col='#19e6a2' if c>=o else '#ff4e6a'
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
        ly=y(live_price); lc='#31e889' if active=='UP' else '#ff5367' if active=='DOWN' else '#38bdf8'
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
    direction_color='#31e889' if change>=0 else '#ff5367'
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

# =========================================================
# AUTO TRADING — PANEL SEPARADO (NO MODIFICA build_signal)
# Configuración, conexión, simulación y ejecución REAL mediante el worker.
# Las credenciales viven en memoria del servidor; nunca se escriben en SQLite.
# =========================================================

KALSHI_API_BASE = "https://external-api.kalshi.com"
AUTO_DB = "btc_auto_trading.db"

def _auto_db():
    con = sqlite3.connect(AUTO_DB, check_same_thread=False)
    con.execute("""
        CREATE TABLE IF NOT EXISTS auto_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            ticker TEXT,
            mode TEXT,
            side TEXT,
            level INTEGER,
            entry_cents REAL,
            contracts INTEGER,
            amount REAL,
            take_profit_pct REAL,
            take_profit_cents REAL,
            stop_loss_pct REAL,
            status TEXT,
            pnl REAL DEFAULT 0,
            note TEXT
        )
    """)
    con.commit()
    return con

def load_auto_orders(limit=100):
    con = _auto_db()
    try:
        return pd.read_sql_query(
            "SELECT * FROM auto_orders ORDER BY id DESC LIMIT ?", con,
            params=(int(limit),)
        )
    finally:
        con.close()

def _normalize_private_key(pem_text):
    return (pem_text or "").strip().replace("\\n", "\n")

def _kalshi_private_key(pem_text):
    return serialization.load_pem_private_key(
        _normalize_private_key(pem_text).encode("utf-8"), password=None
    )

def _kalshi_signature(private_key, message):
    raw = message.encode("utf-8")
    if isinstance(private_key, Ed25519PrivateKey):
        sig = private_key.sign(raw)
    else:
        sig = private_key.sign(
            raw,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
    return base64.b64encode(sig).decode("utf-8")

def kalshi_auth_headers(method, path, key_id, private_key_text):
    timestamp = str(int(time.time() * 1000))
    clean_path = path.split("?")[0]
    private_key = _kalshi_private_key(private_key_text)
    signature = _kalshi_signature(private_key, timestamp + method.upper() + clean_path)
    return {
        "KALSHI-ACCESS-KEY": key_id.strip(),
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "Content-Type": "application/json",
    }

def kalshi_get_balance(key_id, private_key_text):
    path = "/trade-api/v2/portfolio/balance"
    headers = kalshi_auth_headers("GET", path, key_id, private_key_text)
    r = requests.get(KALSHI_API_BASE + path, headers=headers, timeout=12)
    if r.status_code != 200:
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:300]
        raise RuntimeError(f"Kalshi {r.status_code}: {detail}")
    data = r.json()
    # Prefer fixed-point dollars; legacy integer balance is cents.
    if data.get("balance_dollars") is not None:
        balance = float(data["balance_dollars"])
    else:
        balance = float(data.get("balance", 0)) / 100.0
    return balance, data

def martingale_plan(capital, levels, multiplier):
    capital = max(0.0, float(capital))
    levels = max(1, min(12, int(levels)))
    multiplier = max(1.0, float(multiplier))
    if multiplier == 1.0:
        weights = [1.0] * levels
    else:
        weights = [multiplier ** i for i in range(levels)]
    total_w = sum(weights) or 1.0
    raw = [capital * w / total_w for w in weights]
    # cents-safe display; last level absorbs rounding without exceeding capital.
    amounts = [math.floor(x * 100) / 100 for x in raw]
    if amounts:
        remainder = round(capital - sum(amounts), 2)
        amounts[-1] = round(amounts[-1] + max(0, remainder), 2)
    return amounts

def profit_target_cents(entry_cents, profit_pct):
    if entry_cents is None:
        return None
    pct = max(0.0, min(100.0, float(profit_pct)))
    return min(100.0, float(entry_cents) * (1.0 + pct / 100.0))

def _auto_default_config():
    return {
        "enabled": False, "mode": "SIMULACIÓN", "capital": 20.0,
        "min_price": 20, "max_price": 70, "min_conf": 65,
        "profit_on": True, "profit_pct": 85,
        "stop_on": False, "stop_pct": 20,
        "martingale_on": False, "levels": 4, "multiplier": 2.0,
        "one_per_round": True, "max_trades_day": 12, "reserve": 0.0,
        "level_directions": ["Seguir señal"] * 12,
        "entry_source": "SEÑAL PRINCIPAL",
    }

def _ensure_auto_config_table():
    con = _auto_db()
    con.execute("""CREATE TABLE IF NOT EXISTS auto_config (
        id INTEGER PRIMARY KEY CHECK (id=1), config_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    con.commit(); con.close()

def load_auto_config():
    _ensure_auto_config_table()
    cfg = _auto_default_config()
    con = _auto_db()
    row = con.execute("SELECT config_json FROM auto_config WHERE id=1").fetchone()
    con.close()
    if row:
        try:
            saved = json.loads(row[0]); cfg.update(saved)
        except Exception:
            pass
    cfg["entry_source"] = "SEÑAL PRINCIPAL"
    dirs = cfg.get("level_directions") or []
    cfg["level_directions"] = (dirs + ["Seguir señal"] * 12)[:12]
    return cfg

def save_auto_config(cfg):
    _ensure_auto_config_table()
    con = _auto_db()
    con.execute("""INSERT INTO auto_config(id, config_json, updated_at)
        VALUES(1, ?, ?) ON CONFLICT(id) DO UPDATE SET
        config_json=excluded.config_json, updated_at=excluded.updated_at""",
        (json.dumps(cfg), datetime.now(timezone.utc).isoformat()))
    con.commit(); con.close()

# =========================================================
# EJECUCIÓN AUTÓNOMA: PRESEÑAL DIRECTA + ÓRDENES KALSHI V2
# Uso individual: proteger el acceso al despliegue y sus ajustes.
# Credenciales solo en memoria; al reiniciar se necesita reconectar
# o configurar KALSHI_KEY_ID / KALSHI_PRIVATE_KEY en st.secrets.
# =========================================================

def execution_choice(sig, cfg, secs):
    # La decisión automática pertenece únicamente al motor principal.
    side = sig.get("candidate")
    return side, sig.get("up_probability" if side == "UP" else "down_probability", 50)

def refine_main_signal(sig):
    """Compatibilidad: no modifica el cerebro original v4.6.1."""
    return sig

def v2_order_payload(ticker, direction, action, quantity, price, client_id):
    # V2 cotiza siempre el lado YES. Compra NO = ask YES.
    yes_price = price if direction == "UP" else 1.0 - price
    bid = (direction == "UP") == (action == "buy")
    if not (0 < yes_price < 1) or quantity <= 0:
        raise ValueError("Precio o cantidad inválidos")
    return {"ticker": ticker, "client_order_id": client_id,
            "side": "bid" if bid else "ask", "count": f"{quantity:.2f}",
            "price": f"{yes_price:.4f}",
            "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
            "reduce_only": action == "sell", "cancel_order_on_pause": True}

class RecentEntryConfirmation:
    """Filtro de entrada, no estimador de probabilidad ni señal de salida.

    Exige cinta continua de 30s, movimiento coincidente en 5/10/30s y
    coincidencia sostenida 10s. Umbrales iniciales sin calibración histórica.
    """
    def __init__(self):
        self.key = None
        self.samples = []
        self.candidate = None
        self.since = None

    def reset_candidate(self):
        self.candidate = None
        self.since = None

    def observe(self, ticker, source, price, now):
        key = (ticker, source)
        if not math.isfinite(price) or price <= 0:
            self.samples = []
            self.reset_candidate()
            return
        if key != self.key or (self.samples and
                (now <= self.samples[-1][0] or now - self.samples[-1][0] > 12)):
            self.key = key
            self.samples = []
            self.reset_candidate()
        self.samples.append((now, price))
        self.samples = [(t, p) for t, p in self.samples if now - t <= 50]

    def check(self, side, atr, now):
        if side not in ("UP", "DOWN"):
            self.reset_candidate()
            return False, "Preseñal sin dirección suficiente"
        if not self.samples or now - self.samples[-1][0] > 6:
            self.reset_candidate()
            return False, "Esperando precios recientes"
        deltas = []
        for seconds in (5, 10, 30):
            ref = next(((t, p) for t, p in reversed(self.samples)
                        if t <= now - seconds), None)
            if ref is None or now - seconds - ref[0] > 6:
                self.reset_candidate()
                return False, "Reuniendo 30 s de precios para confirmar entrada temprana"
            deltas.append(self.samples[-1][1] - ref[1])
        # Descarta movimiento plano; no exige estar ya del lado del target.
        atr = float(atr)
        if not math.isfinite(atr) or atr <= 0:
            self.reset_candidate()
            return False, "Volatilidad inválida; esperando datos"
        minimum = max(0.50, atr * 0.01)
        sign = 1 if side == "UP" else -1
        detail = "/".join(f"{d:+.2f}" for d in deltas)
        if any(sign * d < minimum for d in deltas):
            self.reset_candidate()
            return False, f"Esperando impulso {side}: 5/10/30 s {detail} USD"
        if self.candidate != side:
            self.candidate, self.since = side, now
        elapsed = now - self.since
        if elapsed < 10:
            return False, f"Confirmando impulso {side}: {elapsed:.0f}/10 s"
        return True, f"Impulso {side} confirmado · 5/10/30 s {detail} USD"

    def movement(self, atr, now):
        # Lectura pura: no avanza ni autoriza el temporizador de compras.
        if not self.samples or now - self.samples[-1][0] > 6:
            return {"ready":False, "reason":"Esperando precios recientes"}
        deltas = []
        for seconds in (5, 10, 30):
            ref = next(((t, p) for t, p in reversed(self.samples)
                        if t <= now - seconds), None)
            if ref is None or now - seconds - ref[0] > 6:
                return {"ready":False, "reason":"Reuniendo 30 s de precios de esta ronda"}
            deltas.append(self.samples[-1][1] - ref[1])
        if not math.isfinite(float(atr)) or float(atr) <= 0:
            return {"ready":False, "reason":"Esperando volatilidad válida"}
        return {"ready":True, "deltas":deltas, "minimum":max(0.50, float(atr)*0.01)}

class ExecutionWorker:
    def __init__(self):
        self.lock = threading.RLock()
        self.key_id = ""; self.pem = ""
        self.message = "Conecta Kalshi para operar en REAL"
        self.status_by_mode = {}
        self.heartbeat = None
        self.balance = None
        self.entry_gates = {}
        self.thread = threading.Thread(target=self.run, name="alpha-execution", daemon=True)
        self.thread.start()

    def connect(self, key_id, pem):
        with self.lock:
            if self.key_id and self.key_id != key_id:
                raise ValueError("Desconecta la cuenta actual antes de cambiarla")
            self.key_id, self.pem = key_id, pem
            self.status_by_mode["REAL"] = {"message": "Kalshi conectado; preparando próximo ciclo",
                                          "heartbeat": None}

    def disconnect(self):
        with self.lock:
            self.key_id = ""; self.pem = ""
            self.message = "Desconectado: compras y ventas automáticas detenidas"
            self.status_by_mode["REAL"] = {"message": self.message, "heartbeat": None}

    def scope(self, mode):
        account = hashlib.sha256(self.key_id.encode()).hexdigest()[:20] if mode == "REAL" else "paper"
        return mode + ":" + account

    def database(self):
        c = sqlite3.connect(AUTO_DB, timeout=15)
        c.execute("CREATE TABLE IF NOT EXISTS execution_ledger(scope TEXT PRIMARY KEY,payload TEXT NOT NULL)")
        return c

    def read_ledger(self, scope):
        c = self.database()
        try:
            row = c.execute("SELECT payload FROM execution_ledger WHERE scope=?", (scope,)).fetchone()
            return json.loads(row[0]) if row else {"positions": [], "pending": None}
        finally:
            c.close()

    def write_ledger(self, scope, ledger):
        c = self.database()
        try:
            c.execute("INSERT INTO execution_ledger VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET payload=excluded.payload",
                      (scope, json.dumps(ledger)))
            c.commit()
        finally:
            c.close()

    def loss_streak(self, ledger):
        start = max(0, int(ledger.get("cycle_start", 0)))
        losses = 0
        for p in reversed(ledger["positions"][start:]):
            if p["pnl"] is not None and p["pnl"] < 0:
                losses += 1
            else:
                break
        return losses

    def reset_cycle(self, mode):
        with self.lock:
            if mode == "REAL" and not (self.key_id and self.pem):
                raise ValueError("Conecta la misma cuenta Kalshi antes de reiniciar su ciclo.")
            scope = self.scope(mode)
            ledger = self.read_ledger(scope)
            if ledger.get("pending"):
                raise ValueError("Hay una orden pendiente de reconciliar; el ciclo todavía no se puede reiniciar.")
            if any(p["remaining"] > .0001 for p in ledger["positions"]):
                raise ValueError("Hay una posición abierta; espera su cierre antes de reiniciar el ciclo.")
            ledger["cycle_start"] = len(ledger["positions"])
            ledger.setdefault("cycle_resets", []).append(datetime.now(timezone.utc).isoformat())
            self.write_ledger(scope, ledger)
            self.status_by_mode[mode] = {
                "message": "Ciclo reiniciado al nivel 1; conserva pérdidas y límites",
                "heartbeat": datetime.now(timezone.utc).isoformat(),
            }

    def api(self, method, path, payload=None, params=None):
        headers = kalshi_auth_headers(method, path, self.key_id, self.pem)
        r = requests.request(method, KALSHI_API_BASE + path, headers=headers,
                             json=payload, params=params, timeout=10)
        try:
            r.raise_for_status()
        except requests.HTTPError as error:
            # Preserve HTTPError/response so submit() still handles rejected
            # versus ambiguous orders without duplicating an unknown POST.
            try:
                detail = r.json()
                if isinstance(detail, dict):
                    detail = detail.get("error", detail)
                if isinstance(detail, dict):
                    detail = " · ".join(str(detail.get(k, "")) for k in
                                        ("code", "message", "details") if detail.get(k))
            except ValueError:
                detail = "Respuesta de error sin JSON"
            raise requests.HTTPError(
                f"Kalshi {r.status_code}: {str(detail)[:180]}",
                response=r, request=getattr(error, "request", None),
            ) from error
        return r.json()

    def market(self, ticker):
        r = requests.get(KALSHI_API_BASE + "/trade-api/v2/markets/" + ticker, timeout=8)
        r.raise_for_status()
        return r.json()["market"]

    def position(self, ticker):
        data = self.api("GET", "/trade-api/v2/portfolio/positions", params={"ticker": ticker})
        return sum(float(p.get("position_fp", p.get("position", 0))) for p in data.get("market_positions", [])
                   if p.get("ticker") == ticker)

    def reconcile(self, intent):
        # Nunca repetir un POST cuyo resultado sea desconocido.
        cursor = ""
        for _ in range(20):
            data = self.api("GET", "/trade-api/v2/portfolio/orders",
                            params={"ticker": intent["ticker"], "limit": 200, "cursor": cursor})
            for order in data.get("orders", []):
                if order.get("client_order_id") == intent["client_id"]:
                    if order.get("status") not in ("executed", "canceled"):
                        return None
                    oid = order["order_id"]
                    fills = []; fc = ""
                    for _ in range(20):
                        d = self.api("GET", "/trade-api/v2/portfolio/fills",
                                     params={"order_id": oid, "limit": 200, "cursor": fc})
                        fills += d.get("fills", [])
                        fc = d.get("cursor", "")
                        if not fc: break
                    else:
                        raise ValueError("Fills incompletos; esperando reconciliación")
                    qty = sum(float(f.get("count_fp", f.get("count", 0))) for f in fills)
                    expected = float(order.get("fill_count_fp", order.get("fill_count", 0)))
                    if abs(qty - expected) > .0001: return None
                    value = sum(float(f.get("count_fp", f.get("count", 0))) *
                                float(f["yes_price_dollars"] if intent["direction"] == "UP" else f["no_price_dollars"])
                                for f in fills)
                    fees = sum(float(f.get("fee_cost", 0)) for f in fills)
                    return {"quantity": qty, "value": value, "fees": fees, "order_id": oid}
            cursor = data.get("cursor", "")
            if not cursor: break
        return None

    def apply_result(self, ledger, result):
        it = ledger["pending"]; qty = result["quantity"]
        if qty > it["quantity"] + .0001:
            raise ValueError("Cantidad ejecutada inesperada")
        if qty > 0 and it["action"] == "buy":
            ledger["positions"].append({
                "id": it["client_id"], "created_at": it["created_at"], "ticker": it["ticker"],
                "mode": it["mode"], "side": it["direction"], "level": it["level"],
                "contracts": qty, "remaining": qty,
                "entry_cents": result["value"] / qty * 100,
                "amount": result["value"] + result["fees"], "proceeds": 0.0,
                "take_profit_pct": it["cfg"]["profit_pct"],
                "take_profit_cents": profit_target_cents(result["value"]/qty*100, it["cfg"]["profit_pct"]),
                "stop_loss_pct": it["cfg"]["stop_pct"], "cfg": it["cfg"],
                "status": "ABIERTA", "pnl": None, "order_id": result["order_id"],
                "note": it.get("note", "")
            })
        elif qty > 0:
            p = next(p for p in ledger["positions"] if p["id"] == it["position_id"])
            p["remaining"] = max(0, p["remaining"] - qty)
            p["proceeds"] += result["value"] - result["fees"]
            if p["remaining"] < .0001:
                p["status"] = it["reason"]; p["closed_at"] = datetime.now(timezone.utc).isoformat()
                p["pnl"] = round(p["proceeds"] - p["amount"], 6)
        ledger["pending"] = None
        self.message = (f'{it["action"].upper()} {it["direction"]}: {qty:g} contratos ejecutados'
                        if qty else "Orden sin ejecución: liquidez insuficiente; reevalúa en próximo ciclo")

    def submit(self, scope, ledger, intent):
        ledger["pending"] = intent
        self.write_ledger(scope, ledger)  # durable antes de contactar el exchange
        if intent["mode"] == "SIMULACIÓN":
            result = {"quantity": intent["quantity"], "value": intent["quantity"] * intent["price"],
                      "fees": 0, "order_id": "SIM-" + intent["client_id"]}
        else:
            body = v2_order_payload(intent["ticker"], intent["direction"], intent["action"],
                                    intent["quantity"], intent["price"], intent["client_id"])
            try:
                d = self.api("POST", "/trade-api/v2/portfolio/events/orders", body)
            except requests.HTTPError as e:
                # 409/5xx son ambiguos: conservar el intento para reconciliar.
                if e.response is not None and e.response.status_code in (400, 401, 403, 404, 422, 429):
                    ledger["pending"] = None; self.write_ledger(scope, ledger)
                raise
            qty = float(d["fill_count"])
            if qty > 0 and ("average_fill_price" not in d or "average_fee_paid" not in d):
                result = self.reconcile(intent)
                if result is None: return
            else:
                yes_price = float(d.get("average_fill_price", 0))
                cost = yes_price if intent["direction"] == "UP" else 1 - yes_price
                result = {"quantity": qty, "value": qty * cost,
                          "fees": qty * float(d.get("average_fee_paid", 0)), "order_id": d["order_id"]}
        self.apply_result(ledger, result)
        self.write_ledger(scope, ledger)

    def manage(self, scope, ledger, mode):
        for p in ledger["positions"]:
            if p["remaining"] <= .0001: continue
            m = self.market(p["ticker"])
            # Kalshi reports completed settlements as 'finalized'. Accept the
            # older 'settled' spelling too, but never infer a result from time,
            # a zero quote, or a merely closed/determined market.
            market_status = str(m.get("status") or "").lower()
            result = str(m.get("result") or "").lower()
            if market_status in ("finalized", "settled") and result in ("yes", "no"):
                winner = "UP" if result == "yes" else "DOWN"
                p["proceeds"] += p["remaining"] if p["side"] == winner else 0
                p["remaining"] = 0; p["status"] = "LIQUIDADA"
                p["closed_at"] = datetime.now(timezone.utc).isoformat()
                p["pnl"] = round(p["proceeds"] - p["amount"], 6)
                p["settlement_result"] = result
                p["settlement_ts"] = m.get("settlement_ts")
                p["settlement_market_status"] = market_status
                self.write_ledger(scope, ledger)
                continue
            if market_status != "active":
                p["status"] = "ESPERANDO LIQUIDACIÓN"
                p["market_status"] = market_status
                self.write_ledger(scope, ledger)
                continue
            p["status"] = "ABIERTA"
            bid = numeric_kalshi_price(m.get("yes_bid_dollars" if p["side"] == "UP" else "no_bid_dollars"),
                                      m.get("yes_bid" if p["side"] == "UP" else "no_bid"))
            if bid is None or bid <= 0: continue
            change = (bid * 100 / p["entry_cents"] - 1) * 100
            cfg = p["cfg"]
            reason = "TAKE PROFIT" if cfg["profit_on"] and change >= cfg["profit_pct"] else (
                     "STOP LOSS" if cfg["stop_on"] and change <= -cfg["stop_pct"] else None)
            if reason:
                if mode == "REAL":
                    actual = self.position(p["ticker"])
                    expected = p["remaining"] if p["side"] == "UP" else -p["remaining"]
                    if abs(actual - expected) > .0001:
                        raise ValueError("Posición cambió fuera del bot; revisar Kalshi antes de vender")
                intent = {"client_id": str(uuid.uuid4()), "ticker": p["ticker"], "direction": p["side"],
                          "action": "sell", "quantity": p["remaining"], "price": bid,
                          "position_id": p["id"], "mode": mode, "reason": reason,
                          "created_at": datetime.now(timezone.utc).isoformat()}
                self.submit(scope, ledger, intent)
                if ledger["pending"]: return

    def tick(self, mode, cfg):
        # Bloqueo de seguridad de esta integración: no ejecutar órdenes reales
        # antes de validar señales y comportamiento del sistema.
        if mode == "REAL" and not ALLOW_REAL_TRADING:
            self.message = "Modo REAL bloqueado para pruebas de integración"
            self.status_by_mode[mode] = {
                "message": self.message,
                "heartbeat": datetime.now(timezone.utc).isoformat(),
            }
            return
        # A running thread keeps its original run() code after an in-place
        # class upgrade. Publish here as well so even that legacy loop supplies
        # a fresh, mode-specific status on every completed evaluation.
        try:
            return self._tick(mode, cfg)
        except Exception as error:
            if mode in self.entry_gates:
                self.entry_gates[mode].reset_candidate()
            self.message = "No se ejecutó otra orden: " + str(error)[:240]
            raise
        finally:
            self.status_by_mode[mode] = {
                "message": self.message,
                "heartbeat": datetime.now(timezone.utc).isoformat(),
            }

    def _tick(self, mode, cfg):
        scope = self.scope(mode); ledger = self.read_ledger(scope)
        if ledger["pending"]:
            if mode == "REAL":
                result = self.reconcile(ledger["pending"])
                if result is None:
                    self.message = "Orden pendiente de reconciliar con Kalshi; no se duplica"
                    return
                self.apply_result(ledger, result); self.write_ledger(scope, ledger)
            else:
                raise ValueError("Intento de simulación interrumpido; revisar el registro")
        self.manage(scope, ledger, mode)
        if ledger["pending"]: return
        if cfg["mode"] != mode or not cfg["enabled"]:
            self.message = "Compras apagadas; continúa gestionando posiciones existentes"
            return
        if any(p["remaining"] > .0001 for p in ledger["positions"]):
            awaiting = next((p for p in ledger["positions"]
                             if p["remaining"] > .0001 and
                             p.get("status") == "ESPERANDO LIQUIDACIÓN"), None)
            self.message = (f'Esperando liquidación oficial: {awaiting["ticker"]} '
                            f'· estado {awaiting.get("market_status", "desconocido")}'
                            if awaiting else
                            "Gestionando compra abierta: profit / stop / liquidación")
            return
        losses = self.loss_streak(ledger)
        levels = cfg["levels"] if cfg["martingale_on"] else 1
        if cfg["martingale_on"] and losses >= levels:
            self.message = "Ciclo de martingala agotado; usa REINICIAR CICLO en Auto Trading"
            return
        m = _background_get_market()
        if not m or m.get("status") != "active": self.message = "Sin mercado activo"; return
        secs = get_seconds_remaining(m); target = get_target_from_market(m)
        if secs is None or secs <= 0 or target is None:
            self.message = "Sin reloj o target válidos"; return
        with ThreadPoolExecutor(max_workers=2) as pool:
            candles_job = pool.submit(_background_get_btc_data)
            price_job = pool.submit(_background_get_live_price, m, True)
            df = candles_job.result()
            live_price, live_source = price_job.result()
        gate = self.entry_gates.setdefault(mode, RecentEntryConfirmation())
        gate.observe(m["ticker"], live_source, float(live_price), time.monotonic())
        sig = build_signal(df, target, secs, live_price)
        sig["recent_moves"] = gate.movement(sig.get("atr", 0), time.monotonic())
        # Cerebro original v4.6.1: señal y confirmación temporal intactas.
        confirm_states = self.__dict__.setdefault("brain_confirm_states", {})
        confirm_key = (mode, m["ticker"])
        if confirm_key not in confirm_states:
            confirm_states[confirm_key] = new_round_state(m["ticker"], secs)
        confirm_state = confirm_states[confirm_key]
        confirm_round_candidate(confirm_state, sig.get("candidate"), m, secs, datetime.now(timezone.utc))
        side = confirm_state.get("active_direction")
        confidence = sig.get("up_probability" if side == "UP" else "down_probability", 50)
        if side not in ("UP", "DOWN") or confidence < cfg["min_conf"]:
            gate.reset_candidate()
            pre_reason = sig.get("quality") if side not in ("UP", "DOWN") else None
            self.message = pre_reason or f'Lectura {side or "NEUTRAL"} · puntuación {confidence}: mínimo {cfg["min_conf"]}'; return
        positions = ledger["positions"]
        if cfg["one_per_round"] and any(p["ticker"] == m["ticker"] for p in positions):
            self.message = "Esta ronda ya tuvo una compra"; return
        today = datetime.now(ZoneInfo("America/New_York")).date()
        count = sum(datetime.fromisoformat(p["created_at"]).astimezone(ZoneInfo("America/New_York")).date() == today
                    for p in positions)
        if count >= cfg["max_trades_day"]: self.message = "Límite diario alcanzado"; return
        level = losses if cfg["martingale_on"] else 0
        rule = cfg["level_directions"][level]
        if rule == "No operar": self.message = "Nivel configurado: No operar"; return
        if rule == "Solo UP": side = "UP"
        elif rule == "Solo DOWN": side = "DOWN"
        elif rule == "Contraria a la señal": side = "DOWN" if side == "UP" else "UP"
        confirmation_note = sig.get("quality", "Entrada por motor principal")
        price = get_yes_ask(m) if side == "UP" else get_no_ask(m)
        if price is None or not cfg["min_price"] <= price * 100 <= cfg["max_price"]:
            self.message = f'{side}: precio fuera de {cfg["min_price"]}–{cfg["max_price"]}¢'; return
        # Capital = presupuesto global: descuenta pérdidas netas y costes abiertos.
        realized = sum(p["pnl"] or 0 for p in positions)
        available = max(0, cfg["capital"] + min(0, realized))
        allocation = martingale_plan(max(0, cfg["capital"] - cfg["reserve"]), levels,
                                     cfg["multiplier"] if cfg["martingale_on"] else 1)[level]
        budget = min(allocation, max(0, available - cfg["reserve"]))
        if mode == "REAL":
            bal, _ = kalshi_get_balance(self.key_id, self.pem); self.balance = bal
            budget = min(budget, max(0, bal - cfg["reserve"]))
            if abs(self.position(m["ticker"])) > .0001:
                self.message = "Ya hay posición externa en esta ronda; revisar Kalshi"; return
        # Reserva conservadora para fees (hasta 7¢ por contrato); no promete costes.
        fee_buffer = .07 if mode == "REAL" else 0
        qty = math.floor((budget + 1e-9) / (price + fee_buffer))
        if qty < 1:
            # Diagnóstico preciso: el saldo total no equivale al presupuesto del nivel.
            # No aumentar capital, saltar niveles ni enviar una orden sin cobertura.
            required = price + fee_buffer
            balance_info = f" · saldo Kalshi ${self.balance:.2f}" if mode == "REAL" and self.balance is not None else ""
            self.message = (
                f"Nivel {level + 1}/{levels}: presupuesto ${budget:.2f}; "
                f"1 contrato {side} cuesta ${price:.2f} + reserva de comisión "
                f"${fee_buffer:.2f} = ${required:.2f}. "
                f"Faltan ${max(0, required - budget):.2f}. "
                f"Capital total autorizado ${cfg['capital']:.2f}{balance_info}. "
                "No se envió orden."
            )
            return
        intent = {"client_id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
                  "ticker": m["ticker"], "direction": side, "action": "buy", "quantity": qty,
                  "price": price, "level": level + 1, "mode": mode, "cfg": cfg,
                  "note": f'{cfg.get("entry_source","PRESEÑAL")} puntuación {confidence} · {confirmation_note}'}
        self.submit(scope, ledger, intent)

    def run(self):
        # Exclusión entre procesos sobre la misma carpeta / SQLite.
        with open(AUTO_DB + ".worker.lock", "a") as handle:
            try: fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.message = "Otro proceso está gestionando este bot"
                self.status_by_mode = {m: {"message": self.message, "heartbeat": None}
                                       for m in ("REAL", "SIMULACIÓN")}
                return
            while True:
                with self.lock:
                    try:
                        cfg = load_auto_config()
                        modes = ["SIMULACIÓN"]
                        if self.key_id and self.pem: modes.append("REAL")
                        for mode in modes:
                            self.message = "Procesando ciclo"
                            try:
                                self.tick(mode, cfg)
                            except Exception as e:
                                self.message = "No se ejecutó otra orden: " + str(e)[:240]
                            # Publica solo ciclos terminados; SIMULACIÓN no altera el estado de REAL.
                            self.status_by_mode[mode] = {
                                "message": self.message,
                                "heartbeat": datetime.now(timezone.utc).isoformat(),
                            }
                        if cfg["mode"] == "REAL" and cfg["enabled"] and not self.key_id:
                            self.message = "REAL activado: falta conectar Kalshi"
                            self.status_by_mode["REAL"] = {"message": self.message,
                                "heartbeat": datetime.now(timezone.utc).isoformat()}
                    except Exception as e:
                        self.message = "No se ejecutó otra orden: " + str(e)[:240]
                        self.status_by_mode = {m: {
                            "message": self.message, "heartbeat": datetime.now(timezone.utc).isoformat()}
                            for m in ("REAL", "SIMULACIÓN")}
                    self.heartbeat = datetime.now(timezone.utc).isoformat()
                time.sleep(2)

    def snapshot(self):
        # Lectura sin bloquear la UI durante solicitudes de red.
        mode = load_auto_config()["mode"]
        status = self.status_by_mode.get(mode, {
            "message": "Conecta Kalshi para operar en REAL" if mode == "REAL" and not self.key_id
                       else "Preparando primer ciclo", "heartbeat": None})
        return {"message": status["message"], "heartbeat": status["heartbeat"], "connected": bool(self.key_id),
                "balance": self.balance}

@st.cache_resource
def execution_worker():
    return ExecutionWorker()

def current_execution_worker():
    # Streamlit may retain an instance of the previous class after a source edit.
    # Upgrade that same instance under its existing lock. Do not create a second
    # trading thread, clear credentials, or discard the ledger.
    worker = execution_worker()
    with worker.lock:
        if worker.__class__ is not ExecutionWorker:
            worker.__class__ = ExecutionWorker
        if not hasattr(worker, "status_by_mode"):
            worker.status_by_mode = {}
        if not hasattr(worker, "entry_gates"):
            worker.entry_gates = {}
    return worker

def load_execution_orders(limit=100):
    worker = current_execution_worker()
    mode = load_auto_config()["mode"]
    ledger = worker.read_ledger(worker.scope(mode))
    rows = []
    for p in reversed(ledger["positions"][-limit:]):
        rows.append({k: v for k, v in p.items() if k != "cfg"})
    if ledger["pending"]:
        it = ledger["pending"]
        rows.insert(0, {"created_at": it["created_at"], "ticker": it["ticker"],
                        "mode": it["mode"], "side": it["direction"],
                        "status": "RECONCILIANDO", "order_id": it["client_id"]})
    return pd.DataFrame(rows)

@st.fragment(run_every="2s")
def render_execution_status():
    status = current_execution_worker().snapshot()
    cfg = load_auto_config()
    st.markdown(f'**Auto Trading · {cfg["mode"]} · {"ENCENDIDO" if cfg["enabled"] else "APAGADO"}**')
    orders = load_execution_orders(20)
    if not orders.empty:
        latest = orders.iloc[0]
        side = str(latest.get("side", ""))
        trade_status = str(latest.get("status", ""))
        st.caption(f"Última operación: {side} · {trade_status}")
    else:
        st.caption("Todavía no hay operaciones registradas en este modo.")
    st.caption("Ahora: " + str(status["message"]))
    if status["heartbeat"]:
        st.caption("Última revisión: " + status["heartbeat"])
    with st.expander("Ver operaciones y detalles", expanded=False):
        st.caption("Entrada directa por preseñal. Los porcentajes son puntuaciones heurísticas, sin calibración estadística.")
        if not orders.empty:
            cols = ["created_at", "ticker", "side", "level", "entry_cents", "contracts", "remaining", "status", "pnl", "order_id"]
            st.dataframe(orders[[c for c in cols if c in orders]], hide_index=True, use_container_width=True)

def _select_value(label, options, current, key, help_text=None, disabled=False):
    if current not in options: current = options[0]
    return st.selectbox(label, options, index=options.index(current), key=key,
                        help=help_text, disabled=disabled)

def render_auto_trading_page():
    cfg = load_auto_config()
    st.markdown("""
    <style>
    .block-container{max-width:760px!important;padding:18px 22px 120px!important}
    .auto-head{display:flex;justify-content:space-between;align-items:center;margin:4px 0 24px}
    .auto-head h2{font-size:27px;margin:0;font-weight:900}.auto-x{font-size:38px;color:#eef2f3;text-decoration:none;line-height:1}
    .auto-section{font-size:20px;font-weight:950;letter-spacing:1.5px;margin:28px 0 10px;border-top:1px solid #20282a;padding-top:24px}
    .auto-note{color:#87938f;font-size:13px;font-weight:650;margin:-5px 0 14px}
    .level-card{border:1px solid #20282a;border-radius:13px;padding:13px 16px;margin:8px 0;background:#050909}
    .level-title{font-weight:900;font-size:16px}.level-sub{color:#85918d;font-size:13px;font-weight:700;margin-top:3px}
    .balance-box{border:1px solid #0b693f;background:#06160f;border-radius:10px;padding:14px 16px;color:#89948f;font-weight:750;margin:14px 0}.balance-box b{color:#31d184}
    div[data-testid="stSelectbox"] label,div[data-testid="stNumberInput"] label{font-weight:850!important;color:#eef2f3!important}
    div[data-baseweb="select"]>div{background:#080c0c!important;border-color:#303838!important;min-height:58px;border-radius:10px!important}
    div[data-testid="stNumberInput"] input{background:#080c0c!important;color:#eef2f3!important;min-height:54px}
    div[data-testid="stToggle"] label{font-weight:800!important}
    .stButton>button{min-height:52px;border-radius:26px;font-weight:900}
    .st-key-reset_martingale_cycle button{background:#087f4f!important;color:#ffffff!important;border:2px solid #31d184!important}
    .st-key-reset_martingale_cycle button p{color:#ffffff!important;font-weight:900!important}
    </style>
    <div class="auto-head"><h2>Ajustes del bot</h2><a class="auto-x" href="?page=signal" target="_self">×</a></div>
    """, unsafe_allow_html=True)

    # Credentials in session are temporary; Streamlit Secrets persist across restarts.
    for k,v in [("kalshi_key_id",""),("kalshi_private_key",""),("kalshi_balance",None)]:
        if k not in st.session_state: st.session_state[k]=v

    st.markdown('<div class="auto-section" style="border-top:0;padding-top:0">CONEXIÓN KALSHI</div>', unsafe_allow_html=True)
    with st.expander("Conectar / cambiar credenciales", expanded=False):
        stored_id, stored_pem = read_kalshi_secrets()
        key_id = st.text_input("API Key ID", value=stored_id or st.session_state.kalshi_key_id)
        private_key = st.text_area("Private Key PEM", value="", help="Pega tu clave privada aquí. Este campo no oculta el texto; evita mostrar la pantalla a otras personas.")
        if stored_id and stored_pem:
            st.success("Credenciales guardadas disponibles. Se intentará reconectar automáticamente.")
        else:
            st.info("Al conectar, la clave se guarda cifrada en el servidor. Streamlit Cloud puede borrar el archivo al reiniciar o redesplegar.")
        a,b=st.columns(2)
        if a.button("CONECTAR", use_container_width=True):
            kid=key_id.strip(); pk=_normalize_private_key(private_key) or (stored_pem if kid == stored_id else "")
            if not kid or not pk: st.error("Falta API Key ID o Private Key.")
            else:
                try:
                    balance,_=kalshi_get_balance(kid,pk)
                    save_local_kalshi_credentials(kid, pk)
                    current_execution_worker().connect(kid, pk)
                    st.session_state.kalshi_key_id=kid; st.session_state.kalshi_private_key=pk; st.session_state.kalshi_balance=balance
                    st.success(f"Conectado · ${balance:,.2f} disponibles")
                except Exception as e: st.error("No se pudo conectar: "+str(e))
        if b.button("DESCONECTAR", use_container_width=True):
            current_execution_worker().disconnect()
            st.session_state.kalshi_key_id=""; st.session_state.kalshi_private_key=""; st.session_state.kalshi_balance=None
            if stored_id and stored_pem:
                st.warning("Las credenciales siguen guardadas localmente. Usa BORRAR CLAVE GUARDADA para eliminarlas.")
            else:
                st.rerun()

    if st.button("BORRAR CLAVE GUARDADA"):
        delete_local_kalshi_credentials()
        current_execution_worker().disconnect()
        st.session_state.kalshi_key_id = ""
        st.session_state.kalshi_private_key = ""
        st.success("Clave local eliminada.")
    st.markdown('<div class="auto-section">OPERACIÓN</div>', unsafe_allow_html=True)
    mode=_select_value("Modo",["SIMULACIÓN","REAL"],cfg["mode"],"a_mode")
    entry_source = "SEÑAL PRINCIPAL"
    st.caption("Entradas conectadas al motor principal · lectura temprana del impulso actual.")
    st.caption("La preseñal es informativa. Las puntuaciones no son probabilidades comprobadas.")
    enabled=st.toggle("Auto Trading", value=bool(cfg["enabled"]), key="a_enabled")
    capital_opts=[5,10,15,20,25,30,40,50,75,100,150,200,300,500,1000]
    cap_current=min(capital_opts,key=lambda x:abs(x-float(cfg["capital"])))
    capital=float(_select_value("Capital máximo a usar ($)",capital_opts,cap_current,"a_cap"))
    min_price=_select_value("Precio mínimo de compra",list(range(5,96,5)),int(round(cfg["min_price"]/5)*5),"a_minp")
    max_price=_select_value("Precio máximo de compra",list(range(5,100,5)),int(round(cfg["max_price"]/5)*5),"a_maxp")
    min_conf=_select_value("Confianza mínima de señal",list(range(50,96,5)),int(round(cfg["min_conf"]/5)*5),"a_conf")
    st.caption("Los precios están en centavos por contrato. El bot solo entra cuando cumple todos los filtros.")
    st.caption("Sigue operando al cerrar esta pantalla mientras el servidor esté encendido. Si Streamlit suspende o reinicia el servidor, necesita reconectar; las credenciales locales pueden perderse.")

    st.markdown('<div class="auto-section">FINALIZACIÓN</div>', unsafe_allow_html=True)
    profit_on=st.toggle("Tomar profit automáticamente",value=bool(cfg["profit_on"]),key="a_profiton")
    profit_opts=list(range(5,101,5))
    profit_pct=_select_value("Tomar profit",profit_opts,int(round(cfg["profit_pct"]/5)*5),"a_profit",disabled=not profit_on)
    stop_on=st.toggle("Stop Loss",value=bool(cfg["stop_on"]),key="a_stopon")
    stop_pct=_select_value("Stop Loss",list(range(5,101,5)),int(round(cfg["stop_pct"]/5)*5),"a_stop",disabled=not stop_on)

    st.markdown('<div class="auto-section">MARTINGALA</div>', unsafe_allow_html=True)
    martingale_on=st.toggle("Martingala",value=bool(cfg["martingale_on"]),key="a_marton")
    levels=_select_value("Máximo de niveles",list(range(1,13)),int(cfg["levels"]),"a_levels",disabled=not martingale_on)
    multiplier=_select_value("Multiplicador",[1.25,1.5,1.75,2.0,2.25,2.5,3.0],float(cfg["multiplier"]) if float(cfg["multiplier"]) in [1.25,1.5,1.75,2.0,2.25,2.5,3.0] else 2.0,"a_mult",disabled=not martingale_on)
    st.caption("Reinicia el contador del modo guardado al nivel 1. Conserva operaciones, pérdidas, capital y límites.")
    if st.button("REINICIAR CICLO", key="reset_martingale_cycle", use_container_width=True):
        try:
            current_execution_worker().reset_cycle(cfg["mode"])
            st.success("Ciclo reiniciado al nivel 1. Las compras siguen sujetas a tus filtros y al capital restante.")
        except ValueError as error:
            st.error(str(error))
    plan=martingale_plan(max(0,capital-float(cfg["reserve"])),int(levels) if martingale_on else 1,float(multiplier) if martingale_on else 1.0)
    # El trabajador de ejecución es la fuente de verdad de la conexión.
    # La sesión de Streamlit puede reiniciarse aunque Kalshi siga autenticado.
    active_worker = current_execution_worker()
    if active_worker.key_id and active_worker.pem:
        bal = active_worker.balance
        if bal is None:
            try:
                bal, _ = kalshi_get_balance(active_worker.key_id, active_worker.pem)
                active_worker.balance = bal
            except Exception:
                bal = None
        st.session_state.kalshi_balance = bal
        bal_text = f"${bal:,.2f}" if bal is not None else "saldo no disponible"
    else:
        bal_text = "sin conectar"
    st.markdown(f'<div class="balance-box">Saldo disponible: <b>{bal_text}</b> · Capital autorizado: <b>${capital:,.2f}</b></div>',unsafe_allow_html=True)

    st.markdown('<div class="auto-section">ELIGE LA DIRECCIÓN</div><div class="auto-note">Configura cada nivel por separado.</div>',unsafe_allow_html=True)
    directions=[]
    visible_levels=int(levels) if martingale_on else 1
    dir_options=["Seguir señal","Solo UP","Solo DOWN","Contraria a la señal","No operar"]
    for i in range(visible_levels):
        amount=plan[i] if i<len(plan) else 0
        title="Entrada inicial" if i==0 else f"Martingala {i}"
        st.markdown(f'<div class="level-card"><div class="level-title">{title}</div><div class="level-sub">Nivel {i+1} · ${amount:.2f}</div></div>',unsafe_allow_html=True)
        cur=cfg["level_directions"][i]
        directions.append(_select_value(f"Dirección nivel {i+1}",dir_options,cur,f"a_dir_{i}"))
    directions += cfg["level_directions"][visible_levels:12]

    st.markdown('<div class="auto-section">PROTECCIONES</div>',unsafe_allow_html=True)
    one_per_round=st.toggle("Máximo una compra por ronda",value=bool(cfg["one_per_round"]),key="a_one")
    max_trades_day=_select_value("Máximo de operaciones por día",[1,2,3,5,10,12,15,20,25,30,40,50],int(cfg["max_trades_day"]) if int(cfg["max_trades_day"]) in [1,2,3,5,10,12,15,20,25,30,40,50] else 12,"a_maxday")
    reserve_opts=[0,1,2,5,10,15,20,25,50,100]
    reserve=float(_select_value("Reserva que el bot no puede tocar ($)",reserve_opts,min(reserve_opts,key=lambda x:abs(x-float(cfg["reserve"]))),"a_reserve"))

    new_cfg={"enabled":bool(enabled),"mode":mode,"capital":capital,"min_price":int(min_price),"max_price":int(max_price),"min_conf":int(min_conf),"profit_on":bool(profit_on),"profit_pct":int(profit_pct),"stop_on":bool(stop_on),"stop_pct":int(stop_pct),"martingale_on":bool(martingale_on),"levels":int(levels),"multiplier":float(multiplier),"one_per_round":bool(one_per_round),"max_trades_day":int(max_trades_day),"reserve":reserve,"level_directions":directions[:12]}

    st.markdown('<div class="auto-section">GUARDAR</div>',unsafe_allow_html=True)
    new_cfg["entry_source"] = entry_source
    c1,c2,c3=st.columns([1.2,1,1.25])
    if c1.button("RESTAURAR",use_container_width=True):
        save_auto_config(_auto_default_config()); st.rerun()
    if c2.button("CANCELAR",use_container_width=True):
        st.query_params["page"]="signal"; st.rerun()
    if c3.button("GUARDAR CAMBIOS",type="primary",use_container_width=True):
        if new_cfg["min_price"]>new_cfg["max_price"]: st.error("El precio mínimo no puede ser mayor que el máximo.")
        elif new_cfg["reserve"]>=new_cfg["capital"]: st.error("La reserva debe ser menor que el capital autorizado.")
        else:
            save_auto_config(new_cfg); st.session_state.auto_config=new_cfg
            st.success("Configuración guardada. Auto Trading conservará estos ajustes al salir de esta pantalla.")

    st.markdown('<div class="auto-section">COMPRAS / ÓRDENES</div>',unsafe_allow_html=True)
    orders=load_execution_orders(100)
    if orders.empty: st.caption("Todavía no hay operaciones registradas.")
    else:
        cols=["created_at","ticker","mode","side","level","entry_cents","contracts","amount","take_profit_pct","take_profit_cents","status","pnl"]
        st.dataframe(orders[[c for c in cols if c in orders.columns]],use_container_width=True,hide_index=True)

def render_history_page():
    # SOLO COLOR/CONTRASTE DEL HISTORIAL. No cambia datos ni lógica.
    st.markdown(
        """
        <style>
        /* Texto de las cuatro métricas: visible sobre fondo oscuro */
        div[data-testid="stMetricLabel"] { color:#d7e2ee !important; opacity:1 !important; }
        div[data-testid="stMetricValue"] { color:#f4f7fb !important; opacity:1 !important; }
        /* Rondas */
        div[data-testid="stHorizontalBlock"] > div:nth-child(1) div[data-testid="stMetricValue"] { color:#54c6f5 !important; }
        /* Ganadas */
        div[data-testid="stHorizontalBlock"] > div:nth-child(2) div[data-testid="stMetricLabel"],
        div[data-testid="stHorizontalBlock"] > div:nth-child(2) div[data-testid="stMetricValue"] { color:#34e982 !important; }
        /* Perdidas */
        div[data-testid="stHorizontalBlock"] > div:nth-child(3) div[data-testid="stMetricLabel"],
        div[data-testid="stHorizontalBlock"] > div:nth-child(3) div[data-testid="stMetricValue"] { color:#ff4e5f !important; }
        /* Acierto */
        div[data-testid="stHorizontalBlock"] > div:nth-child(4) div[data-testid="stMetricLabel"],
        div[data-testid="stHorizontalBlock"] > div:nth-child(4) div[data-testid="stMetricValue"] { color:#f7bd4d !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<a href="?page=signal" target="_self" style="text-decoration:none;color:#b9c9db;font-size:14px;font-weight:800">← Señal</a>',
        unsafe_allow_html=True,
    )
    st.markdown("### ⚙ Ajustes")
    st.caption("Historial y rendimiento · registro automático por ronda")
    df = load_history(250)
    stats = history_stats(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rondas", stats["total"])
    c2.metric("Ganadas", stats["wins"])
    c3.metric("Perdidas", stats["losses"])
    c4.metric("Acierto", f'{stats["win_rate"]:.1f}%')
    st.caption(f'NO TRADE: {stats["no_trade"]} · El % de acierto usa solo GANADA + PERDIDA.')

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
            if coinbase_live_ok or live_btc_price is not None
            else "SIN DATOS"
        )

    if market:
        ticker = market.get("ticker", "--")
        target = get_target_from_market(market)
        seconds_left = get_seconds_remaining(market)
    else:
        ticker = "--"
        target = None
        seconds_left = None

    if btc_ok:
        sig = build_signal(
            btc_df, target, seconds_left, live_btc_price
        )
    else:
        sig = {
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

    # Cinta live de segundos para el Lector de Cierre.
    update_micro_tape(ticker, live_btc_price)
    micro = micro_reading()
    ui_gate = st.session_state.setdefault("recent_presignal_gate_v10", RecentEntryConfirmation())
    if live_btc_price is not None:
        ui_gate.observe(ticker, source, float(live_btc_price), time.monotonic())
    sig["recent_moves"] = ui_gate.movement(sig.get("atr", 0), time.monotonic())
    round_signal = process_round_signal(ticker, sig, market, seconds_left)
    reader = closing_reader(sig, round_signal, seconds_left, micro)

    # Ballenas: capa visual independiente; NO modifica señales ni probabilidades v4.6.1.
    try:
        whale = get_coinbase_whale_flow()
    except Exception:
        whale = None

    state = round_signal.get("round_state")
    active = (
        state.get("active_direction")
        if state
        else None
    )

    # Render del panel de ballenas. Solo visual; no altera el motor v4.6.1.
    whale_html = render_whale_panel(whale, active)
    early_reversal_html = render_early_reversal_panel(
        detect_early_reversal(ticker, micro, whale, live_btc_price)
    )

    if active == "UP":
        accent = "#34e982"
        glow = "rgba(52,233,130,.46)"
        soft = "rgba(52,233,130,.10)"
        hero = "↑ UP"
        confidence = sig["up_probability"]
    elif active == "DOWN":
        accent = "#ff4e5f"
        glow = "rgba(255,78,95,.45)"
        soft = "rgba(255,78,95,.10)"
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
        distance_color = "#34e982" if distance > 0 else "#ff4e5f" if distance < 0 else "#94a3b8"
    first_signal = (state.get("first_direction") if state else None) or "--"
    first_time = "--"
    if state and state.get("first_signal_time"):
        signal_dt = state["first_signal_time"]
        if signal_dt.tzinfo is None:
            signal_dt = signal_dt.replace(tzinfo=timezone.utc)
        first_time = signal_dt.astimezone(ZoneInfo("America/New_York")).strftime("%-I:%M %p")

    # Etiqueta visual en español; el motor conserva internamente BULL/BEAR.
    ema_display = "ALCISTA" if sig.get("ema") == "BULL" else "BAJISTA" if sig.get("ema") == "BEAR" else sig.get("ema", "N/A")

    # PRESEÑAL independiente: permanece visible toda la ronda y NO copia
    # las probabilidades oficiales.
    pre = build_presignal(sig, seconds_left)
    pre_direction = pre["direction"]
    pre_percent = pre["percent"]

    if pre_direction == "UP":
        pre_color, pre_bg, pre_glow = "#34e982", "rgba(18,91,57,.26)", "rgba(52,233,130,.20)"
        pre_note = "Presión alcista temprana detectada. Esperando evolución del mercado."
        pre_label = "POSIBLE UP"
    elif pre_direction == "DOWN":
        pre_color, pre_bg, pre_glow = "#ff4e5f", "rgba(104,25,37,.28)", "rgba(255,78,95,.20)"
        pre_note = "Presión bajista temprana detectada. Esperando evolución del mercado."
        pre_label = "POSIBLE DOWN"
    else:
        pre_color, pre_bg, pre_glow = "#38bdf8", "rgba(24,73,101,.24)", "rgba(56,189,248,.18)"
        pre_note = pre.get("reason", "Sin inclinación temprana suficiente. La preseñal sigue observando.")
        pre_label = "NEUTRAL"

    pre_badge = "INFORMATIVA · NO EJECUTA COMPRAS"
    pre_note += " La compra exige impulso coincidente en 5/10/30 s sostenido 10 s; este porcentaje es una puntuación, no una probabilidad comprobada."

    pre_html = f'''<section class="presignal" style="--precolor:{pre_color};--prebg:{pre_bg};--preglow:{pre_glow}">
      <div class="prehead"><span class="pretitle">PRESEÑAL · TENDENCIA EN FORMACIÓN</span><span class="prebadge">{pre_badge}</span></div>
      <div class="premain"><span class="predirection">{pre_label}</span><span class="prepercent">{pre_percent}%</span></div>
      <div class="prebar"><b style="width:{pre_percent}%"></b></div>
      <div class="prenote">{pre_note}</div>
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
    speed10 = c10 / 10.0
    speed_word = "SUBIENDO" if speed10 > 0.15 else "BAJANDO" if speed10 < -0.15 else "ESTABLE"
    speed_arrow = "↑" if speed10 > 0.15 else "↓" if speed10 < -0.15 else "→"
    speed_color = "#34e982" if speed10 > 0.15 else "#ff4e5f" if speed10 < -0.15 else "#94a3b8"
    market_side = "UP" if (distance or 0) > 0 else "DOWN" if (distance or 0) < 0 else "NEUTRAL"
    abs_final_distance = abs(distance or 0)

    # El cuadro inferior usa EXACTAMENTE la misma lectura adaptativa y el mismo reloj.
    final_status = reader["headline"]
    final_note = reader["note"]
    final_distance = abs(distance) if distance is not None else 0.0
    final_dist_pct = abs(distance_pct) if distance_pct is not None else 0.0
    final_panel = f'''<div class="finalclose">
      <div class="finalgrid">
        <div class="finalcard motion"><div class="finaltitle">▥ &nbsp; MOVIMIENTO ÚLTIMOS SEGUNDOS</div><div class="motionrow">
          <div><small>30s</small><b style="color:{'#34e982' if c30>=0 else '#ff4e5f'}">{'↑' if c30>=0 else '↓'}<br>{c30:+.0f}</b></div>
          <div><small>10s</small><b style="color:{'#34e982' if c10>=0 else '#ff4e5f'}">{'↑' if c10>=0 else '↓'}<br>{c10:+.0f}</b></div>
          <div><small>5s</small><b style="color:{'#34e982' if c5>=0 else '#ff4e5f'}">{'↑' if c5>=0 else '↓'}<br>{c5:+.0f}</b></div>
        </div><div class="finalnote">Cambio de precio en los últimos segundos.</div></div>
        <div class="finalcard distance"><div class="finaltitle">▥ &nbsp; DISTANCIA AL TARGET</div><div class="finalbig" style="color:{distance_color}">${final_distance:,.0f}</div><div class="finalsub" style="color:{distance_color}">{final_dist_pct:.2f}%</div></div>
        <div class="finalcard speed"><div class="finaltitle">VELOCIDAD</div><div class="finalbig" style="color:{speed_color}">{speed_arrow} {speed_word}</div><div class="finalsub" style="color:{speed_color}">{speed10:+.1f}/s</div><div class="finalnote">En los últimos 10 s.</div></div>
      </div>
      <div class="finalanalysis">
        <div class="analysisbox"><div class="analysisicon">◎</div><div class="analysistext"><small>ANÁLISIS DE CIERRE (ÚLTIMOS 60 s)</small><b>{final_status}</b><span>{final_note}</span></div></div>
        <div class="probbox"><small>PROBABILIDAD</small><b>{reader['percent']}%</b></div>
      </div>
    </div>'''

    st.markdown(
        f"""
<div class="refapp dir-{active.lower() if active in ("UP","DOWN") else "wait"}" style="--accent:{accent};--glow:{glow};--soft:{soft};">
  <header class="rhead">
    <div class="rtitle">BTC Signal</div>
    <div class="rver">v4.6.1</div>
    <a class="gear" href="?page=settings" target="_self" aria-label="Ajustes">⚙</a>
    <div class="rlive"><i></i>{'Mercado en vivo' if market_live else 'Conexión parcial'}</div>
  </header>

  <section class="rhero {'waiting' if active not in ('UP','DOWN') else ''}">
    <div class="rsignal"><span class="cssarrow"></span><span>{hero_word}</span></div>
    <div class="rconf">{'CONFIANZA ' + str(confidence) + '%' if active in ('UP','DOWN') else round_signal["signal"]}</div>
  </section>

  {pre_html}

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
    <div class="rlabel">PROBABILIDADES</div>
    <div class="pbar"><div class="pup" style="width:{up}%">{up}%</div><div class="pdown" style="width:{down}%">{down}%</div></div>
    <div class="pleg"><span class="green">● &nbsp;UP&nbsp; {up}%</span><span class="red">● &nbsp;DOWN&nbsp; {down}%</span></div>
  </section>

  <section class="reader" style="--rb:{reader['border']};--rbg:{reader['bg']};--rr:{reader['color']}">
    <div class="readerhead"><span class="pulse">⌁</span><span>LECTOR DE CIERRE</span><em>ACTIVO</em></div>
    <div class="readerbody"><div><strong>{reader['headline']}</strong><small>{reader['note']}</small></div>
    <div class="rring" style="--p:{reader['percent']}"><span>{reader['percent']}%</span></div></div>
    {final_panel}
  </section>

  {whale_html}{early_reversal_html}

  <section class="rcard tech">
    <div class="techhead"><span>DETALLES TÉCNICOS</span><span>⌃</span></div>
    <div class="techrow">
      <div><small>1ª SEÑAL</small><b style="color:var(--accent)">{first_signal}</b><i>{first_time}</i></div>
      <div><small>KALSHI</small><b>{confidence}%</b><i>{round_signal["entry_quality"]}</i></div>
      <div><small>EMA</small><b class="{ema_class}">{ema_display}</b><i>9 / 21</i></div>
      <div><small>RSI</small><b class="{rsi_class}">{sig["rsi"]:.0f}</b><i>14</i></div>
      <div><small>MOMENTUM</small><b class="{mom_class}">{sig["mom3"]:+.2f}</b><i>3 MIN</i></div>
    </div>
  </section>

  <nav class="rnav">
    <div class="active"><b>⌂</b><span>Señal</span></div>
    <div><b>⌁</b><span>Gráfico</span></div>
    <div><b>▣</b><span>Kalshi</span></div>
    <div><b>⚙</b><span>Ajustes</span></div>
  </nav>

  <section class="features">
    <div><b>ϟ</b><p><strong>SEÑAL EN TIEMPO REAL</strong><span>UP o DOWN, sin duda</span></p></div>
    <div><b>◎</b><p><strong>DATOS CLAVE</strong><span>BTC, target, distancia y countdown</span></p></div>
    <div><b>▥</b><p><strong>PROBABILIDADES VISUALES</strong><span>Con barra y porcentaje</span></p></div>
  </section>
  <footer><span>BTC SIGNAL v4.6.1 &nbsp; | &nbsp; DISEÑADO PARA TRADERS REALES</span><span>MENOS RUIDO. MÁS RESULTADOS.</span></footer>
</div>
<div class="ticker">{ticker} • SCORE {sig["final_score"]:+.2f}</div>
""", unsafe_allow_html=True)

    # Gráfico real BTC/USD de 1 minuto. No modifica ninguna señal del motor.
    if btc_ok:
        chart_timeframe = st.radio(
            "Temporalidad del gráfico",
            ["1m", "3m", "5m"],
            horizontal=True,
            key="chart_timeframe",
            label_visibility="collapsed",
        )
        st.markdown(
            render_live_candles(
                btc_df, live_btc_price, target, active, chart_timeframe
            ),
            unsafe_allow_html=True,
        )

    if round_signal["reversal"]:
        st.markdown(
            f'<div class="alert">⚠ {round_signal["reversal_text"]}</div>',
            unsafe_allow_html=True,
        )

    if target is None and kalshi_ok:
        st.warning(
            "Kalshi está conectado, pero esta ronda no entregó un target numérico."
        )
    if btc_error:
        st.error("Error Coinbase velas: " + btc_error)
    if live_price_error and live_btc_price is None:
        st.warning("Coinbase live: " + live_price_error)
    if kalshi_live_error and coinbase_live_price is not None:
        st.warning(
            "Kalshi BTC live falló temporalmente; usando Coinbase."
        )
    if kalshi_error:
        st.error("Error Kalshi: " + kalshi_error)

    st.markdown(
        '<div style="margin-top:12px;text-align:center"><a href="?page=auto" target="_self" style="display:inline-block;padding:10px 16px;border:1px solid #26364a;border-radius:12px;color:#f4f7fb;text-decoration:none;font-weight:900">AUTO TRADING</a></div>',
        unsafe_allow_html=True,
    )


ALLOW_REAL_TRADING = True  # Permite modo REAL si el usuario lo activa en la configuración.
LEGACY_ROUND_STATE_DB = "btc_signal_round_state.db"
ROUND_STATE_DB = "btc_signal_round_state_v2.db"
_ROUND_TRANSACTION = threading.local()
LEGACY_HISTORY_DB = "btc_signal_history.db"
HISTORY_DB = "btc_signal_history_v2.db"
import zlib
SIGNAL_TRACE_DB = "btc_signal_decisions.db"
_TRACE_CONTEXT = threading.local()


# ===== FUNCIONES ADICIONALES ORIGINALES v4.6.1 =====

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


def _write_state_to_connection(conn, state):
    row = conn.execute('SELECT payload FROM round_state WHERE ticker=?', (state['ticker'],)).fetchone()
    saved = json.loads(row[0]) if row else {}
    if saved.get('first_direction') in ('UP','DOWN'):
        for key in ('first_direction','first_signal_time','first_signal_seconds','first_signal_price'):
            value = saved.get(key)
            if key == 'first_signal_time' and isinstance(value, str) and value:
                value = datetime.fromisoformat(value)
            state[key] = value
    keep = {key:value for key,value in state.items() if key != '_restored_from_disk'}
    for key in ('detected_at','first_signal_time','active_since'):
        if isinstance(keep.get(key), datetime):
            keep[key] = keep[key].isoformat()
    conn.execute('INSERT INTO round_state(ticker,payload,updated_at) VALUES(?,?,?) '
                 'ON CONFLICT(ticker) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',
                 (state['ticker'],json.dumps(keep,allow_nan=False),datetime.now(timezone.utc).isoformat()))


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
                response = requests.get(
                    'https://external-api.kalshi.com/trade-api/v2/markets/' + ticker,
                    headers={'User-Agent': 'MacalyAlphaBot/4.6.1'}, timeout=5)
                response.raise_for_status()
                market = response.json().get('market')
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
    while time.monotonic() - started < BACKGROUND_RUN_SECONDS:
        try:
            reconcile_history_once()
        except Exception:
            pass
        time.sleep(30)


@st.cache_resource(validate=lambda worker: worker.is_alive())
def start_history_verifier():
    worker = threading.Thread(target=_history_verification_loop, name='btc-history-verification-v2', daemon=True)
    worker.start()
    return worker


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


def _signal_engine_without_trace(df, target, seconds_left, live_price=None):
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
    candidate=None; quality="SIN CONFIRMACIÓN"
    if aligned=="UP" and (trend_strong or (rsi3>=52 and rsi5>=50)) and vwap_atr>-0.15:
        candidate="UP"
    elif aligned=="DOWN" and (trend_strong or (rsi3<=48 and rsi5<=50)) and vwap_atr<0.15:
        candidate="DOWN"
    # Señal temprana: no espera alineación perfecta de 3M/5M cuando 5M no se opone
    # y el impulso de 1M/3M + VWAP/participación ya apuntan a la misma dirección.
    elif d5 != "DOWN" and l3["macd_hist"] > 0 and rsi1 >= 53 and rsi3 >= 50 and vwap_atr >= 0.05 and (rvol >= 0.90 or mom3 > 0.025):
        candidate="UP"
        quality="TEMPRANA"
    elif d5 != "UP" and l3["macd_hist"] < 0 and rsi1 <= 47 and rsi3 <= 50 and vwap_atr <= -0.05 and (rvol >= 0.90 or mom3 < -0.025):
        candidate="DOWN"
        quality="TEMPRANA"
    # Near expiry, the contract target can dominate only when BTC has a meaningful ATR cushion.
    if seconds_left is not None and seconds_left<=180 and distance is not None:
        if target_atr>=0.35 and d5!="DOWN": candidate="UP"
        elif target_atr<=-0.35 and d5!="UP": candidate="DOWN"
    if near_noise and not trend_strong: candidate=None
    if candidate:
        confirmations=(d3==candidate)+(d5==candidate)+((l3["macd_hist"]>0) if candidate=="UP" else (l3["macd_hist"]<0))+((l5["plus_di"]>l5["minus_di"]) if candidate=="UP" else (l5["minus_di"]>l5["plus_di"]))
        if quality != "TEMPRANA":
            quality="CONFIRMADA" if confirmations>=3 else "EN FORMACIÓN"
    # Compatibility score: descriptive evidence for existing UI/closing reader; no longer gates entries at +/-4.
    evidence=(1 if d3=="UP" else -1 if d3=="DOWN" else 0)+(1.5 if d5=="UP" else -1.5 if d5=="DOWN" else 0)+(0.75 if l3["macd_hist"]>0 else -0.75)+(0.75 if l5["plus_di"]>l5["minus_di"] else -0.75)+float(np.clip(target_atr,-2,2))
    up_probability=float(np.clip(50+evidence*7,5,95)); down_probability=100-up_probability
    momentum="ALCISTA" if aligned=="UP" else "BAJISTA" if aligned=="DOWN" else "NEUTRAL"
    return {"price":price,"candle_price":candle_price,"rsi":rsi1,"rsi3":rsi3,"rsi5":rsi5,"mom3":mom3,"mom5":mom5,"mom15":mom15,"vol_ratio":rvol,"ema":"BULL" if l1["ema9"]>l1["ema21"] else "BEAR","technical_score":evidence,"target_score":target_atr,"final_score":evidence,"distance":distance,"distance_pct":distance_pct,"momentum":momentum,"up_probability":round(up_probability),"down_probability":round(down_probability),"candidate":candidate,"quality":quality,"trend3":d3,"trend5":d5,"adx":adx5,"plus_di":float(l5["plus_di"]),"minus_di":float(l5["minus_di"]),"macd3":float(l3["macd_hist"]),"macd5":float(l5["macd_hist"]),"atr":atr,"vwap":vwap,"vwap_atr":vwap_atr,"target_atr":target_atr}


def _confirmation_without_trace(state, candidate, market, seconds_left, now):
    """Confirmación compartida por la pantalla y el registrador de fondo.

    La primera señal queda inmutable. Un cambio UP/DOWN posterior también
    necesita confirmación. Una lectura neutral cancela la candidatura pendiente.
    """
    if candidate not in ("UP", "DOWN"):
        state["pending_direction"] = None
        state["pending_count"] = 0
        state["pending_since"] = None
        state["pending_last_at"] = None
        state["active_direction"] = None
        state["active_since"] = None
        return

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
    score = float(sig.get("final_score", 0.0))
    price = float(sig.get("price", 0.0))
    distance_now = sig.get("distance")
    if distance_now is not None:
        try:
            state["last_target"] = price - float(distance_now)
        except Exception:
            pass

    previous_live_price = state.get("last_live_price")
    state["previous_live_price"] = previous_live_price
    state["last_live_price"] = price
    price_change = price - previous_live_price if previous_live_price is not None else 0.0

    previous_score = float(state.get("last_score", 0.0))
    state["previous_score"] = previous_score
    state["last_score"] = score
    score_change = score - previous_score

    # El cerebro propone; tres lecturas espaciadas confirman la señal.
    candidate = sig.get("candidate")
    if restored_from_disk and candidate not in ("UP", "DOWN"):
        # No se mantiene una señal antigua ante una lectura neutral actual.
        pass
    confirm_round_candidate(state, candidate, market, seconds_left, now)

    active = state.get("active_direction")
    reversal = False
    reversal_text = ""

    # Aviso informativo solamente; nunca bloquea ni congela la señal.
    if active == "UP":
        weakness_points = 0
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
        decision, signal, icon, color = "UP","SEÑAL UP","⬆","#34e982"
        current_entry_price = get_yes_ask(market)
    elif active == "DOWN":
        decision, signal, icon, color = "DOWN","SEÑAL DOWN","⬇","#ff4e5f"
        current_entry_price = get_no_ask(market)
    else:
        decision, signal, icon, color = "ESPERANDO","SIN CONFIRMACIÓN","•","#38bdf8"
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
    confirm_round_candidate(state, sig.get("candidate"), market, seconds_left, now)
    save_round_state(state)
    return state


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
        return float(earlier[-1]["p"]) if earlier else None

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
    color = "#ff5367" if direction == "DOWN" else "#34e982" if direction == "UP" else "#8fa3b8"
    title = result.get("status", "OBSERVANDO")
    detail = result.get("detail", "")
    return f'''<section style="margin:7px 0;padding:10px;border:1px solid {color};border-radius:10px;background:#0b1520">
      <div style="font-size:9px;font-weight:900;color:#dce7f3">DETECTOR DE REVERSIÓN · EXPERIMENTAL</div>
      <div style="margin-top:6px;font-size:13px;font-weight:950;color:{color}">{title}{' → ' + direction if direction else ''}</div>
      <div style="margin-top:5px;font-size:9px;color:#b5c4d4">{detail}</div>
      <div style="margin-top:4px;font-size:8px;color:#8495aa">Alerta informativa, no orden de compra ni predicción garantizada. No cambia la señal oficial.</div>
    </section>'''


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
        header = dict(schema_version=1,ticker=ticker,
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



from pathlib import Path

def _local_vault_path():
    return Path(__file__).resolve().parent / ".kalshi_credentials.enc"

def _local_vault_key_path():
    return Path(__file__).resolve().parent / ".kalshi_vault.key"

def _local_fernet():
    from cryptography.fernet import Fernet
    keyfile = _local_vault_key_path()
    if not keyfile.exists():
        keyfile.write_bytes(Fernet.generate_key())
        keyfile.chmod(0o600)
    return Fernet(keyfile.read_bytes())

def save_local_kalshi_credentials(kid, pem):
    encrypted = _local_fernet().encrypt(json.dumps({"id":kid,"pem":pem}).encode())
    path = _local_vault_path()
    path.write_bytes(encrypted)
    path.chmod(0o600)

def read_local_kalshi_credentials():
    path = _local_vault_path()
    if not path.exists():
        return "", ""
    try:
        obj = json.loads(_local_fernet().decrypt(path.read_bytes()))
        return obj["id"], obj["pem"]
    except Exception:
        return "", ""

def delete_local_kalshi_credentials():
    _local_vault_path().unlink(missing_ok=True)
    _local_vault_key_path().unlink(missing_ok=True)

def read_kalshi_secrets():
    """Read persistent server-side secrets; never write private keys to code or SQLite."""
    try:
        key_id = str(st.secrets.get("KALSHI_KEY_ID", "") or "").strip()
        pem = str(st.secrets.get("KALSHI_PRIVATE_KEY", "") or "")
        return (key_id, _normalize_private_key(pem)) if key_id and pem else read_local_kalshi_credentials()
    except (FileNotFoundError, KeyError):
        return read_local_kalshi_credentials()

# Inicia ejecución independiente de la pantalla, mientras el servidor esté activo.
worker = current_execution_worker()
if (not worker.key_id and st.session_state.get("kalshi_key_id")
        and st.session_state.get("kalshi_private_key")):
    try:
        verified_balance, _ = kalshi_get_balance(st.session_state.kalshi_key_id, st.session_state.kalshi_private_key)
        worker.connect(st.session_state.kalshi_key_id, st.session_state.kalshi_private_key)
        worker.balance = verified_balance
    except Exception as exc:
        worker.message = "Kalshi no autenticado: " + str(exc)[:180]
secret_id, secret_pem = read_kalshi_secrets()
if secret_id and secret_pem and not worker.key_id:
    try:
        verified_balance, _ = kalshi_get_balance(secret_id, secret_pem)
        worker.connect(secret_id, secret_pem)
        worker.balance = verified_balance
    except Exception as exc:
        worker.message = "Kalshi no autenticado: " + str(exc)[:180]

# Inicia una sola vez el registrador autónomo de 12 horas.
start_12h_history_worker()
start_history_verifier()

page = str(st.query_params.get("page", "signal"))
if page == "signal_trace":
    render_signal_trace_page()
elif page == "settings":
    render_history_page()
elif page == "auto":
    render_auto_trading_page()
else:
    render_execution_status()
    live_dashboard()
