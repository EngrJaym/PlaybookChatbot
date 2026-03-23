#Requires -Version 5.1
<#
.SYNOPSIS
    Registers the NDS Playbook Chatbot native messaging host with Chrome.
    Run this once on each machine after deploying the extension.
    No elevation required — writes to HKCU (current user only).
    Re-running is safe; it overwrites the registry key with the correct path.
#>

$ErrorActionPreference = "Stop"

$HostName    = "com.nds.whoami"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BatFile     = (Resolve-Path (Join-Path $ScriptDir "nds_whoami_host.bat")).Path
$ManifestDst = Join-Path $ScriptDir "com.nds.whoami.json"
$ExtManifest = Join-Path $ScriptDir "..\extension\manifest.json"

if (-not (Test-Path $BatFile)) {
    Write-Error "nds_whoami_host.bat not found in $ScriptDir"
    exit 1
}

$ExtId = "flkppflhklekibbmmlmlpijmjepglhnk"

if (Test-Path $ExtManifest) {
    $ExtManifestAbs = (Resolve-Path $ExtManifest).Path
    $tmpPy = [System.IO.Path]::GetTempFileName() + ".py"
    @"
import base64, hashlib, json, sys
with open(sys.argv[1], encoding='utf-8') as f:
    data = json.load(f)
key = data.get('key', '')
if key:
    pub = base64.b64decode(key)
    h = hashlib.sha256(pub).hexdigest()
    print(''.join(chr(ord('a') + int(c, 16)) for c in h[:32]))
"@ | Set-Content $tmpPy -Encoding UTF8
    $computed = (python $tmpPy $ExtManifestAbs 2>$null)
    Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue
    if ($computed -and $computed.Trim().Length -eq 32) { $ExtId = $computed.Trim() }
}

Write-Host "Extension ID : $ExtId"
Write-Host "Native host  : $BatFile"

$tmpWrite = [System.IO.Path]::GetTempFileName() + ".py"
$BatFileJson = $BatFile -replace '\\', '\\\\'
$ManifestDstFwd = $ManifestDst -replace '\\', '/'
@"
import json, pathlib
m = {
    'name': '$HostName',
    'description': 'NDS Playbook Chatbot - Windows username helper',
    'path': '$BatFileJson',
    'type': 'stdio',
    'allowed_origins': ['chrome-extension://$ExtId/']
}
pathlib.Path('$ManifestDstFwd').write_text(json.dumps(m, indent=2), encoding='utf-8')
print('Manifest written.')
"@ | Set-Content $tmpWrite -Encoding UTF8
python $tmpWrite
Remove-Item $tmpWrite -Force -ErrorAction SilentlyContinue

$RegPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HostName"
if (-not (Test-Path $RegPath)) { New-Item -Path $RegPath -Force | Out-Null }
Set-ItemProperty -Path $RegPath -Name "(Default)" -Value $ManifestDst

Write-Host ""
Write-Host "======================================================"
Write-Host " NDS Whoami native host registered successfully."
Write-Host " Extension ID : $ExtId"
Write-Host " Registry key : $RegPath"
Write-Host " Manifest     : $ManifestDst"
Write-Host "======================================================"
Write-Host ""
Write-Host "Reload the extension at chrome://extensions then click Reload."
