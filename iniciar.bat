@echo off
REM Inicia Colombia Business Intelligence Hub (Windows).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual e instalando dependencias...
  python -m venv .venv || goto :error
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)
".venv\Scripts\python.exe" -m streamlit run app\dashboard.py
goto :eof
:error
echo No fue posible preparar el entorno. Verifique que Python 3.11 o 3.12 este instalado.
pause
