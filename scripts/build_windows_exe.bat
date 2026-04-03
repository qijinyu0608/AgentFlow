@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0\.."

if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)

echo [1/4] Building frontend...
pushd frontend
call npm install
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1
popd

echo [2/4] Installing PyInstaller...
call %PYTHON% -m pip install pyinstaller
if errorlevel 1 exit /b 1

echo [3/4] Packaging AgentMesh...
call %PYTHON% -m PyInstaller --noconfirm --clean agentmesh.spec
if errorlevel 1 exit /b 1

echo [4/4] Copying runtime files...
if exist "config-template.yaml" copy /y "config-template.yaml" "dist\AgentMesh\config-template.yaml" >nul
if exist "config.yaml" copy /y "config.yaml" "dist\AgentMesh\config.yaml" >nul
if exist "data" xcopy "data" "dist\AgentMesh\data" /e /i /y >nul

echo.
echo Packaging complete.
echo Output directory: dist\AgentMesh
echo Launch: dist\AgentMesh\AgentMesh.exe
