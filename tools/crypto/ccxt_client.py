"""Lightweight ccxt helpers shared by crypto agents and tools."""

from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional

import ccxt  # type: ignore

DEFAULT_EXCHANGE = os.getenv("CRYPTO_EXCHANGE", "hyperliquid").lower()
DEFAULT_PAIR = os.getenv("CRYPTO_PAIR", "BTC/USDT").upper()
DEFAULT_TIMEFRAME = os.getenv("CRYPTO_TIMEFRAME", "1d")
DEFAULT_HISTORY_LIMIT = int(os.getenv("CRYPTO_HISTORY_LIMIT", "365"))
DEFAULT_MODE = os.getenv("CRYPTO_TRADE_MODE", "paper").lower()

_OHLCV_CACHE: Dict[str, Dict[str, Any]] = {}
_TICKER_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = int(os.getenv("CRYPTO_CACHE_TTL", "60"))


def _load_exchange_params(mode: str) -> Dict[str, Any]:
    """Build auth params per mode (paper/live) from env."""
    base_params: Dict[str, Any] = {"enableRateLimit": True}

    # Allow JSON encoded overrides for exotic exchanges (e.g., Hyperliquid routes)
    extra = os.getenv("CRYPTO_EXCHANGE_PARAMS")
    if extra:
        try:
            base_params.update(json.loads(extra))
        except json.JSONDecodeError:
            pass

    prefix = "CRYPTO_LIVE_" if mode == "live" else "CRYPTO_PAPER_"
    api_key = os.getenv(f"{prefix}API_KEY", os.getenv("CRYPTO_API_KEY"))
    api_secret = os.getenv(f"{prefix}API_SECRET", os.getenv("CRYPTO_API_SECRET"))
    password = os.getenv(f"{prefix}API_PASSWORD", os.getenv("CRYPTO_API_PASSWORD"))

    if api_key:
        base_params["apiKey"] = api_key
    if api_secret:
        base_params["secret"] = api_secret
    if password:
        base_params["password"] = password

    return base_params


@lru_cache(maxsize=4)
def _build_exchange(exchange_id: str, mode: str, sandbox: bool) -> ccxt.Exchange:
    if not hasattr(ccxt, exchange_id):
        raise ValueError(f"Exchange '{exchange_id}' not supported by ccxt build")
    exchange_cls = getattr(ccxt, exchange_id)
    params = _load_exchange_params(mode)
    exchange: ccxt.Exchange = exchange_cls(params)
    if sandbox and hasattr(exchange, "set_sandbox_mode"):
        try:
            exchange.set_sandbox_mode(True)
        except Exception:
            pass
    return exchange


def get_exchange(
    *,
    exchange_id: Optional[str] = None,
    mode: Optional[str] = None,
    sandbox: Optional[bool] = None,
) -> ccxt.Exchange:
    """Return a cached ccxt exchange instance."""
    exch = (exchange_id or DEFAULT_EXCHANGE).lower()
    trade_mode = (mode or DEFAULT_MODE).lower()
    use_sandbox = sandbox if sandbox is not None else trade_mode != "live"
    return _build_exchange(exch, trade_mode, use_sandbox)


def _cache_key(symbol: str, timeframe: str, limit: int) -> str:
    return f"{symbol}:{timeframe}:{limit}"


def fetch_ohlcv(
    *,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    limit: Optional[int] = None,
    mode: Optional[str] = None,
) -> List[List[float]]:
    """Fetch OHLCV data with a small in-memory cache."""
    pair = (symbol or DEFAULT_PAIR).upper()
    frame = timeframe or DEFAULT_TIMEFRAME
    bars = limit or DEFAULT_HISTORY_LIMIT
    cache_id = _cache_key(pair, frame, bars)
    cached = _OHLCV_CACHE.get(cache_id)
    now = time.time()
    if cached and now - cached["ts"] < _CACHE_TTL:
        return cached["data"]

    exchange = get_exchange(mode=mode)
    data = exchange.fetch_ohlcv(pair, frame, limit=bars)
    _OHLCV_CACHE[cache_id] = {"ts": now, "data": data}
    return data


def fetch_ticker(*, symbol: Optional[str] = None, mode: Optional[str] = None) -> Dict[str, Any]:
    pair = (symbol or DEFAULT_PAIR).upper()
    cache_id = pair
    now = time.time()
    cached = _TICKER_CACHE.get(cache_id)
    if cached and now - cached["ts"] < _CACHE_TTL:
        return cached["data"]
    exchange = get_exchange(mode=mode)
    ticker = exchange.fetch_ticker(pair)
    _TICKER_CACHE[cache_id] = {"ts": now, "data": ticker}
    return ticker


def get_last_price(*, symbol: Optional[str] = None, mode: Optional[str] = None) -> float:
    ticker = fetch_ticker(symbol=symbol, mode=mode)
    price = ticker.get("last") or ticker.get("close") or ticker.get("info", {}).get("lastPrice")
    if price is None:
        raise RuntimeError(f"No last price found for {symbol or DEFAULT_PAIR}")
    return float(price)


def execute_order(
    *,
    side: str,
    amount: float,
    symbol: Optional[str] = None,
    order_type: str = "market",
    price: Optional[float] = None,
    mode: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Route an order through ccxt or simulate if in paper mode."""
    pair = (symbol or DEFAULT_PAIR).upper()
    trade_mode = (mode or DEFAULT_MODE).lower()
    px = price
    if px is None:
        px = get_last_price(symbol=pair, mode=trade_mode)
    if trade_mode != "live":
        return {
            "mode": "paper",
            "symbol": pair,
            "side": side,
            "amount": amount,
            "fill_price": px,
            "order_type": order_type,
            "timestamp": time.time(),
        }

    exchange = get_exchange(mode=trade_mode, sandbox=False)
    order = exchange.create_order(pair, order_type, side, amount, price, params or {})
    return {
        "mode": "live",
        "symbol": pair,
        "side": side,
        "amount": amount,
        "order": order,
    }
