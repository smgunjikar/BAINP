# BAINP NeuroVision: start the existing import worker using the conda bainp-brain Python,
# even when this PowerShell terminal currently has the (bainp) environment activated.
# No raw MRI files are modified by this launcher.
[CmdletBinding()]
param([string]$ProjectRoot='')
$ErrorActionPreference='Stop'
if (-not $ProjectRoot) { $ProjectRoot=Join-Path $env:USERPROFILE 'OneDrive\Desktop\BAINP' }
$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot -ErrorAction Stop).Path
$worker=Join-Path $ProjectRoot 'apps\neurovision\backend\import_worker.py'
if (-not (Test-Path -LiteralPath $worker -PathType Leaf)) {throw "Worker missing: $worker"}
if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    throw 'Conda was not found in this terminal. Open Anaconda/Miniconda PowerShell or use the original worker startup script after activating bainp-brain.'
}
# Discover the actual environment root; never guess C:\Users\...\miniconda3.
try {$envInfo=(& conda info --envs --json | Out-String | ConvertFrom-Json)}
catch {throw 'Cannot read conda environment locations. Run: conda info --envs'}
$brainEnvs=@($envInfo.envs | Where-Object { (Split-Path -Path $_ -Leaf) -eq 'bainp-brain' })
if ($brainEnvs.Count -ne 1) {
    throw 'Exactly one bainp-brain conda environment is required. Run: conda env list'
}
$python=Join-Path $brainEnvs[0] 'python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {throw "Imaging Python is missing: $python"}
Write-Host "Verifying imaging environment: $python"
& $python -c 'import numpy, scipy, nibabel; from skimage.measure import marching_cubes; from nibabel.processing import resample_to_output'
if ($LASTEXITCODE -ne 0) {throw 'Imaging dependencies are missing in bainp-brain. Do not install packages into the regular bainp web environment.'}
$dataRoot=if($env:NEUROVISION_DATA_DIR){$env:NEUROVISION_DATA_DIR}else{Join-Path $env:USERPROFILE 'BAINP_DATA\derived\neurovision\v1'}
$logDir=Join-Path $dataRoot 'import_jobs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
# Avoid launching a duplicate when another healthy worker is already running.
$heartbeat=Join-Path $logDir 'heartbeat.json'
if(Test-Path -LiteralPath $heartbeat -PathType Leaf){
 try {
    $info=Get-Content -LiteralPath $heartbeat -Raw | ConvertFrom-Json
    $age=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-[double]$info.time
    if($age -ge 0 -and $age -lt 15) {
        if($info.protocol -ne 'tenant-v2') {
            throw "An OLDER imaging worker (PID $($info.pid)) is still running. Stop that worker safely, then run this launcher again. It cannot process user workspaces."
        }
        Write-Host "Compatible imaging worker is already active (PID $($info.pid))."
        return
    }
 } catch {}
}
$stamp=Get-Date -Format 'yyyyMMddTHHmmssfff'
$stdout=Join-Path $logDir "worker-$stamp.log"
$stderr=Join-Path $logDir "worker-$stamp-error.log"
$p=Start-Process -FilePath $python -ArgumentList @('-u',('"'+$worker+'"'),'--watch') -WorkingDirectory $ProjectRoot -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
Start-Sleep -Seconds 3
$p.Refresh()
if($p.HasExited){
 Write-Host "Worker ended with exit code $($p.ExitCode). Check: $stderr"
 if(Test-Path -LiteralPath $stderr){Get-Content -LiteralPath $stderr -Tail 12}
 throw 'Imaging worker did not remain running.'
}
Write-Host "NeuroVision worker started (PID $($p.Id))."
Write-Host "Log: $stdout"
Write-Host "Errors: $stderr"
Write-Host "Now return to NeuroVision and click Check import status / retry."
Write-Host 'Keep the imaging worker available while importing. It uses local storage, not cloud processing.'
