<#
.SYNOPSIS
    Copy this skill's essential files into a destination skill directory,
    e.g. a personal Cursor skills folder or a project's .cursor/skills/
    directory.

.EXAMPLE
    .\install\install.ps1 -Destination "$HOME\.cursor\skills\gui-playtest-loop"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Destination
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

New-Item -ItemType Directory -Force -Path $Destination | Out-Null

$items = @("SKILL.md", "AGENTS.md", "reference", "prompts", "templates", "scripts", "docs", "LICENSE", "README.md")

foreach ($item in $items) {
    $source = Join-Path $repoRoot $item
    Copy-Item -Path $source -Destination $Destination -Recurse -Force
}

Write-Host "Installed gui-playtest-loop into: $Destination"
Write-Host "Point your agent at $Destination\SKILL.md to start."
