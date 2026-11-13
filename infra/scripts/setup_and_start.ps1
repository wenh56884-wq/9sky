# ============================================================
#  九天梧桐 AI 工作台 -- 一键启动脚本
#  首次运行：自动下载并配置 MySQL（绿色免安装）-> 导入内置数据 -> 启动网页
#  再次运行：直接启动网页（秒开）
#  数据库运行环境固定放在 C:\ProgramData\JiuTianWuTong（纯英文路径，避免中文路径兼容问题）
#  全程无需管理员权限；请保持网络连接（下载引擎 / 调用大模型均需联网）
# ============================================================
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PyExe    = Join-Path $ProjectRoot "infra\runtime\python\python.exe"
$AppDir   = Join-Path $ProjectRoot "backend"
# 数据库运行环境放固定英文路径（不随包解压位置变化，规避中文路径/中文用户名兼容问题）
$DataHome = "C:\ProgramData\JiuTianWuTong"
$MyRoot   = Join-Path $DataHome "mysql"
$MySrv    = Join-Path $MyRoot "server"
$MyData   = Join-Path $MyRoot "data"
$MyIni    = Join-Path $MyRoot "my.ini"
$MyExe    = Join-Path $MySrv "bin\mysqld.exe"
$MyCli    = Join-Path $MySrv "bin\mysql.exe"
$SqlDir   = Join-Path $ProjectRoot "infra\sql"
$LogDir   = Join-Path $DataHome "logs"
$LogFile  = Join-Path $LogDir "setup_log.txt"
$DbPort  = 3306
$DbPass  = "123456"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Say   ($m, $c = "White") { Write-Host $m -ForegroundColor $c }
function Log   ($m) { Add-Content -Path $LogFile -Value ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m) -Encoding UTF8 }
function Fatal ($m) {
    Say ""
    Say "[X] $m" Red
    Say "    详细日志：$LogFile" Yellow
    Say "    如多次失败，请联系作者（可在日志中查看具体原因）" Yellow
    Read-Host "按回车键退出"
    exit 1
}
function Test-TcpPort ($p) {
    try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $p); $c.Close(); return $true } catch { return $false }
}

Say "============================================================" Cyan
Say "   九天梧桐 AI 工作台" Cyan
Say "============================================================" Cyan
Say ""
Log "=== 启动脚本运行 ==="

# ---------- 0. 预检 ----------
if (-not (Test-Path $PyExe)) { Fatal "缺少 runtime\python（发布包不完整），请重新解压完整压缩包" }
if (-not (Test-Path (Join-Path $AppDir "web.py"))) { Fatal "缺少 backend\web.py（发布包不完整）" }
foreach ($f in @("financial_asset_management.sql", "healthcare_analytics_competition.sql", "telecom_operations_db.sql")) {
    if (-not (Test-Path (Join-Path $SqlDir $f))) { Fatal "缺少数据文件 infra\sql\$f" }
}
Say "[1/5] 发布包完整性检查通过" Green

$driveName = (Get-Item $ProjectRoot).PSDrive.Name
$freeGB = [math]::Round((Get-PSDrive $driveName).Free / 1GB, 1)
Say ("[2/5] 磁盘剩余 {0} GB（首次运行建议预留 4 GB 以上）" -f $freeGB) Green
if ($freeGB -lt 4) { Say "      [提示] 磁盘空间偏少，如后续报错请清理空间后重试" Yellow }

# ---------- 1. 首次配置：安装或下载 MySQL 引擎 ----------
$needSetup = -not (Test-Path (Join-Path $MyRoot ".configured"))

