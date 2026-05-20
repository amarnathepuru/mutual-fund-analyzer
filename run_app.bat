@echo off
cd /d "%~dp0"
echo.
echo  Starting Mutual Fund Analyzer...
echo  Keep this window open while you use the app.
echo  Browser should open to: http://localhost:8501
echo  If it does not, copy that address into Chrome or Edge.
echo.
python -m streamlit run app.py
if errorlevel 1 (
    echo.
    echo  Failed to start. Try: pip install -r requirements.txt
    echo.
)
pause
