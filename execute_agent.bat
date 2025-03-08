@echo off
@REM Script para ejecutar un agente desde línea de comandos
@REM Uso: execute_agent.bat <ID_AGENTE> [--verbose]

if "%1"=="" (
  echo ERROR: Debe especificar el ID del agente
  echo.
  echo Uso:   execute_agent.bat ID_AGENTE [--verbose]
  echo.
  echo Ejemplo: execute_agent.bat 8191feef-546d-46a8-a26f-b92073882f5c
  exit /b 1
)

echo Ejecutando agente %1...
python src/execute_agent_cli.py %* 