# 1.0 最快路径：发布包内自带预装数据库（引擎+数据），复制到固定位置即可（约 1~3 分钟）
if ((-not (Test-Path (Join-Path $MyRoot ".configured"))) -and (Test-Path (Join-Path $ProjectRoot "infra\mysql\.configured"))) {
    Say ""
    Say "[3/5] 正在安装内置数据库引擎与数据（约 1~3 分钟，请耐心等待）..." Yellow
    New-Item -ItemType Directory -Force -Path $MyRoot | Out-Null
    robocopy (Join-Path $ProjectRoot "infra\mysql") $MyRoot /E /MT:8 /NFL /NDL /NJH /NJS /NP | Out-Null
    if (-not (Test-Path $MyExe)) { Fatal "内置数据库安装失败（请检查磁盘空间或安全软件拦截）" }
    Say "      内置数据库安装完成" Green
    Log "已复制预装数据库到 $MyRoot"
    $needSetup = -not (Test-Path (Join-Path $MyRoot ".configured"))
}

if ($needSetup) {
    Say ""
    Say "============================================================" Cyan
    Say " 首次运行，自动配置（仅需一次，约 3~8 分钟，视网速）" Cyan
    Say " 流程：下载 MySQL 引擎 -> 初始化 -> 导入三个数据库" Cyan
    Say "============================================================" Cyan
    New-Item -ItemType Directory -Force -Path $MyRoot | Out-Null

    # 1.1 下载 MySQL 引擎（已解压过则直接跳过）
    $zip = Join-Path $MyRoot "mysql.zip"
    if (Test-Path (Join-Path $MySrv "bin\mysqld.exe")) {
        Say "[3/5] 已发现解压好的 MySQL 引擎，跳过下载与解压" Green
        Log "MySQL 引擎已就绪（跳过下载解压）"
    } else {
        if ((Test-Path $zip) -and ((Get-Item $zip).Length -gt 100MB)) {
            Say "[3/5] 已发现下载好的 MySQL 引擎压缩包，跳过下载" Green
        } else {
            Say ""
            Say "[3/5] 正在下载 MySQL 引擎（约 230 MB，请保持网络连接）..." Yellow
            Say "      下载源：cdn.mysql.com" Gray
            $url = "https://cdn.mysql.com/Downloads/MySQL-8.4/mysql-8.4.9-winx64.zip"
            Log "下载: $url"
            curl.exe -L --fail --retry 3 -# -o "$zip" "$url"
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path $zip) -or (Get-Item $zip).Length -lt 100MB) {
                Say ""
                Say "[!] 自动下载失败（可能是网络问题）。请手动下载： " Yellow
                Say "    $url" White
                Say "    下载完成后，把文件放到：$MyRoot\mysql.zip" White
                Say "    然后重新双击 启动.bat 即可（会跳过下载直接继续）" White
                Fatal "MySQL 引擎下载失败"
            }
            Say "      下载完成" Green
        }
        Log "下载完成"

        # 1.2 解压
        Say "[4/5] 正在解压 MySQL 引擎..." Yellow
        if (Test-Path $MySrv) { Remove-Item $MySrv -Recurse -Force }
        $extractTmp = Join-Path $MyRoot "_extract"
        if (Test-Path $extractTmp) { Remove-Item $extractTmp -Recurse -Force }
        try {
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $extractTmp)
        } catch { Fatal "解压失败：$($_.Exception.Message)" }
        $inner = Get-ChildItem $extractTmp -Directory | Select-Object -First 1
        if (-not $inner) { Fatal "解压结果异常" }
        Move-Item $inner.FullName $MySrv
        Remove-Item $extractTmp -Recurse -Force
        Remove-Item $zip -Force
        Say "      解压完成" Green
    }

    # 1.3 初始化数据目录
    Say "[5/5] 初始化数据库并导入数据（约 2~4 分钟，请耐心等待）..." Yellow
    if (Test-Path $MyData) { Remove-Item $MyData -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $MyData | Out-Null
    $srvSlash  = $MySrv.Replace('\', '/')
    $dataSlash = $MyData.Replace('\', '/')
    @"
[mysqld]
basedir=$srvSlash
datadir=$dataSlash
port=$DbPort
character-set-server=utf8mb4
collation-server=utf8mb4_0900_ai_ci
max_connections=200
skip-log-bin
innodb_flush_log_at_trx_commit=2
innodb_buffer_pool_size=512M
innodb_redo_log_capacity=512M
max_allowed_packet=256M
"@ | Set-Content -Path $MyIni -Encoding Ascii

    Log "开始初始化 MySQL"
    & $MyExe "--defaults-file=$MyIni" --initialize-insecure --console 2>&1 |
        ForEach-Object { $_ | Tee-Object -FilePath $LogFile -Append }
    if (-not (Test-Path (Join-Path $MyData "mysql"))) { Fatal "MySQL 初始化失败（详见日志）" }
    Say "      初始化完成，正在启动数据库服务..." Green

    Start-Process -FilePath $MyExe -ArgumentList "--defaults-file=`"$MyIni`"" -WindowStyle Hidden
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        & $MyCli -u root --protocol=TCP -h 127.0.0.1 -P $DbPort --connect-timeout=2 -e "SELECT 1;" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    }
    if (-not $ready) { Fatal "数据库服务启动超时" }

    & $MyCli -u root --protocol=TCP -h 127.0.0.1 -P $DbPort -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$DbPass'; FLUSH PRIVILEGES;" 2>$null | Out-Null
    Say "      数据库服务就绪" Green

    # 1.4 建库 + 导入（硬链接到英文临时路径，兼容中文安装目录）
    $linkDir = Join-Path $env:TEMP "jiutian_import_links"
    New-Item -ItemType Directory -Force -Path $linkDir | Out-Null
    $dbs = [ordered]@{
        "financial_asset_management"       = "financial_asset_management.sql"
        "healthcare_analytics_competition" = "healthcare_analytics_competition.sql"
        "telecom_operations_db"            = "telecom_operations_db.sql"
    }
    foreach ($db in $dbs.Keys) {
        & $MyCli -u root "-p$DbPass" --protocol=TCP -h 127.0.0.1 -P $DbPort -e "DROP DATABASE IF EXISTS $db; CREATE DATABASE $db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;" 2>$null
    }
    $tAll = Get-Date
    foreach ($db in $dbs.Keys) {
        $src = Join-Path $SqlDir $dbs[$db]
        $lnk = Join-Path $linkDir ($db + ".sql")
        if (Test-Path $lnk) { Remove-Item $lnk -Force }
        New-Item -ItemType HardLink -Path $lnk -Target $src | Out-Null
        $sizeMB = [math]::Round((Get-Item $src).Length / 1MB, 0)
        Say ("      正在导入 {0}（约 {1} MB）..." -f $db, $sizeMB) Yellow
        $t0 = Get-Date
        Log "导入 $db 开始"
        cmd /c "`"$MyCli`" -u root -p$DbPass --protocol=TCP -h 127.0.0.1 -P $DbPort --default-character-set=utf8mb4 $db < `"$lnk`""
        if ($LASTEXITCODE -ne 0) { Fatal "导入 $db 失败（详见日志）" }
        $sec = [math]::Round(((Get-Date) - $t0).TotalSeconds)
        Log "导入 $db 完成，用时 $sec 秒"
        Say ("        完成，用时 {0} 秒" -f $sec) Green
    }
    Remove-Item $linkDir -Recurse -Force -ErrorAction SilentlyContinue

    $cnt = & $MyCli -u root "-p$DbPass" --protocol=TCP -h 127.0.0.1 -P $DbPort -N -B -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('financial_asset_management','healthcare_analytics_competition','telecom_operations_db');" 2>$null
    Say ("      数据导入完成：三库共 {0} 张表，总用时 {1} 秒" -f $cnt, [math]::Round(((Get-Date) - $tAll).TotalSeconds)) Green
    Set-Content -Path (Join-Path $MyRoot ".configured") -Value (Get-Date -Format "yyyy-MM-dd HH:mm:ss") -Encoding ascii
    Log "首次配置完成"
    Say ""
    Say " 首次配置全部完成！之后再次启动只需几秒钟。" Green

    # 1.5 创建三个专用 MySQL 账号（写数据能力的数据库层兜底，§8.2）
    # jt_read  ：三库只读（Agent 默认读账号）
    # jt_write ：白名单表读写（初始不授权任何表，由超管后续逐表开启）
    # jt_admin ：三库 ALL（仅超管提权会话使用）
    # 口令随机生成，写入 backend/.env（DB_USER_READ / DB_USER_WRITE / DB_USER_ADMIN）
    Say ""
    Say "正在创建数据库专用账号（jt_read / jt_write / jt_admin）..." Yellow
    function _gen_pass {
        $b = New-Object byte[] 18
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
        $s = [System.Convert]::ToBase64String($b) -replace '[/+]','_' -replace '[=]',''
        return $s.Substring(0, 24)
    }
    $readPass  = _gen_pass
    $writePass = _gen_pass
    $adminPass = _gen_pass

    $envFile = Join-Path $AppDir ".env"
    if (-not (Test-Path $envFile)) {
        Set-Content -Path $envFile -Value "# 九天梧桐 AI 工作台 - 运行时配置（由启动脚本自动生成）" -Encoding UTF8
    }

    # jt_read：三库 SELECT
    $sqlRead = "CREATE USER IF NOT EXISTS 'jt_read'@'localhost' IDENTIFIED BY '$readPass';" +
        " GRANT SELECT ON financial_asset_management.* TO 'jt_read'@'localhost';" +
        " GRANT SELECT ON healthcare_analytics_competition.* TO 'jt_read'@'localhost';" +
        " GRANT SELECT ON telecom_operations_db.* TO 'jt_read'@'localhost';"
    & $MyCli -u root "-p$DbPass" --protocol=TCP -h 127.0.0.1 -P $DbPort -e $sqlRead 2>$null
    if ($LASTEXITCODE -ne 0) { Log "jt_read 账号创建失败：$sqlRead" }

    # jt_write：仅建用户，不授权任何表（白名单由超管逐表开启）
    $sqlWrite = "CREATE USER IF NOT EXISTS 'jt_write'@'localhost' IDENTIFIED BY '$writePass';"
    & $MyCli -u root "-p$DbPass" --protocol=TCP -h 127.0.0.1 -P $DbPort -e $sqlWrite 2>$null
    if ($LASTEXITCODE -ne 0) { Log "jt_write 账号创建失败：$sqlWrite" }

    # jt_admin：三库 ALL
    $sqlAdmin = "CREATE USER IF NOT EXISTS 'jt_admin'@'localhost' IDENTIFIED BY '$adminPass';" +
        " GRANT ALL ON financial_asset_management.* TO 'jt_admin'@'localhost';" +
        " GRANT ALL ON healthcare_analytics_competition.* TO 'jt_admin'@'localhost';" +
        " GRANT ALL ON telecom_operations_db.* TO 'jt_admin'@'localhost';"
    & $MyCli -u root "-p$DbPass" --protocol=TCP -h 127.0.0.1 -P $DbPort -e $sqlAdmin 2>$null
    if ($LASTEXITCODE -ne 0) { Log "jt_admin 账号创建失败：$sqlAdmin" }

    # 写入 .env（追加，不覆盖已有配置）
    Add-Content -Path $envFile -Encoding UTF8 -Value @(
        "# --- 数据库专用账号（启动脚本自动生成，写数据能力兜底） ---",
        "DB_USER_READ=$readPass",
        "DB_USER_WRITE=$writePass",
        "DB_USER_ADMIN=$adminPass"
    )
    Log "三个数据库专用账号已创建，口令已写入 $envFile"
    Say "      数据库专用账号创建完成" Green
} else {
    Say "[3/5] 检测到已完成首次配置，跳过（直接启动）" Green
}

# ---------- 1.6 每次启动都确保专用账号存在（写数据能力兜底，§8.2）----------
# 首次配置已跳过的情况下，账号可能从未创建，这里补建（幂等：已存在则跳过）
$envFile = Join-Path $AppDir ".env"
if (-not (Test-Path $envFile)) {
    Set-Content -Path $envFile -Value "# 九天梧桐 AI 工作台 - 运行时配置" -Encoding UTF8
}
$envContent = ""
if (Test-Path $envFile) { $envContent = Get-Content $envFile -Raw }

function _ensure_account ($sql) {
    & $MyCli -u root "-p$DbPass" --protocol=TCP -h 127.0.0.1 -P $DbPort -e $sql 2>$null
    if ($LASTEXITCODE -ne 0) { Log "账号创建失败：$sql" }
}

# jt_read / jt_write / jt_admin 已存在则跳过，不存在则创建
$acctCheck = & $MyCli -u root "-p$DbPass" --protocol=TCP -h 127.0.0.1 -P $DbPort -N -B -e "SELECT user FROM mysql.user WHERE user IN ('jt_read','jt_write','jt_admin');" 2>$null
$existingAccts = @($acctCheck | ForEach-Object { $_.Trim() })

# 无条件执行（不再用 Count -lt 3 跳过）：每次启动都把库里的口令对齐到 .env，
# 修掉历史版本 CREATE USER IF NOT EXISTS 造成的「口令漂移 → Access denied」。
if ($true) {
    Say ""
    Say "正在确保数据库专用账号就绪..." Yellow
    function _gen_pass2 {
        $b = New-Object byte[] 18
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
        $s = [System.Convert]::ToBase64String($b) -replace '[/+]','_' -replace '[=]',''
        return $s.Substring(0, 24)
    }
    # 关键：优先沿用 .env 里已有的口令，保证「库里的口令」与「应用读到的口令」永远一致。
    # 早期版本用 CREATE USER IF NOT EXISTS，账号已存在时不改密码，
    # 导致 .env 换了新口令而库里还是旧口令 → 应用连库被拒（Access denied）。
    function _read_env_pass ($key, $fallback) {
        if ($envContent -match "(?m)^\s*$key\s*=\s*(\S+)\s*$") { return $Matches[1] }
        return $fallback
    }
    $readPass  = _read_env_pass 'DB_USER_READ'  (_gen_pass2)
    $writePass = _read_env_pass 'DB_USER_WRITE' (_gen_pass2)
    $adminPass = _read_env_pass 'DB_USER_ADMIN' (_gen_pass2)

    # 逐个账号：先 CREATE IF NOT EXISTS，再 ALTER USER 强制对齐口令（幂等且修漂移）
    $sqlRead = "CREATE USER IF NOT EXISTS 'jt_read'@'localhost' IDENTIFIED BY '$readPass';" +
        " ALTER USER 'jt_read'@'localhost' IDENTIFIED BY '$readPass';" +
        " GRANT SELECT ON financial_asset_management.* TO 'jt_read'@'localhost';" +
        " GRANT SELECT ON healthcare_analytics_competition.* TO 'jt_read'@'localhost';" +
        " GRANT SELECT ON telecom_operations_db.* TO 'jt_read'@'localhost';"
    _ensure_account $sqlRead
    Say "      jt_read 已就绪" Green

    $sqlWrite = "CREATE USER IF NOT EXISTS 'jt_write'@'localhost' IDENTIFIED BY '$writePass';" +
        " ALTER USER 'jt_write'@'localhost' IDENTIFIED BY '$writePass';"
    _ensure_account $sqlWrite
    Say "      jt_write 已就绪" Green

    $sqlAdmin = "CREATE USER IF NOT EXISTS 'jt_admin'@'localhost' IDENTIFIED BY '$adminPass';" +
        " ALTER USER 'jt_admin'@'localhost' IDENTIFIED BY '$adminPass';" +
        " GRANT ALL ON financial_asset_management.* TO 'jt_admin'@'localhost';" +
        " GRANT ALL ON healthcare_analytics_competition.* TO 'jt_admin'@'localhost';" +
        " GRANT ALL ON telecom_operations_db.* TO 'jt_admin'@'localhost';"
    _ensure_account $sqlAdmin
    Say "      jt_admin 已就绪" Green

    # 写入 .env（仅当变量不存在时追加）
    $needEnvWrite = $false
    if ($envContent -notmatch 'DB_USER_READ')  { $needEnvWrite = $true }
    if ($envContent -notmatch 'DB_USER_WRITE') { $needEnvWrite = $true }
    if ($envContent -notmatch 'DB_USER_ADMIN') { $needEnvWrite = $true }
    if ($needEnvWrite) {
        Add-Content -Path $envFile -Encoding UTF8 -Value @(
            "# --- 数据库专用账号（启动脚本自动生成） ---",
            "DB_USER_READ=$readPass",
            "DB_USER_WRITE=$writePass",
            "DB_USER_ADMIN=$adminPass"
        )
        Log "数据库专用账号口令已写入 $envFile"
    }
} else {
    Log "数据库专用账号已存在，跳过创建"
}

# ---------- 2. 确保数据库在运行 ----------
# 先清理残留 mysqld 进程（端口不匹配或上次未正常退出时避免持锁）
Get-Process mysqld -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path.StartsWith($MyRoot, [System.StringComparison]::OrdinalIgnoreCase) } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

