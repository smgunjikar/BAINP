# Start the local import worker with the research environment's Python.
$ErrorActionPreference='Stop'
if($env:CONDA_DEFAULT_ENV -ne 'bainp-brain'){throw 'Activate bainp-brain first.'}
$python=(Get-Command python -ErrorAction Stop).Source
& $python -c 'import numpy,scipy,nibabel; from skimage.measure import marching_cubes'
if($LASTEXITCODE -ne 0){throw 'Imaging dependencies are missing. Share the error.'}
$folder=if($env:NEUROVISION_DATA_DIR){$env:NEUROVISION_DATA_DIR}else{Join-Path $env:USERPROFILE 'BAINP_DATA\derived\neurovision\v1'}
$logs=Join-Path $folder 'import_jobs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$worker=Join-Path $PSScriptRoot 'backend\import_worker.py'
$stamp=Get-Date -Format yyyyMMddTHHmmssfff
$p=Start-Process -FilePath $python -ArgumentList @(('"'+$worker+'"'),'--watch') -RedirectStandardOutput (Join-Path $logs ('worker-'+$stamp+'.log')) -RedirectStandardError (Join-Path $logs ('worker-'+$stamp+'-error.log')) -PassThru
Write-Host "Worker start requested (PID $($p.Id)). Its exclusive lock prevents duplicate workers. Check worker status in NeuroVision."
