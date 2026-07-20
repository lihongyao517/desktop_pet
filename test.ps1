$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$cscCandidates = @(
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe")
)
$csc = $cscCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $csc) { throw "Windows .NET Framework C# compiler was not found." }

$outputDir = Join-Path $root "build\csharp-tests"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$output = Join-Path $outputDir "CodexDesktopPet.Tests.exe"
$references = @(
    "/reference:System.dll",
    "/reference:System.Core.dll",
    "/reference:System.Drawing.dll",
    "/reference:System.Windows.Forms.dll",
    "/reference:System.Management.dll",
    "/reference:System.Web.Extensions.dll"
)
$sources = @(
    (Join-Path $root "src\CodexDesktopPet\AppPaths.cs"),
    (Join-Path $root "src\CodexDesktopPet\JsonUtil.cs"),
    (Join-Path $root "src\CodexDesktopPet\Models.cs"),
    (Join-Path $root "src\CodexDesktopPet\ReviewStateStore.cs"),
    (Join-Path $root "src\CodexDesktopPet\HookBridge.cs"),
    (Join-Path $root "src\CodexDesktopPet\AgentProcessMonitor.cs"),
    (Join-Path $root "src\CodexDesktopPet\HookIntegration.cs"),
    (Join-Path $root "src\CodexDesktopPet\CodexMonitor.cs"),
    (Join-Path $root "src\CodexDesktopPet\PetRenderer.cs"),
    (Join-Path $root "src\CodexDesktopPet\LayoutMath.cs"),
    (Join-Path $root "src\CodexDesktopPet.Tests\TestProgram.cs")
)
& $csc /nologo /utf8output /optimize+ /platform:x64 /target:exe "/out:$output" @references @sources
if ($LASTEXITCODE -ne 0) { throw "C# tests did not compile." }
& $output
if ($LASTEXITCODE -ne 0) { throw "C# tests failed." }
