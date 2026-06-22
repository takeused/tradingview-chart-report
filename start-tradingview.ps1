# TradingView 데스크톱을 CDP 디버깅 포트(9222)로 실행해 MCP 연결을 준비하는 런처
# 사용법: PowerShell에서  powershell -ExecutionPolicy Bypass -File .\start-tradingview.ps1

$port = 9222

# 1) 이미 9222 포트가 살아 있으면 그대로 사용
try {
  $r = Invoke-WebRequest -Uri "http://localhost:$port/json/version" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
  if ($r.StatusCode -eq 200) { Write-Host "이미 CDP가 연결돼 있습니다 (포트 $port). 그대로 사용하세요." -ForegroundColor Green; exit 0 }
} catch {}

# 2) MSIX 패키지 확인 (버전이 올라가도 자동 대응)
$pkg = Get-AppxPackage -Name *TradingView*
if (-not $pkg) {
  Write-Host "TradingView가 설치돼 있지 않습니다. 프로젝트 폴더의 TradingView.msix를 먼저 설치하세요." -ForegroundColor Red
  exit 1
}

# 3) 기존 인스턴스가 있으면 종료 (CDP를 새로 붙이기 위해)
Get-Process -Name TradingView -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 4) ApplicationActivationManager COM API로 AUMID에 디버그 포트 인자를 넘겨 실행
#    (WindowsApps의 exe를 직접 Start-Process하면 UWP 앱이 활성화되지 않고 즉시 종료되므로 이 방식이 필요)
$src = @"
using System;
using System.Runtime.InteropServices;
[ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IApplicationActivationManager {
    int ActivateApplication([In] string appUserModelId, [In] string arguments, [In] int options, [Out] out uint processId);
    int ActivateForFile([In] string appUserModelId, [In] IntPtr itemArray, [In] string verb, [Out] out uint processId);
    int ActivateForProtocol([In] string appUserModelId, [In] IntPtr itemArray, [Out] out uint processId);
}
[ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
public class ApplicationActivationManagerCo { }
public static class TvLauncher {
    public static uint Launch(string aumid, string args) {
        var mgr = (IApplicationActivationManager)(new ApplicationActivationManagerCo());
        uint procId;
        mgr.ActivateApplication(aumid, args, 0, out procId);
        return procId;
    }
}
"@
Add-Type -TypeDefinition $src -ErrorAction Stop

# AUMID = PackageFamilyName!ApplicationId (매니페스트에서 동적으로 구함)
$appId = ([xml]((Get-AppxPackageManifest $pkg).OuterXml)).Package.Applications.Application.Id
$aumid = "$($pkg.PackageFamilyName)!$appId"

Write-Host "TradingView 실행 중... (CDP 포트 $port, AUMID $aumid)" -ForegroundColor Cyan
[void][TvLauncher]::Launch($aumid, "--remote-debugging-port=$port")

# 5) 포트가 열릴 때까지 최대 90초 대기 (콜드 스타트 시 디버그 포트가 늦게 열릴 수 있음)
for ($i = 0; $i -lt 90; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://localhost:$port/json/version" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    if ($r.StatusCode -eq 200) {
      Write-Host "준비 완료. 이제 Claude에게 'tv_health_check 해줘' 라고 하세요." -ForegroundColor Green
      exit 0
    }
  } catch {}
  Start-Sleep -Seconds 1
}
Write-Host "90초 안에 CDP 포트가 열리지 않았습니다. 앱이 완전히 켜진 뒤 다시 시도하세요." -ForegroundColor Yellow
exit 1
