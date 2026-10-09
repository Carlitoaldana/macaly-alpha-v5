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
# MACALY + ALPHA BOT v4.6.1 • MOBILE PRO UI (OPTIMIZADO)
# BTC 15 MIN • CEREBRO AJUSTADO PARA MÁXIMA AGILIDAD
# =========================================================

st.set_page_config(
    page_title="BTC Signal v4.6.1",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =========================================================
# CONFIGURACIÓN TÁCTICA OPTIMIZADA (AJUSTES APLICADOS)
# =========================================================

NEW_ROUND_WAIT = 8
NEW_ENTRY_LOCK = 75

# Umbrales más dinámicos para entradas tempranas en rangos de 15m
UP_THRESHOLD = 3.5
DOWN_THRESHOLD = -3.5

FLIP_UP_THRESHOLD = 4.25
FLIP_DOWN_THRESHOLD = -4.25
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
.tech{margin-top:6px;padding:7px 8px}.techhead{display:flex;justify-content:space-between;font-size:9px;color:#c2d0df;padding-bottom:6px}.techrow{display:grid;grid-template-columns:repeat(5,1fr);border-top:1px solid #172737}.techrow>div{text-align:center;padding:7px 2px 2px;border-right:1px solid #172737}.techrow>div:last-child{border:0}.techrow small, .techrow i{display:block;font-size:6px;color:#8d9db0;font-style:normal}.techrow b{display:block;font-size:10px;margin:4px 0}
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

.rarrow{font-family:Arial Black,Arial,sans-serif!important;font-weight:1000!important}

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
.refapp.dir-down .cssarrow{transform:rotate(180deg);}
.rhero.waiting .cssarrow{display:none!important}

.block-container{max-width:365px!important;padding-top:3px!important}
.rgrid{margin-top:1px!important}
.reader{min-height:0!important}

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
    }

# =========================================================
# PERSISTENCIA DE RONDA — SOBREVIVE SALIR/ENTRAR A LA APP
# =========================================================

ROUND_STATE_DB = "btc_signal_round_state.db"

def _round_db():
    conn = sqlite3.connect(ROUND_STATE_DB, timeout=5)
    conn.execute("CREATE TABLE IF NOT EXISTS round_state (ticker TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
    return conn

def save_round_state(state):
    if not state or not state.get("ticker"):
        return
    keep = dict(state)
    for key in ("detected_at", "first_signal_time", "active_since"):
        value = keep.get(key)
        if isinstance(value, datetime):
            keep[key] = value.isoformat()
    try:
        with _round_db() as conn:
            conn.execute(
                "INSERT INTO round_state(ticker,payload,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(ticker) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (state["ticker"], json.dumps(keep), datetime.now(timezone.utc).isoformat()),
            )
    except Exception:
        pass

def load_round_state(ticker):
    if not ticker or ticker == "--":
        return None
    try:
        with _round_db() as conn:
            row = conn.execute("SELECT payload FROM round_state WHERE ticker=?", (ticker,)).fetchone()
        if not row:
            return None
        state = json.loads(row[0])
        for key in ("detected_at", "first_signal_time", "active_since"):
            value = state.get(key)
            if isinstance(value, str) and value:
                try:
                    state[key] = datetime.fromisoformat(value)
                except Exception:
                    state[key] = None
        state["_restored_from_disk"] = True
        return state
    except Exception:
        return None

# =========================================================
# HISTORIAL Y RENDIMIENTO — CAPA INDEPENDIENTE
# =========================================================

HISTORY_DB = "btc_signal_history.db"

def _history_db():
    conn = sqlite3.connect(HISTORY_DB, timeout=5)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS round_history (
            ticker TEXT PRIMARY KEY,
            target REAL,
            final_btc REAL,
            final_outcome TEXT,
            bot_signal TEXT,
            result TEXT,
            first_signal TEXT,
            first_signal_time TEXT,
            closed_at TEXT NOT NULL
        )
    """)
    return conn

def save_round_history(state):
    if not state or not state.get("ticker"):
        return
    target = state.get("last_target")
    final_btc = state.get("last_live_price")
    if target is None or final_btc is None:
        return
    try:
        target = float(target); final_btc = float(final_btc)
    except Exception:
        return

    if final_btc > target:
        outcome = "UP"
    elif final_btc < target:
        outcome = "DOWN"
    else:
        outcome = "EMPATE"

    bot_signal = state.get("active_direction")
    if bot_signal not in ("UP", "DOWN"):
        result = "NO TRADE"
        bot_signal = None
    elif outcome == "EMPATE":
        result = "EMPATE"
    else:
        result = "GANADA" if bot_signal == outcome else "PERDIDA"

    fst = state.get("first_signal_time")
    if isinstance(fst, datetime):
        fst = fst.isoformat()

    try:
        with _history_db() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO round_history
                (ticker,target,final_btc,final_outcome,bot_signal,result,first_signal,first_signal_time,closed_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (state["ticker"], target, final_btc, outcome, bot_signal, result,
                 state.get("first_direction"), fst, datetime.now(timezone.utc).isoformat())
            )
    except Exception:
        pass

def load_history(limit=100):
    try:
        with _history_db() as conn:
            rows = conn.execute(
                """SELECT ticker,target,final_btc,final_outcome,bot_signal,result,
                          first_signal,first_signal_time,closed_at
                   FROM round_history ORDER BY closed_at DESC LIMIT ?""",
                (int(limit),)
            ).fetchall()
        cols = ["Ronda","Target","BTC final","Resultado real","Señal bot","Estado",
                "1ª señal","Hora 1ª señal","Cierre"]
        return pd.DataFrame(rows, columns=cols)
    except Exception:
        return pd.DataFrame()

def history_stats(df):
    if df is None or df.empty:
        return {"total":0,"wins":0,"losses":0,"no_trade":0,"win_rate":0.0}
    wins = int((df["Estado"] == "GANADA").sum())
    losses = int((df["Estado"] == "PERDIDA").sum())
    no_trade = int((df["Estado"] == "NO TRADE").sum())
    decided = wins + losses
    rate = (wins / decided * 100.0) if decided else 0.0
    return {"total":len(df),"wins":wins,"losses":losses,"no_trade":no_trade,"win_rate":rate}

# =========================================================
# COINBASE — VELAS ORIGINALES DE 1 MINUTO
# =========================================================

@st.cache_data(ttl=5)
def get_btc_data():
    response = requests.get(
        "https://api.exchange.coinbase.com/products/BTC-USD/candles",
        params={"granularity": 60},
        headers={"User-Agent": "MacalyAlphaBot/4.6.1"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, list) or len(data) < 30:
        raise ValueError("Coinbase no devolvió suficientes datos.")

    df = pd.DataFrame(
        data, columns=["time", "low", "high", "open", "close", "volume"]
    )

    for column in ["low", "high", "open", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.dropna().sort_values("time").reset_index(drop=True)

def get_coinbase_whale_flow():
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
        </section>'''

    a = whale["alert"]
    up = a["direction"] == "UP"
    color = "#35e986" if up else "#ff5367"
    arrow = "↑" if up else "↓"
    label = "COMPRADOR · POSIBLE IMPULSO UP" if up else "VENDEDOR · POSIBLE IMPULSO DOWN"
    dominant = a["buy"] if up else a["sell"]
    return f'''<section style="{base};border-color:{color};box-shadow:0 0 20px {color}33">
      <div style="display:flex;justify-content:space-between;align-items:center"><b style="font-size:10px;color:#e4edf7">🐋 FLUJO BALLENA · EN VIVO</b><span style="font-size:8px;color:{color}">● ALERTA</span></div>
      <div style="margin-top:8px;font-size:15px;font-weight:950;color:{color}">⚡ {arrow} FLUJO EXTREMO {label}</div>
      <div style="margin-top:6px;font-size:12px;font-weight:900;color:#f3f7fb">{compact_usd(dominant)} dominantes en ~30 s</div>
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
    return float(candidates[-1]) if candidates else None

def get_kalshi_live_btc(market):
    event_ticker = get_event_ticker_from_market(market)
    if not event_ticker:
        raise ValueError("La ronda no entregó event_ticker.")
    response = requests.get(
        f"https://external-api.kalshi.com/trade-api/v2/live_data/events/{event_ticker}",
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
# INDICADORES Y CEREBRO OPTIMIZADO
# =========================================================

def _indicator_frame(df):
    x = df.copy().sort_values("time").reset_index(drop=True)
    close, high, low = x["close"], x["high"], x["low"]
    x["ema9"] = close.ewm(span=9, adjust=False).mean()
    x["ema21"] = close.ewm(span=21, adjust=False).mean()
    delta = close.diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    al = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rsi = 100-(100/(1+(ag/al.replace(0,np.nan))))
    rsi = rsi.mask((al == 0) & (ag > 0), 100).mask((ag == 0) & (al > 0), 0)
    x["rsi"] = rsi.fillna(50)
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
        close_dt = datetime.fromisoformat(str(market["close_time"]).replace("Z", "+00:00"))
        seconds = int((close_dt - datetime.now(timezone.utc)).total_seconds())
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
    return numeric_kalshi_price(market.get("yes_ask_dollars"), market.get("yes_ask"))

def get_no_ask(market):
    if not market:
        return None
    direct = numeric_kalshi_price(market.get("no_ask_dollars"), market.get("no_ask"))
    if direct is not None:
        return direct
    yes_bid = numeric_kalshi_price(market.get("yes_bid_dollars"), market.get("yes_bid"))
    if yes_bid is not None:
        return max(0.0, min(1.0, 1.0 - yes_bid))
    return None

def build_signal(df, target, seconds_left, live_price=None):
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
    
    # AJUSTE 2: Filtro de ruido optimizado (más sensible a rupturas rápidas en VWAP/Target)
    trend_strong=adx5>=18; near_noise=abs(vwap_atr)<0.15 and (distance is None or abs(target_atr)<0.18)
    
    candidate=None; quality="SIN CONFIRMACIÓN"
    if aligned=="UP" and (trend_strong or (rsi3>=50 and rsi5>=48)) and vwap_atr>-0.18:
        candidate="UP"
    elif aligned=="DOWN" and (trend_strong or (rsi3<=50 and rsi5<=52)) and vwap_atr<0.18:
        candidate="DOWN"
    elif d5 != "DOWN" and l3["macd_hist"] > 0 and rsi1 >= 51 and rsi3 >= 48 and vwap_atr >= 0.03 and (rvol >= 0.85 or mom3 > 0.02):
        candidate="UP"
        quality="TEMPRANA"
    elif d5 != "UP" and l3["macd_hist"] < 0 and rsi1 <= 49 and rsi3 <= 52 and vwap_atr <= -0.03 and (rvol >= 0.85 or mom3 < -0.02):
        candidate="DOWN"
        quality="TEMPRANA"
    
    if seconds_left is not None and seconds_left<=180 and distance is not None:
        if target_atr>=0.30 and d5!="DOWN": candidate="UP"
        elif target_atr<=-0.30 and d5!="UP": candidate="DOWN"
    if near_noise and not trend_strong: candidate=None
    
    if candidate:
        confirmations=(d3==candidate)+(d5==candidate)+((l3["macd_hist"]>0) if candidate=="UP" else (l3["macd_hist"]<0))+((l5["plus_di"]>l5["minus_di"]) if candidate=="UP" else (l5["minus_di"]>l5["plus_di"]))
        if quality != "TEMPRANA":
            quality="CONFIRMADA" if confirmations>=2 else "EN FORMACIÓN"
            
    evidence=(1 if d3=="UP" else -1 if d3=="DOWN" else 0)+(1.5 if d5=="UP" else -1.5 if d5=="DOWN" else 0)+(0.75 if l3["macd_hist"]>0 else -0.75)+(0.75 if l5["plus_di"]>l5["minus_di"] else -0.75)+float(np.clip(target_atr,-2,2))
    up_probability=float(np.clip(50+evidence*7,5,95)); down_probability=100-up_probability
    momentum="ALCISTA" if aligned=="UP" else "BAJISTA" if aligned=="DOWN" else "NEUTRAL"
    return {"price":price,"candle_price":candle_price,"rsi":rsi1,"rsi3":rsi3,"rsi5":rsi5,"mom3":mom3,"mom5":mom5,"mom15":mom15,"vol_ratio":rvol,"ema":"BULL" if l1["ema9"]>l1["ema21"] else "BEAR","technical_score":evidence,"target_score":target_atr,"final_score":evidence,"distance":distance,"distance_pct":distance_pct,"momentum":momentum,"up_probability":round(up_probability),"down_probability":round(down_probability),"candidate":candidate,"quality":quality,"trend3":d3,"trend5":d5,"adx":adx5,"plus_di":float(l5["plus_di"]),"minus_di":float(l5["minus_di"]),"macd3":float(l3["macd_hist"]),"macd5":float(l5["macd_hist"]),"atr":atr,"vwap":vwap,"vwap_atr":vwap_atr,"target_atr":target_atr}

def build_presignal(sig, seconds_left):
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

    if mom3 > 0.015: bull += 1.15
    elif mom3 < -0.015: bear += 1.15

    if macd3 > 0: bull += 0.70 * slow
    elif macd3 < 0: bear += 0.70 * slow
    if plus_di > minus_di: bull += 0.50 * slow
    elif minus_di > plus_di: bear += 0.50 * slow

    if vwap_atr >= 0.03: bull += 0.70
    elif vwap_atr <= -0.03: bear += 0.70

    # AJUSTE 3: Ponderación de la preseñal acelerada para reacción más temprana al cierre
    if secs > 300:
        tw = 0.85
    elif secs > 180:
        tw = 1.70
    elif secs > 90:
        tw = 2.90
    elif secs > 30:
        tw = 4.20
    else:
        tw = 6.00

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
    recent = sig.get("recent_moves")
    if not recent or not recent.get("ready"):
        return {"direction":"NEUTRAL", "percent":50, "bull":bull, "bear":bear,
                "reason": (recent or {}).get("reason", "Reuniendo precios de esta ronda")}
    sign = 1 if direction == "UP" else -1
    if any(sign * delta < recent["minimum"] for delta in recent["deltas"]):
        return {"direction":"NEUTRAL", "percent":50, "bull":bull, "bear":bear,
                "reason":"Impulso de 5/10/30 s no coincide; sin preseñal firme"}
    dominant = max(bull, bear)
    share = dominant / total if total else 0.5
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

def process_round_signal(ticker, sig, market, seconds_left):
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

    candidate = sig.get("candidate")
    if candidate in ("UP", "DOWN"):
        previous_active = state.get("active_direction")
        state["active_direction"] = candidate
        if previous_active != candidate:
            state["active_since"] = now
        if state.get("first_direction") is None:
            direction_price = get_yes_ask(market) if candidate == "UP" else get_no_ask(market)
            state["first_direction"] = candidate
            state["first_signal_time"] = now
            state["first_signal_seconds"] = seconds_left
            state["first_signal_price"] = direction_price
    else:
        if not restored_from_disk:
            state["active_direction"] = None
            state["active_since"] = None

    active = state.get("active_direction")
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
        "round_state":state,"reversal":False,"reversal_text":"",
        "entry_price":current_entry_price,"entry_quality":quality,
        "entry_quality_color":quality_color,
    }

# =========================================================
# REGISTRADOR AUTÓNOMO 12 HORAS Y LECTOR DE CIERRE
# =========================================================

BACKGROUND_RUN_SECONDS = 12 * 60 * 60
BACKGROUND_POLL_SECONDS = 2

def _background_get_btc_data():
    response = requests.get(
        "https://api.exchange.coinbase.com/products/BTC-USD/candles",
        params={"granularity": 60},
        headers={"User-Agent": "MacalyAlphaBot/4.6.1"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data, columns=["time", "low", "high", "open", "close", "volume"])
    for column in ["low", "high", "open", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.dropna().sort_values("time").reset_index(drop=True)

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
                f"https://external-api.kalshi.com/trade-api/v2/live_data/events/{event_ticker}",
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
    return (float(price), "COINBASE") if with_source else float(price)

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
                active_state = restored or new_round_state(ticker, get_seconds_remaining(market))
            seconds_left = get_seconds_remaining(market)
            target = get_target_from_market(market)
            live_price = _background_get_live_price(market)
            btc_df = _background_get_btc_data()
            sig = build_signal(btc_df, target, seconds_left, live_price)
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

def update_micro_tape(ticker, live_price):
    if not ticker or ticker == "--" or live_price is None:
        return
    if st.session_state.micro_ticker != ticker:
        st.session_state.micro_ticker = ticker
        st.session_state.micro_prices = []
    now_ts = datetime.now(timezone.utc).timestamp()
    tape = st.session_state.micro_prices
    if not tape or now_ts - tape[-1]["t"] >= 1.0:
        tape.append({"t": now_ts, "p": float(live_price)})
    cutoff = now_ts - 90
    st.session_state.micro_prices = [x for x in tape if x["t"] >= cutoff]

def micro_reading():
    tape = st.session_state.micro_prices
    if len(tape) < 4:
        return {"ready": False, "change_5s": 0.0, "change_10s": 0.0, "change_30s": 0.0, "slope": 0.0, "up_ratio": 0.5, "pressure": "NEUTRAL"}
    now_t = tape[-1]["t"]
    current = tape[-1]["p"]
    def price_ago(seconds):
        target_t = now_t - seconds
        candidates = [x for x in tape if x["t"] <= target_t]
        return candidates[-1]["p"] if candidates else tape[0]["p"]
    p5 = price_ago(5); p10 = price_ago(10); p30 = price_ago(30)
    changes = [tape[i]["p"] - tape[i-1]["p"] for i in range(1, len(tape))]
    nonzero = [x for x in changes if x != 0]
    up_ratio = sum(1 for x in nonzero if x > 0) / len(nonzero) if nonzero else 0.5
    xs = np.array([x["t"] - tape[0]["t"] for x in tape], dtype=float)
    ys = np.array([x["p"] for x in tape], dtype=float)
    slope = float(np.polyfit(xs, ys, 1)[0]) if len(xs) >= 3 and xs[-1] > 0 else 0.0
    pressure = "ALCISTA" if slope > 0.35 and up_ratio >= 0.58 else "BAJISTA" if slope < -0.35 and up_ratio <= 0.42 else "NEUTRAL"
    return {"ready": True, "change_5s": current - p5, "change_10s": current - p10, "change_30s": current - p30, "slope": slope, "up_ratio": up_ratio, "pressure": pressure}

def closing_reader(sig, round_signal, seconds_left, micro):
    state = round_signal.get("round_state")
    active_direction = state.get("active_direction") if state else None
    distance = sig.get("distance")
    secs = 900 if seconds_left is None else max(0, int(seconds_left))

    if seconds_left is not None and seconds_left <= 0:
        color = "#34e982" if (distance or 0) > 0 else "#ff4e5f"
        return {"percent": 100, "headline": "RONDA FINALIZADA", "note": "Fin de ronda.", "micro": "CERRADO", "color": color, "border": "rgba(148,163,184,.45)", "bg": "", "direction": None}

    if distance is None:
        return {"percent": 50, "headline": "ESPERANDO TARGET", "note": "Sin referencia.", "micro": "ESPERANDO", "color": "#38bdf8", "border": "", "bg": "", "direction": None}

    market_side = "UP" if distance > 0 else "DOWN" if distance < 0 else None
    direction = market_side or active_direction or ("UP" if float(sig.get("mom3", 0) or 0) >= 0 else "DOWN")
    atr1 = max(float(sig.get("atr", 0) or 0), 1.0)
    remaining_sigma = atr1 * np.sqrt(max(secs, 1) / 60.0)

    if micro.get("ready"):
        c10 = float(micro.get("change_10s", 0) or 0)
        c30 = float(micro.get("change_30s", 0) or 0)
        observed_drift = (0.45 * float(micro.get("change_5s", 0)) / 5.0 + 0.35 * c10 / 10.0 + 0.20 * c30 / 30.0)
        time_focus = 1.0 - min(1.0, secs / 180.0)
        micro_drift = observed_drift * secs * (0.20 + 0.80 * time_focus)
    else:
        micro_drift = 0.0

    projected_distance = float(distance) + micro_drift
    z = projected_distance / max(remaining_sigma * 0.72, 0.75)
    up_close_prob = 100.0 / (1.0 + np.exp(-np.clip(z, -12, 12)))
    side_prob = up_close_prob if direction == "UP" else 100.0 - up_close_prob
    confidence = int(round(np.clip(side_prob, 0, 100)))

    return {"percent": confidence, "headline": f"VENTAJA {direction}", "note": f"Quedan {secs}s · Distancia ${abs(distance):,.0f}", "micro": "ACTIVO", "color": "#34e982" if direction == "UP" else "#ff4e5f", "border": "", "bg": "", "direction": direction}

def render_live_candles(df, live_price, target, active, timeframe="1m"):
    if df is None or len(df) < 5:
        return '<div class="chartbox"><div class="chartempty">Esperando velas…</div></div>'
    tf_minutes = {"1m": 1, "3m": 3, "5m": 5}.get(timeframe, 1)
    source_df = df.copy().sort_values("time")
    d = source_df.set_index("time").resample(f"{tf_minutes}min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index() if tf_minutes > 1 else source_df[["time", "open", "high", "low", "close", "volume"]].copy()
    d = d.tail(42).reset_index(drop=True)
    if live_price is not None and len(d):
        i = d.index[-1]
        d.loc[i, "close"] = float(live_price)
    W, H = 760, 430
    return f'<div class="chartbox"><div class="charttop"><b>BTC/USD · {timeframe}</b></div><div class="ohlc">Cierre Live: ${float(d.iloc[-1]["close"]):,.0f}</div></div>'

# =========================================================
# AUTO TRADING Y NAVEGACIÓN
# =========================================================

AUTO_DB = "btc_auto_trading.db"

def _auto_db():
    con = sqlite3.connect(AUTO_DB, check_same_thread=False)
    con.execute("""
        CREATE TABLE IF NOT EXISTS auto_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL, ticker TEXT, mode TEXT, side TEXT,
            level INTEGER, entry_cents REAL, contracts INTEGER, amount REAL,
            take_profit_pct REAL, stop_loss_pct REAL, status TEXT, pnl REAL DEFAULT 0, note TEXT
        )
    """)
    con.commit()
    return con

def load_auto_orders(limit=100):
    con = _auto_db()
    try:
        return pd.read_sql_query("SELECT * FROM auto_orders ORDER BY id DESC LIMIT ?", con, params=(int(limit),))
    finally:
        con.close()

def load_auto_config():
    cfg = {"enabled": False, "mode": "SIMULACIÓN", "capital": 20.0, "min_price": 20, "max_price": 70, "min_conf": 65, "profit_on": True, "profit_pct": 85, "stop_on": False, "stop_pct": 20, "martingale_on": False, "levels": 4, "multiplier": 2.0, "one_per_round": True, "max_trades_day": 12, "reserve": 0.0, "level_directions": ["Seguir señal"] * 12}
    return cfg

def render_history_page():
    st.markdown('<a href="?page=signal" target="_self" style="color:#b9c9db;font-weight:800">← Señal</a>', unsafe_allow_html=True)
    st.markdown("### ⚙ Ajustes e Historial")
    df = load_history(250)
    stats = history_stats(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rondas", stats["total"])
    c2.metric("Ganadas", stats["wins"])
    c3.metric("Perdidas", stats["losses"])
    c4.metric("Acierto", f'{stats["win_rate"]:.1f}%')

@st.fragment(run_every="2s")
def live_dashboard():
    try:
        btc_df = add_indicators(get_btc_data())
        btc_ok = True
    except Exception:
        btc_ok = False; btc_df = None

    try:
        market = get_kalshi_btc_market()
        kalshi_ok = market is not None
    except Exception:
        kalshi_ok = False; market = None

    try:
        live_btc_price = get_btc_live_price()
    except Exception:
        live_btc_price = float(btc_df.iloc[-1]["close"]) if btc_ok else None

    ticker = market.get("ticker", "--") if market else "--"
    target = get_target_from_market(market) if market else None
    seconds_left = get_seconds_remaining(market) if market else None

    sig = build_signal(btc_df, target, seconds_left, live_btc_price) if btc_ok else {"price": live_btc_price or 0, "rsi": 50, "mom3": 0, "mom5": 0, "mom15": 0, "vol_ratio": 1, "ema": "N/A", "final_score": 0, "distance": None, "up_probability": 50, "down_probability": 50}
    
    update_micro_tape(ticker, live_btc_price)
    micro = micro_reading()
    round_signal = process_round_signal(ticker, sig, market, seconds_left)
    reader = closing_reader(sig, round_signal, seconds_left, micro)
    
    try:
        whale = get_coinbase_whale_flow()
    except Exception:
        whale = None

    state = round_signal.get("round_state")
    active = state.get("active_direction") if state else None

    accent = "#34e982" if active == "UP" else "#ff4e5f" if active == "DOWN" else "#38bdf8"
    glow = "rgba(52,233,130,.46)" if active == "UP" else "rgba(255,78,95,.45)" if active == "DOWN" else "rgba(56,189,248,.30)"
    soft = "rgba(52,233,130,.10)" if active == "UP" else "rgba(255,78,95,.10)" if active == "DOWN" else "rgba(56,189,248,.09)"
    hero_word = active if active in ("UP", "DOWN") else "ESPERANDO"
    confidence = sig.get("up_probability", 50) if active == "UP" else sig.get("down_probability", 50) if active == "DOWN" else 50

    distance = sig.get("distance")
    up = int(sig.get("up_probability", 50))
    down = int(sig.get("down_probability", 50))
    target_text = f"${target:,.0f}" if target is not None else "--"
    countdown = format_countdown(seconds_left)
    distance_text = f"${abs(distance):,.0f}" if distance is not None else "--"
    distance_sub = f"{abs(sig.get('distance_pct', 0)):.2f}%" if distance is not None else "SIN TARGET"
    distance_color = "#34e982" if (distance or 0) > 0 else "#ff4e5f" if (distance or 0) < 0 else "#94a3b8"

    pre = build_presignal(sig, seconds_left)
    pre_label = pre["direction"]
    pre_percent = pre["percent"]
    pre_color = "#34e982" if pre_label == "UP" else "#ff4e5f" if pre_label == "DOWN" else "#38bdf8"
    
    pre_html = f'''<section class="presignal" style="--precolor:{pre_color};--prebg:rgba(18,91,57,.26);--preglow:rgba(52,233,130,.20)">
      <div class="prehead"><span class="pretitle">PRESEÑAL OPTIMIZADA</span><span class="prebadge">ACTIVA</span></div>
      <div class="premain"><span class="predirection">{pre_label}</span><span class="prepercent">{pre_percent}%</span></div>
      <div class="prebar"><b style="width:{pre_percent}%"></b></div>
    </section>'''

    time_pct = max(0, min(100, int((seconds_left or 0) / 900 * 100)))

    st.markdown(f"""
<div class="refapp dir-{active.lower() if active in ("UP","DOWN") else "wait"}" style="--accent:{accent};--glow:{glow};--soft:{soft};">
  <header class="rhead">
    <div class="rtitle">BTC Signal</div>
    <div class="rver">v4.6.1 · Optimizado</div>
    <a class="gear" href="?page=settings" target="_self">⚙</a>
    <div class="rlive"><i></i>Mercado en vivo</div>
  </header>

  <section class="rhero {'waiting' if active not in ('UP','DOWN') else ''}">
    <div class="rsignal"><span class="cssarrow"></span><span>{hero_word}</span></div>
    <div class="rconf">CONFIANZA {confidence}%</div>
  </section>

  {pre_html}

  <div class="rgrid">
    <div class="rcard keycard"><div class="bigicon btcicon">₿</div><div><div class="rlabel">BTC</div><div class="rvalue">${sig["price"]:,.0f}</div></div></div>
    <div class="rcard keycard"><div class="bigicon targeticon">◎</div><div><div class="rlabel">TARGET</div><div class="rvalue">{target_text}</div></div></div>
    <div class="rcard keycard"><div class="bars" style="--accent:{distance_color}"><b></b><b></b><b></b></div><div><div class="rlabel">DISTANCIA</div><div class="rvalue" style="color:{distance_color}">{distance_text}</div></div></div>
    <div class="rcard keycard"><div class="clock">◷</div><div class="timecontent"><div class="rlabel">TIEMPO</div><div class="rvalue">{countdown}</div><div class="timebar"><b style="width:{time_pct}%"></b></div></div></div>
  </div>

  <section class="rcard probs">
    <div class="rlabel">PROBABILIDADES</div>
    <div class="pbar"><div class="pup" style="width:{up}%">{up}%</div><div class="pdown" style="width:{down}%">{down}%</div></div>
  </section>

  <section class="reader" style="--rb:{reader['color']};--rbg:rgba(5,15,22,.8);--rr:{reader['color']}">
    <div class="readerhead"><span>LECTOR DE CIERRE</span><em>{reader['percent']}%</em></div>
    <div class="readerbody"><div><strong>{reader['headline']}</strong><small>{reader['note']}</small></div></div>
  </section>
</div>
""", unsafe_allow_html=True)

start_12h_history_worker()

page = str(st.query_params.get("page", "signal"))
if page == "settings":
    render_history_page()
else:
    live_dashboard()
