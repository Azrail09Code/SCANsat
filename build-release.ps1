<#
build-release.ps1 - build + package SCANsat-GPU for a GitHub/CKAN release.

Produces under .\Releases\ :
  SCANsat-GPU-<version>.zip   the installable mod (GameData/SCANsat/... ready to drop into KSP)
  SCANsat.version            the KSP-AVC file - attach this to the GitHub release too, so the
                             "releases/latest/download/SCANsat.version" AVC URL resolves.

The zip is assembled from git-tracked GameData/SCANsat content (so gitignored build output and the
user's PluginData/Settings.cfg are excluded), with the freshly built DLLs + the build-stamped
.version overlaid on top.

Usage:   .\build-release.ps1 [-KspRoot C:\git\ksp\ksp_ro_expanded] [-Version 21.1.1]
Requires: dotnet SDK, git, PowerShell 5+.
#>
[CmdletBinding()]
param(
    [string]$KspRoot = "C:\git\ksp\ksp_ro_expanded",
    [string]$Version
)
$ErrorActionPreference = "Stop"
$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$proj    = Join-Path $root "SCANsat\SCANsat.csproj"
$bin     = Join-Path $root "SCANsat\bin\Release\net4.8"
$verFile = Join-Path $root "GameData\SCANsat\SCANsat.version"

# Version source of truth = SCANsat.version.props (override with -Version). The csproj does NOT import
# that props file, so pass it to the build explicitly as $(Version); KSPBuildTools stamps whatever
# $(Version) resolves to into GameData\SCANsat\SCANsat.version.
if (-not $Version) {
    [xml]$vp = Get-Content (Join-Path $root "SCANsat.version.props")
    $Version = ([string]($vp.Project.PropertyGroup.Version | Select-Object -First 1)).Trim()
}
Write-Host "==> Building SCANsat.dll (Release) v$Version against $KspRoot"
dotnet build $proj -c Release -p:Version=$Version -p:KSPRoot=$($KspRoot -replace '\\','/') -p:RepoRootPath="$($root -replace '\\','/')/"
if ($LASTEXITCODE -ne 0) { throw "dotnet build failed" }

# KSPBuildTools regenerated GameData\SCANsat\SCANsat.version with VERSION/KSP_VERSION filled in.
$ver = (Get-Content $verFile -Raw | ConvertFrom-Json).VERSION
$verStr = if ($ver -is [string]) { $ver } else { (@($ver.MAJOR,$ver.MINOR,$ver.PATCH,$ver.BUILD) | Where-Object { $null -ne $_ }) -join '.' }
Write-Host "==> Packaging version $verStr"

$stage = Join-Path $env:TEMP "scansat-gpu-stage"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

# 1) export git-tracked GameData/SCANsat via a zip (no gitignored DLL, no user Settings.cfg, no untracked junk)
$arch = Join-Path $env:TEMP "scansat-gpu-archive.zip"
if (Test-Path $arch) { Remove-Item $arch -Force }
git -C $root archive --format=zip -o $arch HEAD GameData/SCANsat
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
Expand-Archive -Path $arch -DestinationPath $stage -Force
Remove-Item $arch
$sat = Join-Path $stage "GameData\SCANsat"

# 2) overlay the build-stamped .version (archive shipped the pre-build template)
Copy-Item $verFile (Join-Path $sat "SCANsat.version") -Force

# 3) overlay freshly built DLLs
$plugins = Join-Path $sat "Plugins"
New-Item -ItemType Directory -Path $plugins -Force | Out-Null
Copy-Item (Join-Path $bin "SCANsat.dll")       $plugins -Force
Copy-Item (Join-Path $bin "SCANsat.Unity.dll") $plugins -Force

# 4) license must travel with the (BSD) distribution
Copy-Item (Join-Path $root "LICENSE.txt") (Join-Path $sat "LICENSE.txt") -Force

# 5) zip GameData -> dist\  (forward-slash entry names; Windows PowerShell's Compress-Archive writes
#    backslashes, which violate the ZIP spec and break CKAN's installer, so build the archive by hand)
$dist = Join-Path $root "Releases"
New-Item -ItemType Directory -Path $dist -Force | Out-Null
$zip = Join-Path $dist "SCANsat-GPU-$verStr.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$fs = [System.IO.Compression.ZipFile]::Open($zip, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem -Path (Join-Path $stage "GameData") -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($stage.Length + 1) -replace '\\','/'
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($fs, $_.FullName, $rel, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally { $fs.Dispose() }
Copy-Item $verFile (Join-Path $dist "SCANsat.version") -Force

# 6) undo build side effects so the working tree stays clean
foreach ($f in "GameData\SCANsat.dll","GameData\SCANsat.pdb","GameData\SCANsat.Unity.dll","GameData\SCANsat.Unity.pdb") {
    Remove-Item (Join-Path $root $f) -ErrorAction SilentlyContinue
}
git -C $root checkout -- GameData/SCANsat/SCANsat.version

Write-Host ""
Write-Host "==> Done."
Write-Host "    $zip"
Write-Host "    $(Join-Path $dist 'SCANsat.version')   (attach to the GitHub release)"
