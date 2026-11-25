---
name: check-connectors
description: Read-only check of whether the Zerodha (AZ) and Dhan (ND) broker connectors are signed in and working, or need re-authentication, before a refresh or an order run. Makes one cheap read call per broker, places and changes nothing, and tells the user exactly what to do for each. Use when the user says "check MCP", "check connectors", "/check-connectors", "do I need to re-login", or before /refresh-zerodha, /refresh-dhan, /dhan-order or /zerodha-order.
---

# check-connectors - are the broker connectors signed in? (read-only)

**Tool names.** Zerodha tools may appear as `mcp__Zerodha__*` or `mcp__claude_ai_Zerodha_Mcp__*`; Dhan tools as `mcp__dhan_mcp__*_agent_tool` or `mcp__claude_ai_dhan_mcp__*_agent_tool`. They are the same tools. If a tool's schema is not loaded, load it with ToolSearch (`select:<name>`); a ToolSearch query that contains the server name (`dhan_mcp`) also makes the harness try to reconnect with the saved sign-in.

This skill only READS. It never places, modifies or cancels anything, never logs out, and never asks the user to paste a token or code into chat.

## Steps
1. **Zerodha (AZ).**
   - `session` with `mode: "status"`: note `status`, `terminated`, `kite_session_expires_at` and `expires_at`. Kite's own session expires every day at 06:00 IST; `kite_session_expired: true` is NORMAL while the connector can refresh it, so do not call it a failure by itself.
   - Then one cheap data read to prove it works: `portfolio` with `mode: "margins"`. Result: **OK** if it returns data; **NEEDS LOGIN** if it says not authenticated / login required / session expired (then call the connector's `login` tool, show its warning and link verbatim and wait for the user: never complete a login on their behalf); **ERROR** for anything else (quote the message).
2. **Dhan (ND).**
   - If the Dhan tools are not available, run ToolSearch with the query `dhan_mcp portfolio` once. If the result says the connector was refused or needs sign-in, Dhan is **NEEDS RE-AUTH**: the user must reauthorise it in their claude.ai connector settings (this session cannot start that sign-in).
   - If the tools are available, make one cheap read: `portfolio_agent_tool` with action `funds` and payload `{}`. **OK** if it returns data; **NEEDS RE-AUTH** if it reports not logged in / token expired (call the Dhan `login` tool only if it exists and the user asks, give the link, wait; `complete_login` only if the flow itself asks for a code); **ERROR** otherwise.
3. **Report in ONE table, nothing else long:**

   | Connector | Status | What to do |
   |---|---|---|
   | Zerodha (AZ) | OK / NEEDS LOGIN / ERROR | one short phrase |
   | Dhan (ND) | OK / NEEDS RE-AUTH / ERROR | one short phrase |

   Add the IST time of the check. If both are OK, say so in one line and name the next command (`/refresh-zerodha`, `/refresh-dhan`). If one needs action, say which command is blocked until it is fixed.
4. Plugin servers that fail to connect (GitHub, Slack, Figma and similar) are NOT part of this check; do not report them unless the user asks.

## Rules
- Read-only: no order, GTT, cancel, file edit or commit.
- One read call per broker; do not pull holdings, positions or orders (that is the refresh skills' job).
- Never state how long a Dhan token lasts: report what the tools said.
- Output format: follow the user's standing rules (one small table, closing `Next step:` line).

Closing: end with the single line `Next step: <the one command or manual action>`.
