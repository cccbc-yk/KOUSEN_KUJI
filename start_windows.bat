@echo off
rem Double-click to start. See MANUAL.md
cd /d "%~dp0"
set UV=uv
where uv >nul 2>nul || set UV="%USERPROFILE%\.local\bin\uv.exe"
%UV% --version >nul 2>nul
if errorlevel 1 (
  echo uv was not found. Install it first. See MANUAL.md
  pause
  exit /b 1
)
%UV% run kuji
if errorlevel 1 pause
