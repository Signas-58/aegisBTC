"""
Aegis-Weltrade Master Execution Engine.
Profile-Driven Architecture supporting:
1. Multi-Asset Dual-AI Ensemble (MULTI_ASSET_ENSEMBLE) [Default - ~1 Trade/Hour Target]
2. 5-Minute Intraday Momentum Expansion (EXPANSION_M5)
3. 1-Minute Micro-Scalper (SCALP_M1)
4. Strict 60-Minute ICT Silver Bullet (SILVER_BULLET_PURE)
"""

import sys
import os
import time
import argparse
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

import config
from indicators import calculate_ema, calculate_rsi, calculate_adx, calculate_tr_and_atr
from intelligence import calculate_intelligence_score, classify_market_regime
from strategy import evaluate_confluence_proposal, is_in_session_window, calculate_confluence_details
from risk_engine import RiskEngine
from ai_ensemble import DualAIEnsemble
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
    symbols = getattr(config, "SYMBOLS", [config.SYMBOL])
    symbols_str = ", ".join(symbols)

    banner = f"""
================================================================================
    AEGIS-WELTRADE: MULTI-PROFILE AI TRADING ENGINE
================================================================================
  [ACTIVE PROFILE: {mode} | SYMBOLS: {symbols_str} | MAGIC: {config.MAGIC_NUMBER}]
--------------------------------------------------------------------------------
  Timeframes          : Macro: {tf_macro} | Structure: {tf_struct} | Trigger: {tf_trig}
  Session Windows CAT : {windows}
  Portfolio Limit     : Max {config.MAX_PORTFOLIO_POSITIONS} Open Position(s) Globally
  Risk & Reward       : Hard SL: {config.HARD_SL_PIPS:.1f}p | Target TP: {config.FIXED_TP_PIPS:.1f}p (1:2 R:R)
                        Break-Even: +{config.BE_TRIGGER_PIPS:.1f}p | Step Ratchet: +{config.TRAILING_STEP_PIPS:.1f}p
                        Stagnation Time-Stop: {config.TIME_STOP_SECONDS}s ({config.TIME_STOP_SECONDS // 60}m)
  Safeguards          : Max Spread: {config.MAX_ALLOWED_SPREAD_PIPS:.1f}p | Rel Spread: {config.RELATIVE_SPREAD_MULTIPLIER}x 20-MA
                        Max Daily Loss: ${config.MAX_DAILY_LOSS_USD:.2f} | Loss Quarantine: {config.COOLDOWN_AFTER_LOSS_SECONDS}s
  Dual-AI Ensemble    : RandomForest + HistGradientBoosting Voting Consensus
                        Lookback: {config.AI_LOOKBACK_CANDLES} bars | Min Conf: {config.AI_CONFIDENCE_THRESHOLD * 100:.0f}%
================================================================================
"""
    print(banner)


