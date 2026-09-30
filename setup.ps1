# =========================================================================
# Auto-installer for PK Studio
# Automates the steps that used to be typed manually:
#   1. Check/install Python 3.12 (kept separate from any other Python version)
#   2. Detect NVIDIA GPU + CUDA version automatically
#   3. Install PyTorch matching the detected CUDA version (or CPU-only if no GPU)
#   4. Install ultralytics + opencv-python + pillow + pyyaml
#      (ultralytics pulls in numpy/opencv/pillow/pyyaml as dependencies anyway,
#      but installed explicitly here too so version resolution stays reliable)
#   5. Launch the GUI app automatically at the end
#
# Do not run this file directly - double-click "install_and_run.bat" instead
# (it calls this file with the correct permissions).
# =========================================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Write-Step($msg) {
    Write-Host ""
    Write-Host "===> $msg" -ForegroundColor Cyan
}

function Write-Warn($msg) {
    Write-Host "!! $msg" -ForegroundColor Yellow
}

function Write-Err($msg) {
    Write-Host "XX $msg" -ForegroundColor Red
}

# -------------------------------------------------------------------
# Step 1: Check if Python 3.12 is already installed
# -------------------------------------------------------------------
Write-Step "Step 1/6: Checking for Python 3.12"

$python312Found = $false
try {
    $verOutput = & py -3.12 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Found Python 3.12 already installed: $verOutput"
        $python312Found = $true
    }
} catch {
    $python312Found = $false
}

if (-not $python312Found) {
    Write-Warn "Python 3.12 not found. Downloading and installing automatically..."
    Write-Host "(This may take a few minutes depending on your internet speed. Please wait.)"

    $pythonInstallerUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
    $installerPath = Join-Path $env:TEMP "python-3.12.7-installer.exe"

    Invoke-WebRequest -Uri $pythonInstallerUrl -OutFile $installerPath

    # Silent install, add to PATH, include the py launcher
    Start-Process -FilePath $installerPath -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1" -Wait

    Remove-Item $installerPath -ErrorAction SilentlyContinue

    try {
        $verOutput = & py -3.12 --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Python 3.12 installed successfully: $verOutput"
        } else {
            throw "Installed but cannot be invoked"
        }
    } catch {
        Write-Err "Failed to install Python 3.12 automatically."
        Write-Err "Please install it manually from https://www.python.org/downloads/release/python-3127/"
        Write-Err "(During install, make sure to check 'Add python.exe to PATH')"
        Read-Host "Press Enter to close this window"
        exit 1
    }
}

# -------------------------------------------------------------------
# Step 2: Detect NVIDIA GPU + CUDA version
# -------------------------------------------------------------------
Write-Step "Step 2/6: Checking for NVIDIA GPU and CUDA version"

$cudaTag = $null
$hasNvidiaGpu = $false

try {
    $nvidiaSmiOutput = & nvidia-smi 2>&1
    if ($LASTEXITCODE -eq 0) {
        $hasNvidiaGpu = $true
        $cudaLine = $nvidiaSmiOutput | Select-String -Pattern "CUDA Version:\s*([\d.]+)"
        if ($cudaLine) {
            $cudaVersionStr = $cudaLine.Matches[0].Groups[1].Value
            $cudaVersion = [version]$cudaVersionStr
            Write-Host "NVIDIA GPU found - CUDA Version: $cudaVersionStr"

            if ($cudaVersion -ge [version]"12.8") {
                $cudaTag = "cu128"
            } elseif ($cudaVersion -ge [version]"12.6") {
                $cudaTag = "cu126"
            } elseif ($cudaVersion -ge [version]"12.4") {
                $cudaTag = "cu124"
            } elseif ($cudaVersion -ge [version]"12.1") {
                $cudaTag = "cu121"
            } else {
                $cudaTag = "cu118"
            }
            Write-Host "Will install PyTorch build: $cudaTag"
        } else {
            Write-Warn "NVIDIA GPU found but could not read CUDA version. Defaulting to cu124."
            $cudaTag = "cu124"
        }
    }
} catch {
    $hasNvidiaGpu = $false
}

if (-not $hasNvidiaGpu) {
    Write-Warn "No NVIDIA GPU detected on this machine - will install CPU-only PyTorch instead."
    Write-Warn "(Auto-labeling will still work, just much slower than a machine with an NVIDIA GPU.)"
}

# -------------------------------------------------------------------
# Step 3: Install PyTorch (skip if already correctly installed)
# -------------------------------------------------------------------
Write-Step "Step 3/6: Installing PyTorch (large download, may take a few minutes)"

