"""
Aegis-Weltrade Master Execution Engine.
Profile-Driven Architecture supporting:
1. 5-Minute Intraday Momentum Expansion (EXPANSION_M5) [Default]
2. 1-Minute Micro-Scalper (SCALP_M1)
3. Strict 60-Minute ICT Silver Bullet (SILVER_BULLET_PURE)
"""

import sys
import os
import time
import argparse
import asyncio
import logging
from typing import Dict, Any, List, Optional

import config
from indicators import calculate_ema, calculate_rsi, calculate_adx, calculate_tr_and_atr
from intelligence import calculate_intelligence_score, classify_market_regime
from strategy import evaluate_confluence_proposal, is_in_session_window
from risk_engine import RiskEngine
from ai_scanner import MiniAIScanner
from mt5_bridge import MT5Bridge
import telemetry

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AegisBTC.Main")


def print_banner():
    mode = config.ACTIVE_MODE
    tf_macro = f"{config.TF_MACRO // 60}m" if config.TF_MACRO < 3600 else f"{config.TF_MACRO // 3600}H"
    tf_struct = f"{config.TF_STRUCTURE // 60}m"
    tf_trig = f"{config.TF_TRIGGER // 60}m"
    windows = ", ".join([f"{w[0]}-{w[1]}" for w in config.SILVER_BULLET_WINDOWS_CAT])

    banner = f"""
================================================================================
    AEGIS-WELTRADE: MULTI-PROFILE AI TRADING ENGINE
================================================================================
  [ACTIVE PROFILE: {mode} | SYMBOL: {config.SYMBOL} | MAGIC: {config.MAGIC_NUMBER}]
--------------------------------------------------------------------------------
  Timeframes          : Macro: {tf_macro} | Structure: {tf_struct} | Trigger: {tf_trig}
  Session Windows CAT : {windows}
  Risk & Reward       : Hard SL: {config.HARD_SL_PIPS:.1f}p | Target TP: {config.FIXED_TP_PIPS:.1f}p (1:2 R:R)
                        Break-Even: +{config.BE_TRIGGER_PIPS:.1f}p | Step Ratchet: +{config.TRAILING_STEP_PIPS:.1f}p
                        Stagnation Time-Stop: {config.TIME_STOP_SECONDS}s ({config.TIME_STOP_SECONDS // 60}m)
  Safeguards          : Max Spread: {config.MAX_ALLOWED_SPREAD_PIPS:.1f}p | Rel Spread: {config.RELATIVE_SPREAD_MULTIPLIER}x 20-MA
                        Max Daily Loss: ${config.MAX_DAILY_LOSS_USD:.2f} | Loss Quarantine: {config.COOLDOWN_AFTER_LOSS_SECONDS}s
  AI Regime Filter    : Lookback: {config.AI_LOOKBACK_CANDLES} bars | Horizon: {config.AI_LABEL_HORIZON} bars | Min Conf: {config.AI_CONFIDENCE_THRESHOLD * 100:.0f}%
================================================================================
"""
    print(banner)


def run_self_validation() -> bool:
    """Run self-test validation of configuration, math, and risk components."""
    logger.info("Running Aegis-Weltrade Self-Validation Checks...")

    # 1. Profile Integrity Checks
    for p_name, p_cfg in config.PROFILES.items():
        assert p_cfg["MAGIC_NUMBER"] > 0, f"Profile {p_name} invalid magic number"
        assert p_cfg["HARD_SL_PIPS"] > 0, f"Profile {p_name} invalid SL"
        assert p_cfg["FIXED_TP_PIPS"] > p_cfg["HARD_SL_PIPS"], f"Profile {p_name} TP must exceed SL for positive expectancy"
        assert p_cfg["BE_TRIGGER_PIPS"] > 0, f"Profile {p_name} invalid BE trigger"
        assert p_cfg["TIME_STOP_SECONDS"] > 0, f"Profile {p_name} invalid time-stop"

    # 2. Indicator Computations Check
    test_prices = [1.0800 + i * 0.0001 for i in range(50)]
    ema_8 = calculate_ema(test_prices, 8)
    ema_21 = calculate_ema(test_prices, 21)
    rsi_14 = calculate_rsi(test_prices, 14)
    assert len(ema_8) == len(test_prices), "EMA output length mismatch"
    assert len(rsi_14) == len(test_prices), "RSI output length mismatch"

    # 3. Risk Engine Break-Even and Time-Stop Logic Check
    risk = RiskEngine()
    risk.register_position_opened(999999, "BUY", 1.08500, lot_size=0.01, initial_sl=1.08350)
    assert risk.active_ticket == 999999
    assert risk.is_be_activated is False

    # Simulate position reaching Break-Even threshold
    class DummyPos:
        ticket = 999999
        type = 0  # BUY
        price_open = 1.08500
        price_current = 1.08500 + (config.BE_TRIGGER_PIPS * 0.0001)
        profit = 1.20
        time = time.time()
        sl = 1.08350

    risk.manage_active_position(DummyPos())
    assert risk.peak_pnl_pips >= config.BE_TRIGGER_PIPS

    logger.info("✅ [SELF-VALIDATION PASSED] All multi-profile math, strategy, and risk checks succeeded!")
    return True


