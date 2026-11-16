@echo off
setlocal
echo ====================================================================
echo  Configurando entorno local (uv) para Comparador de Precios
echo ====================================================================

cd /d "%~dp0\.."

where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] No se encontro 'uv' en el PATH. Instala uv antes de continuar.
    exit /b 1
)

if not exist "backend\.venv" (
    echo [*] Creando entorno virtual en backend\.venv...
    uv venv backend\.venv
) else (
    echo [*] Entorno virtual existente detectado en backend\.venv.
)

echo [*] Sincronizando dependencias de backend (incluyendo dev)...
uv pip install --python backend\.venv -e "./backend[dev]"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Fallo la instalacion de dependencias con uv pip.
    exit /b %ERRORLEVEL%
)

echo.
echo ====================================================================
echo  [OK] Entorno configurado exitosamente.
echo  Para activar el entorno virtual en CMD:
echo    backend\.venv\Scripts\activate.bat
echo  En PowerShell:
echo    .\backend\.venv\Scripts\Activate.ps1
echo ====================================================================