def log_candle_heartbeat(
    symbol: str,
    score: int,
    ai_conf: float,
    spread: float,
    is_window_active: bool,
    extra_status: str = ""
):
    """Prints a clear diagnostic status breakdown every time a candle closes."""
    time_str = datetime.now().strftime("%H:%M:%S")

    reasons = []
    if not is_window_active:
        reasons.append("Outside Session Window")
    if spread > config.MAX_ALLOWED_SPREAD_PIPS:
        reasons.append(f"Spread Too High ({spread:.1f}p)")
    if score < config.MIN_CONFIDENCE_SCORE:
        reasons.append(f"Score Low ({score}/100)")
    if ai_conf < config.AI_CONFIDENCE_THRESHOLD:
        reasons.append(f"AI Low ({ai_conf*100:.1f}%)")
    if extra_status:
        reasons.append(extra_status)

    status_reason = " | ".join(reasons) if reasons else "READY TO EXECUTE"

    print(
        f"⏱️ [{time_str}] {config.ACTIVE_MODE} | {symbol:6s} | "
        f"Score: {score:2d}/100 | AI Conf: {ai_conf*100:.1f}% | "
        f"Spread: {spread:.1f}p | Status: ⏳ {status_reason}"
    )


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

    # 3. Dual-AI Ensemble Self-Test
    ensemble = DualAIEnsemble(mode="MULTI_ASSET_ENSEMBLE", symbol="EURUSD")
    synthetic_candles = [
        {"open": 1.08 + i * 0.0001, "high": 1.0805 + i * 0.0001, "low": 1.0795 + i * 0.0001, "close": 1.0802 + i * 0.0001, "volume": 100}
        for i in range(60)
    ]
    ensemble.train_on_history(synthetic_candles)
    passed, conf, breakdown = ensemble.evaluate_consensus(synthetic_candles)
    assert 0.0 <= conf <= 1.0, "AI confidence out of bounds"
    assert "rf_prob" in breakdown and "gb_prob" in breakdown, "Breakdown format mismatch"

    # 4. Risk Engine Break-Even and Time-Stop Logic Check
    risk = RiskEngine()
    risk.register_position_opened(999999, "BUY", 1.08500, lot_size=0.01, initial_sl=1.08350, symbol="EURUSD")
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
        symbol = "EURUSD"

    risk.manage_active_position(DummyPos())
    assert risk.peak_pnl_pips >= config.BE_TRIGGER_PIPS

    logger.info("✅ [SELF-VALIDATION PASSED] All multi-profile math, Dual-AI ensemble, and risk checks succeeded!")
    return True


