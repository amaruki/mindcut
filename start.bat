@echo off
setlocal

cd /d "%~dp0"

title MindCut Launcher
cls

echo   MindCut - Auto Launcher
echo ===================================================
echo(

set "VENV_DIR=.venv"
set "PYTHON_CMD="
set "USE_UV=0"

:: Check if uv is installed
where uv >nul 2>nul
if %errorlevel% equ 0 set "USE_UV=1"

if exist "%VENV_DIR%\Scripts\python.exe" set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
if defined PYTHON_CMD goto :DEPS

echo [*] Virtual Environment tidak ditemukan.
if "%USE_UV%"=="1" (
    echo [*] Menggunakan 'uv' untuk membuat venv...
    uv venv "%VENV_DIR%"
    if errorlevel 1 goto :VENV_FAIL
) else (
    echo [*] 'uv' tidak ditemukan. Menggunakan 'python' bawaan system...
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 (
        echo [OK] Python 3.11 ditemukan. Membuat venv...
        py -3.11 -m venv "%VENV_DIR%"
    ) else (
        echo [WARN] Python 3.11 tidak ditemukan di system. Menggunakan default 'python'...
        python -m venv "%VENV_DIR%"
    )
    if errorlevel 1 goto :VENV_FAIL
)

:SET_PY
if not exist "%VENV_DIR%\Scripts\python.exe" goto :VENV_FAIL
set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
echo [OK] Venv berhasil dibuat.

:DEPS
echo(
echo [*] Checking ^& Installing dependencies...
if "%USE_UV%"=="1" (
    uv pip install -r requirements.txt --python "%PYTHON_CMD%"
) else (
    "%PYTHON_CMD%" -m pip install --upgrade pip >nul
    "%PYTHON_CMD%" -m pip install -r requirements.txt
)
if errorlevel 1 goto :REQ_FAIL

echo [*] Checking AI Subtitle dependencies (faster-whisper)...
"%PYTHON_CMD%" -c "import faster_whisper" >nul 2>nul
if errorlevel 1 goto :INSTALL_FWHISPER
echo [OK] faster-whisper already installed.
goto :RUN

:INSTALL_FWHISPER
echo [*] Installing faster-whisper...
if "%USE_UV%"=="1" (
    uv pip install faster-whisper --python "%PYTHON_CMD%"
) else (
    "%PYTHON_CMD%" -m pip install faster-whisper
)
if errorlevel 1 (
    echo [WARN] Gagal install faster-whisper. Fitur subtitle mungkin tidak jalan.
    echo        (Biasanya karena versi Python tidak kompatibel/preview version^)
) else (
    echo [OK] faster-whisper installed.
)

:RUN
echo(
echo ===================================================
echo   PENTING:
echo   Pastikan FFmpeg sudah terinstall agar fungsi crop jalan.
echo   Jika belum, install manual via PowerShell (Administrator^):
echo       winget install Gyan.FFmpeg
echo.
echo   Semua siap! Menjalankan Web App...
echo   Buka browser di: http://127.0.0.1:5173 (Frontend SPA^)
echo                    http://127.0.0.1:5000 (Backend API^)
echo ===================================================
echo(

if defined YHC_CHECK_ONLY goto :DONE

:: Check if frontend exists and start it in a separate window
if exist "frontend\package.json" (
    echo [*] Starting Frontend Server (Vite^)...
    start "MindCut Frontend (Vite)" cmd /c "cd frontend && npm install && npm run dev"
) else (
    echo [WARN] Frontend folder not found. Skipping Vite start.
)

:: Start Backend
"%PYTHON_CMD%" webapp.py
goto :DONE

:NO_PY
echo [X] Python tidak ditemukan sama sekali!
echo     Install Python 3.11 dari python.org atau Microsoft Store.
goto :FAIL

:VENV_FAIL
echo [X] Gagal membuat venv.
goto :FAIL

:REQ_FAIL
echo [X] Gagal install basic dependencies. Cek koneksi internet.
goto :FAIL

:FAIL
echo(
echo [INFO] Aplikasi berhenti.
echo Tekan sembarang tombol untuk menutup jendela ini...
pause
exit /b 1

:DONE
echo(
echo [INFO] Aplikasi berhenti.
echo Tekan sembarang tombol untuk menutup jendela ini...
pause
exit /b 0
