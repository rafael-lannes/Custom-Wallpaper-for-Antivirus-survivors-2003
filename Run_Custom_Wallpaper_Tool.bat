@echo off
title Custom Wallpaper for Antivirus Survivors 2003
cd /d "%~dp0"
python custom_wallpaper_tool.py
if errorlevel 1 (
    echo.
    echo An error occurred while launching the tool.
    pause
)
