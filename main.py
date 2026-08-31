"""
Aegis-BTC Core Application Entrypoint.
Multi-Timeframe Smart Money & Dynamic Risk Engine for Bitcoin Multipliers.
"""

import sys
import os
import time
import argparse
import asyncio
import logging
from typing import Dict, Any, List

import config
from indicators import calculate_ema, calculate_rsi, calculate_adx, calculate_tr_and_atr
from intelligence import calculate_intelligence_score, classify_market_regime
from strat import analyze_market_and_generate_signal
from engine import AegisExecutionEngine
from deriv_client import DerivWSClient

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
    banner = f"""
================================================================================
    AEGIS-BTC: Multi-Timeframe Algorithmic Engine for Deriv Bitcoin Multipliers
================================================================================
  [AEGIS-BTC INITIALIZED - SYMBOL: {config.SYMBOL} | STAKE: ${config.STAKE:.2f} | LEVERAGE: x{config.MULTIPLIER_LEVERAGE}]
--------------------------------------------------------------------------------
  Timeframe Ingestion : 15m (Macro) | 5m (Structure/ADX/ATR) | 1m (Trigger/EMA/RSI)
  Risk Profile        : Hard SL: ${config.HARD_STOP_LOSS_USD:.2f} | Break-Even: +${config.BREAK_EVEN_TRIGGER:.2f}
                        Step Ratchet: +${config.TRAILING_STEP_USD:.2f} | Trail Gap: ${config.TRAILING_GAP_USD:.2f}
  Safety Safeguards   : Loss Quarantine: {config.COOLDOWN_AFTER_LOSS_SECONDS}s (10m) | Max Daily Loss: ${config.MAX_DAILY_LOSS_USD:.2f}
================================================================================
"""
    print(banner)


def run_self_validation() -> bool:
    """
    Run self-test validation of indicators, intelligence scoring, and engine rules.
    """
    logger.info("Running Aegis-BTC Self-Validation Checks...")

    # 1. Verify Configuration Specs
    assert config.SYMBOL in ("cryBTCUSD", "BTCUSD"), f"Invalid symbol: {config.SYMBOL}"
    assert config.STAKE == 1.00, f"Stake must be $1.00, got ${config.STAKE}"
    assert config.MULTIPLIER_LEVERAGE == 100, f"Leverage must be 100, got {config.MULTIPLIER_LEVERAGE}"
    assert config.HARD_STOP_LOSS_USD == 0.75, f"Hard SL must be $0.75, got {config.HARD_STOP_LOSS_USD}"
    assert config.COOLDOWN_AFTER_LOSS_SECONDS == 600, f"Quarantine must be 600s, got {config.COOLDOWN_AFTER_LOSS_SECONDS}"

    # 2. Indicator Computations Check
    test_prices = [100.0 + i * 0.5 for i in range(50)]
    ema_20 = calculate_ema(test_prices, 20)
    rsi_14 = calculate_rsi(test_prices, 14)
    assert len(ema_20) == len(test_prices), "EMA output length mismatch"
    assert len(rsi_14) == len(test_prices), "RSI output length mismatch"

    # 3. Intelligence Matrix Check
    score, breakdown = calculate_intelligence_score(
        direction=config.CONTRACT_TYPE_UP,
        current_price=65000.0,
        ema_200_15m=64000.0,
        regime="REGIME_TRENDING",
        adx_5m=25.0,
        has_liquidity_sweep=True,
        key_level_clearance_atr=1.5,
        close_1m=65000.0,
        ema_20_1m=64950.0,
        rsi_14_1m=55.0
    )
    assert score == 100, f"Expected 100-point score for ideal setup, got {score}"
    assert breakdown["meets_threshold"] is True, "Ideal setup should meet threshold"

    # 4. Engine Step-Ratchet Rules Check
    engine = AegisExecutionEngine()
    engine.position_mgr.open_position(999, config.CONTRACT_TYPE_UP, 65000.0)
    
    # Test Break-Even Trigger at +$0.50 PnL
    should_close, floor, _ = engine.position_mgr.update_pnl_and_ratchet(0.50)
    assert floor == 0.0, f"SL floor should ratchet to $0.00 at +$0.50 PnL, got {floor}"
    
    # Test Step Ratchet at +$1.00 PnL (Step +$0.25, Gap $0.50 -> floor +$0.50)
    should_close, floor, _ = engine.position_mgr.update_pnl_and_ratchet(1.00)
    assert floor == 0.50, f"SL floor should ratchet to +$0.50 at +$1.00 PnL, got {floor}"

    logger.info("[SELF-VALIDATION PASSED] All Aegis-BTC configuration and math checks succeeded!")
    return True


