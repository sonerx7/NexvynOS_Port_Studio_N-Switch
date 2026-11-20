@echo off
title Red Alert 2: Yuri Port - Nexvyn OS (SDK 1.2)
echo ============================================================
echo   Red Alert 2 / Yuri's Revenge - Nexvyn OS Switch Port v1.1
echo   SDK: v1.3.28-beta.2 (Native SDK 1.2) + Full Launcher
echo ============================================================
echo.

echo [*] Acik emulator kontrolleri yapiliyor...
taskkill /F /IM Ryujinx.exe >nul 2>&1
timeout /t 1 /nobreak >nul

set "RYU_DIR="
if exist "C:\Users\soned\OneDrive\Masaüstü\ryujinx\Ryujinx.exe" (
    set "RYU_DIR=C:\Users\soned\OneDrive\Masaüstü\ryujinx"
) else if exist "%USERPROFILE%\OneDrive\Masaüstü\ryujinx\Ryujinx.exe" (
    set "RYU_DIR=%USERPROFILE%\OneDrive\Masaüstü\ryujinx"
) else if exist "C:\Users\soned\OneDrive\MASAST~1\ryujinx\Ryujinx.exe" (
    set "RYU_DIR=C:\Users\soned\OneDrive\MASAST~1\ryujinx"
)

if not defined RYU_DIR (
    echo [HATA] Ryujinx.exe bulunamadi!
    pause
    exit /b 1
)

set "NRO_PATH=C:\Users\soned\Documents\antigravityProjects\NintendoSwitchProjects\SnxOS-NX\build\release-candidate\NexvynOS-1.3.28-beta.2-efb1fc2b.nro"
if not exist "%NRO_PATH%" (
    set "NRO_PATH=C:\Users\soned\Documents\antigravityProjects\NintendoSwitchProjects\SnxOS-NX\NexvynOS.nro"
)
if not exist "%NRO_PATH%" (
    set "NRO_PATH=%APPDATA%\Ryujinx\sdcard\switch\NexvynOS.nro"
)

echo [+] Emulator: %RYU_DIR%\Ryujinx.exe
echo [+] OS NRO:   %NRO_PATH%
echo [+] Paket:    %APPDATA%\Ryujinx\sdcard\NexvynOS\Applications\com.sonerx7.redalert2.nxvapp
echo [+] Nexvyn OS baslatiliyor...
echo.

cd /d "%RYU_DIR%"
start "" "Ryujinx.exe" "%NRO_PATH%"
