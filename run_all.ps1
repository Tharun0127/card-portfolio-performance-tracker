# Rebuild everything from raw data on Windows:  .\run_all.ps1
# Creates the virtual environment on first use, installs the pinned requirements,
# then runs the whole pipeline and the tests.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment with Python 3.11"
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11 not found. Install it with: py install 3.11" }
}

.\.venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

.\.venv\Scripts\python.exe run_all.py
exit $LASTEXITCODE
