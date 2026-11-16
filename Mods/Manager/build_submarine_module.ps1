param([switch]$LayoutTest)
$ErrorActionPreference = 'Stop'
$rtwCompiler = 'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe'
if ($LayoutTest) {
    & $rtwCompiler /nologo /target:winexe /platform:x86 /optimize+ /langversion:5 /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll ("/out:" + (Join-Path $PSScriptRoot 'NativeDesignerLayoutTest.exe')) (Join-Path $PSScriptRoot 'BackendClient.cs') (Join-Path $PSScriptRoot 'NativeSubmarinePanel.cs') (Join-Path $PSScriptRoot 'NativeDesignerLayoutTest.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Subsystem layout test build failed.' }
    Start-Process -FilePath (Join-Path $PSScriptRoot 'NativeDesignerLayoutTest.exe') -WindowStyle Hidden -Wait
    $rtwResult = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'native-designer-layout-test.json') -Raw | ConvertFrom-Json
    if (-not $rtwResult.ok) { throw 'Subsystem layout test failed.' }
    $rtwResult
    return
}
& $rtwCompiler /nologo /target:library /platform:x86 /optimize+ /langversion:5 /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll ("/out:" + (Join-Path $PSScriptRoot 'RTW3.SubmarineDesigner.dll')) (Join-Path $PSScriptRoot 'BackendClient.cs') (Join-Path $PSScriptRoot 'NativeDesignerPlugin.cs') (Join-Path $PSScriptRoot 'NativeShipDesignerScreen.cs') (Join-Path $PSScriptRoot 'NativeSubmarinePanel.cs')
if ($LASTEXITCODE -ne 0) { throw 'In-game submarine module build failed.' }
Get-Item -LiteralPath (Join-Path $PSScriptRoot 'RTW3.SubmarineDesigner.dll') | Select-Object FullName,Length
