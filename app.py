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
import base64
import math

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
    }

# =========================================================
# PERSISTENCIA DE RONDA — SOBREVIVE SALIR/ENTRAR A LA APP
# Solo guarda el estado de la ronda; NO cambia el cerebro.
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
# No modifica build_signal(), preseñal, lector, ballenas ni gráfico.
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
    """Cierra una ronda una sola vez usando el último BTC/target conocidos."""
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
    x["rsi"] = (100-(100/(1+(ag/al.replace(0,np.nan))))).fillna(50)
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
    price_change = price - previous_live_price if previous_live_price is not None else 0.0

    previous_score = float(state.get("last_score", 0.0))
    state["previous_score"] = previous_score
    state["last_score"] = score
    score_change = score - previous_score

    # build_signal() es el cerebro. No hay espera fija, bloqueo final,
    # votos externos, fresh_support ni distancia mínima externa.
    candidate = sig.get("candidate")

    if candidate in ("UP", "DOWN"):
        previous_active = state.get("active_direction")
        state["active_direction"] = candidate

        if previous_active != candidate:
            state["active_since"] = now

        # La primera señal se guarda SOLO como historial; no congela la señal actual.
        if state.get("first_direction") is None:
            direction_price = get_yes_ask(market) if candidate == "UP" else get_no_ask(market)
            state["first_direction"] = candidate
            state["first_signal_time"] = now
            state["first_signal_seconds"] = seconds_left
            state["first_signal_price"] = direction_price
    else:
        # Al volver a abrir la app, conserva la señal que ya tenía ESA ronda.
        # En los siguientes ciclos el cerebro vuelve a mandar normalmente.
        if not restored_from_disk:
            state["active_direction"] = None
            state["active_since"] = None

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


# =========================================================
# REGISTRADOR AUTÓNOMO 12 HORAS — SOLO HISTORIAL
# Sigue leyendo las rondas aunque no haya una sesión de Streamlit abierta,
# siempre que el proceso del servidor siga encendido.
# NO modifica el motor, la preseñal, el lector, ballenas ni la interfaz.
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
    if not isinstance(data, list) or len(data) < 30:
        raise ValueError("Coinbase no devolvió suficientes datos.")
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

def _background_get_live_price(market):
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
    price = response.json().get("price")
    if price in (None, ""):
        raise ValueError("Sin precio BTC live.")
    return float(price)

