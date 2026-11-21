# Start/stop the fresh local NeuroAccess stack. Never stops research or Docker.
[CmdletBinding()]
param([ValidateSet('All','Api','Web','Stop','Status','Verify','VerifyCognition')][string]$Service='All')
$ErrorActionPreference='Stop'
$moduleRoot=$PSScriptRoot
$dataDir=if($env:NEUROACCESS_DATA_DIR){$env:NEUROACCESS_DATA_DIR}else{Join-Path $env:USERPROFILE 'BAINP_DATA\local\neuroaccess_v1'}
$env:NEUROACCESS_DATA_DIR=$dataDir
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
$pidFile=Join-Path $dataDir 'processes.json'
if($Service -in @('Stop','Status')){
    if(-not(Test-Path -LiteralPath $pidFile)){Write-Host 'No managed NeuroAccess processes recorded.';return}
    $records=Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
    foreach($record in $records){
        $process=Get-CimInstance Win32_Process -Filter "ProcessId = $($record.process_id)" -ErrorAction SilentlyContinue
        $expected=$null -ne $process -and $process.Name -match '^python(w)?\.exe$' -and $process.CommandLine -like "*$moduleRoot*"
        if($expected){
            if($Service -eq 'Stop'){Stop-Process -Id $record.process_id;Write-Host "Stopped NeuroAccess $($record.service)."}
            else{Write-Host "$($record.service): running, PID $($record.process_id)"}
        }else{Write-Host "$($record.service): not running or PID no longer matches this module."}
    }
    if($Service -eq 'Stop'){Remove-Item -LiteralPath $pidFile}
    return
}
$python=(Get-Command python -ErrorAction Stop).Source
& $python -c "import fastapi, uvicorn, pydantic; assert pydantic.__version__.split('.')[0]=='2'"
if($LASTEXITCODE -ne 0){throw 'Activate bainp with FastAPI, Uvicorn and Pydantic v2 installed.'}
if($Service -in @('Verify','VerifyCognition')){
    $testFile=if($Service -eq 'VerifyCognition'){'tests\verify_inputs.py'}else{'tests\verify_neuroaccess.py'}
    & $python (Join-Path $moduleRoot $testFile)
    if($LASTEXITCODE -ne 0){throw 'NeuroAccess tests failed. Share the output.'}
    return
}
$ports=if($Service -eq 'Api'){@(8000)}elseif($Service -eq 'Web'){@(3000)}else{@(3000,8000)}
if(@(Get-NetTCPConnection -LocalPort $ports -State Listen -ErrorAction SilentlyContinue).Count -gt 0){throw "Ports $ports are in use. Stop the previous frontend/API only, then retry."}
if($Service -in @('All','Api')){
    & $python (Join-Path $moduleRoot 'backend\api.py') --show-login
    if($LASTEXITCODE -ne 0){throw 'Local database initialization failed.'}
}
if($Service -eq 'Api'){
    & $python -m uvicorn api:create_app --factory --app-dir (Join-Path $moduleRoot 'backend') --host 127.0.0.1 --port 8000 --no-access-log
    return
}
if($Service -eq 'Web'){
    & $python (Join-Path $moduleRoot 'backend\serve_frontend.py')
    return
}
# All mode starts two owned Python processes and records only their PIDs.
$spawned=@()
try{
    $backend=Join-Path $moduleRoot 'backend'
    $apiProcess=Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','api:create_app','--factory','--app-dir',('"'+$backend+'"'),'--host','127.0.0.1','--port','8000','--no-access-log') -WorkingDirectory $moduleRoot -RedirectStandardOutput (Join-Path $dataDir 'api-output.log') -RedirectStandardError (Join-Path $dataDir 'api-error.log') -PassThru
    $spawned+=@{service='api';process_id=$apiProcess.Id}
    $webScript=Join-Path $backend 'serve_frontend.py'
    $webProcess=Start-Process -FilePath $python -ArgumentList @(('"'+$webScript+'"')) -WorkingDirectory $moduleRoot -RedirectStandardOutput (Join-Path $dataDir 'web-output.log') -RedirectStandardError (Join-Path $dataDir 'web-error.log') -PassThru
    $spawned+=@{service='web';process_id=$webProcess.Id}
    $ready=$false
    for($attempt=0;$attempt -lt 30;$attempt++){
        try{
            $health=Invoke-RestMethod 'http://127.0.0.1:3000/api/health' -TimeoutSec 1
            if($health.service -eq 'neuroaccess-v1'){$ready=$true;break}
        }catch{}
        Start-Sleep -Milliseconds 300
    }
    if(-not $ready){throw "Startup failed. Inspect api-error.log and web-error.log in $dataDir"}
    $spawned | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding UTF8
    Write-Host 'READY: http://127.0.0.1:3000'
    Write-Host 'Use the LOCAL OPERATOR LOGIN CODE printed above. Do not commit or share it.'
    Write-Host "Records persist in: $dataDir"
}catch{
    foreach($record in $spawned){Stop-Process -Id $record.process_id -ErrorAction SilentlyContinue}
    throw
}
