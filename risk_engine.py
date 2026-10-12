"""
Risk Engine & Safety Safeguards for Aegis Multi-Profile Engine.
Handles:
1. Magic-number position concurrency lock
2. Delayed Break-Even ratchet (SL to entry price)
3. Step-Ratchet trailing stop loss
4. Stagnation time-stop (exits stagnant trade at profit >= 0)
5. Rollover & weekend blackout guards
6. Daily drawdown circuit breaker & post-trade loss quarantine
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
import config
from telemetry import send_alert

logger = logging.getLogger("AegisBTC.RiskEngine")


class RiskEngine:
    """
    Profile-Driven Risk and Position Manager.
    All safeguards dynamically read parameters from the active profile via config.
    """
    def __init__(self, bridge=None):
        self.bridge = bridge
        self.active_ticket: Optional[int] = None
        self.entry_price: float = 0.0
        self.entry_time: float = 0.0
        self.direction: str = ""
        self.lot_size: float = config.LOT_SIZE
        self.magic_number: int = config.MAGIC_NUMBER
        self.peak_pnl_pips: float = 0.0
        self.current_sl_price: float = 0.0
        self.is_be_activated: bool = False
        self.last_ratchet_level_pips: float = 0.0

        # Account & Daily Circuit Breaker
        self.daily_pnl_usd: float = 0.0
        self.consecutive_losses: int = 0
        self.is_kill_switch_active: bool = False
        self.last_trade_close_time: float = 0.0
        self.last_trade_was_loss: bool = False

    def is_blackout_active(self, dt: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Check if market execution is blocked by rollover or weekend blackout in CAT (UTC+2).
        """
        if dt is None:
            dt = datetime.now(timezone.utc) + timedelta(hours=2)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc) + timedelta(hours=2)
        else:
            dt = dt.astimezone(timezone(timedelta(hours=2)))

        time_str = dt.strftime("%H:%M")
        weekday = dt.weekday()  # Monday=0, Friday=4, Saturday=5, Sunday=6

        # Weekend blackout (Friday 21:00 CAT through Sunday)
        if weekday == 4 and time_str >= config.FRIDAY_CLOSE_TIME:
            return True, f"Weekend blackout active (Friday after {config.FRIDAY_CLOSE_TIME} CAT)"
        if weekday in (5, 6):
            return True, "Weekend market closed"

        # Rollover spread spike window (22:45 to 00:30 CAT)
        if config.ROLLOVER_START <= time_str or time_str < config.ROLLOVER_END:
            return True, f"Daily rollover blackout active ({config.ROLLOVER_START} to {config.ROLLOVER_END} CAT)"

        return False, "Market execution allowed"

    def is_execution_allowed(self) -> Tuple[bool, str]:
        """Verify whether the engine is allowed to evaluate new setups."""
        if self.is_kill_switch_active:
            return False, f"Daily Kill Switch Active (Max Daily Loss: -${config.MAX_DAILY_LOSS_USD:.2f})"

        # Check blackouts
        is_blackout, reason = self.is_blackout_active()
        if is_blackout:
            return False, reason

        # Check cooldown / quarantine
        now = time.time()
        elapsed = now - self.last_trade_close_time

        if self.last_trade_was_loss:
            quarantine = getattr(config, "COOLDOWN_AFTER_LOSS_SECONDS", 600)
            if elapsed < quarantine:
                remaining = int(quarantine - elapsed)
                return False, f"10-Minute Loss Quarantine Active ({remaining}s remaining)"
        else:
            cooldown = getattr(config, "COOLDOWN_SECONDS", 60)
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                return False, f"Post-Trade Cooldown Active ({remaining}s remaining)"

        return True, "Execution allowed"

    def register_position_opened(
        self,
        ticket: int,
        direction: str,
        entry_price: float,
        lot_size: float = config.LOT_SIZE,
        initial_sl: float = 0.0
    ):
        """Track newly executed position."""
        self.active_ticket = ticket
        self.direction = direction.upper()
        self.entry_price = entry_price
        self.entry_time = time.time()
        self.lot_size = lot_size
        self.magic_number = config.MAGIC_NUMBER
        self.peak_pnl_pips = 0.0
        self.current_sl_price = initial_sl
        self.is_be_activated = False
        self.last_ratchet_level_pips = 0.0

        logger.info(
            f"🎯 [RISK ENGINE: POSITION REGISTERED] Ticket #{ticket} | {self.direction} "
            f"| Entry: {entry_price:.5f} | Initial SL: {initial_sl:.5f} | Profile: {config.ACTIVE_MODE}"
        )

        send_alert(
            f"🚀 *TRADE ENTERED [{config.ACTIVE_MODE}]*\n"
            f"• Ticket: `#{ticket}`\n"
            f"• Direction: *{self.direction}*\n"
            f"• Entry: `{entry_price:.5f}`\n"
            f"• Initial SL: `{initial_sl:.5f}` ({config.HARD_SL_PIPS:.1f}p)\n"
            f"• TP Target: `{config.FIXED_TP_PIPS:.1f}p`\n"
            f"• Lots: `{lot_size}`"
        )

    def manage_active_position(self, position: Any) -> Tuple[bool, str]:
        """
        Evaluates active open position against Step-Ratchet Trailing & Stagnation Time-Stop.
        Returns (should_close, reason).
        """
        if position is None:
            return False, ""

        ticket = position.ticket
        is_buy = (position.type == 0)  # mt5.ORDER_TYPE_BUY
        current_price = position.price_current
        entry_price = position.price_open
        pip_unit = 0.0001 if ("EUR" in config.SYMBOL.upper() or "USD" in config.SYMBOL.upper()) else 0.01

        # Calculate floating pnl in pips
        pnl_pips = (current_price - entry_price) / pip_unit if is_buy else (entry_price - current_price) / pip_unit
        runtime_seconds = time.time() - (self.entry_time if self.entry_time > 0 else position.time)

        if pnl_pips > self.peak_pnl_pips:
            self.peak_pnl_pips = pnl_pips

        # 1. Rollover force close at 22:30 CAT to prevent spread gap blowup
        now_cat = datetime.now(timezone.utc) + timedelta(hours=2)
        cat_time_str = now_cat.strftime("%H:%M")
        if cat_time_str >= config.FORCE_CLOSE_ROLLOVER and cat_time_str < config.ROLLOVER_END:
            return True, f"Rollover Force-Close (CAT {cat_time_str} >= {config.FORCE_CLOSE_ROLLOVER})"

        # 2. Stagnation Time-Stop Exit
        if runtime_seconds >= config.TIME_STOP_SECONDS and position.profit >= 0.0:
            return True, f"Stagnation Time-Stop triggered ({int(runtime_seconds)}s >= {config.TIME_STOP_SECONDS}s, Profit: ${position.profit:.2f})"

        # 3. Delayed Break-Even Ratchet
        be_trigger = config.BE_TRIGGER_PIPS
        if not self.is_be_activated and pnl_pips >= be_trigger:
            new_sl = entry_price  # Move SL to exact open price ($0.00 risk)
            if self.bridge and self.bridge.modify_position_sl(ticket, new_sl):
                self.is_be_activated = True
                self.current_sl_price = new_sl
                self.last_ratchet_level_pips = be_trigger
                logger.info(f"🛡️ [BREAK-EVEN ACTIVE] Ticket #{ticket} SL moved to entry {new_sl:.5f} (+{pnl_pips:.1f} pips peak)")
                send_alert(
                    f"🛡️ *BREAK-EVEN LOCKED [{config.ACTIVE_MODE}]*\n"
                    f"• Ticket: `#{ticket}`\n"
                    f"• Peak Gain: `+{pnl_pips:.1f} pips`\n"
                    f"• SL Adjusted: `{new_sl:.5f}` ($0.00 Risk)"
                )

        # 4. Step-Ratchet Trailing Stop
        if self.is_be_activated:
            step = config.TRAILING_STEP_PIPS
            if pnl_pips >= self.last_ratchet_level_pips + step:
                # Advance SL forward by step
                self.last_ratchet_level_pips += step
                ratchet_sl_pips = self.last_ratchet_level_pips - step
                new_sl = entry_price + (ratchet_sl_pips * pip_unit) if is_buy else entry_price - (ratchet_sl_pips * pip_unit)

                if self.bridge and self.bridge.modify_position_sl(ticket, new_sl):
                    self.current_sl_price = new_sl
                    logger.info(f"🪜 [STEP RATCHET] Ticket #{ticket} SL advanced to {new_sl:.5f} (Locking +{ratchet_sl_pips:.1f} pips)")
                    send_alert(
                        f"🪜 *STEP RATCHET ADVANCED [{config.ACTIVE_MODE}]*\n"
                        f"• Ticket: `#{ticket}`\n"
                        f"• Float Gain: `+{pnl_pips:.1f} pips`\n"
                        f"• Guaranteed Profit: `+{ratchet_sl_pips:.1f} pips`\n"
                        f"• New SL: `{new_sl:.5f}`"
                    )

        return False, ""

    def register_position_closed(self, pnl_usd: float, reason: str = ""):
        """Record trade close, update daily PnL, and check circuit breaker."""
        self.last_trade_close_time = time.time()
        self.daily_pnl_usd += pnl_usd
        is_loss = (pnl_usd < 0.0)
        self.last_trade_was_loss = is_loss

        if is_loss:
            self.consecutive_losses += 1
            logger.warning(
                f"🛑 [TRADE LOSS] Realized: -${abs(pnl_usd):.2f} | Consecutive Losses: {self.consecutive_losses} | "
                f"Daily PnL: ${self.daily_pnl_usd:.2f} | Reason: {reason}"
            )
        else:
            self.consecutive_losses = 0
            logger.info(
                f"🎉 [TRADE PROFIT] Realized: +${pnl_usd:.2f} | Daily PnL: ${self.daily_pnl_usd:.2f} | Reason: {reason}"
            )

        send_alert(
            f"🏁 *TRADE CLOSED [{config.ACTIVE_MODE}]*\n"
            f"• Realized PnL: `${pnl_usd:+.2f}`\n"
            f"• Cumulative Daily PnL: `${self.daily_pnl_usd:+.2f}`\n"
            f"• Close Reason: `{reason}`"
        )

        # Check Daily Drawdown Circuit Breaker
        max_daily_loss = config.MAX_DAILY_LOSS_USD
        if self.daily_pnl_usd <= -max_daily_loss:
            self.is_kill_switch_active = True
            logger.critical(
                f"🚨 [DAILY KILL-SWITCH ENGAGED] Cumulative loss ${abs(self.daily_pnl_usd):.2f} "
                f"exceeds limit ${max_daily_loss:.2f}. Halting trading for the session!"
            )
            send_alert(
                f"🚨 *DAILY KILL-SWITCH ACTIVATED [{config.ACTIVE_MODE}]*\n"
                f"• Cumulative Loss: `$-{abs(self.daily_pnl_usd):.2f}`\n"
                f"• Daily Max Threshold: `$-{max_daily_loss:.2f}`\n"
                f"• Trading halted for the rest of the day."
            )

        # Reset active tracker
        self.active_ticket = None
        self.peak_pnl_pips = 0.0
        self.is_be_activated = False
