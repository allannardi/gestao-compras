@echo off
cd /d "%~dp0"
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)
start "" "http://localhost:8502"
streamlit run app.py --server.port 8502 --server.address 0.0.0.0
