from fastmcp import FastMCP
import os
import sys
from typing import Dict, Any

# Ensure project root on path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.crypto.price_tools import (
    BASE_SYMBOL,
    get_daily_snapshot,
    snapshot_history,
)
mcp = FastMCP("CryptoPrices")


@mcp.tool()
def get_crypto_price(date: str, symbol_alias: str = BASE_SYMBOL) -> Dict[str, Any]:
    """Return BTC daily OHLC data for the requested date (YYYY-MM-DD)."""
    payload = get_daily_snapshot(date, symbol_alias=symbol_alias)
    payload["date"] = date
    payload["symbol"] = symbol_alias
    return payload


@mcp.tool()
def sync_crypto_history(limit: int = 365) -> Dict[str, str]:
    """Force a pull of recent CCXT candles to the crypto_history folder."""
    path = snapshot_history(limit=limit)
    return {"path": str(path)}


if __name__ == "__main__":
    mcp.run()
