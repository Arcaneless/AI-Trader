"""Helpers for crypto agent position bookkeeping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

from .price_tools import get_yesterday_date

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _position_path(signature: str) -> Path:
    return PROJECT_ROOT / "data" / "agent_data" / signature / "position" / "position.jsonl"


def get_latest_position(today_date: str, signature: str) -> Tuple[Dict[str, float], int]:
    file_path = _position_path(signature)
    if not file_path.exists():
        return {}, -1

    latest_positions: Dict[str, float] = {}
    max_id_today = -1

    with file_path.open("r", encoding="utf-8") as fin:
        for line in fin:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("date") == today_date:
                rec_id = record.get("id", -1)
                if rec_id > max_id_today:
                    max_id_today = rec_id
                    latest_positions = record.get("positions", {})

    if max_id_today >= 0:
        return latest_positions, max_id_today

    prev_date = get_yesterday_date(today_date)
    latest_prev: Dict[str, float] = {}
    max_id_prev = -1
    with file_path.open("r", encoding="utf-8") as fin:
        for line in fin:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("date") == prev_date:
                rec_id = record.get("id", -1)
                if rec_id > max_id_prev:
                    max_id_prev = rec_id
                    latest_prev = record.get("positions", {})
    return latest_prev, max_id_prev


def get_today_init_position(today_date: str, signature: str) -> Dict[str, float]:
    prev_date = get_yesterday_date(today_date)
    positions, _ = get_latest_position(prev_date, signature)
    return positions


def add_no_trade_record(today_date: str, signature: str) -> None:
    positions, max_id = get_latest_position(today_date, signature)
    file_path = _position_path(signature)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": today_date,
        "id": max_id + 1,
        "this_action": {"action": "no_trade", "symbol": "", "amount": 0},
        "positions": positions,
    }
    with file_path.open("a", encoding="utf-8") as fout:
        fout.write(json.dumps(payload) + "\n")
