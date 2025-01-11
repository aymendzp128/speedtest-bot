@echo off
echo Uninstalling Telegram Bot Service...

set "SERVICE_NAME=TelegramSpeedBot"

:: إيقاف الخدمة
net stop %SERVICE_NAME%

:: إزالة الخدمة
nssm remove %SERVICE_NAME% confirm

echo Service uninstalled successfully!
pause
