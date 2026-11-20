"""frenbot - Smartfren via Telegram Bot / CLI / MCP.

Pemakaian:
    python frenbot.py --bot     # bot Telegram (butuh .env: BOT_TOKEN, ADMIN_ID)
    python frenbot.py --cli     # menu interaktif di terminal
    python frenbot.py --mcp     # MCP server stdio untuk AI agent

Opsional auto re-login: OTP_WEBHOOK_PORT + OTP_WEBHOOK_SECRET di .env,
arahkan SMS forwarder ke http://host:PORT/api/otp (header X-Webhook-Secret).
"""
import argparse
import sys

import config
from otpwebhook import OtpListener


def main():
    ap = argparse.ArgumentParser(description="frenbot - Smartfren Telegram/CLI/MCP")
    ap.add_argument("--bot", action="store_true")
    ap.add_argument("--cli", action="store_true")
    ap.add_argument("--mcp", action="store_true")
    args = ap.parse_args()
    cfg = config.load()

    listener = None
    if cfg.get("OTP_WEBHOOK_PORT"):
        listener = OtpListener(int(cfg["OTP_WEBHOOK_PORT"]), cfg.get("OTP_WEBHOOK_SECRET", "")).start()
        print("[frenbot] webhook OTP di port", cfg["OTP_WEBHOOK_PORT"], file=sys.stderr)

    if args.mcp:
        import mcp
        mcp.main(listener)
    elif args.cli:
        import cli
        cli.main(listener)
    elif args.bot:
        if not cfg.get("BOT_TOKEN") or not cfg.get("ADMIN_ID"):
            print("Isi BOT_TOKEN dan ADMIN_ID di .env dulu (lihat .env.example).")
            sys.exit(1)
        import bot
        bot.Bot(cfg["BOT_TOKEN"], cfg["ADMIN_ID"], listener).run()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