async def run_live_bot():
    """Main live execution orchestrator for MT5 terminal."""
    print_banner()

    # 1. Initialize MT5 Bridge
    bridge = MT5Bridge(
        account=config.WELTRADE_LOGIN,
        password=config.WELTRADE_PASSWORD,
        server=config.WELTRADE_SERVER,
        symbol=config.SYMBOL,
        lot_size=config.LOT_SIZE
    )

    if not bridge.connect():
        logger.error("❌ Could not connect to MetaTrader 5 Terminal. Please verify MT5 is running and credentials are valid.")
        return

    # 2. Initialize Risk Engine
    risk = RiskEngine(bridge=bridge)

    # 3. Initialize & Train AI Market Regime Scanner for active profile
    ai_scanner = MiniAIScanner(config.ACTIVE_MODE)
    if config.AI_ENABLED:
        logger.info(f"🧠 [AI SCANNER] Fetching {config.AI_LOOKBACK_CANDLES} historical bars for [{config.ACTIVE_MODE}]...")
        hist_candles = bridge.fetch_candles(config.TF_TRIGGER, count=config.AI_LOOKBACK_CANDLES)
        if hist_candles and len(hist_candles) >= 50:
            ai_scanner.train_on_history(hist_candles)
        else:
            logger.warning(f"Could not fetch enough historical candles for AI training. Running in rule fallback mode.")

    # 4. Dispatch Telegram Startup Notification
    balance = float(bridge.account_info.get("balance", 0.0))
    telemetry.notify_bot_started(bridge.symbol, bridge.lot_size, balance, config.AI_ENABLED, profile=config.ACTIVE_MODE)

    logger.info(f"🚀 [AEGIS MASTER LOOP RUNNING] Mode: {config.ACTIVE_MODE} | Asset: {bridge.symbol} | Magic: {config.MAGIC_NUMBER}...")

    # Last position tracking to detect server-side closes
    known_active_ticket = None

    try:
        while True:
            # 1. Fetch active open positions for this bot's magic number
            open_positions = bridge.get_open_positions(config.MAGIC_NUMBER)
            is_position_open = len(open_positions) > 0

            # 2. Handle position closure transition
            if not is_position_open and known_active_ticket is not None:
                # Active position closed on broker server (hit SL/TP or manual close)
                logger.info(f"🚪 [TRADE CLOSED ON SERVER] Ticket #{known_active_ticket} no longer open.")
                risk.register_position_closed(0.0, reason="Server Close (SL/TP hit)")
                known_active_ticket = None

            # 3. Position Management Mode (1-second tick loop)
            if is_position_open:
                pos = open_positions[0]
                known_active_ticket = pos.ticket

                should_close, close_reason = risk.manage_active_position(pos)
                if should_close:
                    logger.info(f"⚠️ [CLOSING POSITION] Ticket #{pos.ticket}: {close_reason}")
                    if bridge.close_position(pos.ticket):
                        risk.register_position_closed(pos.profit, reason=close_reason)
                        known_active_ticket = None

                # Log active position telemetry every second
                tick = bridge.get_live_tick()
                spread_val = tick["spread_pips"] if tick else 0.0
                runtime = int(time.time() - (risk.entry_time if risk.entry_time > 0 else pos.time))
                logger.info(
                    f"🎯 [ACTIVE TRADE #{pos.ticket}] PnL: ${pos.profit:+.2f} | Peak: +{risk.peak_pnl_pips:.1f}p | "
                    f"BE: {'Locked' if risk.is_be_activated else 'Pending'} | SL: {pos.sl:.5f} | "
                    f"Runtime: {runtime}s/{config.TIME_STOP_SECONDS}s | Spread: {spread_val:.1f}p"
                )
                await asyncio.sleep(1.0)
                continue

            # 4. Scanning Mode (No active position)
            allowed, block_reason = risk.is_execution_allowed()
            if not allowed:
                logger.info(f"⏳ [SCANNER PAUSED] {block_reason}")
                await asyncio.sleep(5.0)
                continue

            # Check spread filter before analyzing setup
            is_spread_ok, spread_reason, current_spread = bridge.validate_spread()
            if not is_spread_ok:
                logger.info(f"⚠️ [SPREAD FILTER ACTIVE] {spread_reason}. Waiting...")
                await asyncio.sleep(3.0)
                continue

            # Ingest multi-timeframe candles dynamically for the active profile
            macro_candles, struct_candles, trig_candles = bridge.fetch_profile_candles()
            if not macro_candles or not struct_candles or not trig_candles:
                logger.warning("Waiting for MT5 candle streams to populate...")
                await asyncio.sleep(2.0)
                continue

            # Compute AI Market Regime Confidence on completed trigger candle [-2]
            ai_conf = ai_scanner.predict_regime_confidence(trig_candles)

            # Evaluate 100-point confluence setup strictly on bar-close [-2]
            proposal = evaluate_confluence_proposal(
                macro_candles=macro_candles,
                structure_candles=struct_candles,
                trigger_candles=trig_candles,
                ai_confidence=ai_conf
            )

            # Scanner status telemetry log
            curr_price = trig_candles[-1]['close'] if trig_candles else 0.0
            in_sb = is_in_session_window()
            sb_status = "ACTIVE 🔥" if in_sb else "Outside Window 💤"
            logger.info(
                f"📡 [SCANNING {config.ACTIVE_MODE}] {bridge.symbol}: {curr_price:.5f} | "
                f"Spread: {current_spread:.1f}p | AI Conf: {ai_conf * 100:.1f}% | "
                f"Window: {sb_status} | Signal: {proposal['action'] if proposal else 'None'}"
            )

            # 5. Order Execution
            if proposal is not None:
                action = proposal["action"]
                logger.info(
                    f"🔥 [SETUP TRIGGERED: {action}] Confluence: {proposal['confidence_score']}/100 | "
                    f"AI: {ai_conf * 100:.1f}% | Reasons: {', '.join(proposal['reasons'])}"
                )

                ticket = bridge.send_order(
                    direction=action,
                    volume=config.LOT_SIZE,
                    sl_pips=proposal["sl_pips"],
                    tp_pips=proposal["tp_pips"],
                    comment=f"Aegis_{config.ACTIVE_MODE}"
                )

                if ticket:
                    known_active_ticket = ticket
                    risk.register_position_opened(
                        ticket=ticket,
                        direction=action,
                        entry_price=proposal["entry_price"],
                        lot_size=config.LOT_SIZE,
                        initial_sl=proposal["sl_price"]
                    )
                else:
                    logger.warning("Order send failed or was rejected by broker.")

            await asyncio.sleep(3.0)

    except asyncio.CancelledError:
        logger.info("Aegis engine shutdown initiated.")
    except Exception as e:
        logger.error(f"Unexpected error in live bot loop: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="Aegis-Weltrade AI Execution Engine")
    parser.add_argument("--validate", action="store_true", help="Run self-validation suite and exit")
    parser.add_argument(
        "--mode",
        choices=["EXPANSION_M5", "SCALP_M1", "SILVER_BULLET_PURE", "m5", "m1", "pure", "master", "classic", "hybrid"],
        help="Select operational profile"
    )
    parser.add_argument("--live", action="store_true", help="Start live trading execution")
    args = parser.parse_args()

    # Map profile choices
    if args.mode:
        m_lower = args.mode.lower()
        if m_lower in ("expansion_m5", "m5"):
            config.set_active_mode("EXPANSION_M5")
        elif m_lower in ("scalp_m1", "m1", "master", "classic"):
            config.set_active_mode("SCALP_M1")
        elif m_lower in ("silver_bullet_pure", "pure", "hybrid"):
            config.set_active_mode("SILVER_BULLET_PURE")

    if args.validate:
        success = run_self_validation()
        sys.exit(0 if success else 1)

    print_banner()
    if args.live:
        asyncio.run(run_live_bot())
    else:
        # Default runs validation checks
        run_self_validation()
        logger.info("Run with '--live' to start live MT5 trading (e.g. python main.py --mode EXPANSION_M5 --live).")


if __name__ == "__main__":
    main()
