$ErrorActionPreference = 'Stop'
# One maintained deck source; it also updates the canonical proposal paths.
& (Join-Path $PSScriptRoot 'v3\build_slides.ps1')
