@echo off
title AEGIS-WELTRADE LIVE TRADING TERMINAL
cd /d "%~dp0"

echo ================================================================================
echo     AEGIS-WELTRADE MULTI-STRATEGY LAUNCHER
echo ================================================================================
echo  Select Strategy Execution Mode:
echo    [1] Option 1: EURUSD Master Strategy (15m Macro + 3m FVG + 1m Bar-Close Momentum) [Default]
echo    [2] Option 2: Aegis Classic Strategy (24/7 MTF Sweep & Momentum)
echo    [3] Option 3: ICT Silver Bullet Hybrid Strategy (CAT Timing + 3m FVG)
echo ================================================================================
set /p choice="Enter choice (1, 2, or 3, default 1): "

if "%choice%"=="2" (
    echo Launching Aegis Classic Strategy Mode...
    python main.py --live --mode classic
) else if "%choice%"=="3" (
    echo Launching ICT Silver Bullet Hybrid Strategy Mode...
    python main.py --live --mode hybrid
) else (
    echo Launching EURUSD Master Strategy Mode...
    python main.py --live --mode master
)

pause
