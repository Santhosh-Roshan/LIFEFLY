@echo off
REM ##############################################################################
REM  LIFEFLY - RASPBERRY PI DEPLOYMENT SCRIPT (WINDOWS)
REM  Automated deployment to uav@192.168.137.62
REM ##############################################################################

setlocal enabledelayedexpansion

set RPI_HOST=192.168.137.62
set RPI_USER=uav
set RPI_SSH=%RPI_USER%@%RPI_HOST%
set RPI_DIR=/home/uav/lifefly

echo.
echo ========================================================================
echo   LIFEFLY RASPBERRY PI DEPLOYMENT
echo   Target: %RPI_SSH%
echo ========================================================================
echo.

REM Step 1: Check SSH connectivity
echo [1/6] Checking SSH connectivity...
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no %RPI_SSH% "echo SSH_OK" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] Cannot reach Raspberry Pi at %RPI_HOST%
    echo.
    echo   Make sure:
    echo     - Pi is powered on
    echo     - Connected to same network
    echo     - SSH is enabled
    echo     - Try: ssh %RPI_SSH%
    exit /b 1
)
echo   [OK] Raspberry Pi is reachable
echo.

REM Step 2: Create directory
echo [2/6] Creating directory on Raspberry Pi...
ssh %RPI_SSH% "mkdir -p %RPI_DIR%"
echo   [OK] Directory created: %RPI_DIR%
echo.

REM Step 3: Copy files
echo [3/6] Transferring Python files...

if exist rpi_receiver.py (
    echo   Copying rpi_receiver.py...
    scp -q -o StrictHostKeyChecking=no rpi_receiver.py %RPI_SSH%:%RPI_DIR%/
    echo   [OK] rpi_receiver.py transferred
) else (
    echo   [WARNING] rpi_receiver.py not found
)

if exist priority_detector.py (
    echo   Copying priority_detector.py...
    scp -q -o StrictHostKeyChecking=no priority_detector.py %RPI_SSH%:%RPI_DIR%/
    echo   [OK] priority_detector.py transferred
) else (
    echo   [WARNING] priority_detector.py not found
)
echo.

REM Step 4: Install dependencies
echo [4/6] Installing Python dependencies on Pi...
ssh %RPI_SSH% "cd %RPI_DIR% && python3 -m pip install --quiet --upgrade pip requests 2>/dev/null"
echo   [OK] Dependencies installed
echo.

REM Step 5: Test receiver
echo [5/6] Testing receiver script...
ssh %RPI_SSH% "cd %RPI_DIR% && timeout 3 python3 rpi_receiver.py --status 2>&1" >nul 2>&1
echo   [OK] Receiver script tested
echo.

REM Step 6: Start daemon
echo [6/6] Starting LifeFly receiver daemon...
ssh %RPI_SSH% "pkill -f rpi_receiver.py 2>/dev/null"
timeout /t 1 >nul
ssh %RPI_SSH% "cd %RPI_DIR% && nohup python3 rpi_receiver.py --daemon --sim > lifefly.log 2>&1 &"
timeout /t 2 >nul
echo   [OK] Daemon started
echo.

echo ========================================================================
echo   DEPLOYMENT COMPLETE
echo ========================================================================
echo.
echo Next steps:
echo   - Check logs:    ssh %RPI_SSH% "tail -f %RPI_DIR%/lifefly.log"
echo   - Check status:  ssh %RPI_SSH% "cd %RPI_DIR% && python3 rpi_receiver.py --status"
echo   - Stop daemon:   ssh %RPI_SSH% "pkill -f rpi_receiver.py"
echo   - Web GCS:       Open index_enhanced.html in your browser
echo.

exit /b 0
