param([string]$ImagePath = '',[string]$SegmentationPath = '',[int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$server = Join-Path $PSScriptRoot 'server.py'
$arguments = @($server,'--port',"$Port")
if ($ImagePath) { $arguments += @('--image', $ImagePath) }
if ($SegmentationPath) { $arguments += @('--segmentation', $SegmentationPath) }
Write-Host "BAINP NeuroVision LOCAL RESEARCH DEMO: http://127.0.0.1:$Port/"
Write-Host 'No BAINP participant records are written.'
python @arguments
if ($LASTEXITCODE -ne 0) {throw 'NeuroVision local research demo failed. Review the preceding error.'}