def _background_update_state(state, sig, market, seconds_left):
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
    candidate = sig.get("candidate")
    if candidate in ("UP", "DOWN"):
        if state.get("active_direction") != candidate:
            state["active_since"] = now
        state["active_direction"] = candidate
        if state.get("first_direction") is None:
            state["first_direction"] = candidate
            state["first_signal_time"] = now
            state["first_signal_seconds"] = seconds_left
            state["first_signal_price"] = get_yes_ask(market) if candidate == "UP" else get_no_ask(market)
    else:
        state["active_direction"] = None
        state["active_since"] = None
    save_round_state(state)
    return state

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
# Primera fase: configuración + conexión Kalshi + simulación segura.
# Las credenciales viven SOLO en la sesión de Streamlit y no se escriben en SQLite.
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
    </style>
    <div class="auto-head"><h2>Ajustes del bot</h2><a class="auto-x" href="?page=signal" target="_self">×</a></div>
    """, unsafe_allow_html=True)

    # Credentials remain session-only; never persist the private key.
    for k,v in [("kalshi_key_id",""),("kalshi_private_key",""),("kalshi_balance",None)]:
        if k not in st.session_state: st.session_state[k]=v

    st.markdown('<div class="auto-section" style="border-top:0;padding-top:0">CONEXIÓN KALSHI</div>', unsafe_allow_html=True)
    with st.expander("Conectar / cambiar credenciales", expanded=False):
        key_id = st.text_input("API Key ID", value=st.session_state.kalshi_key_id)
        private_key = st.text_area("Private Key (PEM)", value="", height=100, placeholder="No se guarda en la configuración")
        a,b=st.columns(2)
        if a.button("CONECTAR", use_container_width=True):
            kid=key_id.strip(); pk=private_key.strip() or st.session_state.kalshi_private_key
            if not kid or not pk: st.error("Falta API Key ID o Private Key.")
            else:
                try:
                    balance,_=kalshi_get_balance(kid,pk)
                    st.session_state.kalshi_key_id=kid; st.session_state.kalshi_private_key=pk; st.session_state.kalshi_balance=balance
                    st.success(f"Conectado · ${balance:,.2f} disponibles")
                except Exception as e: st.error("No se pudo conectar: "+str(e))
        if b.button("DESCONECTAR", use_container_width=True):
            st.session_state.kalshi_key_id=""; st.session_state.kalshi_private_key=""; st.session_state.kalshi_balance=None; st.rerun()

    st.markdown('<div class="auto-section">OPERACIÓN</div>', unsafe_allow_html=True)
    mode=_select_value("Modo",["SIMULACIÓN","REAL"],cfg["mode"],"a_mode")
    enabled=st.toggle("Auto Trading", value=bool(cfg["enabled"]), key="a_enabled")
    capital_opts=[5,10,15,20,25,30,40,50,75,100,150,200,300,500,1000]
    cap_current=min(capital_opts,key=lambda x:abs(x-float(cfg["capital"])))
    capital=float(_select_value("Capital máximo a usar ($)",capital_opts,cap_current,"a_cap"))
    min_price=_select_value("Precio mínimo de compra",list(range(5,96,5)),int(round(cfg["min_price"]/5)*5),"a_minp")
    max_price=_select_value("Precio máximo de compra",list(range(5,100,5)),int(round(cfg["max_price"]/5)*5),"a_maxp")
    min_conf=_select_value("Confianza mínima de señal",list(range(50,96,5)),int(round(cfg["min_conf"]/5)*5),"a_conf")
    st.caption("Los precios están en centavos por contrato. El bot solo entra cuando cumple todos los filtros.")

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
    plan=martingale_plan(capital,int(levels) if martingale_on else 1,float(multiplier) if martingale_on else 1.0)
    bal=st.session_state.kalshi_balance
    bal_text=f"${bal:,.2f}" if bal is not None else "sin conectar"
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
    c1,c2,c3=st.columns([1.2,1,1.25])
    if c1.button("RESTAURAR",use_container_width=True):
        save_auto_config(_auto_default_config()); st.rerun()
    if c2.button("CANCELAR",use_container_width=True):
        st.query_params["page"]="signal"; st.rerun()
    if c3.button("GUARDAR CAMBIOS",type="primary",use_container_width=True):
        if new_cfg["min_price"]>new_cfg["max_price"]: st.error("El precio mínimo no puede ser mayor que el máximo.")
        elif new_cfg["reserve"]>=new_cfg["capital"]: st.error("La reserva debe ser menor que el capital autorizado.")
        elif new_cfg["mode"]=="REAL": st.error("REAL continúa bloqueado por seguridad; guarda primero en SIMULACIÓN.")
        else:
            save_auto_config(new_cfg); st.session_state.auto_config=new_cfg
            st.success("Configuración guardada. Auto Trading conservará estos ajustes al salir de esta pantalla.")

    st.markdown('<div class="auto-section">ESTADO</div>',unsafe_allow_html=True)
    saved=load_auto_config()
    if saved["enabled"]: st.success(f'Auto Trading ENCENDIDO · {saved["mode"]}')
    else: st.info("Auto Trading apagado.")
    st.markdown('<div class="auto-section">COMPRAS / ÓRDENES</div>',unsafe_allow_html=True)
    orders=load_auto_orders(100)
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

    round_signal = process_round_signal(
        ticker, sig, market, seconds_left
    )

    # Cinta live de segundos para el Lector de Cierre.
    update_micro_tape(ticker, live_btc_price)
    micro = micro_reading()
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
        pre_note = "Sin inclinación temprana suficiente. La preseñal sigue observando."
        pre_label = "NEUTRAL"

    pre_badge = "CONFIRMADA" if active in ("UP", "DOWN") and pre_direction == active else "NO CONFIRMADA"

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

  {whale_html}

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


# Inicia una sola vez el registrador autónomo de 12 horas.
start_12h_history_worker()

page = str(st.query_params.get("page", "signal"))
if page == "settings":
    render_history_page()
elif page == "auto":
    render_auto_trading_page()
else:
    live_dashboard()
