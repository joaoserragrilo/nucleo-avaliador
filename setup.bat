@echo off
echo.
echo ===== Setup Avaliador de Propriedades =====
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Confirma que Python x64 foi instalado com "Add Python to PATH" marcado.
    pause
    exit /b 1
)

python --version
python -c "import sys; arch='ARM64' if 'ARM64' in sys.version else 'AMD64' if 'AMD64' in sys.version else 'OUTRA'; print('Binario Python:', arch)"
echo.

if exist .venv (
    echo A apagar .venv anterior...
    rmdir /s /q .venv
)
echo A criar virtualenv em .venv...
python -m venv .venv
if errorlevel 1 (
    echo [ERRO] Falhou a criar virtualenv.
    pause
    exit /b 1
)

echo A instalar dependencias...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
python -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falhou a instalar dependencias.
    pause
    exit /b 1
)

echo.
echo ===== Setup completo =====
echo Para correr o app, executa: run.bat
echo.
pause
