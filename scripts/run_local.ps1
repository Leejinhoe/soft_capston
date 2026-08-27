param(
  [string]$Device = "chrome",
  [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Get-ChildItem -LiteralPath $ProjectRoot -Directory |
  Where-Object { $_.Name -like "DB*" } |
  Select-Object -First 1 -ExpandProperty FullName
$EnvPath = Join-Path $ProjectRoot ".env"

if (-not $BackendDir) {
  throw "Backend directory starting with DB was not found under $ProjectRoot"
}

if (-not (Test-Path -LiteralPath $EnvPath)) {
  throw "Missing .env at $EnvPath"
}

function Import-DotEnv {
  param([string]$Path)

  Get-Content -LiteralPath $Path | ForEach-Object {
    $line = $_.Trim()
    if ($line.Length -eq 0 -or $line.StartsWith("#")) {
      return
    }

    $equalsIndex = $line.IndexOf("=")
    if ($equalsIndex -le 0) {
      return
    }

    $name = $line.Substring(0, $equalsIndex).Trim()
    $value = $line.Substring($equalsIndex + 1).Trim()

    if (
      ($value.StartsWith('"') -and $value.EndsWith('"')) -or
      ($value.StartsWith("'") -and $value.EndsWith("'"))
    ) {
      $value = $value.Substring(1, $value.Length - 2)
    }

    Set-Item -Path "Env:$name" -Value $value
  }
}

Import-DotEnv -Path $EnvPath

$env:DB_API_BASE_URL = if ($env:DB_API_BASE_URL) {
  $env:DB_API_BASE_URL
} else {
  "http://127.0.0.1:$BackendPort"
}

$env:AI_API_BASE_URL = if ($env:AI_API_BASE_URL) {
  $env:AI_API_BASE_URL
} else {
  $env:DB_API_BASE_URL
}

$backendJob = $null
$startedBackend = $false
$healthUrl = "$env:DB_API_BASE_URL/"

function Test-Backend {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
    return $response.StatusCode -lt 500
  } catch {
    return $false
  }
}

if (-not (Test-Backend)) {
  $backendJob = Start-Job -Name "fairytale-fastapi" -ScriptBlock {
    param([string]$BackendDir, [int]$BackendPort)
    Set-Location -LiteralPath $BackendDir
    python -m uvicorn main:app --host 0.0.0.0 --port $BackendPort --reload
  } -ArgumentList $BackendDir, $BackendPort
  $startedBackend = $true

  $ready = $false
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Backend) {
      $ready = $true
      break
    }

    if ($backendJob.State -ne "Running") {
      Receive-Job -Job $backendJob
      throw "FastAPI backend stopped before it became ready."
    }
  }

  if (-not $ready) {
    throw "FastAPI backend did not become ready at $healthUrl"
  }
}

try {
  $flutterArgs = @(
    "run",
    "-d",
    $Device,
    "--dart-define=DB_API_BASE_URL=$env:DB_API_BASE_URL"
  )

  foreach ($name in @("AI_API_BASE_URL", "GOOGLE_CLIENT_ID", "KAKAO_NATIVE_KEY", "KAKAO_JS_KEY", "MEDIA_INCLUDE_VIDEO")) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value) {
      $flutterArgs += "--dart-define=$name=$value"
    }
  }

  Set-Location -LiteralPath $ProjectRoot
  flutter @flutterArgs
} finally {
  if ($startedBackend -and $backendJob) {
    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob -Force -ErrorAction SilentlyContinue
  }
}
