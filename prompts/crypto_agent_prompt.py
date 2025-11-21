import os
from typing import Dict

from prompts.agent_prompt import STOP_SIGNAL
from tools.crypto.price_tools import (
    BASE_SYMBOL,
    get_open_prices,
    get_yesterday_open_and_close_price,
)
from tools.crypto.position_tools import get_today_init_position

CRYPTO_AGENT_SYSTEM_PROMPT = """
You are a dedicated BTC discretionary trading assistant.

Objectives:
- Review current BTC holdings and cash, using the ccxt-backed history that has been provided.
- Reason about the latest BTC/USDT prices, yesterday's close, and intraday context before acting.
- When taking action, call the available MCP trade tools rather than emitting instructions.
- Default to paper-trade sizing unless explicitly told the run is live.

You must show the steps you take:
1. Summarize yesterday's portfolio value and pricing context.
2. Identify if new information (news, macro, momentum) justifies trades.
3. Decide on buy/sell/hold and call the proper tool with explicit size.

Inputs for {date}:
- Current positions: {positions}
- Yesterday's BTC open/close (UTC): {yesterday_close_price}
- Today's indicative buy price: {today_buy_price}

If you believe no trade is needed, explain why. When done, emit {STOP_SIGNAL} on its own line.
"""


def get_crypto_agent_system_prompt(today_date: str, signature: str) -> str:
    yesterday_buy, yesterday_sell = get_yesterday_open_and_close_price(today_date, symbol_alias=BASE_SYMBOL)
    today_buy = get_open_prices(today_date, symbol_alias=BASE_SYMBOL)
    positions = get_today_init_position(today_date, signature) or {"CASH": 0.0, BASE_SYMBOL: 0.0}
    return CRYPTO_AGENT_SYSTEM_PROMPT.format(
        date=today_date,
        positions=positions,
        yesterday_close_price=yesterday_sell,
        today_buy_price=today_buy,
        STOP_SIGNAL=STOP_SIGNAL,
    )
