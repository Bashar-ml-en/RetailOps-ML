[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $repositoryRoot "backend"
$frontendDirectory = Join-Path $repositoryRoot "frontend"
$pytestBaseTemp = Join-Path $repositoryRoot ".pytest-tmp"

Push-Location $backendDirectory
try {
    & $Python -m pytest --basetemp $pytestBaseTemp -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

if (-not $SkipFrontend) {
    Push-Location $frontendDirectory
    try {
        & pnpm install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        & pnpm run verify
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    finally {
        Pop-Location
    }
}