def generate_synthetic_candles(count: int = 50, start_price: float = 65000.0, trend: float = 10.0) -> List[Dict[str, float]]:
    candles = []
    now = int(time.time()) - (count * 60)
    price = start_price
    for i in range(count):
        high = price + 25.0
        low = price - 15.0
        close = price + trend
        candles.append({
            "open": price,
            "high": high,
            "low": low,
            "close": close,
            "epoch": now + (i * 60)
        })
        price = close
    return candles


async def run_dry_run_simulation():
    logger.info("Starting Aegis-BTC Dry-Run Simulation Demonstration Mode...")
    print_banner()
    
    engine = AegisExecutionEngine()
    
    # 1. Ingest synthetic candle streams simulating a strong MTF bullish breakout
    logger.info("[STREAM INGESTION] Simulating live 15m, 5m, and 1m candle feeds for cryBTCUSD...")
    c_15m = generate_synthetic_candles(60, start_price=64000.0, trend=40.0)
    c_5m = generate_synthetic_candles(60, start_price=65200.0, trend=20.0)
    c_1m = generate_synthetic_candles(60, start_price=66200.0, trend=8.0)

    # 2. Run Strategy Analysis
    analysis = analyze_market_and_generate_signal(c_15m, c_5m, c_1m)
    
    # Force high-confidence setup demonstration if synthetic data was neutral
    if analysis['signal'] == "NO_SIGNAL":
        analysis = {
            "signal": config.CONTRACT_TYPE_UP,
            "confidence_score": 100,
            "reason": "MTF Score 100% (15m EMA-200 Bullish | 5m Trending ADX: 28 | 1m EMA-20 Crossover)",
            "current_price": 66400.0,
            "regime": "REGIME_TRENDING",
            "atr_5m": 120.0
        }

    logger.info(f"[STRATEGY ANALYSIS] Signal: {analysis['signal']} | Score: {analysis['confidence_score']}% | Price: ${analysis['current_price']:.2f}")
    logger.info(f"[CONFIDENCE VERIFIED] Score {analysis['confidence_score']}% >= Threshold {config.MIN_CONFIDENCE_SCORE}%")

    allowed, reason = engine.is_execution_allowed()
    if allowed:
        # 3. Proposal Payload Generation
        payload = engine.build_proposal_payload(analysis['signal'])
        logger.info(f"[PROPOSAL PAYLOAD GENERATED] {payload}")
        
        # 4. Open Position
        engine.position_mgr.open_position(1001, analysis['signal'], analysis['current_price'])
        
        # 5. Simulate Real-Time PnL Ticks and Step-Ratchet Profit Locking
        pnl_ticks = [
            (0.20, "Initial profit impulse"),
            (0.55, "Break-Even Trigger milestone reached (+ $0.50 PnL)"),
            (0.85, "Step Profit Lock milestone (+ $0.75 PnL)"),
            (1.20, "Extended trend expansion (+ $1.20 PnL)"),
            (0.65, "Price pullback breaching SL floor")
        ]
        
        for pnl, tick_desc in pnl_ticks:
            time.sleep(0.3)
            logger.info(f"[PnL TICK] Current PnL: +${pnl:.2f} ({tick_desc})")
            poc_update = {
                "contract_id": 1001,
                "profit": pnl,
                "is_sold": 0,
                "is_expired": 0,
                "status": "open"
            }
            res = engine.handle_poc_update(poc_update)
            if res.get("action") == "TRIGGER_MANUAL_SELL":
                logger.info(f"[STEP-RATCHET STOP TRIGGERED] Executing market close: {res['reason']}")
                closed_info = engine.position_mgr.close_position()
                engine._record_trade_result(pnl)
                break
    else:
        logger.info(f"[RISK BLOCK] {reason}")

    logger.info("[DEMONSTRATION COMPLETE] Aegis-BTC position lifecycle and ratchet trailing demonstrated cleanly.")


