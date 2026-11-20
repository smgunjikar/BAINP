# Add an authorized local MRI to the research catalog. Never associates a scan
# with a live participant automatically. No diagnosis or segmentation is inferred.
[CmdletBinding()]
param([string]$Image='', [string]$DicomFolder='', [string]$Mask='', [string]$Labels='', [string]$LabelNames='', [string]$Cohort='LOCAL-RESEARCH', [string]$Subject='', [string]$Visit='', [string]$Modality='', [string]$Protocol='unknown', [string]$VisitDate='')
$ErrorActionPreference='Stop'
if($env:CONDA_DEFAULT_ENV -ne 'bainp-brain'){throw 'Activate bainp-brain before importing MRI.'}
$root=$PSScriptRoot
$base=Join-Path $env:USERPROFILE 'BAINP_DATA\derived\neurovision'
$out=if($env:NEUROVISION_DATA_DIR){$env:NEUROVISION_DATA_DIR}else{Join-Path $base 'v1'}
if($Image -and $DicomFolder){throw 'Choose Image or DicomFolder, not both.'}
if(!$Image -and !$DicomFolder){
 Add-Type -AssemblyName System.Windows.Forms
 $dialog=New-Object System.Windows.Forms.OpenFileDialog
 $dialog.Title='Select an authorized 3D NIfTI MRI (use -DicomFolder for a scanner series)'
 $dialog.Filter='NIfTI MRI (*.nii;*.nii.gz)|*.nii;*.nii.gz'
 if($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK){Write-Host 'Import cancelled.';return}
 $Image=$dialog.FileName
}
if(!$Subject){$Subject=Read-Host 'Pseudonymous research subject ID (no patient name)'}
if(!$Visit){$Visit=Read-Host 'Visit ID (e.g. baseline or followup-1)'}
if(!$Modality){$Modality=Read-Host 'Image modality (e.g. T1w, T2w, FLAIR)'}
if(!$Subject.Trim() -or !$Visit.Trim() -or !$Modality.Trim()){throw 'Subject, visit and modality are required.'}
if($VisitDate){[void][datetime]::ParseExact($VisitDate,'yyyy-MM-dd',[Globalization.CultureInfo]::InvariantCulture)}
if($DicomFolder){
 $converter=(Get-Command dcm2niix -ErrorAction Stop).Source
 $converted=Join-Path $base ('converted_'+(Get-Date -Format yyyyMMddTHHmmssfff))
 New-Item -ItemType Directory -Path $converted -Force | Out-Null
 # BIDS sidecar anonymization does not guarantee removal of every identifying
 # image feature. Keep original exports and conversion output outside Git.
 & $converter -z y -b y -ba y -f 'series_%s' -o $converted $DicomFolder
 if($LASTEXITCODE -ne 0){throw 'DICOM conversion failed. Inspect converter output.'}
 Add-Type -AssemblyName System.Windows.Forms
 $dialog=New-Object System.Windows.Forms.OpenFileDialog
 $dialog.Title='Select ONE converted 3D series; never combine unrelated sequences'
 $dialog.InitialDirectory=$converted
 $dialog.Filter='NIfTI MRI (*.nii;*.nii.gz)|*.nii;*.nii.gz'
 if($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK){Write-Host "Conversion retained in $converted. Import cancelled.";return}
 $Image=$dialog.FileName
}
if(!(Test-Path -LiteralPath $Image)){throw 'MRI file does not exist.'}
$meta=@{cohort=$Cohort;subject=$Subject;visit=$Visit;modality=$Modality;protocol=$Protocol;pipeline='local-nifti-import-v2';review='UNRECORDED';synthetic=$false;longitudinal_comparable=$false;source_kind='Locally authorized research MRI'}
if($VisitDate){$meta['date']=$VisitDate}
New-Item -ItemType Directory -Force -Path $base | Out-Null
$metadata=Join-Path $base ('import_metadata_'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($metadata,($meta|ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
$arguments=@((Join-Path $root 'backend\engine.py'),'image','--image',$Image,'--metadata',$metadata,'--out',$out)
if($Mask){$arguments+=@('--mask',$Mask)}
if($Labels){$arguments+=@('--labels',$Labels)}
if($LabelNames){$arguments+=@('--lut',$LabelNames)}
& python @arguments
if($LASTEXITCODE -ne 0){throw 'MRI import failed. Share the error. No raw source file was changed.'}
Write-Host 'Prepared. Open NeuroVision Active research mode and click Reload catalog.'
Write-Host 'No anatomical segmentation is invented when a mask/label image is not provided.'
