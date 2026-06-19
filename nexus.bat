@echo off
REM Nexus CLI wrapper for Windows
REM Coloca este directorio en tu PATH o ejecuta setup_path.bat

set NEXUS_DIR=%~dp0
python "%NEXUS_DIR%nexus" %*
