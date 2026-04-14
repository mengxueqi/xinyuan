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

function Replace-TextValue {
    param(
        [Parameter(Mandatory = $true)]
        [System.Xml.XmlNode]$Node,

        [Parameter(Mandatory = $true)]
        [object[]]$Mappings
    )

    $changed = 0

    if ($Node.NodeType -eq [System.Xml.XmlNodeType]::Text -or
        $Node.NodeType -eq [System.Xml.XmlNodeType]::CDATA) {
        $value = $Node.Value
        foreach ($mapping in $Mappings) {
            if ([string]::IsNullOrEmpty($mapping.old)) {
                continue
            }

            $newValue = $value.Replace($mapping.old, $mapping.new)
            if ($newValue -ne $value) {
                $value = $newValue
                $changed++
            }
        }

        if ($value -ne $Node.Value) {
            $Node.Value = $value
        }
    }

    foreach ($child in $Node.ChildNodes) {
        $changed += Replace-TextValue -Node $child -Mappings $Mappings
    }

    return $changed
}

$inputFullPath = Resolve-FullPath -Path $InputPath
$csvFullPath = Resolve-FullPath -Path $CsvPath

if (-not $inputFullPath.EndsWith(".vsdx", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "InputPath must point to a .vsdx file."
}

$mappings = Import-Csv -LiteralPath $csvFullPath
if (-not $mappings -or $mappings.Count -eq 0) {
    throw "CSV is empty. Expected headers: old,new"
}

foreach ($mapping in $mappings) {
    if (-not ($mapping.PSObject.Properties.Name -contains "old") -or
        -not ($mapping.PSObject.Properties.Name -contains "new")) {
        throw "CSV must contain headers named old and new."
    }
}

if ($InPlace) {
    $outputFullPath = $inputFullPath
} elseif ($OutputPath) {
    $outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
} else {
    $directory = [System.IO.Path]::GetDirectoryName($inputFullPath)
    $fileName = [System.IO.Path]::GetFileNameWithoutExtension($inputFullPath)
    $outputFullPath = [System.IO.Path]::Combine($directory, "$fileName.updated.vsdx")
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("vsdx-edit-" + [System.Guid]::NewGuid().ToString("N"))
$extractDir = Join-Path $tempRoot "extract"
$tempZipPath = Join-Path $tempRoot "output.zip"

New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

try {
    [System.IO.Compression.ZipFile]::ExtractToDirectory($inputFullPath, $extractDir)

    $xmlFiles = Get-ChildItem -LiteralPath $extractDir -Recurse -Filter *.xml
    $totalReplacements = 0
    $changedFiles = 0

    foreach ($file in $xmlFiles) {
        $xml = New-Object System.Xml.XmlDocument
        $xml.PreserveWhitespace = $true
        $xml.Load($file.FullName)

        $textNodes = $xml.SelectNodes("//*[local-name()='Text']")
        if (-not $textNodes -or $textNodes.Count -eq 0) {
            continue
        }

        $fileChanged = 0
        foreach ($textNode in $textNodes) {
            $fileChanged += Replace-TextValue -Node $textNode -Mappings $mappings
        }

        if ($fileChanged -gt 0) {
            $xml.Save($file.FullName)
            $changedFiles++
            $totalReplacements += $fileChanged
        }
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

    Write-Host ("Changed XML files: {0}" -f $changedFiles)
    Write-Host ("Replacement hits: {0}" -f $totalReplacements)
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