$torchOk = $false
try {
    $cudaCheck = & py -3.12 -c "import torch; print(torch.cuda.is_available())" 2>&1
    if ($LASTEXITCODE -eq 0) {
        if ($hasNvidiaGpu -and $cudaCheck.Trim() -eq "True") {
            Write-Host "GPU-enabled PyTorch already installed. Skipping."
            $torchOk = $true
        } elseif ((-not $hasNvidiaGpu) -and $cudaCheck.Trim() -eq "False") {
            Write-Host "CPU PyTorch already installed. Skipping."
            $torchOk = $true
        }
    }
} catch {
    $torchOk = $false
}

if (-not $torchOk) {
    if ($hasNvidiaGpu) {
        Write-Host "Downloading GPU PyTorch build ($cudaTag) - approximately 2-3 GB, please wait..."
        & py -3.12 -m pip install torch torchvision --index-url "https://download.pytorch.org/whl/$cudaTag"
    } else {
        Write-Host "Downloading CPU-only PyTorch build..."
        & py -3.12 -m pip install torch torchvision
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to install PyTorch. Check your internet connection and run this file again."
        Read-Host "Press Enter to close this window"
        exit 1
    }
}

# -------------------------------------------------------------------
# Step 4: Install ultralytics + remaining libraries used across PK Studio
# (opencv-python: Multi Video Tool + Auto-Labeler image handling
#  pillow: image display on canvas
#  pyyaml: Dataset Splitter's optional data.yaml class-name reading)
# -------------------------------------------------------------------
Write-Step "Step 4/6: Installing ultralytics, opencv-python, pillow, pyyaml"
& py -3.12 -m pip install -U ultralytics opencv-python pillow pyyaml -q

if ($LASTEXITCODE -ne 0) {
    Write-Err "Failed to install required libraries. Check your internet connection and run this file again."
    Read-Host "Press Enter to close this window"
    exit 1
}

# -------------------------------------------------------------------
# Step 5: Verify and launch the app
# -------------------------------------------------------------------
Write-Step "Step 5/6: Verifying installation"

$finalCheck = & py -3.12 -c "import torch; print(torch.cuda.is_available())" 2>&1
Write-Host "torch.cuda.is_available() = $finalCheck"

if ($hasNvidiaGpu -and $finalCheck.Trim() -ne "True") {
    Write-Warn "Setup finished, but GPU is not being used (got False despite having an NVIDIA GPU)."
    Write-Warn "The app will still work, just slower (running on CPU instead)."
}

Write-Step "Setup complete!"

# -------------------------------------------------------------------
# Step 6: Create Desktop + Start Menu shortcuts (so the app can be found
# by typing its name in Windows Search, or double-clicked from Desktop)
# -------------------------------------------------------------------
Write-Step "Step 6/6: Creating shortcuts"

try {
    $WshShell = New-Object -ComObject WScript.Shell
    $runAppBat = Join-Path $ScriptDir "run_app.bat"
    $appName = "PK Studio"

    # Use the custom icon.ico if it exists next to this script, otherwise fall
    # back to a built-in Windows system icon (guaranteed to exist on every
    # machine, so the shortcut icon never fails to show).
    $customIconPath = Join-Path (Join-Path $ScriptDir "assets") "icon.ico"
    if (Test-Path $customIconPath) {
        $iconTarget = $customIconPath
    } else {
        $iconTarget = "shell32.dll,13"
    }

    # Desktop shortcut
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $desktopShortcut = $WshShell.CreateShortcut((Join-Path $desktopPath "$appName.lnk"))
    $desktopShortcut.TargetPath = $runAppBat
    $desktopShortcut.WorkingDirectory = $ScriptDir
    $desktopShortcut.IconLocation = $iconTarget
    $desktopShortcut.Description = "PK Studio - Dataset Studio"
    $desktopShortcut.Save()
    Write-Host "Desktop shortcut created: $appName"

    # Start Menu shortcut (this is what makes it findable via Windows Search by name)
    $startMenuPath = [Environment]::GetFolderPath("StartMenu")
    $startMenuShortcut = $WshShell.CreateShortcut((Join-Path $startMenuPath "$appName.lnk"))
    $startMenuShortcut.TargetPath = $runAppBat
    $startMenuShortcut.WorkingDirectory = $ScriptDir
    $startMenuShortcut.IconLocation = $iconTarget
    $startMenuShortcut.Description = "PK Studio - Dataset Studio"
    $startMenuShortcut.Save()
    Write-Host "Start Menu shortcut created - you can now search '$appName' in Windows Search"
} catch {
    Write-Warn "Could not create shortcuts automatically. You can still use run_app.bat directly."
}

Write-Step "All done! Launching PK Studio now..."
Start-Sleep -Seconds 2

& py -3.12 (Join-Path $ScriptDir "main.py")
