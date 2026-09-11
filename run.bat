@echo off
chcp 65001 >nul
title Cam-EDC - Electricity Management System

echo ===================================================================
echo     Cam-EDC: ប្រព័ន្ធគ្រប់គ្រងការប្រើប្រាស់ និងវិក័យប័ត្រអគ្គិសនី
echo ===================================================================
echo.

:: 1. បិទ Process ចាស់នៅលើ Port 5000 ប្រសិនបើមាន
echo [1/4] កំពុងពិនិត្យ និងសម្អាត Port 5000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 2. ពិនិត្យ និងតម្លើងបណ្ណាល័យដែលត្រូវការ
echo [2/4] កំពុងពិនិត្យបណ្ណាល័យ Python...
python -m pip install -r requirements.txt --quiet >nul 2>&1

:: 3. ចាប់ផ្តើម Web Server
echo [3/4] កំពុងដំណើរការ Web Server...
start "" /b python app.py

:: រង់ចាំ 2 វិនាទីឱ្យ Server ដំណើរការស្រួលបួល
ping 127.0.0.1 -n 3 >nul

:: 4. បើក Browser ទៅកាន់ Web Application ដោយស្វ័យប្រវត្តិ
echo [4/4] កំពុងបើកកម្មវិធីនៅលើ Browser (http://127.0.0.1:5000)...
start http://127.0.0.1:5000

echo.
echo ===================================================================
echo  [OK] កម្មវិធីដំណើរការជោគជ័យនៅលើ: http://127.0.0.1:5000
echo.
echo  * ចុចគ្រាប់ចុចណាមួយ (Any Key) លើផ្ទាំងនេះ ដើម្បី បិទកម្មវិធី ដោយស្វ័យប្រវត្តិ...
echo ===================================================================
pause >nul

echo.
echo កំពុងបិទកម្មវិធី Cam-EDC ដោយស្វ័យប្រវត្តិ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo [OK] បានបិទកម្មវិធី និង Port 5000 រួចរាល់ដោយជោគជ័យ!
ping 127.0.0.1 -n 2 >nul
exit
