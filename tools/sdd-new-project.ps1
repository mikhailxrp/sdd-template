<#
.SYNOPSIS
    Creates a new SDD project: copies a stack starter and a finished
    TZ (from the tz-template pipeline) into a self-contained project
    ready for the sdd-init / sdd-schema / sdd-roadmap planning steps.

.PARAMETER Name
    Project name. Becomes the folder name.

.PARAMETER Stack
    Folder name under stacks\ (e.g. "php-ecommerce").

.PARAMETER TzProject
    Path to a finished TZ project (from the tz-template pipeline).
    Must contain 01-tz\tz.md. If it has 01-tz\screens.md or
    00-input\design\, those are copied too.

.PARAMETER Path
    Where to create the project. Defaults to the folder next to
    sdd-template.

.EXAMPLE
    .\tools\sdd-new-project.ps1 -Name domform-sdd -Stack php-ecommerce `
        -TzProject D:\Development\domform
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [string]$Stack,

    [Parameter(Mandatory = $true)]
    [string]$TzProject,

    [string]$Path = "..",

    [switch]$NoGit
)

$ErrorActionPreference = "Stop"

$templateRoot = Split-Path -Parent $PSScriptRoot
$stackDir = Join-Path $templateRoot "stacks\$Stack"

if (-not (Test-Path $stackDir)) {
    Write-Host "Stack not found: $stackDir" -ForegroundColor Red
    $available = Get-ChildItem (Join-Path $templateRoot "stacks") -Directory -ErrorAction SilentlyContinue
    if ($available) {
        Write-Host "Available stacks:" -ForegroundColor Yellow
        $available | ForEach-Object { Write-Host "  $($_.Name)" }
    }
    exit 1
}

$tzFile = Join-Path $TzProject "01-tz\tz.md"
if (-not (Test-Path $tzFile)) {
    Write-Host "tz.md not found at: $tzFile" -ForegroundColor Red
    Write-Host "Expected a finished TZ project from the tz-template pipeline." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $Path)) {
    Write-Host "Path not found: $Path" -ForegroundColor Red
    exit 1
}

$target = Join-Path (Resolve-Path $Path) $Name

if (Test-Path $target) {
    Write-Host "Directory already exists: $target" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Creating SDD project: $Name" -ForegroundColor Cyan
Write-Host "Stack: $Stack"
Write-Host "TZ source: $TzProject"
Write-Host "Path: $target"
Write-Host ""

# --- Copy stack starter -----------------------------------------------

Copy-Item -Path $stackDir -Destination $target -Recurse

# reference/ and tools/ from the sdd-template (planning agent + validator)
Copy-Item -Path (Join-Path $templateRoot "reference") -Destination $target -Recurse
Copy-Item -Path (Join-Path $templateRoot "tools")     -Destination $target -Recurse
Copy-Item -Path (Join-Path $templateRoot ".claude")   -Destination $target -Recurse -ErrorAction SilentlyContinue

Remove-Item (Join-Path $target "tools\sdd-new-project.ps1") -ErrorAction SilentlyContinue

# --- Copy TZ and design references into 00-input ----------------------

$inputDir = Join-Path $target "00-input"
New-Item -ItemType Directory -Path $inputDir -Force | Out-Null

Copy-Item -Path $tzFile -Destination (Join-Path $inputDir "tz.md")

$screensFile = Join-Path $TzProject "01-tz\screens.md"
if (Test-Path $screensFile) {
    Copy-Item -Path $screensFile -Destination (Join-Path $inputDir "screens.md")
    Write-Host "Copied screens.md (design registry found)" -ForegroundColor Green
}

$designDir = Join-Path $TzProject "00-input\design"
if ((Test-Path $designDir) -and (Get-ChildItem $designDir -ErrorAction SilentlyContinue)) {
    Copy-Item -Path $designDir -Destination (Join-Path $inputDir "design") -Recurse
    Write-Host "Copied design/ (mockups/markup found)" -ForegroundColor Green
}

$clientSummary = Join-Path $TzProject "01-tz\tz-client-summary.md"
if (Test-Path $clientSummary) {
    Copy-Item -Path $clientSummary -Destination (Join-Path $inputDir "tz-client-summary.md")
}

# --- .docs scaffolding not present in stack starter yet ----------------
# (tz-coverage.md and planning-log.md are created by sdd-init on first run,
#  not here — the planning agent creates them from templates in
#  reference/sdd-planning-agent.md so the format stays in one place.)

# --- .gitignore ----------------------------------------------------------

$gitignore = @"
vendor/
node_modules/
.env
*.tmp
*.bak
~`$*
.DS_Store
Thumbs.db
storage/logs/*.log
storage/cache/*
"@

Set-Content -Path (Join-Path $target ".gitignore") -Value $gitignore -Encoding UTF8

# --- Git -------------------------------------------------------------

if (-not $NoGit) {
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    Push-Location $target
    try {
        git init -q
        git config core.hooksPath .githooks 2>$null
        git config core.autocrlf false
        git add . 2>$null
        git commit -q -m "init: $Stack stack + tz.md from $Name" 2>$null

        git rev-parse --verify HEAD *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Git: repository initialized, first commit created" -ForegroundColor Green
        }
        else {
            Write-Host "Git: repository initialized, commit skipped" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Git skipped: $_" -ForegroundColor Yellow
    }
    finally {
        Pop-Location
        $ErrorActionPreference = $prevEAP
    }
}

# --- Summary -----------------------------------------------------------

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. cd `"$target`""
Write-Host "  2. claude"
Write-Host "  3. /sdd-init"
Write-Host ""