async def run_live_bot():
    """Main live execution orchestrator for MT5 terminal."""
    print_banner()

    symbols = getattr(config, "SYMBOLS", [config.SYMBOL])

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

    # 3. Initialize & Pre-Train Dual-AI Ensembles across all active symbols
    ai_ensembles: Dict[str, DualAIEnsemble] = {}
    for sym in symbols:
        ai_ensembles[sym] = DualAIEnsemble(mode=config.ACTIVE_MODE, symbol=sym)
        if config.AI_ENABLED:
            logger.info(f"🧠 [AI ENSEMBLE] Fetching {config.AI_LOOKBACK_CANDLES} historical bars for [{config.ACTIVE_MODE}] {sym}...")
            hist_candles = bridge.fetch_candles(config.TF_TRIGGER, count=config.AI_LOOKBACK_CANDLES, symbol=sym)
            if hist_candles and len(hist_candles) >= 50:
                ai_ensembles[sym].train_on_history(hist_candles)
            else:
                logger.warning(f"Could not fetch enough historical candles for AI training on {sym}. Running in fallback mode.")

    # 4. Instant Telegram Startup Alert
    balance = float(bridge.account_info.get("balance", 0.0))
    startup_msg = (
        f"🚀 *AEGIS ENGINE ONLINE*\n"
        f"• Profile: `{config.ACTIVE_MODE}`\n"
        f"• Symbols: `{', '.join(symbols)}`\n"
        f"• Magic ID: `{config.MAGIC_NUMBER}`\n"
        f"• Target SL/TP: `{config.HARD_SL_PIPS:.1f}p / {config.FIXED_TP_PIPS:.1f}p`\n"
        f"• Max Portfolio Positions: `{config.MAX_PORTFOLIO_POSITIONS}`\n"
        f"• Balance: `${balance:.2f}`\n"
        f"• Heartbeat: Active"
    )
    telemetry.send_alert(startup_msg)
    telemetry.notify_bot_started(bridge.symbol, bridge.lot_size, balance, config.AI_ENABLED, profile=config.ACTIVE_MODE)

    logger.info(f"🚀 [AEGIS MASTER LOOP RUNNING] Mode: {config.ACTIVE_MODE} | Assets: {', '.join(symbols)} | Magic: {config.MAGIC_NUMBER}...")

    # Last position tracking to detect server-side closes
    known_active_ticket = None
    last_closed_candle_times: Dict[str, int] = {sym: 0 for sym in symbols}

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

            # 3. Position Management Mode (Enforces Strict MAX_PORTFOLIO_POSITIONS lock)
            if len(open_positions) >= config.MAX_PORTFOLIO_POSITIONS:
                pos = open_positions[0]
                known_active_ticket = pos.ticket
                pos_sym = getattr(pos, "symbol", bridge.symbol)

                should_close, close_reason = risk.manage_active_position(pos)
                if should_close:
                    logger.info(f"⚠️ [CLOSING POSITION] Ticket #{pos.ticket} ({pos_sym}): {close_reason}")
                    if bridge.close_position(pos.ticket, symbol=pos_sym):
                        risk.register_position_closed(pos.profit, reason=close_reason)
                        known_active_ticket = None

                # Log active position telemetry every second
                tick = bridge.get_live_tick(symbol=pos_sym)
                spread_val = tick["spread_pips"] if tick else 0.0
                runtime = int(time.time() - (risk.entry_time if risk.entry_time > 0 else pos.time))
                logger.info(
                    f"🎯 [ACTIVE TRADE #{pos.ticket} ({pos_sym})] PnL: ${pos.profit:+.2f} | Peak: +{risk.peak_pnl_pips:.1f}p | "
                    f"BE: {'Locked' if risk.is_be_activated else 'Pending'} | SL: {pos.sl:.5f} | "
                    f"Runtime: {runtime}s/{config.TIME_STOP_SECONDS}s | Spread: {spread_val:.1f}p"
                )
                await asyncio.sleep(1.0)
                continue

            # 4. Global Circuit Breakers and Blackouts Check
            allowed, block_reason = risk.is_execution_allowed()
            if not allowed:
                logger.info(f"⏳ [SCANNER PAUSED] {block_reason}")
                await asyncio.sleep(5.0)
                continue

            # 5. Multi-Asset Scanning Loop across active symbols
            for sym in symbols:
                # Re-check portfolio risk limit before evaluating next asset
                if len(bridge.get_open_positions(config.MAGIC_NUMBER)) >= config.MAX_PORTFOLIO_POSITIONS:
                    break

                # Ingest multi-timeframe candles dynamically
                macro_candles, struct_candles, trig_candles = bridge.fetch_profile_candles(symbol=sym)
                if not macro_candles or not struct_candles or not trig_candles:
                    continue

                closed_candle = trig_candles[-2]
                closed_time = int(closed_candle.get("time", 0))

                # Check spread and session window
                is_spread_ok, spread_reason, current_spread = bridge.validate_spread(symbol=sym)
                in_sb = is_in_session_window()

                # Evaluate Dual-AI Voting Consensus on completed trigger bar [-2]
                passed_ai, ai_conf, ai_breakdown = ai_ensembles[sym].evaluate_consensus(trig_candles)

                # Calculate confluence score and details
                score, candidate_dir, score_reasons = calculate_confluence_details(
                    macro_candles=macro_candles,
                    structure_candles=struct_candles,
                    trigger_candles=trig_candles
                )

                # Diagnostic Heartbeat Logger: Fire when a new candle closes
                if closed_time != last_closed_candle_times.get(sym, 0):
                    last_closed_candle_times[sym] = closed_time
                    log_candle_heartbeat(
                        symbol=sym,
                        score=score,
                        ai_conf=ai_conf,
                        spread=current_spread,
                        is_window_active=in_sb
                    )

                # 6. Trade Setup Evaluation & Execution
                if in_sb and is_spread_ok:
                    proposal = evaluate_confluence_proposal(
                        macro_candles=macro_candles,
                        structure_candles=struct_candles,
                        trigger_candles=trig_candles,
                        ai_confidence=ai_conf,
                        symbol=sym
                    )

                    if proposal is not None:
                        action = proposal["action"]
                        logger.info(
                            f"🔥 [SETUP TRIGGERED: {action}] Symbol: {sym} | Confluence: {proposal['confidence_score']}/100 | "
                            f"AI: {ai_conf * 100:.1f}% ({ai_breakdown}) | Reasons: {', '.join(proposal['reasons'])}"
                        )

                        ticket = bridge.send_order(
                            direction=action,
                            volume=config.LOT_SIZE,
                            sl_pips=proposal["sl_pips"],
                            tp_pips=proposal["tp_pips"],
                            comment=f"Aegis_{config.ACTIVE_MODE}",
                            symbol=sym
                        )

                        if ticket:
                            known_active_ticket = ticket
                            risk.register_position_opened(
                                ticket=ticket,
                                direction=action,
                                entry_price=proposal["entry_price"],
                                lot_size=config.LOT_SIZE,
                                initial_sl=proposal["sl_price"],
                                symbol=sym
                            )
                            time_now = datetime.now().strftime("%H:%M:%S")
                            print(
                                f"⏱️ [{time_now}] {config.ACTIVE_MODE} | {sym:6s} | "
                                f"Status: ⚡ EXECUTING {action} ORDER #{ticket}"
                            )
                            break
                        else:
                            logger.warning(f"Order send failed or was rejected by broker for {sym}.")

            await asyncio.sleep(2.0)

    except asyncio.CancelledError:
        logger.info("Aegis engine shutdown initiated.")
    except Exception as e:
        logger.error(f"Unexpected error in live bot loop: {e}", exc_info=True)


