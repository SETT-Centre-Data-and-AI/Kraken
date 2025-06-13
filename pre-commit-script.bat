@echo off
setlocal

REM Get the list of staged files
for /f "tokens=*" %%i in ('git diff --cached --name-only') do (
    set "staged_files=%%i !staged_files!"
)

REM Check if there are any staged files
if "%staged_files%"=="" (
    echo No files staged for commit.
    exit /b 0
)

REM Run pre-commit on the staged files
pre-commit run --files %staged_files%

endlocal
