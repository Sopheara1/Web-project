@echo off
chcp 65001 >nul
title Cam-EDC - Stop Server

echo ===================================================================
echo     កំពុងបិទដំណើរការកម្មវិធី Cam-EDC (Port 5000)...
echo ===================================================================
echo.

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
    echo បានបិទ Process PID: %%a
)

echo.
echo [OK] បានបិទដំណើរការកម្មវិធី និងសម្អាត Port 5000 រួចរាល់ហើយ!
ping 127.0.0.1 -n 2 >nul
exit
