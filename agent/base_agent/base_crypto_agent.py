"""Crypto-focused agent built on top of BaseAgent."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from langchain.agents import create_agent

from agent.base_agent.base_agent import BaseAgent
from prompts.agent_prompt import STOP_SIGNAL
from prompts.crypto_agent_prompt import get_crypto_agent_system_prompt
from tools.crypto.price_tools import snapshot_history
from tools.crypto.position_tools import add_no_trade_record as add_crypto_no_trade_record
from tools.general_tools import (
    extract_conversation,
    extract_tool_messages,
    get_config_value,
    write_config_value,
)


class BaseCryptoAgent(BaseAgent):
    DEFAULT_SYMBOLS = ["BTC"]

    def __init__(
        self,
        signature: str,
        basemodel: str,
        *,
        crypto_pair: str = os.getenv("CRYPTO_PAIR", "BTC/USDT"),
        history_limit: int = int(os.getenv("CRYPTO_HISTORY_LIMIT", "365")),
        timeframe: str = os.getenv("CRYPTO_TIMEFRAME", "1d"),
        **kwargs,
    ) -> None:
        stock_symbols = kwargs.pop("stock_symbols", None) or self.DEFAULT_SYMBOLS
        super().__init__(
            signature=signature,
            basemodel=basemodel,
            stock_symbols=stock_symbols,
            **kwargs,
        )
        self.crypto_pair = crypto_pair
        self.history_limit = history_limit
        self.timeframe = timeframe

    def _get_default_mcp_config(self) -> Dict[str, Dict[str, Any]]:
        config = super()._get_default_mcp_config()
        config.update(
            {
                "crypto_price": {
                    "transport": "streamable_http",
                    "url": f"http://localhost:{os.getenv('CRYPTO_PRICE_HTTP_PORT', '8011')}/mcp",
                },
                "crypto_trade": {
                    "transport": "streamable_http",
                    "url": f"http://localhost:{os.getenv('CRYPTO_TRADE_HTTP_PORT', '8010')}/mcp",
                },
            }
        )
        return config

    async def initialize(self) -> None:
        await super().initialize()
        # Prime history cache for prompts/tools
        snapshot_history(symbol=self.crypto_pair, timeframe=self.timeframe, limit=self.history_limit)

    async def run_trading_session(self, today_date: str) -> None:
        print(f"📈 Starting BTC session: {today_date}")
        log_file = self._setup_logging(today_date)
        write_config_value("LOG_FILE", log_file)
        self.agent = create_agent(
            self.model,
            tools=self.tools,
            system_prompt=get_crypto_agent_system_prompt(today_date, self.signature),
        )

        user_query = [
            {"role": "user", "content": f"Review BTC portfolio and update actions for {today_date}."}
        ]
        message = user_query.copy()
        self._log_message(log_file, user_query)

        current_step = 0
        while current_step < self.max_steps:
            current_step += 1
            print(f"🔄 Step {current_step}/{self.max_steps}")
            try:
                response = await self._ainvoke_with_retry(message)
                agent_response = extract_conversation(response, "final") or ""

                if STOP_SIGNAL in agent_response:
                    print("✅ Received stop signal (crypto)")
                    self._log_message(log_file, [{"role": "assistant", "content": agent_response}])
                    break

                tool_msgs = extract_tool_messages(response)
                tool_response = "\n".join([msg.content for msg in tool_msgs if getattr(msg, "content", None)])

                new_messages = [
                    {"role": "assistant", "content": agent_response},
                    {"role": "user", "content": f"Tool results: {tool_response}"},
                ]
                message.extend(new_messages)
                self._log_message(log_file, new_messages[0])
                self._log_message(log_file, new_messages[1])
            except Exception as exc:
                print(f"❌ Crypto trading error: {exc}")
                raise

        await self._handle_trading_result(today_date)

    async def _handle_trading_result(self, today_date: str) -> None:
        if get_config_value("IF_TRADE"):
            write_config_value("IF_TRADE", False)
            print("✅ BTC trading completed")
        else:
            print("📊 No BTC trades, carrying positions")
            add_crypto_no_trade_record(today_date, self.signature)

    def get_trading_dates(self, init_date: str, end_date: str) -> List[str]:
        if not os.path.exists(self.position_file):
            self.register_agent()
            start = datetime.strptime(init_date, "%Y-%m-%d")
        else:
            last_record_date = init_date
            with open(self.position_file, "r", encoding="utf-8") as fin:
                for line in fin:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    last_record_date = record.get("date", last_record_date)
            start = datetime.strptime(last_record_date, "%Y-%m-%d")

        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        dates: List[str] = []
        current = start + timedelta(days=1)
        while current <= end_dt:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        return dates
