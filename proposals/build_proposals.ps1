$ErrorActionPreference = 'Stop'
# One maintained deck source; it also updates the canonical proposal paths.
& (Join-Path $PSScriptRoot 'v2\build_six_slides.ps1')