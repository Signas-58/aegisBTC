@echo off
title AEGIS-WELTRADE LIVE TRADING TERMINAL
cd /d "%~dp0"

echo ================================================================================
echo     AEGIS-WELTRADE MULTI-PROFILE AI EXECUTION ENGINE
echo ================================================================================
echo  Select Operational Profile:
echo    [1] Profile 1: 5-Minute Intraday Momentum Expansion (EXPANSION_M5) [Recommended Default]
echo                   - 10-45 Min Holding Time | 1:2 Risk/Reward | 15p SL / 30p TP
echo    [2] Profile 2: 1-Minute Micro-Scalper (SCALP_M1)
echo                   - 2-12 Min Holding Time | Fast Break-Even | 10p SL / 15p TP
echo    [3] Profile 3: Strict Pure ICT Silver Bullet (SILVER_BULLET_PURE)
echo                   - Exact 60-Min CAT Windows (10-11 & 16-17) | 12p SL / 24p TP
echo ================================================================================
set /p choice="Enter choice (1, 2, or 3, default 1): "

if "%choice%"=="2" (
    echo Launching 1-Minute Micro-Scalper Mode (SCALP_M1)...
    python main.py --live --mode SCALP_M1
) else if "%choice%"=="3" (
    echo Launching Strict Pure Silver Bullet Mode (SILVER_BULLET_PURE)...
    python main.py --live --mode SILVER_BULLET_PURE
) else (
    echo Launching 5-Minute Intraday Momentum Expansion Mode (EXPANSION_M5)...
    python main.py --live --mode EXPANSION_M5
)

pause
