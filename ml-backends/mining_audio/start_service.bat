@echo off
echo Starting Mining Audio ML Backend Service...
echo.

REM Activate virtual environment if it exists
if exist "..\..\venv\Scripts\activate.bat" (
    call ..\..\venv\Scripts\activate.bat
    echo Virtual environment activated.
) else (
    echo Warning: Virtual environment not found. Using system Python.
)

REM Start the service
echo Starting the ML backend service on port 9090...
python _wsgi.py --host 0.0.0.0 --port 9090 --debug

echo.
echo Service stopped.
pause