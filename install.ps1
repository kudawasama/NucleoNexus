# Nexus CLI Installer for PowerShell
# Usage: .\install.ps1 [-Force] [-Help]
param([switch]$Force, [switch]$Help)

if ($Help) { Write-Host "Nexus CLI Installer - .\install.ps1 [-Force]"; exit 0 }
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "============================================"
Write-Host "  Nucleo Nexus - PowerShell Installer"
Write-Host "============================================"
Write-Host "  Directory: $dir"
Write-Host ""

# Check requirements
Write-Host "[*] Checking requirements..."
$ok = $true
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if ($py) { $v = & $py.Source --version 2>&1; Write-Host "  [OK] Python: $v" }
else { Write-Host "  [FAIL] Python not found"; $ok = $false }
try { git --version 2>&1 | Out-Null; Write-Host "  [OK] Git" } catch { Write-Host "  [WARN] Git not found" }
try { $null = Invoke-WebRequest "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop; Write-Host "  [OK] Ollama" } catch { Write-Host "  [WARN] Ollama not detected" }
if (-not $ok) { Write-Host "[FAIL] Missing Python 3.10+"; exit 1 }

# Confirm
if (-not $Force) {
    $r = Read-Host "Install Nexus CLI? [Y/n]"
    if ($r -match "^[Nn]") { Write-Host "Cancelled."; exit 0 }
}

# PowerShell Profile
Write-Host ""
Write-Host "[*] Setting up PowerShell profile..."
$pf = $PROFILE.CurrentUserCurrentHost
$pd = Split-Path $pf -Parent
if (-not (Test-Path $pd)) { New-Item -ItemType Directory -Path $pd -Force | Out-Null }
$nl = ". $dir\nexus.ps1  # Nexus CLI"
if (Test-Path $pf) {
    $c = Get-Content $pf -Raw
    if ($c -notmatch "Nexus CLI") {
        Add-Content -Path $pf -Value ""
        Add-Content -Path $pf -Value "# Nexus CLI"
        Add-Content -Path $pf -Value $nl
        Write-Host "  [OK] Added to profile"
    } else { Write-Host "  [SKIP] Already in profile" }
} else {
    "# Nexus CLI" | Set-Content -Path $pf
    Add-Content -Path $pf -Value $nl
    Write-Host "  [OK] Profile created"
}

# User PATH
Write-Host "[*] Setting up PATH..."
$op = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($op -notlike "*$dir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$op;$dir", "User")
    Write-Host "  [OK] Added to PATH"
} else { Write-Host "  [SKIP] Already in PATH" }

# git-bash setup
Write-Host "[*] Setting up git-bash..."
$br = "$env:USERPROFILE\.bashrc"
$np = $dir.Replace("\", "/")
$bl1 = "export PATH=""${np}:$PATH""  # Nexus CLI"
$bl2 = "alias nexus='${np}/nexus'  # Nexus CLI"
if (Test-Path $br) {
    $bc = Get-Content $br -Raw
    if ($bc -notmatch "Nexus CLI") {
        Add-Content -Path $br -Value ""
        Add-Content -Path $br -Value "# Nexus CLI"
        Add-Content -Path $br -Value $bl1
        Add-Content -Path $br -Value $bl2
        Write-Host "  [OK] Added to .bashrc"
    } else { Write-Host "  [SKIP] Already in .bashrc" }
} else {
    "# Nexus CLI" | Set-Content -Path $br
    Add-Content -Path $br -Value $bl1
    Add-Content -Path $br -Value $bl2
    Write-Host "  [OK] Created .bashrc"
}

# Verify
Write-Host ""
Write-Host "[*] Verifying..."
try {
    . "$dir\nexus.ps1"
    nexus version 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "  [OK] nexus works" }
} catch { Write-Host "  [ERR] $($_.Exception.Message)" }

Write-Host ""
Write-Host "============================================"
Write-Host "  INSTALLATION COMPLETE"
Write-Host "============================================"
Write-Host "  nexus              Start chat"
Write-Host "  nexus status       System status"
Write-Host "  nexus model list   Ollama models"
Write-Host "  nexus help         All commands"
Write-Host ""
Write-Host "  Open a NEW terminal and try: nexus version"