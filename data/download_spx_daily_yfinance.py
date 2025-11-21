"""Download historical S&P 500 (SPX) daily data with yfinance and store as CSV.

Example:
    python data/download_spx_daily_yfinance.py --ticker ^GSPC --period max
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch SPX daily data via yfinance and save to CSV."
    )
    parser.add_argument(
        "--ticker",
        default="^GSPC",
        help="Ticker to download (default: ^GSPC)",
    )
    parser.add_argument(
        "--period",
        default="max",
        help="yfinance period (default: max). Ignored when --start is provided.",
    )
    parser.add_argument(
        "--interval",
        default="1d",
        help="yfinance interval (default: 1d)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Optional start date YYYY-MM-DD. Overrides --period when set.",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="Optional end date YYYY-MM-DD.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "spx_daily_yfinance.csv",
        help="Output CSV path (default: data/spx_daily_yfinance.csv)",
    )
    return parser.parse_args()


def fetch_daily_bars(
    ticker: str,
    period: str,
    interval: str,
    start: Optional[str],
    end: Optional[str],
) -> pd.DataFrame:
    if start:
        data = yf.download(ticker, start=start, end=end, interval=interval, progress=False)
    else:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
    if data.empty:
        raise ValueError("No data returned from yfinance; check ticker or date range.")
    return data


def write_csv(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = df.reset_index()  # Ensure the date index becomes a column
    df.rename(columns={"Date": "date"}, inplace=True)
    # Align with common OHLCV naming
    df.to_csv(output_path, index=False)


def main() -> None:
    args = parse_args()
    bars = fetch_daily_bars(args.ticker, args.period, args.interval, args.start, args.end)
    write_csv(bars, args.output)
    print(f"Saved {len(bars)} rows to {args.output}")


if __name__ == "__main__":
    main()
