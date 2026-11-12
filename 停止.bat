@echo off
chcp 65001 >nul
title Stop - JiuTianWuTong AI Workbench
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0infra\scripts\stop_all.ps1"
if errorlevel 1 pause
