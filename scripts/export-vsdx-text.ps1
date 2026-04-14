[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [string]$OutputCsvPath
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression.FileSystem

function Resolve-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-PlainText {
    param([Parameter(Mandatory = $true)][System.Xml.XmlNode]$Node)

    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($child in $Node.ChildNodes) {
        if ($child.NodeType -eq [System.Xml.XmlNodeType]::Text -or
            $child.NodeType -eq [System.Xml.XmlNodeType]::CDATA) {
            $parts.Add($child.Value)
            continue
        }

        if ($child.LocalName -eq "cp" -or $child.LocalName -eq "fld") {
            continue
        }

        if ($child.LocalName -eq "pp") {
            continue
        }

        $parts.Add((Get-PlainText -Node $child))
    }

    return ($parts -join "")
}

$inputFullPath = Resolve-FullPath -Path $InputPath

if (-not $inputFullPath.EndsWith(".vsdx", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "InputPath must point to a .vsdx file."
}

if (-not $OutputCsvPath) {
    $directory = [System.IO.Path]::GetDirectoryName($inputFullPath)
    $fileName = [System.IO.Path]::GetFileNameWithoutExtension($inputFullPath)
    $OutputCsvPath = [System.IO.Path]::Combine($directory, "$fileName.text-export.csv")
}

$outputFullPath = [System.IO.Path]::GetFullPath($OutputCsvPath)

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("vsdx-export-" + [System.Guid]::NewGuid().ToString("N"))
$extractDir = Join-Path $tempRoot "extract"

New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

try {
    [System.IO.Compression.ZipFile]::ExtractToDirectory($inputFullPath, $extractDir)
    $pageFiles = Get-ChildItem -LiteralPath (Join-Path $extractDir "visio\pages") -Filter *.xml | Sort-Object Name
    $rows = New-Object System.Collections.Generic.List[object]

    foreach ($file in $pageFiles) {
        $xml = New-Object System.Xml.XmlDocument
        $xml.PreserveWhitespace = $true
        $xml.Load($file.FullName)

        $shapeNodes = $xml.SelectNodes("//*[local-name()='Shape'][*[local-name()='Text']]")
        foreach ($shape in $shapeNodes) {
            $textNode = $shape.SelectSingleNode("./*[local-name()='Text']")
            if (-not $textNode) {
                continue
            }

            $plainText = Get-PlainText -Node $textNode
            $rows.Add([pscustomobject]@{
                page_file = $file.Name
                shape_id  = $shape.Attributes["ID"].Value
                shape_name = if ($shape.Attributes["Name"]) { $shape.Attributes["Name"].Value } else { "" }
                text      = $plainText
            })
        }
    }

    $rows | Export-Csv -LiteralPath $outputFullPath -NoTypeInformation -Encoding UTF8
    Write-Host ("Exported: {0}" -f $outputFullPath)
    Write-Host ("Rows: {0}" -f $rows.Count)
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
