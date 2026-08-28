@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Rahul AI - Premium Launcher
cd /d "%~dp0"

color 0E

echo ==========================================================================
echo    ____  ____    _    _   _  _____   _    ____   _   _    
echo   ^|  _ \^|  _ \  / \  ^| \ ^|^| ^|____^| / \  ^|  _ \ / \ ^|^| ^|   
echo   ^| ^|_) ^| ^|_) ^|/ _ \ ^|  \^|^| ^|^|_  / _ \ ^| ^|_) / _ \^|^| ^|   
echo   ^|  _ ^<^|  _ ^<^| ___ \^| ^|\  ^|^|^| ^|___/ ___ \^|  __/ ___ \^|^|__  
echo   ^|_^| \_\_^| \_\_^|   \_\_^| \_^|_____/_/   \_\_^| /_/   \_\_\___^| 
echo                       P R E M I U M   L O A D E R
echo ==========================================================================
echo.
echo Launching automated bootstrap sequence...

powershell.exe -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"

if %errorlevel% neq 0 (
  echo ERROR: Bootstrap failed.
  pause
  exit /b %errorlevel%
)
exit /b 0
