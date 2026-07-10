@echo off
REM Build and deploy DC-ShiftMaster Web to Amazon S3.
REM
REM Usage:
REM   build_and_deploy.bat <S3_BUCKET_NAME>
REM
REM Prerequisites:
REM   - Python with flet installed (pip install flet)
REM   - AWS CLI configured with appropriate credentials

if "%~1"=="" (
    echo Usage: %~nx0 ^<S3_BUCKET_NAME^>
    exit /b 1
)

set BUCKET=%~1
set BUILD_DIR=build\web

echo ==> Building Flet web app...
flet build web --output %BUILD_DIR%

if not exist "%BUILD_DIR%\index.html" (
    echo ERROR: index.html not found in %BUILD_DIR%
    exit /b 1
)

echo ==> index.html found in %BUILD_DIR%

echo ==> Deploying to s3://%BUCKET% ...
aws s3 sync "%BUILD_DIR%" "s3://%BUCKET%" --delete --cache-control "max-age=3600"

echo ==> Done.
