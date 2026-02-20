@echo off
REM ALS Doctor - Ableton Project Health Analyzer
REM Usage:
REM   als-doctor quick "path\to\project.als"
REM   als-doctor diagnose "path\to\project.als"
REM   als-doctor compare "before.als" "after.als"
REM   als-doctor scan "D:\Ableton Projects" --limit 30

python "%~dp0projects\music-analyzer\src\als_doctor.py" %*
