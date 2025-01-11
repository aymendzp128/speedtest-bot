@echo off
echo Installing Telegram Bot Service...

:: تحديد المسارات
set "PYTHON_PATH=python"
set "BOT_SCRIPT=%~dp0bot.py"
set "SERVICE_NAME=TelegramSpeedBot"

:: تثبيت الخدمة
nssm install %SERVICE_NAME% %PYTHON_PATH%
nssm set %SERVICE_NAME% AppParameters "%BOT_SCRIPT%"
nssm set %SERVICE_NAME% AppDirectory "%~dp0"
nssm set %SERVICE_NAME% DisplayName "Telegram Speed Test Bot"
nssm set %SERVICE_NAME% Description "خدمة بوت تيليجرام لقياس سرعة الإنترنت"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% AppStdout "%~dp0logs\service.log"
nssm set %SERVICE_NAME% AppStderr "%~dp0logs\error.log"

:: بدء الخدمة
net start %SERVICE_NAME%

echo Service installed successfully!
pause
