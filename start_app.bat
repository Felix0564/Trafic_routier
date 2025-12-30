@echo off
echo Starting Traffic Simulation Application...

REM Set environment variables to fix OpenCV threading issues
set OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp|buffer_size;64
set PYTHONUNBUFFERED=1

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated.
)

REM Start the application
echo Running application...
python app.py

REM Deactivate virtual environment if activated
if exist venv\Scripts\deactivate.bat (
    call venv\Scripts\deactivate.bat
)

echo Application closed.
pause 