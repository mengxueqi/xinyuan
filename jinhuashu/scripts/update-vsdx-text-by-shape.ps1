[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$CsvPath,

    [string]$OutputPath,

    [switch]$InPlace
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression.FileSystem

function Resolve-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Resolve-Path -LiteralPath $Path).Path
}

function Normalize-NewText {
    param([string]$Value)
    if ($null -eq $Value) {
        return ""
    }

    return $Value.Replace('\n', [Environment]::NewLine)
}

$inputFullPath = Resolve-FullPath -Path $InputPath
$csvFullPath = Resolve-FullPath -Path $CsvPath

if (-not $inputFullPath.EndsWith(".vsdx", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "InputPath must point to a .vsdx file."
}

$rows = Import-Csv -LiteralPath $csvFullPath
if (-not $rows -or $rows.Count -eq 0) {
    throw "CSV is empty. Expected headers: page_file,shape_id,new_text"
}

foreach ($row in $rows) {
    foreach ($required in @("page_file", "shape_id", "new_text")) {
        if (-not ($row.PSObject.Properties.Name -contains $required)) {
            throw "CSV must contain headers named page_file, shape_id, new_text."
        }
    }
}

if ($InPlace) {
    $outputFullPath = $inputFullPath
} elseif ($OutputPath) {
    $outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
} else {
    $directory = [System.IO.Path]::GetDirectoryName($inputFullPath)
    $fileName = [System.IO.Path]::GetFileNameWithoutExtension($inputFullPath)
    $outputFullPath = [System.IO.Path]::Combine($directory, "$fileName.by-shape.updated.vsdx")
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("vsdx-shape-edit-" + [System.Guid]::NewGuid().ToString("N"))
$extractDir = Join-Path $tempRoot "extract"
$tempZipPath = Join-Path $tempRoot "output.zip"

New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

try {
    [System.IO.Compression.ZipFile]::ExtractToDirectory($inputFullPath, $extractDir)

    $grouped = $rows | Group-Object page_file
    $updatedShapes = 0

    foreach ($group in $grouped) {
        $pagePath = Join-Path $extractDir ("visio\pages\" + $group.Name)
        if (-not (Test-Path -LiteralPath $pagePath)) {
            throw ("Page file not found in vsdx: {0}" -f $group.Name)
        }

        $xml = New-Object System.Xml.XmlDocument
        $xml.PreserveWhitespace = $true
        $xml.Load($pagePath)

        foreach ($row in $group.Group) {
            $shapeNode = $xml.SelectSingleNode("//*[local-name()='Shape'][@ID='$($row.shape_id)']")
            if (-not $shapeNode) {
                throw ("Shape ID not found: page={0}, shape_id={1}" -f $group.Name, $row.shape_id)
            }

            $textNode = $shapeNode.SelectSingleNode("./*[local-name()='Text']")
            if (-not $textNode) {
                throw ("Text node not found: page={0}, shape_id={1}" -f $group.Name, $row.shape_id)
            }

            $newText = Normalize-NewText -Value $row.new_text
            $textNode.RemoveAll()
            $textNode.InnerText = $newText
            $updatedShapes++
        }

        $xml.Save($pagePath)
    }

    if (Test-Path -LiteralPath $tempZipPath) {
        Remove-Item -LiteralPath $tempZipPath -Force
    }

    [System.IO.Compression.ZipFile]::CreateFromDirectory($extractDir, $tempZipPath)

    if ($InPlace) {
        $backupPath = $inputFullPath + ".bak"
        Copy-Item -LiteralPath $inputFullPath -Destination $backupPath -Force
        Move-Item -LiteralPath $tempZipPath -Destination $inputFullPath -Force
        Write-Host ("Updated in place: {0}" -f $inputFullPath)
        Write-Host ("Backup created: {0}" -f $backupPath)
    } else {
        if (Test-Path -LiteralPath $outputFullPath) {
            Remove-Item -LiteralPath $outputFullPath -Force
        }
        Move-Item -LiteralPath $tempZipPath -Destination $outputFullPath -Force
        Write-Host ("Created: {0}" -f $outputFullPath)
    }

    Write-Host ("Updated shapes: {0}" -f $updatedShapes)
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
