@echo off
REM Correr o Avaliador de Propriedades

if not exist .venv (
    echo [ERRO] Virtualenv nao existe. Corre setup.bat primeiro.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
streamlit run app.py
