#Requires -Version 5.1
Set-StrictMode -Off
$ErrorActionPreference = "Continue"
function Write-Banner { param([string]$T) Write-Host ""; Write-Host ("=" * 58) -ForegroundColor DarkCyan; Write-Host "  $T" -ForegroundColor Cyan; Write-Host ("=" * 58) -ForegroundColor DarkCyan }
function Write-OK     { param([string]$T) Write-Host "  [OK]   $T" -ForegroundColor Green  }
function Write-INFO   { param([string]$T) Write-Host "  [--]   $T" -ForegroundColor Gray   }
function Write-WARN   { param([string]$T) Write-Host "  [WARN] $T" -ForegroundColor Yellow }
function Write-FAIL   { param([string]$T) Write-Host "  [FAIL] $T" -ForegroundColor Red    }
$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ExtensionDir = Join-Path $ScriptDir "extension"
$ExtManifest  = Join-Path $ExtensionDir "manifest.json"
Write-Banner "NDS Playbook Chatbot - Setup"
Write-INFO "Root      : $ScriptDir"
Write-INFO "Extension : $ExtensionDir"
Write-Banner "Step 1 - Checking extension files"
if (Test-Path $ExtManifest) {
    Write-OK "manifest.json found"
} else {
    Write-FAIL "Extension folder not found: $ExtensionDir"
    Read-Host "  Press Enter to exit"
    exit 1
}
Write-Banner "Step 2 - Allowlisting extension in Chrome (HKCU)"
$ExtId = $null
try {
    $parsed   = [System.IO.File]::ReadAllText($ExtManifest) | ConvertFrom-Json
    $keyField = $parsed.key
    if ($keyField -and $keyField.Length -gt 10) {
        $pubBytes  = [System.Convert]::FromBase64String($keyField)
        $sha256    = [System.Security.Cryptography.SHA256]::Create()
        $hashBytes = $sha256.ComputeHash($pubBytes)
        $hexStr    = ($hashBytes | ForEach-Object { $_.ToString("x2") }) -join ""
        $idArr     = for ($i = 0; $i -lt 32; $i++) { [char]([int][char]'a' + [System.Convert]::ToInt32($hexStr[$i].ToString(), 16)) }
        $ExtId     = -join $idArr
        Write-OK "Extension ID: $ExtId"
    }
} catch {
    Write-WARN "Could not compute extension ID from manifest key."
}
if ($ExtId) {
    $hkcuPol = "HKCU:\Software\Policies\Google\Chrome\ExtensionInstallAllowlist"
    try {
        if (-not (Test-Path $hkcuPol)) { New-Item -Path $hkcuPol -Force | Out-Null }
        Set-ItemProperty -Path $hkcuPol -Name "1" -Value $ExtId -Type String
        Write-OK "Chrome HKCU allowlist updated"
    } catch {
        Write-WARN "Could not write to registry (non-critical): $_"
    }
}
Write-Host ""
Write-Host ("=" * 58) -ForegroundColor DarkGreen
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host ("=" * 58) -ForegroundColor DarkGreen
Write-Host ""
Write-Host "  Active Directory is handled automatically by the"  -ForegroundColor Cyan
Write-Host "  backend server. No native host or Python needed."  -ForegroundColor Cyan
Write-Host ""
Write-Host "  ---- LOAD THE EXTENSION IN CHROME (one-time) ----" -ForegroundColor Yellow
Write-Host "  1. Open Chrome and go to: chrome://extensions"     -ForegroundColor White
Write-Host "  2. Enable Developer mode (toggle, top-right)"      -ForegroundColor White
Write-Host "  3. Click 'Load unpacked'"                          -ForegroundColor White
Write-Host "  4. Select this folder:"                            -ForegroundColor White
Write-Host "     $ExtensionDir"                                  -ForegroundColor Yellow
Write-Host "  5. The NDS icon will appear in your toolbar."      -ForegroundColor White
Write-Host ""
Write-Host ("=" * 58) -ForegroundColor DarkGreen
Write-Host ""
Read-Host "  Press Enter to close"