def spawn_terminal_window(mode: Optional[str] = None):
    """Launch live bot in a separate, visible PowerShell window on Windows desktop."""
    import subprocess
    mode_name = mode or config.ACTIVE_MODE
    cmd = (
        'powershell -Command "Start-Process powershell '
        f'-ArgumentList \'-NoExit\', \'-Command\', \'cd \\"c:\\Workspace\\aegisBTC\\"; python main.py --live --child --mode {mode_name}\'"'
    )
    logger.info(f"🖥️ Spawning dedicated visible desktop terminal for Aegis [{mode_name}]...")
    subprocess.Popen(cmd, shell=True)


def main():
    parser = argparse.ArgumentParser(description="Aegis-Weltrade AI Execution Engine")
    parser.add_argument("--validate", action="store_true", help="Run self-validation suite and exit")
    parser.add_argument(
        "--mode",
        choices=[
            "MULTI_ASSET_ENSEMBLE", "EXPANSION_M5", "SCALP_M1", "SILVER_BULLET_PURE",
            "multi", "ensemble", "m5", "m1", "pure", "master", "classic", "hybrid"
        ],
        help="Select operational profile"
    )
    parser.add_argument("--live", action="store_true", help="Start live trading execution")
    parser.add_argument("--child", action="store_true", help="Internal flag indicating execution inside spawned window")
    parser.add_argument("--no-spawn", action="store_true", help="Run in current terminal without spawning new window")
    args = parser.parse_args()

    # Map profile choices
    if args.mode:
        m_lower = args.mode.lower()
        if m_lower in ("multi_asset_ensemble", "multi", "ensemble"):
            config.set_active_mode("MULTI_ASSET_ENSEMBLE")
        elif m_lower in ("expansion_m5", "m5"):
            config.set_active_mode("EXPANSION_M5")
        elif m_lower in ("scalp_m1", "m1", "master", "classic"):
            config.set_active_mode("SCALP_M1")
        elif m_lower in ("silver_bullet_pure", "pure", "hybrid"):
            config.set_active_mode("SILVER_BULLET_PURE")

    if args.validate:
        success = run_self_validation()
        sys.exit(0 if success else 1)

    # Auto-spawn dedicated visible window when --live is invoked from an external launcher
    if args.live and not args.child and not args.no_spawn:
        spawn_terminal_window(config.ACTIVE_MODE)
        sys.exit(0)

    print_banner()
    if args.live:
        asyncio.run(run_live_bot())
    else:
        # Default runs validation checks
        run_self_validation()
        logger.info("Run with '--live' to start live MT5 trading (e.g. python main.py --mode MULTI_ASSET_ENSEMBLE --live).")


if __name__ == "__main__":
    main()
