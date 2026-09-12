"""
Automated Test Suite for Aegis-BTC Trading Engine.
"""

import unittest
import time
import config
from indicators import (
    calculate_ema, calculate_rsi, calculate_tr_and_atr,
    calculate_adx, get_swing_levels
)
from intelligence import (
    classify_market_regime, calculate_intelligence_score,
    REGIME_TRENDING, REGIME_CONSOLIDATING, REGIME_HIGH_RISK
)
from strat import check_dynamic_proximity_guard, detect_liquidity_sweep, analyze_market_and_generate_signal
from engine import AegisExecutionEngine, PositionManager


class TestAegisBTC(unittest.TestCase):

    def test_indicators_ema_and_rsi(self):
        prices = [100.0 + i for i in range(30)]
        ema = calculate_ema(prices, 10)
        self.assertEqual(len(ema), 30)
        self.assertGreater(ema[-1], ema[0])

        rsi = calculate_rsi(prices, 14)
        self.assertEqual(len(rsi), 30)
        self.assertGreater(rsi[-1], 50.0)

    def test_indicators_adx_and_atr(self):
        candles = []
        for i in range(30):
            candles.append({
                "open": 100.0 + i,
                "high": 105.0 + i,
                "low": 98.0 + i,
                "close": 103.0 + i
            })
        tr_list, atr_list = calculate_tr_and_atr(candles, 14)
        self.assertEqual(len(atr_list), 30)
        self.assertGreater(atr_list[-1], 0.0)

        adx, pdi, mdi = calculate_adx(candles, 14)
        self.assertEqual(len(adx), 30)

    def test_market_regime_classifier(self):
        regime_high_risk = classify_market_regime(adx_5m=25.0, adx_slope_5m=1.0, atr_ratio_5m=2.0)
        self.assertEqual(regime_high_risk, REGIME_HIGH_RISK)

        regime_trending = classify_market_regime(adx_5m=22.0, adx_slope_5m=0.5, atr_ratio_5m=1.1)
        self.assertEqual(regime_trending, REGIME_TRENDING)

        regime_consolidating = classify_market_regime(adx_5m=15.0, adx_slope_5m=-0.2, atr_ratio_5m=0.9)
        self.assertEqual(regime_consolidating, REGIME_CONSOLIDATING)

    def test_intelligence_scoring_matrix(self):
        # Test HYBRID_SILVER_BULLET Mode
        score_hybrid, breakdown_hybrid = calculate_intelligence_score(
            direction=config.CONTRACT_TYPE_UP,
            current_price=65000.0,
            ema_200_15m=64000.0,
            regime=REGIME_TRENDING,
            adx_5m=25.0,
            atr_ratio_5m=1.0,
            has_liquidity_sweep=True,
            has_fvg=True,
            in_silver_bullet=True,
            key_level_clearance_atr=1.5,
            close_1m=65000.0,
            ema_20_1m=64900.0,
            rsi_14_1m=60.0,
            strategy_mode="HYBRID_SILVER_BULLET"
        )
        self.assertEqual(score_hybrid, 100)
        self.assertTrue(breakdown_hybrid["meets_threshold"])
        self.assertEqual(breakdown_hybrid["mode"], "HYBRID_SILVER_BULLET")

        # Test AEGIS_CLASSIC Mode
        score_classic, breakdown_classic = calculate_intelligence_score(
            direction=config.CONTRACT_TYPE_UP,
            current_price=65000.0,
            ema_200_15m=64000.0,
            regime=REGIME_TRENDING,
            adx_5m=25.0,
            atr_ratio_5m=1.0,
            has_liquidity_sweep=True,
            has_fvg=False,
            in_silver_bullet=False,
            key_level_clearance_atr=1.5,
            close_1m=65000.0,
            ema_20_1m=64900.0,
            rsi_14_1m=60.0,
            strategy_mode="AEGIS_CLASSIC"
        )
        self.assertEqual(score_classic, 100)
        self.assertTrue(breakdown_classic["meets_threshold"])
        self.assertEqual(breakdown_classic["mode"], "AEGIS_CLASSIC")

    def test_dynamic_proximity_guard(self):
        atr_5m = 100.0
        current_price = 65000.0
        res = 65020.0  # Clearance = $20, buffer = $50 -> Should block MULTUP
        sup = 64000.0

        allowed, clearance = check_dynamic_proximity_guard(current_price, res, sup, atr_5m, config.CONTRACT_TYPE_UP)
        self.assertFalse(allowed)

        res_far = 65200.0  # Clearance = $200, buffer = $50 -> Should allow MULTUP
        allowed_far, clearance_far = check_dynamic_proximity_guard(current_price, res_far, sup, atr_5m, config.CONTRACT_TYPE_UP)
        self.assertTrue(allowed_far)

    def test_step_ratchet_trailing_engine(self):
        pm = PositionManager()
        pm.open_position(101, config.CONTRACT_TYPE_UP, 65000.0)

        # Initial SL Floor
        self.assertEqual(pm.current_sl_floor, -0.75)

        # PnL +$0.40 -> Floor remains -$0.75
        should_close, floor, _ = pm.update_pnl_and_ratchet(0.40)
        self.assertEqual(floor, -0.75)
        self.assertFalse(should_close)

        # PnL +$0.50 -> Break-Even ratchets floor to $0.00
        should_close, floor, _ = pm.update_pnl_and_ratchet(0.50)
        self.assertEqual(floor, 0.0)
        self.assertFalse(should_close)

        # PnL +$0.75 -> Dynamic Step Profit Lock (Peak +$0.75 - Gap $0.50 -> +$0.25)
        should_close, floor, _ = pm.update_pnl_and_ratchet(0.75)
        self.assertEqual(floor, 0.25)
        self.assertFalse(should_close)

        # PnL +$0.80 -> Tight 5-cent Step Profit Lock (Peak +$0.80 - Gap $0.50 -> +$0.30)
        should_close, floor, _ = pm.update_pnl_and_ratchet(0.80)
        self.assertEqual(floor, 0.30)
        self.assertFalse(should_close)

        # Drop PnL to +$0.25 -> Breach floor at +$0.30 -> Trigger manual sell
        should_close, floor, reason = pm.update_pnl_and_ratchet(0.25)
        self.assertTrue(should_close)

    def test_native_server_sl_handshake_and_quarantine(self):
        engine = AegisExecutionEngine()
        engine.position_mgr.open_position(202, config.CONTRACT_TYPE_UP, 65000.0)

        poc_server_close = {
            "contract_id": 202,
            "profit": -0.75,
            "is_sold": 1,
            "is_expired": 0,
            "status": "lost"
        }

        res = engine.handle_poc_update(poc_server_close)
        self.assertEqual(res["action"], "SERVER_CLOSED")
        self.assertFalse(engine.position_mgr.is_open)
        self.assertEqual(engine.consecutive_losses, 1)

        # Check 10-Minute Loss Quarantine Enforcement
        allowed, reason = engine.is_execution_allowed()
        self.assertFalse(allowed)
        self.assertIn("Loss Quarantine active", reason)

    def test_mt5_server_sl_sync_and_restart(self):
        engine = AegisExecutionEngine()
        # Simulate position opened on MT5
        engine.position_mgr.open_position(505, config.CONTRACT_TYPE_UP, 65000.0)
        self.assertTrue(engine.position_mgr.is_open)

        # Simulate MT5 server closing position natively on SL (pos becomes None)
        pos = None
        is_active = pos is not None
        if not is_active and engine.position_mgr.is_open:
            engine.position_mgr.close_position()
            engine._record_trade_result(-0.75, is_server_close=True)

        # Verify position manager state is cleared
        self.assertFalse(engine.position_mgr.is_open)

        # Verify 10-minute loss quarantine is active
        allowed, reason = engine.is_execution_allowed()
        self.assertFalse(allowed)
        self.assertIn("Loss Quarantine active", reason)

        # Fast-forward time past quarantine expiry
        engine.quarantine_until = time.time() - 1.0

        # Verify engine re-enables trading after quarantine expires
        allowed_after, reason_after = engine.is_execution_allowed()
        self.assertTrue(allowed_after)
        self.assertEqual(reason_after, "Ready")


if __name__ == "__main__":
    unittest.main()
