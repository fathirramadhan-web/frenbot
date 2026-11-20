"""Config frenbot: baca .env di folder ini atau environment variables."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    cfg = {
        "BOT_TOKEN": "",
        "ADMIN_ID": "",
        "OTP_WEBHOOK_PORT": "",
        "OTP_WEBHOOK_SECRET": "",
    }
    envfile = os.path.join(HERE, ".env")
    if os.path.exists(envfile):
        for line in open(envfile, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    for k in cfg:
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    # hosting cloud (Render/HS): port HTTP dari env PORT bila OTP_WEBHOOK_PORT tidak di-set
    if not cfg.get("OTP_WEBHOOK_PORT") and os.environ.get("PORT"):
        cfg["OTP_WEBHOOK_PORT"] = os.environ["PORT"]
    return cfg