$dbUp = $false
& $MyCli -u root "-p$DbPass" --protocol=TCP -h 127.0.0.1 -P $DbPort --connect-timeout=3 -e "SELECT 1;" 2>$null | Out-Null
$dbUp = ($LASTEXITCODE -eq 0)
if (-not $dbUp) {
    Say "[4/5] 正在启动数据库服务..." Yellow
    Start-Process -FilePath $MyExe -ArgumentList "--defaults-file=`"$MyIni`"" -WindowStyle Hidden
    for ($i = 0; $i -lt 40 -and -not $dbUp; $i++) {
        Start-Sleep -Seconds 1
        & $MyCli -u root "-p$DbPass" --protocol=TCP -h 127.0.0.1 -P $DbPort --connect-timeout=2 -e "SELECT 1;" 2>$null | Out-Null
        $dbUp = ($LASTEXITCODE -eq 0)
    }
    if (-not $dbUp) { Fatal "数据库服务启动失败" }
    Say "      数据库服务已启动（端口 $DbPort）" Green
} else {
    Say "[4/5] 数据库服务运行正常（端口 $DbPort）" Green
}

# ---------- 3. 启动网页（自动打开浏览器） ----------
$WebPort = 5001
while (Test-TcpPort $WebPort) { $WebPort++ }

Say "[5/5] 正在启动网页服务..." Yellow
Say ""
Say "------------------------------------------------------------" Cyan
if ($WebPort -ne 5001) { Say " 提示：默认端口被占用，已自动改用端口 $WebPort" Yellow }
Say " 浏览器即将自动打开：http://127.0.0.1:$WebPort" Cyan
Say " 若浏览器没有自动打开，请手动访问上面这个网址" Cyan
Say " 本窗口即为服务窗口：关闭它 = 停止网页（再次双击 启动.bat 可重新打开）" Cyan
Say " 彻底退出（连数据库一起关）：双击 停止.bat" Cyan
Say "------------------------------------------------------------" Cyan
Say ""
Log "启动 web，端口 $WebPort"

$env:PORT = "$WebPort"
$env:HOST = "127.0.0.1"
Set-Location $AppDir
& $PyExe (Join-Path $AppDir "web.py")

Say ""
Say "网页服务已停止。想再次使用，双击 启动.bat 即可。" Green
Read-Host "按回车键退出"
