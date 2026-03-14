$ErrorActionPreference = "Stop"

$repo = "jiangmuran/clawguard"
$assetUrl = "https://github.com/$repo/releases/latest/download/clawguard.zip"
$tempDir = New-Item -ItemType Directory -Path ([System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.Guid]::NewGuid().ToString()))

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "Node.js is required (18+)."
  exit 1
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Write-Host "npm is required."
  exit 1
}

try {
  Write-Host "Downloading latest Clawguard release..."
  Invoke-WebRequest -Uri $assetUrl -OutFile (Join-Path $tempDir "clawguard.zip")
  Expand-Archive -Path (Join-Path $tempDir "clawguard.zip") -DestinationPath $tempDir -Force
  Set-Location $tempDir
} catch {
  Write-Host "Release asset not found. Falling back to git clone."
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "git is required for fallback install."
    exit 1
  }
  git clone "https://github.com/$repo.git" (Join-Path $tempDir "clawguard")
  Set-Location (Join-Path $tempDir "clawguard")
}

Write-Host "Installing Clawguard..."
npm install -g .
Write-Host "Done. Run: clawguard --help"
