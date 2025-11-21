import os
import sys
import json
import fcntl
from pathlib import Path
from typing import Any, Dict

from fastmcp import FastMCP

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.crypto.ccxt_client import execute_order, get_last_price
from tools.crypto.position_tools import get_latest_position
from tools.general_tools import get_config_value, write_config_value

mcp = FastMCP("CryptoTradeTools")
BASE_SYMBOL = os.getenv("CRYPTO_BASE_SYMBOL", "BTC").upper()


def _position_lock(signature: str):
    class _Lock:
        def __init__(self, name: str):
            base_dir = Path(project_root) / "data" / "agent_data" / name
            base_dir.mkdir(parents=True, exist_ok=True)
            self.lock_path = base_dir / ".position.lock"
            self._fh = open(self.lock_path, "a+")

        def __enter__(self):
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
            return self

        def __exit__(self, exc_type, exc, tb):
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()

    return _Lock(signature)


def _position_file(signature: str) -> Path:
    return Path(project_root) / "data" / "agent_data" / signature / "position" / "position.jsonl"


def _ensure_symbol(position: Dict[str, float]) -> None:
    position.setdefault(BASE_SYMBOL, 0.0)
    position.setdefault("CASH", 0.0)


def _append_record(signature: str, payload: Dict[str, Any]) -> None:
    file_path = _position_file(signature)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as fout:
        fout.write(json.dumps(payload) + "\n")


def _run_order(side: str, amount: float, signature: str, today_date: str, order_type: str = "market") -> Dict[str, Any]:
    with _position_lock(signature):
        positions, last_id = get_latest_position(today_date, signature)
        if not positions:
            positions = {"CASH": 0.0, BASE_SYMBOL: 0.0}
        _ensure_symbol(positions)

        px = get_last_price()  # fallback for validation
        order = execute_order(side=side, amount=amount, order_type=order_type)
        fill_price = order.get("fill_price", px)

        if side == "buy":
            cost = fill_price * amount
            cash = positions.get("CASH", 0.0) - cost
            if cash < 0:
                return {"error": "Insufficient cash for BTC buy", "required_cash": cost, "cash_available": positions.get("CASH", 0.0)}
            positions["CASH"] = cash
            positions[BASE_SYMBOL] = positions.get(BASE_SYMBOL, 0.0) + amount
        else:
            holding = positions.get(BASE_SYMBOL, 0.0)
            if holding < amount:
                return {"error": "Insufficient BTC to sell", "holding": holding, "attempted": amount}
            proceeds = fill_price * amount
            positions[BASE_SYMBOL] = holding - amount
            positions["CASH"] = positions.get("CASH", 0.0) + proceeds

        payload = {
            "date": today_date,
            "id": last_id + 1,
            "this_action": {"action": side, "symbol": BASE_SYMBOL, "amount": amount, "fill_price": fill_price},
            "positions": positions,
            "order": order,
        }
        _append_record(signature, payload)
        write_config_value("IF_TRADE", True)
        return positions


@mcp.tool()
def buy(amount: float) -> Dict[str, Any]:
    signature = get_config_value("SIGNATURE")
    today_date = get_config_value("TODAY_DATE")
    if not signature or not today_date:
        return {"error": "SIGNATURE or TODAY_DATE not set"}
    if amount <= 0:
        return {"error": "amount must be positive"}
    return _run_order("buy", amount, signature, today_date)


@mcp.tool()
def sell(amount: float) -> Dict[str, Any]:
    signature = get_config_value("SIGNATURE")
    today_date = get_config_value("TODAY_DATE")
    if not signature or not today_date:
        return {"error": "SIGNATURE or TODAY_DATE not set"}
    if amount <= 0:
        return {"error": "amount must be positive"}
    return _run_order("sell", amount, signature, today_date)


if __name__ == "__main__":
    mcp.run()
