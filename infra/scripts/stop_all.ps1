# ============================================================
#  九天梧桐 AI 工作台 - 彻底停止（网页 + 数据库 一键全关）
#  说明：直接关闭启动窗口 = 只停网页（数据库留在后台，方便下次秒开）；
#        双击本脚本 = 网页与数据库全部停止，彻底退出。
# ============================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# $InfraRoot 只用于匹配网页进程的可执行路径（infra\ 目录），不是项目根目录
$InfraRoot = Split-Path -Parent $PSScriptRoot
$DataHome = "C:\ProgramData\JiuTianWuTong"
$MySrv    = Join-Path $DataHome "mysql\server"
$MyIni    = Join-Path $DataHome "mysql\my.ini"
$MyAdmin  = Join-Path $MySrv "bin\mysqladmin.exe"
$DbPort  = 3306
$DbPass  = "123456"

# ---------- 1) 停止网页服务（本发布包便携 Python 运行的 web.py） ----------
$webKilled = 0
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.ExecutablePath -and $_.ExecutablePath.StartsWith($InfraRoot, [System.StringComparison]::OrdinalIgnoreCase)
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    $webKilled++
}
if ($webKilled -gt 0) {
    Write-Host "[OK] 网页服务已停止（$webKilled 个进程）" -ForegroundColor Green
} else {
    Write-Host "[i] 未发现运行中的网页服务（可能已经关闭）" -ForegroundColor Cyan
}

# ---------- 2) 停止数据库服务 ----------
Write-Host "正在停止数据库服务..." -ForegroundColor Yellow

$stopped = $false
if (Test-Path $MyAdmin) {
    & $MyAdmin -u root "-p$DbPass" --protocol=TCP -h 127.0.0.1 -P $DbPort shutdown 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $stopped = $true }
}

if (-not $stopped) {
    # 兜底：只结束本软件目录下的 mysqld 进程，避免影响其它 MySQL
    Get-Process mysqld -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($DataHome, [System.StringComparison]::OrdinalIgnoreCase) } |
        ForEach-Object { Stop-Process -Id $_.Id -Force; $stopped = $true }
}

if ($stopped) {
    Write-Host "[OK] 数据库服务已停止" -ForegroundColor Green
} else {
    Write-Host "[i] 未发现运行中的数据库服务（可能已经停止）" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "[完成] 已全部退出。双击 启动.bat 可随时重新打开。" -ForegroundColor Green
Write-Host "[i] 数据库文件保存在 C:\ProgramData\JiuTianWuTong（如需彻底清理，手动删除该文件夹即可）" -ForegroundColor DarkGray
Read-Host "按回车键退出"
