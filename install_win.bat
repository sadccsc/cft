# install.ps1
$ErrorActionPreference = "Stop"

# Where micromamba will be installed
$InstallDir = "$env:USERPROFILE\micromamba"

# Download micromamba for Windows
Write-Host "Downloading micromamba..."
Invoke-WebRequest -Uri "https://micro.mamba.pm/api/micromamba/win-64/latest" -OutFile "$env:TEMP\micromamba.exe"

# Create installation directory
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Move-Item "$env:TEMP\micromamba.exe" "$InstallDir\micromamba.exe" -Force

# Add to PATH (for future terminals)
Write-Host "Adding micromamba to PATH..."
setx PATH "$InstallDir;$env:PATH"

# Initialize micromamba in PowerShell
& "$InstallDir\micromamba.exe" shell init -s powershell -p "$InstallDir"

# Create environment
Write-Host "Creating environment..."
& "$InstallDir\micromamba.exe" create -y -n myenv -f environment.yml

Write-Host "`nInstallation complete!"
Write-Host "Open a new PowerShell window and run:"
Write-Host "    micromamba activate myenv"

