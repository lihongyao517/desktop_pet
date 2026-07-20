param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$icon = Join-Path $root "assets\CodexDesktopPet.ico"
$cscCandidates = @(
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe")
)
$csc = $cscCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $csc) {
    throw "Windows .NET Framework C# compiler was not found."
}

New-Item -ItemType Directory -Path (Join-Path $root "dist") -Force | Out-Null

$references = @(
    "/reference:System.dll",
    "/reference:System.Core.dll",
    "/reference:System.Drawing.dll",
    "/reference:System.Windows.Forms.dll",
    "/reference:System.Web.Extensions.dll"
)
$mainSources = Get-ChildItem -LiteralPath (Join-Path $root "src\CodexDesktopPet") -Filter "*.cs" |
    Select-Object -ExpandProperty FullName
$mainOutput = Join-Path $root "dist\CodexDesktopPet.exe"
& $csc /nologo /utf8output /optimize+ /platform:x64 /target:winexe "/win32icon:$icon" "/out:$mainOutput" @references @mainSources
if ($LASTEXITCODE -ne 0) {
    throw "C# desktop application build failed."
}

$hookSources = @(
    (Join-Path $root "src\CodexDesktopPet\AppPaths.cs"),
    (Join-Path $root "src\CodexDesktopPet\JsonUtil.cs"),
    (Join-Path $root "src\CodexDesktopPet\Models.cs"),
    (Join-Path $root "src\CodexDesktopPet\HookIntegration.cs"),
    (Join-Path $root "src\CodexDesktopPet\HookBridge.cs"),
    (Join-Path $root "src\CodexDesktopPetHook\HookProgram.cs")
)
$hookOutput = Join-Path $root "dist\CodexDesktopPetHook.exe"
& $csc /nologo /utf8output /optimize+ /platform:x64 /target:exe /nowarn:0649 "/win32icon:$icon" "/out:$hookOutput" @references @hookSources
if ($LASTEXITCODE -ne 0) {
    throw "C# hook bridge build failed."
}

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  $root\dist\CodexDesktopPet.exe"
Write-Host "  $root\dist\CodexDesktopPetHook.exe"
