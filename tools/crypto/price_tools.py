"""ccxt-powered price helpers for BTC trading."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .ccxt_client import (
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_PAIR,
    DEFAULT_TIMEFRAME,
    fetch_ohlcv,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = PROJECT_ROOT / "data" / "crypto_history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

BASE_SYMBOL = os.getenv("CRYPTO_BASE_SYMBOL") or DEFAULT_PAIR.split("/")[0]
BASE_SYMBOL = BASE_SYMBOL.upper()


def _normalize_bars(
    *, symbol: str = DEFAULT_PAIR, timeframe: str = DEFAULT_TIMEFRAME, limit: int = DEFAULT_HISTORY_LIMIT
) -> List[Dict[str, float]]:
    ohlcv = fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
    bars: List[Dict[str, float]] = []
    for row in ohlcv:
        ts, opn, high, low, close, vol = row
        bars.append(
            {
                "date": datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
                "open": float(opn),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(vol),
                "timestamp": ts,
            }
        )
    return bars


def snapshot_history(
    *, symbol: str = DEFAULT_PAIR, timeframe: str = DEFAULT_TIMEFRAME, limit: int = DEFAULT_HISTORY_LIMIT
) -> Path:
    """Persist recent OHLCV candles to disk for debugging/prompts."""
    bars = _normalize_bars(symbol=symbol, timeframe=timeframe, limit=limit)
    filename = f"{symbol.replace('/', '_')}_{timeframe}.jsonl"
    path = HISTORY_DIR / filename
    with path.open("w", encoding="utf-8") as fout:
        for bar in bars:
            fout.write(json.dumps(bar) + "\n")
    return path


def _locate_bar(target_date: str, bars: List[Dict[str, float]]) -> Optional[Dict[str, float]]:
    for idx in range(len(bars) - 1, -1, -1):
        bar = bars[idx]
        if bar["date"] == target_date:
            return bar
    return None


def _locate_previous(target_date: str, bars: List[Dict[str, float]]) -> Optional[Dict[str, float]]:
    last_match_index = None
    for idx, bar in enumerate(bars):
        if bar["date"] == target_date:
            last_match_index = idx
            break
    if last_match_index is None:
        return None
    prev_index = max(0, last_match_index - 1)
    if bars[prev_index]["date"] == target_date and prev_index == last_match_index:
        prev_index = max(0, last_match_index - 1)
    if prev_index == last_match_index:
        return None
    return bars[prev_index]


def get_yesterday_date(today_date: str) -> str:
    today = datetime.strptime(today_date, "%Y-%m-%d")
    return (today - timedelta(days=1)).strftime("%Y-%m-%d")


def get_open_prices(today_date: str, symbol_alias: str = BASE_SYMBOL) -> Dict[str, Optional[float]]:
    bars = _normalize_bars()
    bar = _locate_bar(today_date, bars)
    if bar is None:
        return {f"{symbol_alias}_price": None}
    return {f"{symbol_alias}_price": bar["open"]}


def get_yesterday_open_and_close_price(
    today_date: str, symbol_alias: str = BASE_SYMBOL
) -> Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]]]:
    bars = _normalize_bars()
    target_bar = _locate_bar(today_date, bars)
    if target_bar is None:
        return {f"{symbol_alias}_price": None}, {f"{symbol_alias}_price": None}
    prev_bar = _locate_previous(today_date, bars)
    if prev_bar is None:
        prev_bar = target_bar
    buy = {f"{symbol_alias}_price": prev_bar["open"]}
    sell = {f"{symbol_alias}_price": prev_bar["close"]}
    return buy, sell


def get_daily_snapshot(today_date: str, symbol_alias: str = BASE_SYMBOL) -> Dict[str, Dict[str, Optional[float]]]:
    bars = _normalize_bars()
    bar = _locate_bar(today_date, bars)
    if bar is None:
        return {
            "prices": {f"{symbol_alias}_price": None},
            "ohlcv": {},
        }
    return {
        "prices": {f"{symbol_alias}_price": bar["open"]},
        "ohlcv": bar,
    }
