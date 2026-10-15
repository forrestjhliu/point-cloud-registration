$ErrorActionPreference = 'Stop'
$sourceRoot = Join-Path $PSScriptRoot 'v2'
$sourceStem = 'low_overlap_registration_6slides'
$targetStem = 'low_overlap_registration_proposal'

foreach ($extension in @('pptx','pdf')) {
    $source = Join-Path $sourceRoot ($sourceStem+'.'+$extension)
    if (-not (Test-Path -LiteralPath $source)) { throw "Missing current deck: $source" }
}
foreach ($extension in @('pptx','pdf')) {
    $source = Join-Path $sourceRoot ($sourceStem+'.'+$extension)
    $target = Join-Path $PSScriptRoot ($targetStem+'.'+$extension)
    Copy-Item -LiteralPath $source -Destination $target -Force
    if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $target).Hash) {
        throw "Published deck does not match source: $target"
    }
    Write-Output ('UPDATED '+$target)
}

$previewSource = Join-Path $sourceRoot ('previews\'+$sourceStem)
$previewTarget = Join-Path $PSScriptRoot ('previews\'+$targetStem)
[IO.Directory]::CreateDirectory($previewTarget) | Out-Null
Get-ChildItem -LiteralPath $previewSource -File -Filter '*.PNG' | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $previewTarget $_.Name) -Force
}
Copy-Item -LiteralPath (Join-Path $sourceRoot 'layout_check.json') -Destination (Join-Path $PSScriptRoot 'layout_check.json') -Force
