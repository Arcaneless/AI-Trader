"""Download daily Bitcoin OHLCV data with ccxt and store it as CSV in the data folder.

Example:
    python data/download_btc_daily_ccxt.py --exchange binance --symbol BTC/USDT --limit 1000
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import List

import ccxt  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch daily BTC data via ccxt and save to CSV.")
    parser.add_argument(
        "--exchange",
        default="binance",
        help="ccxt exchange id to use (default: binance)",
    )
    parser.add_argument(
        "--symbol",
        default="BTC/USDT",
        help="Trading pair to fetch (default: BTC/USDT)",
    )
    parser.add_argument(
        "--timeframe",
        default="1d",
        help="ccxt timeframe (default: 1d)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Number of candles to fetch (default: 1000, subject to exchange limits)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "btc_daily_ccxt.csv",
        help="Output CSV path (default: data/btc_daily_ccxt.csv)",
    )
    return parser.parse_args()


def build_exchange(exchange_id: str) -> ccxt.Exchange:
    if not hasattr(ccxt, exchange_id):
        raise ValueError(f"Exchange '{exchange_id}' is not supported by ccxt.")
    exchange_cls = getattr(ccxt, exchange_id)
    exchange: ccxt.Exchange = exchange_cls({"enableRateLimit": True})
    # Preload markets for symbols that require it.
    try:
        exchange.load_markets()
    except Exception:
        pass
    return exchange


def fetch_daily_bars(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    limit: int,
) -> List[List[float]]:
    return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)


def write_csv(rows: List[List[float]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fout:
        writer = csv.writer(fout)
        writer.writerow(["timestamp_ms", "date_utc", "open", "high", "low", "close", "volume"])
        for ts, opn, high, low, close, vol in rows:
            date_utc = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            writer.writerow([int(ts), date_utc, opn, high, low, close, vol])


def main() -> None:
    args = parse_args()
    exchange = build_exchange(args.exchange.lower())
    bars = fetch_daily_bars(exchange, args.symbol.upper(), args.timeframe, args.limit)
    write_csv(bars, args.output)
    print(f"Saved {len(bars)} rows to {args.output}")


if __name__ == "__main__":
    main()
