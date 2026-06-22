# TradingView 데스크톱을 CDP 디버깅 포트(9222)로 실행해 MCP 연결을 준비하는 런처
# 사용법: PowerShell에서  powershell -ExecutionPolicy Bypass -File .\start-tradingview.ps1

$port = 9222

# 1) 이미 9222 포트가 살아 있으면 그대로 사용
try {
  $r = Invoke-WebRequest -Uri "http://localhost:$port/json/version" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
  if ($r.StatusCode -eq 200) { Write-Host "이미 CDP가 연결돼 있습니다 (포트 $port). 그대로 사용하세요." -ForegroundColor Green; exit 0 }
} catch {}

# 2) MSIX 패키지에서 실행 파일 경로를 동적으로 찾기 (버전이 올라가도 자동 대응)
$pkg = Get-AppxPackage -Name *TradingView*
if (-not $pkg) {
  Write-Host "TradingView가 설치돼 있지 않습니다. 프로젝트 폴더의 TradingView.msix를 먼저 설치하세요." -ForegroundColor Red
  exit 1
}
$exe = Join-Path $pkg.InstallLocation "TradingView.exe"

# 3) 디버깅 포트 없이 떠 있는 기존 인스턴스가 있으면 종료 (CDP를 새로 붙이기 위해)
Get-Process -Name TradingView -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# 4) 디버깅 포트를 켜서 실행
Write-Host "TradingView 실행 중... (CDP 포트 $port)" -ForegroundColor Cyan
Start-Process -FilePath $exe -ArgumentList "--remote-debugging-port=$port"

# 5) 포트가 열릴 때까지 최대 30초 대기
for ($i = 0; $i -lt 30; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://localhost:$port/json/version" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    if ($r.StatusCode -eq 200) {
      Write-Host "준비 완료. 이제 Claude에게 'tv_health_check 해줘' 라고 하세요." -ForegroundColor Green
      exit 0
    }
  } catch {}
  Start-Sleep -Seconds 1
}
Write-Host "30초 안에 CDP 포트가 열리지 않았습니다. 앱이 완전히 켜진 뒤 다시 시도하세요." -ForegroundColor Yellow
exit 1
