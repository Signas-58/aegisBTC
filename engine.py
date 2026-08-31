"""
Execution & Risk Engine for Aegis-BTC.
Handles Deriv WebSocket order proposals, contract tracking, step-ratchet trailing,
native server SL handshakes, and circuit breaker quarantines.
"""

import time
import logging
from typing import Dict, Any, Optional, Tuple
import config

logger = logging.getLogger("AegisBTC.Engine")


class PositionManager:
    """
    Manages active positions, step-ratchet SL logic, PnL tracking,
    and server-side auto-close sync.
    """
    def __init__(self):
        self.active_contract_id: Optional[int] = None
        self.entry_price: float = 0.0
        self.stake: float = config.STAKE
        self.multiplier: int = config.MULTIPLIER_LEVERAGE
        self.direction: str = ""
        self.peak_pnl: float = 0.0
        self.current_sl_floor: float = -config.HARD_STOP_LOSS_USD
        self.is_open: bool = False
        self.entry_time: float = 0.0

    def open_position(self, contract_id: int, direction: str, entry_price: float):
        self.active_contract_id = contract_id
        self.direction = direction
        self.entry_price = entry_price
        self.stake = config.STAKE
        self.multiplier = config.MULTIPLIER_LEVERAGE
        self.peak_pnl = 0.0
        self.current_sl_floor = -config.HARD_STOP_LOSS_USD
        self.is_open = True
        self.entry_time = time.time()
        logger.info(
            f"[POSITION OPENED] ID: {contract_id} | Type: {direction} | "
            f"Entry: ${entry_price:.2f} | Stake: ${self.stake} | Leverage: x{self.multiplier}"
        )

    def update_pnl_and_ratchet(self, current_pnl: float) -> Tuple[bool, float, str]:
        """
        Evaluates active contract PnL against Step-Ratchet Trailing Rules:
        - At peak PnL >= +$0.50: Ratchet SL floor to $0.00 (Break-Even).
        - At peak PnL >= +$0.75: Advance SL floor in +$0.25 steps, maintaining $0.50 trailing gap.
        
        Returns (should_close_manually, updated_sl_floor, reason).
        """
        if not self.is_open:
            return False, self.current_sl_floor, "No active position"

        if current_pnl > self.peak_pnl:
            self.peak_pnl = current_pnl

        # 1. Break-Even Trigger check (+$0.50 PnL)
        if self.peak_pnl >= config.BREAK_EVEN_TRIGGER:
            if self.current_sl_floor < 0.0:
                self.current_sl_floor = 0.0
                logger.info(f"[STEP-RATCHET] Break-Even triggered! SL Floor moved to $0.00 (Peak PnL: ${self.peak_pnl:.2f})")

        # 2. Step Profit Locking (+$0.75 PnL and above)
        if self.peak_pnl >= (config.BREAK_EVEN_TRIGGER + config.TRAILING_STEP_USD):
            # Calculate dynamic step floor based on peak PnL and fixed trailing gap
            trailing_floor = self.peak_pnl - config.TRAILING_GAP_USD
            # Quantize to $0.25 step increments
            quantized_step_floor = (int(trailing_floor / config.TRAILING_STEP_USD)) * config.TRAILING_STEP_USD
            
            if quantized_step_floor > self.current_sl_floor:
                self.current_sl_floor = quantized_step_floor
                logger.info(
                    f"[STEP-RATCHET] Profit Locked! SL Floor ratcheted to +${self.current_sl_floor:.2f} "
                    f"(Peak PnL: ${self.peak_pnl:.2f} | Gap: ${config.TRAILING_GAP_USD:.2f})"
                )

        # 3. Check if current PnL has breached our local ratchet SL floor
        # Note: Manual sell is only sent if SL floor is >= 0.0 (Break-Even or Profit Lock)
        # Server-side native SL handles initial -0.75 hard SL.
        if self.current_sl_floor >= 0.0 and current_pnl <= self.current_sl_floor:
            reason = f"Ratchet SL Floor hit at ${current_pnl:.2f} <= ${self.current_sl_floor:.2f}"
            logger.info(f"[RATCHET TRAILING STOP TRIGGERED] {reason}")
            return True, self.current_sl_floor, reason

        return False, self.current_sl_floor, "Position holding"

    def close_position(self) -> Dict[str, Any]:
        contract_id = self.active_contract_id
        self.is_open = False
        self.active_contract_id = None
        logger.info(f"[POSITION CLOSED] ID: {contract_id} | Peak PnL: ${self.peak_pnl:.2f} | Final Floor: ${self.current_sl_floor:.2f}")
        return {
            "contract_id": contract_id,
            "peak_pnl": self.peak_pnl,
            "final_sl_floor": self.current_sl_floor
        }