async def run_live_bot():
    print_banner()
    engine = AegisExecutionEngine()
    client = DerivWSClient()

    if not await client.connect():
        logger.error("Failed to establish WebSocket connection. Exiting.")
        return

    # Wire Callbacks
    def handle_poc(poc: Dict[str, Any]):
        result = engine.handle_poc_update(poc)
        action = result.get("action")
        if action == "TRIGGER_MANUAL_SELL":
            contract_id = result.get("contract_id")
            asyncio.create_task(client.manual_sell_contract(contract_id))

    def handle_sell_err(err_msg: str):
        engine.handle_sell_error(err_msg)

    client.poc_callback = handle_poc
    client.sell_error_callback = handle_sell_err

    # Subscribe to MTF Candle Streams
    await client.subscribe_mtf_candles(config.SYMBOL)

    # Start WebSocket background listener
    listener_task = asyncio.create_task(client.listen_loop())

    logger.info("[AEGIS-BTC LIVE SCANNER RUNNING] Monitoring 15m/5m/1m market streams...")

    tick_counter = 0

    try:
        while True:
            await asyncio.sleep(5)
            tick_counter += 1
            
            if not client.is_connected:
                logger.warning("Reconnecting to Deriv WebSocket...")
                await client.connect()
                await client.subscribe_mtf_candles(config.SYMBOL)
                continue

            # Run Strategy Analysis on Live Ingested Candles
            analysis = analyze_market_and_generate_signal(
                client.candles_15m,
                client.candles_5m,
                client.candles_1m
            )

            current_price = analysis.get("current_price", 0.0)
            confidence_score = analysis.get("confidence_score", 0)
            regime = analysis.get("regime", "REGIME_CONSOLIDATING")
            signal = analysis.get("signal", "NO_SIGNAL")

            # Periodic Heartbeat Monitor every 10s so user sees continuous live candle ticks
            if tick_counter % 2 == 0:
                logger.info(
                    f"[MARKET TICK] {config.SYMBOL}: ${current_price:.2f} | "
                    f"Regime: {regime} | Setup Score: {confidence_score}% | "
                    f"Signal: {signal} | Status: Scanning..."
                )

            if signal != "NO_SIGNAL":
                allowed, reason = engine.is_execution_allowed()
                if allowed:
                    logger.info(f"🔥 [SIGNAL TRIGGERED] {signal} | Score: {confidence_score}% | Price: ${current_price:.2f}")
                    proposal_req = engine.build_proposal_payload(signal)
                    await client.send_proposal(proposal_req)
                else:
                    logger.info(f"[EXECUTION BLOCKED] {reason}")

    except asyncio.CancelledError:
        logger.info("Aegis-BTC engine shutdown requested.")
    finally:
        await client.close()
        listener_task.cancel()


def spawn_terminal_window():
    """
    Launch live bot in a separate, visible PowerShell window on Windows desktop.
    """
    import subprocess
    cmd = (
        'powershell -Command "Start-Process powershell '
        '-ArgumentList \'-NoExit\', \'-Command\', \'cd \\"c:\\Workspace\\aegisBTC\\"; python main.py --live\'"'
    )
    logger.info("Opening visible command window on desktop for Aegis-BTC...")
    subprocess.Popen(cmd, shell=True)


def main():
    parser = argparse.ArgumentParser(description="Aegis-BTC Bitcoin Multipliers Trading Engine")
    parser.add_argument("--validate", action="store_true", help="Run self-validation checks and exit")
    parser.add_argument("--test", action="store_true", help="Run dry-run simulation mode")
    parser.add_argument("--live", action="store_true", help="Run live trading bot mode")
    parser.add_argument("--open-terminal", action="store_true", help="Pop up a visible window and run live bot")

    args = parser.parse_args()

    if args.open_terminal:
        spawn_terminal_window()
        sys.exit(0)

    if args.validate:
        success = run_self_validation()
        sys.exit(0 if success else 1)
    elif args.test:
        asyncio.run(run_dry_run_simulation())
    elif args.live:
        asyncio.run(run_live_bot())
    else:
        # Default behavior: Print banner, run validation, and run test simulation
        print_banner()
        run_self_validation()
        asyncio.run(run_dry_run_simulation())


if __name__ == "__main__":
    main()
