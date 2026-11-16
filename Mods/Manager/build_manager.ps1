param([ValidateSet('RTW3 Mod Manager.exe', 'RTW3 Mod Manager Updated.exe')][string]$OutputName = 'RTW3 Mod Manager.exe')
$ErrorActionPreference = 'Stop'
$rtwCompiler = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$rtwRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath $rtwCompiler)) { throw 'The Windows .NET Framework C# compiler was not found.' }
& $rtwCompiler /nologo /target:winexe /optimize+ /langversion:5 /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll ("/out:" + (Join-Path $rtwRoot $OutputName)) (Join-Path $PSScriptRoot 'ModManager.cs') (Join-Path $PSScriptRoot 'CheatMenu.cs') (Join-Path $PSScriptRoot 'GameTools.cs') (Join-Path $PSScriptRoot 'AdvancedSaveEditor.cs')
if ($LASTEXITCODE -ne 0) { throw 'Mod Manager build failed.' }
Get-Item -LiteralPath (Join-Path $rtwRoot $OutputName) | Select-Object FullName,Length
