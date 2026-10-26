"""ALPHA POLY5 - independent 5-minute research signal engine. No trading."""
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timezone
import math
import statistics
import time

@dataclass
class Tick:
    timestamp: float
    price: float

@dataclass
class Signal:
    presignal: str = "NO TRADE"
    direction: str = "NO TRADE"
    strength: float = 0.0
    reason: str = "Esperando datos"
    age: float = 0.0

@dataclass
class Engine:
    round_id: str = ""
    ticks: deque = field(default_factory=lambda: deque(maxlen=1800))
    signal: Signal = field(default_factory=Signal)
    pending: str = ""
    pending_since: float = 0.0
    last_tick: float = 0.0
    def reset(self, round_id):
        if self.round_id != round_id:
            self.round_id = round_id
            self.ticks.clear()
            self.signal = Signal()
            self.pending = ""
            self.pending_since = 0
    def ingest(self, price, timestamp=None):
        timestamp = time.time() if timestamp is None else float(timestamp)
        price = float(price)
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Precio inválido")
        if timestamp <= self.last_tick:
            return False
        if timestamp - time.time() > 3 or time.time() - timestamp > 8:
            raise ValueError("Precio no actualizado")
        self.ticks.append(Tick(timestamp, price))
        self.last_tick = timestamp
        return True
    def candles(self, seconds=5):
        bins = {}
        for tick in self.ticks:
            bucket = int(tick.timestamp // seconds) * seconds
            if bucket not in bins:
                bins[bucket] = [tick.price]*4
            else:
                bar = bins[bucket]
                bar[1] = max(bar[1],tick.price)
                bar[2] = min(bar[2],tick.price)
                bar[3] = tick.price
        return [{"time": datetime.fromtimestamp(k,timezone.utc), "open":v[0],
                 "high":v[1],"low":v[2],"close":v[3]} for k,v in sorted(bins.items())]
    def evaluate(self, now=None):
        now = time.time() if now is None else now
        if not self.ticks or now-self.last_tick > 8:
            self.signal = Signal(reason="Datos atrasados: no operar")
            return self.signal
        ticks = list(self.ticks)
        if len(ticks) < 8 or ticks[-1].timestamp-ticks[0].timestamp < 8:
            self.signal = Signal(reason="Acumulando lecturas")
            return self.signal
        latest = ticks[-1].price
        def past(sec):
            candidates = [t.price for t in ticks if t.timestamp <= now-sec]
            return candidates[-1] if candidates else ticks[0].price
        move5 = latest-past(5)
        move15 = latest-past(15)
        move30 = latest-past(30)
        changes = [b.price-a.price for a,b in zip(ticks[-40:-1],ticks[-39:])]
        noise = max(statistics.median(abs(x) for x in changes) if changes else 0, .05)
        score = .45*math.tanh(move5/(noise*4)) + .35*math.tanh(move15/(noise*7)) + .20*math.tanh(move30/(noise*10))
        presignal = "UP" if score > .24 else "DOWN" if score < -.24 else "NO TRADE"
        # Confirmation is a short, symmetric debounce, not a direction lock.
        if presignal != self.pending:
            self.pending = presignal
            self.pending_since = now
        if now-self.pending_since >= (2 if presignal != "NO TRADE" else 3):
            direction = presignal
        else:
            direction = self.signal.direction
        self.signal = Signal(presignal,direction,round(abs(score)*100,1),
                             f"Impulso 5s: {move5:+.2f} | 15s: {move15:+.2f} | 30s: {move30:+.2f}",
                             now-self.last_tick)
        return self.signal
