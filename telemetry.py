"""
Telegram Mobile Telemetry Engine for Aegis-Weltrade.
Dispatches non-blocking alerts for order fills, Break-Even ratchets,
profit-locking trails, trade exits, and risk kill-switches.
"""

import logging
import threading
from typing import Optional
import config

logger = logging.getLogger("AegisBTC.Telemetry")

try:
    import requests
except ImportError:
    requests = None


def _post_telegram_message(text: str, token: str, chat_id: str):
    """Internal HTTP worker to dispatch Telegram messages without blocking."""
    if not requests or not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        res = requests.post(url, json=payload, timeout=4.0)
        if res.status_code != 200:
            logger.warning(f"[TELEGRAM ALERT FAILED] HTTP {res.status_code}: {res.text}")
    except Exception as e:
        logger.warning(f"[TELEGRAM ALERT EXCEPTION] {e}")


def send_telegram_alert(message: str, blocking: bool = False) -> bool:
    """
    Dispatch Telegram notification to user's mobile device.
    Runs asynchronously in a daemon thread so it never delays execution.
    """
    token = getattr(config, "TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = getattr(config, "TELEGRAM_CHAT_ID", "").strip()
    enabled = getattr(config, "ENABLE_TELEGRAM", False)

    if not enabled or not token or not chat_id:
        return False

    if blocking:
        _post_telegram_message(message, token, chat_id)
    else:
        thread = threading.Thread(
            target=_post_telegram_message,
            args=(message, token, chat_id),
            daemon=True
        )
        thread.start()

    return True


# ==============================================================================
# PRE-FORMATTED TELEMETRY ALERT HELPERS
# ==============================================================================

send_alert = send_telegram_alert


def notify_bot_started(symbol: str, lot: float, balance: float, ai_enabled: bool, profile: str = ""):
    active_prof = profile or getattr(config, "ACTIVE_MODE", "EXPANSION_M5")
    msg = (
        f"🟢 <b>Aegis Multi-Profile Engine Online [{active_prof}]</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Asset:</b> {symbol}\n"
        f"• <b>Volume:</b> {lot} Lots\n"
        f"• <b>Starting Balance:</b> ${balance:.2f}\n"
        f"• <b>AI Regime Scanner:</b> {'Active 🧠' if ai_enabled else 'Disabled'}\n"
        f"• <b>Active Profile:</b> {active_prof}\n"
        f"• <b>Risk Profile:</b> SL {config.HARD_SL_PIPS:.1f}p | TP {config.FIXED_TP_PIPS:.1f}p"
    )
    send_telegram_alert(msg)


def notify_trade_entered(ticket: int, direction: str, price: float, sl: float, tp: float, score: int, ai_conf: float):
    msg = (
        f"🚀 <b>TRADE EXECUTED: #{ticket}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Direction:</b> {direction}\n"
        f"• <b>Entry:</b> {price:.5f}\n"
        f"• <b>Hard SL:</b> {sl:.5f} (10.0 pips)\n"
        f"• <b>Take Profit:</b> {tp:.5f} (20.0 pips)\n"
        f"• <b>Confluence Score:</b> {score}%\n"
        f"• <b>AI Regime Confidence:</b> {ai_conf * 100:.1f}%"
    )
    send_telegram_alert(msg)


def notify_break_even(ticket: int, entry_price: float, current_pnl: float):
    msg = (
        f"🛡️ <b>BREAK-EVEN TRIGGERED: #{ticket}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• <b>SL Floor Ratcheted:</b> Entry ({entry_price:.5f})\n"
        f"• <b>Current Profit:</b> ${current_pnl:+.2f} (+6.0 pips)\n"
        f"• <b>Status:</b> Zero-Risk Position"
    )
    send_telegram_alert(msg)


def notify_step_ratchet(ticket: int, sl_floor: float, peak_pnl: float, server_sl: float):
    msg = (
        f"📈 <b>PROFIT LOCKED (STEP RATCHET): #{ticket}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Locked SL Floor:</b> +${sl_floor:.2f}\n"
        f"• <b>Server SL Price:</b> {server_sl:.5f}\n"
        f"• <b>Peak Profit:</b> ${peak_pnl:+.2f}"
    )
    send_telegram_alert(msg)


def notify_trade_closed(ticket: int, net_pnl: float, peak_pnl: float, runtime_sec: int, reason: str):
    icon = "💰" if net_pnl >= 0 else "🛑"
    result_text = "PROFITABLE WIN" if net_pnl >= 0 else "LOSS (QUARANTINE 10m)"
    msg = (
        f"{icon} <b>TRADE CLOSED: #{ticket} ({result_text})</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Net PnL:</b> ${net_pnl:+.2f}\n"
        f"• <b>Peak PnL:</b> ${peak_pnl:+.2f}\n"
        f"• <b>Runtime:</b> {runtime_sec}s\n"
        f"• <b>Close Reason:</b> {reason}"
    )
    send_telegram_alert(msg)


def notify_kill_switch_triggered(daily_pnl: float, limit: float):
    msg = (
        f"🚨 <b>DAILY KILL-SWITCH TRIGGERED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Daily Drawdown:</b> ${daily_pnl:+.2f}\n"
        f"• <b>Daily Loss Limit:</b> -${limit:.2f}\n"
        f"• <b>Action:</b> All trades halted for the remainder of the session to preserve capital."
    )
    send_telegram_alert(msg)
