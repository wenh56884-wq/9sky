@echo off
chcp 65001 >nul
title JiuTianWuTong AI Workbench
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0infra\scripts\setup_and_start.ps1"
if errorlevel 1 pause
