@echo off
title AEGIS-BTC LIVE TRADING TERMINAL
echo Starting Aegis-BTC Live Trading Bot...
cd /d "%~dp0"
python main.py --live
pause
