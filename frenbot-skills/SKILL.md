---
name: frenbot-mcp
slug: frenbot-mcp
description: >
  Manage Smartfren quota, packages, and profile via natural language over MCP.
  Use for: logging in to Smartfren, checking pulsa/kuota, buying packages
  (pulsa/qris), and scheduling auto-buys.
version: 1.0.0
author: zakak
tags: [smartfren, mcp, bot, quota, account, provider, mobile, indonesia]
---

# Smartfren MCP Server (Frenbot)

This skill connects an AI agent to a Smartfren account using the frenbot
MCP server (Python, stdlib). The server runs from the frenbot folder (frenbot.py).

## Setup

Add the frenbot server to your MCP client configuration (mcporter, Claude
Desktop, or any MCP-capable agent):

```json
{
  "mcpServers": {
    "frenbot": {
      "command": "python",
      "args": ["/path/to/frenbot/frenbot.py", "--mcp"]
    }
  }
}
```

The server manages its own session internally (mysf_session.json), so no
environment variables are needed for MCP mode. Requires Python 3.8+;
optional segno for QRIS images.

## Available Tools

### Authentication
- login — start login with a Smartfren number (e.g. 0881xxxxxxxx). Triggers an SMS OTP.
- submit_otp — submit the OTP code received on the phone to complete login.
- logout — clear the stored session.

### Account & Quota
- get_profile — pulsa balance, masa aktif, nomor status.
- get_quota — remaining internet/voice/SMS quotas and active packages.

### Packages & Purchasing
- get_recommended_offers — list packages available for the number, with codes and prices.
- get_package_details — details of a specific package by code (price, benefits, validity).
- buy_package — purchase a package by code with payment_method "pulsa" or "qris".

### Automation
- start_auto_buy — background monitor that checks quota periodically and
  auto-purchases (via pulsa) when depleted or below a threshold_mb limit.
- auto_buy_status — check whether the monitor is running and its config.
- stop_auto_buy — stop the monitor.

## Usage Guidelines for the Agent

1. Authentication: try get_profile first — a session is usually already
   cached. If it fails because there is no session, call login, STOP and ask
   the user for the OTP received via SMS, then call submit_otp.
2. Fetching data first: always run get_profile or get_quota for general
   account/status questions.
3. Purchasing packages: run get_recommended_offers for valid codes, confirm
   price with get_package_details, then buy_package. payment_method must be
   exactly "pulsa" or "qris". Purchases use real money — confirm with the user.
4. Auto-buy: ask the user for interval (minutes), package code, and threshold
   MB. Remind them auto-buy relies on their pulsa balance.

## Notes

- Session: session_id 24 hours, refresh_token 30 days; the server refreshes
  automatically. Full auto re-login (OTP webhook) needs OTP_WEBHOOK_PORT +
  SMS forwarder; see docs/auto-relogin.md.
- QRIS purchases return a QR string/image that the user must scan manually;
  payment status is polled automatically.
- Unofficial tool for personal use on your own account; subject to
  Smartfren/XLSMART Terms of Service.
