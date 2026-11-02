"""Prueba independiente, sin conexión al bot ni órdenes.

Uso: python ut_bot_prueba_1m_3m.py velas.csv --as-of 2026-11-02T01:15:00Z
CSV: time,open,high,low,close,volume (time = apertura UTC ISO o Unix segundos).
Una sola fuente BTC/USD y velas normales; no Heikin Ashi.
Salida: JSON con estados UT en 1m y 3m, alertas y coincidencia experimental.
No equivale a una predicción de cierre Kalshi ni calcula probabilidad de acierto.

Referencia: UT Bot Alerts, QuantNomad, Pine v4 (2020-02-08):
https://www.tradingview.com/script/n8ss8BID-UT-Bot-Alerts/
Adaptación de su ATR/Wilder y trailing stop; confirmar paridad con TradingView
usando mismo proveedor, velas, historial y ajustes antes de integrar.
La combinación 1m/3m es experimental y NO forma parte del script original.
El arranque de un historial truncado puede producir diferencias iniciales.
"""
import argparse
import bisect
import csv
import json
import math
from datetime import datetime, timezone


def timestamp(value):
    try:
        return int(float(value))
    except ValueError:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError('Las fechas deben incluir zona horaria.')
        return int(dt.timestamp())


def validate(rows):
    rows = sorted(rows, key=lambda r: r['time'])
    for i, r in enumerate(rows):
        if r['time'] % 60:
            raise ValueError('La apertura debe estar alineada al minuto UTC.')
        if not all(math.isfinite(r[k]) for k in ('open','high','low','close','volume')):
            raise ValueError('Hay datos no finitos.')
        if min(r[k] for k in ('open','high','low','close')) <= 0 or r['volume'] < 0:
            raise ValueError('Precio o volumen inválido.')
        if r['high'] < max(r['open'],r['close'],r['low']) or r['low'] > min(r['open'],r['close'],r['high']):
            raise ValueError('OHLC inconsistente.')
        if i and r['time'] - rows[i-1]['time'] != 60:
            raise ValueError('Minutos faltantes o duplicados; no se interpolan.')
    return rows


def aggregate(rows, minutes, as_of):
    groups = {}
    width = minutes * 60
    for r in rows:
        if r['time'] + 60 <= as_of:
            groups.setdefault(r['time'] // width * width, []).append(r)
    out = []
    for start, group in sorted(groups.items()):
        if len(group) != minutes or start + width > as_of:
            continue
        if [r['time'] for r in group] != list(range(start, start+width, 60)):
            continue
        out.append(dict(time=start, available_at=start+width,
                        open=group[0]['open'], close=group[-1]['close'],
                        high=max(r['high'] for r in group),
                        low=min(r['low'] for r in group),
                        volume=sum(r['volume'] for r in group)))
    return out


def ut(rows, sensitivity=1.0, period=10):
    if sensitivity <= 0 or period < 1:
        raise ValueError('Sensibilidad y período deben ser positivos.')
    out, trs = [], []
    atr, previous_close, previous_stop = None, None, None
    for r in rows:
        close = r['close']
        tr = r['high'] - r['low']
        if previous_close is not None:
            tr = max(tr, abs(r['high']-previous_close), abs(r['low']-previous_close))
        trs.append(tr)
        if atr is None and len(trs) >= period:
            atr = sum(trs[-period:]) / period
        elif atr is not None:
            atr = (atr*(period-1)+tr)/period
        stop, alert, direction = None, None, 'SIN_DATOS'
        if atr is not None:
            # Pine nz(previous stop, 0), including the first initialized ATR.
            old = previous_stop if previous_stop is not None else 0.0
            distance = sensitivity * atr
            if close > old and previous_close is not None and previous_close > old:
                stop = max(old, close-distance)
            elif close < old and previous_close is not None and previous_close < old:
                stop = min(old, close+distance)
            else:
                stop = close-distance if close > old else close+distance
            direction = 'UP' if close > stop else 'DOWN' if close < stop else 'NEUTRAL'
            # EMA(src, 1) == src. A label is a crossing event, not every bar.
            if previous_stop is not None:
                if close > stop and previous_close <= previous_stop:
                    alert = 'BUY'
                elif close < stop and previous_close >= previous_stop:
                    alert = 'SELL'
        out.append({**r, 'atr':atr, 'stop':stop, 'direction':direction, 'alert':alert})
        previous_close, previous_stop = close, stop
    return out


def compare(rows, as_of, sensitivity=1.0, period=10):
    rows = validate(rows)
    one = ut(aggregate(rows,1,as_of),sensitivity,period)
    three = ut(aggregate(rows,3,as_of),sensitivity,period)
    if not one or not three:
        raise ValueError('No hay suficientes velas cerradas.')
    keys = [r['available_at'] for r in three]
    timeline = []
    for fast in one:
        i = bisect.bisect_right(keys, fast['available_at'])-1
        if i < 0:
            continue
        slow = three[i]
        a,b = fast['direction'], slow['direction']
        status = 'SIN_CONFIRMAR'
        if a in ('UP','DOWN') and b in ('UP','DOWN'):
            status = 'COINCIDEN_'+a if a == b else 'POSIBLE_RETROCESO_CONTRA_'+b
        timeline.append(dict(available_at=fast['available_at'], one=a, three=b,
                             alert_1m=fast['alert'], status=status))
    return dict(experimental=True, orders=False, heikin_ashi=False,
                sensitivity=sensitivity, atr_period=period,
                last_1m=one[-1], last_3m=three[-1],
                latest=timeline[-1] if timeline else None,
                note='Coincidencia no significa probabilidad de acierto ni resultado Kalshi.',
                recent=timeline[-20:])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('csv_file')
    p.add_argument('--as-of', required=True, help='Momento de corte UTC; excluye velas abiertas.')
    p.add_argument('--sensitivity',type=float,default=1)
    p.add_argument('--atr-period',type=int,default=10)
    args = p.parse_args()
    with open(args.csv_file, newline='', encoding='utf-8-sig') as f:
        rows = [{**{k:float(r[k]) for k in ('open','high','low','close','volume')},
                 'time':timestamp(r['time'])} for r in csv.DictReader(f)]
    print(json.dumps(compare(rows,timestamp(args.as_of),args.sensitivity,args.atr_period),
                     ensure_ascii=False,indent=2,allow_nan=False))


if __name__ == '__main__':
    main()
