@echo off
title AEGIS-WELTRADE LIVE TRADING TERMINAL
cd /d "%~dp0"

echo ================================================================================
echo     AEGIS-WELTRADE MULTI-PROFILE AI EXECUTION ENGINE
echo ================================================================================
echo  Select Operational Profile:
echo    [1] Profile 1: 5-Minute Intraday Momentum Expansion [EXPANSION_M5] - Recommended
echo                   10 to 45 Min Hold -- 1:2 Risk/Reward -- 15p SL / 30p TP
echo    [2] Profile 2: 1-Minute Micro-Scalper [SCALP_M1]
echo                   2 to 12 Min Hold -- Fast Break-Even -- 10p SL / 15p TP
echo    [3] Profile 3: Strict Pure ICT Silver Bullet [SILVER_BULLET_PURE]
echo                   Exact 60-Min CAT Windows -- 12p SL / 24p TP
echo ================================================================================
set choice=1
set /p choice="Enter choice (1, 2, or 3, default 1): "

:: Ensure Weltrade MT5 GUI window is running on Windows desktop
tasklist /fi "imagename eq terminal64.exe" 2>nul | findstr /i "terminal64.exe" >nul
if errorlevel 1 (
    echo [AEGIS] Opening Weltrade MT5 Terminal window...
    start "" "C:\Program Files\Weltrade MT5 Terminal\terminal64.exe"
    timeout /t 2 /nobreak >nul
)

if "%choice%"=="2" goto run_m1
if "%choice%"=="3" goto run_pure
goto run_m5

:run_m1
echo.
echo [AEGIS] Launching Profile 2: 1-Minute Micro-Scalper [SCALP_M1]...
echo.
python main.py --live --child --mode SCALP_M1
goto done

:run_pure
echo.
echo [AEGIS] Launching Profile 3: Strict Pure Silver Bullet [SILVER_BULLET_PURE]...
echo.
python main.py --live --child --mode SILVER_BULLET_PURE
goto done

:run_m5
echo.
echo [AEGIS] Launching Profile 1: 5-Minute Intraday Momentum Expansion [EXPANSION_M5]...
echo.
python main.py --live --child --mode EXPANSION_M5
goto done

:done
echo.
echo ================================================================================
echo Engine execution ended. Press any key to exit.
echo ================================================================================
pause
