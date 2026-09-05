@echo off
title AEGIS-BTC LIVE TRADING TERMINAL
cd /d "%~dp0"

echo ================================================================================
echo     AEGIS-BTC MULTI-STRATEGY LAUNCHER
echo ================================================================================
echo  Select Strategy Execution Mode:
echo    [1] Option 1: Aegis Classic Strategy (24/7 MTF Sweep & Momentum)
echo    [2] Option 2: ICT Silver Bullet Hybrid Strategy (CAT Timing + 3m FVG) [Default]
echo ================================================================================
set /p choice="Enter choice (1 or 2, default 2): "

if "%choice%"=="1" (
    echo Launching Aegis Classic Strategy Mode...
    python main.py --live --mode classic
) else (
    echo Launching ICT Silver Bullet Hybrid Strategy Mode...
    python main.py --live --mode hybrid
)

pause