class AegisExecutionEngine:
    """
    Main Risk & Execution State Machine.
    Tracks session statistics, quarantine periods, daily limits, and proposal generation.
    """
    def __init__(self):
        self.position_mgr = PositionManager()
        self.consecutive_losses: int = 0
        self.daily_pnl: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0
        self.quarantine_until: float = 0.0
        self.cooldown_until: float = 0.0
        self.session_start_time: float = time.time()
        self.is_halted: bool = False
        self.halt_reason: str = ""

    def build_proposal_payload(self, signal_type: str) -> Dict[str, Any]:
        """
        Construct Deriv WebSocket proposal request payload for cryBTCUSD multiplier contract.
        """
        return {
            "proposal": 1,
            "amount": config.STAKE,
            "basis": "stake",
            "contract_type": signal_type,
            "currency": "USD",
            "symbol": config.SYMBOL,
            "multiplier": config.MULTIPLIER_LEVERAGE,
            "limit_order": {"stop_loss": config.HARD_STOP_LOSS_USD},
        }

    def is_execution_allowed(self) -> Tuple[bool, str]:
        """
        Check all safety checks, cooldowns, and circuit breakers.
        """
        now = time.time()

        if self.is_halted:
            return False, f"ENGINE HALTED: {self.halt_reason}"

        # Session Time Limit Check
        elapsed_minutes = (now - self.session_start_time) / 60.0
        if elapsed_minutes >= config.MAX_RUNTIME_MINUTES:
            self.is_halted = True
            self.halt_reason = f"Max runtime limit ({config.MAX_RUNTIME_MINUTES} mins) reached"
            return False, self.halt_reason

        # 10-Minute Loss Quarantine Check
        if now < self.quarantine_until:
            remaining = int(self.quarantine_until - now)
            return False, f"Loss Quarantine active ({remaining}s remaining)"

        # Win Cooldown Check
        if now < self.cooldown_until:
            remaining = int(self.cooldown_until - now)
            return False, f"Post-win cooldown active ({remaining}s remaining)"

        # Position Open Check
        if self.position_mgr.is_open:
            return False, "Position already active"

        # Max Consecutive Losses Circuit Breaker
        if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            self.is_halted = True
            self.halt_reason = f"Max consecutive losses ({config.MAX_CONSECUTIVE_LOSSES}) reached"
            return False, self.halt_reason

        # Max Daily Loss Circuit Breaker
        if self.daily_pnl <= -config.MAX_DAILY_LOSS_USD:
            self.is_halted = True
            self.halt_reason = f"Max daily loss limit (-${config.MAX_DAILY_LOSS_USD:.2f}) reached"
            return False, self.halt_reason

        return True, "Ready"

    def handle_poc_update(self, poc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes proposal_open_contract WebSocket messages.
        Handles server-side native SL closes, PnL updates, and ratchet checks.
        """
        if not poc or not self.position_mgr.is_open:
            return {"action": "NONE"}

        contract_id = poc.get("contract_id")
        if contract_id != self.position_mgr.active_contract_id:
            return {"action": "NONE"}

        is_sold = poc.get("is_sold") == 1
        is_expired = poc.get("is_expired") == 1
        current_pnl = float(poc.get("profit", 0.0))
        status = poc.get("status")

        # 1. Native Server-Side Close Handshake (Deriv backend closed contract on native $0.75 SL)
        if is_sold or is_expired or status in ("lost", "won", "sold"):
            logger.info(f"[CONTRACT CLOSED BY SERVER] Contract {contract_id} closed natively by Deriv server. Final PnL: ${current_pnl:.2f}")
            self.position_mgr.close_position()
            self._record_trade_result(current_pnl, is_server_close=True)
            return {
                "action": "SERVER_CLOSED",
                "pnl": current_pnl,
                "contract_id": contract_id
            }

        # 2. Update local Step-Ratchet Trailing Engine
        should_manual_close, sl_floor, reason = self.position_mgr.update_pnl_and_ratchet(current_pnl)
        if should_manual_close:
            return {
                "action": "TRIGGER_MANUAL_SELL",
                "contract_id": contract_id,
                "pnl": current_pnl,
                "sl_floor": sl_floor,
                "reason": reason
            }

        return {"action": "HOLD", "current_pnl": current_pnl, "sl_floor": sl_floor}

    def handle_sell_error(self, error_message: str):
        """
        Handles WebSocket sell response errors (e.g., 'The contract has expired').
        """
        msg = error_message.lower()
        if "contract has expired" in msg or "already sold" in msg or "not open" in msg:
            logger.warning(f"[SYNC NOTICE] Contract expired/closed during sell request ({error_message}). Force-clearing state.")
            if self.position_mgr.is_open:
                # Treat as server close with last known SL loss
                self.position_mgr.close_position()
                self._record_trade_result(-config.HARD_STOP_LOSS_USD, is_server_close=True)

    def _record_trade_result(self, pnl: float, is_server_close: bool = False):
        """
        Record trade metrics and set appropriate cooldown or 10-minute loss quarantine.
        """
        self.total_trades += 1
        self.daily_pnl += pnl
        now = time.time()

        if pnl >= 0:
            self.winning_trades += 1
            self.consecutive_losses = 0
            self.cooldown_until = now + config.COOLDOWN_AFTER_WIN_SECONDS
            logger.info(f"[TRADE WIN] Profit: +${pnl:.2f} | 30s Cooldown applied. Total Daily PnL: ${self.daily_pnl:.2f}")
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1
            self.quarantine_until = now + config.COOLDOWN_AFTER_LOSS_SECONDS
            logger.warning(
                f"[TRADE LOSS] Loss: -${abs(pnl):.2f} | 10-MINUTE LOSS QUARANTINE APPLIED ({config.COOLDOWN_AFTER_LOSS_SECONDS}s). "
                f"Consecutive Losses: {self.consecutive_losses}/{config.MAX_CONSECUTIVE_LOSSES} | Total Daily PnL: ${self.daily_pnl:.2f}"
            )

        # Check circuit breakers immediately after recording
        if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            self.is_halted = True
            self.halt_reason = f"Reached max consecutive losses limit ({config.MAX_CONSECUTIVE_LOSSES})"
            logger.error(f"[CIRCUIT BREAKER] {self.halt_reason}")

        if self.daily_pnl <= -config.MAX_DAILY_LOSS_USD:
            self.is_halted = True
            self.halt_reason = f"Reached max daily loss limit (-${config.MAX_DAILY_LOSS_USD:.2f})"
            logger.error(f"[CIRCUIT BREAKER] {self.halt_reason}")
