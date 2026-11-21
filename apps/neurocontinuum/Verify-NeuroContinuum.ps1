[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if (-not $env:CONDA_PREFIX) { throw 'Activate the existing bainp environment first.' }
$python = Join-Path $env:CONDA_PREFIX 'python.exe'
& $python (Join-Path $PSScriptRoot 'tests\verify.py')
if ($LASTEXITCODE -ne 0) { throw 'NeuroContinuum verification failed. Share the final test output.' }
