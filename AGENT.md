# 🤖 Agent System Overview

This note describes how the AI-Trader agent layer is wired together and how to extend it. It focuses on the code paths that instantiate `BaseAgent` and `BaseAgent_Hour`, the runtime artefacts they create, and the configuration knobs you can adjust.

## Key Modules
- `main.py` – entrypoint that loads configs, resolves the agent type via `AGENT_REGISTRY`, and drives each enabled model through the full trading range.
- `agent/base_agent/base_agent.py` – core implementation that manages MCP tool connections, model orchestration, trading loops, and persistence of position data.
- `agent/base_agent/base_agent_hour.py` – subclass that reuses the base logic but expects hour-level timestamps sourced from `data/merged.jsonl`.
- `prompts/agent_prompt.py` – builds the system prompt (including positions and prices) that is passed into LangChain’s `create_agent`.
- `tools/general_tools.py` – lightweight runtime configuration store that keeps per-run state such as `TODAY_DATE`, `IF_TRADE`, and `LOG_FILE`.

## Lifecycle at a Glance
1. **Configuration load** – `main.load_config()` reads `configs/*.json` (or a user-supplied path). Environment variables such as `INIT_DATE` and `END_DATE` can override the file.
2. **Agent class selection** – `AGENT_REGISTRY` maps friendly names to import paths. Adding a new agent requires registering it here.
3. **Instance creation** – Each enabled model in the config spawns an agent instance with its own signature, base model ID, and runtime env file (`data/agent_data/<signature>/.runtime_env.json`).
4. **Initialization** – `BaseAgent.initialize()` loads `.env`, creates a `MultiServerMCPClient`, fetches available tools, and sets up `ChatOpenAI` with retry and timeout defaults.
5. **Daily (or hourly) execution** – `run_date_range()` derives trading days via `get_trading_dates()`, writes `TODAY_DATE`, and delegates to `run_with_retry()` which wraps `run_trading_session()`.
6. **Trading loop** – For each session the agent:
   - builds a log file under `data/agent_data/<signature>/log/<date>/log.jsonl`;
   - seeds the conversation with a user prompt asking for position updates;
   - iteratively calls LangChain’s agent until a `<FINISH_SIGNAL>` is emitted or `max_steps` is reached;
   - retransmits tool outputs back into the conversation and logs every exchange.
7. **Post-processing** – `_handle_trading_result()` toggles `IF_TRADE` and, if nothing was traded, records a "no trade" entry via `tools.price_tools.add_no_trade_record()`.

## Configuration Surface
- **Agent registry** (`main.py`, `main_parrallel.py`): map new agent names to their module/class pair.
- **Config files** (`configs/default_config.json`): define `agent_type`, the trading `date_range`, and per-model overrides (signature, base model, optional OpenAI endpoint/auth).
- **Agent defaults** (`BaseAgent.__init__`):
  - `DEFAULT_STOCK_SYMBOLS`: NASDAQ-100 tickers used to pre-populate positions.
  - `max_steps`, `max_retries`, `base_delay`: govern the reasoning loop.
  - `initial_cash`, `init_date`: seed values for the first `position.jsonl` record.
  - `_get_default_mcp_config()`: HTTP endpoints for `math`, `stock_local`, `search`, and `trade` MCP servers. Ports fall back to `.env` keys such as `MATH_HTTP_PORT`.

### Runtime State
- `write_config_value()` persists lightweight run-time keys into `.runtime_env.json`.
- `register_agent()` builds `data/agent_data/<signature>/position/position.jsonl` on first run, injecting `DEFAULT_STOCK_SYMBOLS` plus a `CASH` bucket.
- The logging path is customisable through `log_config.log_path` in the config file.

## Extending the Agent Layer
1. Implement a new agent class (inherit from `BaseAgent` wherever possible to reuse logging, retries, and position handling).
2. Add the class to `AGENT_REGISTRY` so `main.py` can import it dynamically.
3. Create a configuration file that selects the new agent via `agent_type` and enables at least one model.
4. If your agent requires extra MCP tools or prompt context, update `_get_default_mcp_config()` or `prompts/agent_prompt.py` accordingly.

## Troubleshooting
- **Missing API key** – `initialize()` raises a `ValueError` when `OPENAI_API_KEY` is absent. Confirm your `.env` or per-model config supplies credentials.
- **No MCP tools loaded** – The client prints a warning if `MultiServerMCPClient.get_tools()` returns nothing. Start the servers with `python agent_tools/start_mcp_services.py` and verify ports in the `.env`.
- **Position file already exists** – `register_agent()` skips creation if `position.jsonl` is present. Delete or move stale files when re-seeding a signature.
- **Hour-level backtests** – Use `BaseAgent_Hour` with timestamps formatted as `YYYY-MM-DD HH:MM:SS`; the base agent only supports day-level iteration.

## Reference Snippets
```jsonc
// configs/default_config.json
{
  "agent_type": "BaseAgent",
  "date_range": {
    "init_date": "2025-10-01",
    "end_date": "2025-10-21"
  },
  "models": [
    {
      "name": "gpt-5",
      "basemodel": "openai/gpt-5",
      "signature": "gpt-5",
      "enabled": true
    }
  ],
  "agent_config": {
    "max_steps": 30,
    "max_retries": 3,
    "base_delay": 1.0,
    "initial_cash": 10000.0
  }
}
```

```python
# agent/base_agent/base_agent.py
self.agent = create_agent(
    self.model,
    tools=self.tools,
    system_prompt=get_agent_system_prompt(today_date, self.signature),
)
```

Use this document as a jumping-off point when wiring new strategies or diagnosing run-time issues in the agent layer.
