@echo off
title LiveYoung ERP
echo Starting LiveYoung ERP...
echo.
echo The application will open in your browser at http://localhost:8501
echo Press Ctrl+C to stop the server.
echo.
start http://localhost:8501
python -m streamlit run app/main.py --server.port 8501 --server.headless true
pause
