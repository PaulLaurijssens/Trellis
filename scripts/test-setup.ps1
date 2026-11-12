# Tests for setup.ps1 without Docker:   pwsh -File scripts/test-setup.ps1   (or: powershell -File ...)
# 1. The file parses, and its pure functions work (setup.ps1 is dot-sourced; Main does not run then).
# 2. Whole runs of Main -Yes with fakes for docker, health, ports, WSL, browser and clipboard, in a temp folder.
# Works in Windows PowerShell 5.1 and PowerShell 7 (Windows, Linux, Mac). Keep it plain ASCII.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$setup = Join-Path $root 'setup.ps1'
$script:pass = 0
$script:failed = 0

function Fail-Test([string]$Name, [string]$Detail) {
    $script:failed++
    Write-Host "FAIL: $Name"
    if ($Detail) { ($Detail -split "`n" | Select-Object -First 40) | ForEach-Object { Write-Host "      $_" } }
}
function Eq([string]$Name, $Expected, $Got) {
    if ("$Expected" -ceq "$Got") { $script:pass++ } else { Fail-Test $Name "expected: [$Expected]`ngot:      [$Got]" }
}
function Has([string]$Name, [string]$Text, [string]$Needle) {
    if ($Text.Contains($Needle)) { $script:pass++ } else { Fail-Test "$($Name): missing [$Needle]" $Text }
}
function Hasnt([string]$Name, [string]$Text, [string]$Needle) {
    if (-not $Text.Contains($Needle)) { $script:pass++ } else { Fail-Test "$($Name): should not contain [$Needle]" $Text }
}
function Yes-Test([string]$Name, [bool]$Value) { if ($Value) { $script:pass++ } else { Fail-Test $Name 'expected true' } }

# ---------------------------------------------------------------- parse
$tokens = $null
$errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($setup, [ref]$tokens, [ref]$errors)
Eq 'setup.ps1 parses' 0 @($errors).Count
$bytes = [System.IO.File]::ReadAllBytes($setup)
Eq 'setup.ps1 is plain ASCII' 0 @($bytes | Where-Object { $_ -gt 127 }).Count

$T = Join-Path ([System.IO.Path]::GetTempPath()) ("trellis-ps-test-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
$null = New-Item -ItemType Directory -Force -Path $T
$env:LOCALAPPDATA = Join-Path $T 'localappdata'     # setup state goes here, not in the real profile
$env:TRELLIS_SETUP_NO_BROWSER = '1'

. $setup

# ---------------------------------------------------------------- pure functions
$script:Neo4jPw = ''
$script:TrellisDir = ''
Eq 'redact openai key' 'OPENAI_API_KEY=[REDACTED]' (Hide-Secrets 'OPENAI_API_KEY=sk-proj-abcdefghijklmnop123')
Eq 'redact sk- in text' 'used sk-[REDACTED] here' (Hide-Secrets 'used sk-ant-api03-abcdefgh12345 here')
Eq 'redact gemini key' 'key AIza[REDACTED] x' (Hide-Secrets 'key AIzaSyA1234567890abcdefghijklmnopq x')
Eq 'redact json key' '"api_key": "[REDACTED]"' (Hide-Secrets '"api_key": "zzz123"')
Eq 'redact bearer' 'Authorization: Bearer [REDACTED]' (Hide-Secrets 'Authorization: Bearer abc.def.ghi')
Eq 'redact password=' 'NEO4J_PASSWORD=[REDACTED]' (Hide-Secrets 'NEO4J_PASSWORD=hunter2hunter2')
Eq 'redact token:' 'token: [REDACTED]' (Hide-Secrets 'token: ghp_abc')
Eq 'redact long hex' 'sha256:[REDACTED-HEX]' (Hide-Secrets 'sha256:0123456789abcdef0123456789abcdef0123456789abcdef')
Eq 'redact long key' 'azure [REDACTED]' (Hide-Secrets 'azure AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfGhIjKlMn')
Eq 'keep normal text' 'unauthorized: authentication required' (Hide-Secrets 'unauthorized: authentication required')
Eq 'redact keeps lines' "a`nNEO4J_PASSWORD=[REDACTED]`nb" (Hide-Secrets "a`nNEO4J_PASSWORD=x1`nb")
$script:Neo4jPw = 'Sup3r-Secret.Value'
Eq 'redact db password' 'pw is [REDACTED] ok' (Hide-Secrets 'pw is Sup3r-Secret.Value ok')
$script:Neo4jPw = ''
$rd = Join-Path $T 'redact'
$null = New-Item -ItemType Directory -Force -Path $rd
Write-TextFile (Join-Path $rd '.env') "NEO4J_PASSWORD=FromTheEnvFile99`n"
$script:TrellisDir = $rd
Eq 'redact password from .env' 'x [REDACTED] y' (Hide-Secrets 'x FromTheEnvFile99 y')
$script:TrellisDir = ''

$kinds = @(
    @('tls', 'Get "https://ghcr.io/v2/": tls: failed to verify certificate: x509: certificate signed by unknown authority'),
    @('tls', 'Get "https://ghcr.io/v2/": proxyconnect tcp: dial tcp: lookup proxy.corp: no such host'),
    @('tls', 'The underlying connection was closed: Could not establish trust relationship for the SSL/TLS secure channel.'),
    @('dns', 'Get "https://ghcr.io/v2/": dial tcp: lookup ghcr.io: no such host'),
    @('dns', "The remote name could not be resolved: 'github.com'"),
    @('missing', 'manifest unknown'),
    @('missing', 'Error response from daemon: denied'),
    @('missing', 'The remote server returned an error: (404) Not Found.'),
    @('ratelimit', 'toomanyrequests: You have reached your pull rate limit.'),
    @('offline', 'net/http: request canceled while waiting for connection (Client.Timeout exceeded while awaiting headers)'),
    @('offline', 'Unable to connect to the remote server'),
    @('unknown', 'something odd happened')
)
foreach ($k in $kinds) { Eq "class $($k[1])" $k[0] (Get-ErrorKind $k[1]) }

# Ports: a fake "in use" list, then the real check against a listening socket.
$realPortInUse = ${function:Test-PortInUse}
function Test-PortInUse([int]$Port) { return ($script:Busy -contains $Port) }
$script:Busy = @(8080, 8081); Eq 'pick next free port' 8082 (Select-Port 8080)
$script:Busy = @(); Eq 'pick first port' 8080 (Select-Port 8080)
$script:Busy = 9000..9019; Eq 'no free port' 0 (Select-Port 9000)
${function:Test-PortInUse} = $realPortInUse
$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$lport = $listener.LocalEndpoint.Port
Yes-Test 'port in use' (Test-PortInUse $lport)
$listener.Stop()
Yes-Test 'port free after close' (-not (Test-PortInUse $lport))

# .env writing
$example = [System.IO.File]::ReadAllText((Join-Path $root '.env.example')) -replace "`r`n", "`n"   # a Windows checkout may have CRLF
$e1 = Join-Path $T 'env1'
$null = New-Item -ItemType Directory -Force -Path $e1
Write-TextFile (Join-Path $e1 '.env.example') $example
Write-EnvFile $e1 8080
$pw = Get-EnvValue (Join-Path $e1 '.env') 'NEO4J_PASSWORD'
Yes-Test 'password 40+ chars' ($pw.Length -ge 40)
Yes-Test 'password letters and digits' ($pw -cmatch '^[A-Za-z0-9]+$')
Eq 'no port line for 8080' '' (Get-EnvValue (Join-Path $e1 '.env') 'TRELLIS_PORT')
$written = [System.IO.File]::ReadAllText((Join-Path $e1 '.env'))
Eq 'rest of .env.example kept' (($example -split "`n") -notmatch '^NEO4J_PASSWORD=' -join "`n") (($written -split "`n") -notmatch '^NEO4J_PASSWORD=' -join "`n")
$raw = [System.IO.File]::ReadAllBytes((Join-Path $e1 '.env'))
Yes-Test '.env has no byte order mark' (-not ($raw[0] -eq 0xEF -and $raw[1] -eq 0xBB))
Yes-Test '.env has no CR' (-not ($raw -contains 13))
Write-EnvFile $e1 8080
Eq 'second write changes nothing' $written ([System.IO.File]::ReadAllText((Join-Path $e1 '.env')))
Write-EnvFile $e1 8081
Eq 'port written' '8081' (Get-EnvValue (Join-Path $e1 '.env') 'TRELLIS_PORT')
Eq 'password kept on port change' $pw (Get-EnvValue (Join-Path $e1 '.env') 'NEO4J_PASSWORD')
Write-EnvFile $e1 8090
Eq 'port replaced' '8090' (Get-EnvValue (Join-Path $e1 '.env') 'TRELLIS_PORT')
Eq 'one port line' 1 @(([System.IO.File]::ReadAllLines((Join-Path $e1 '.env'))) -match '^TRELLIS_PORT=').Count

$e2 = Join-Path $T 'env2'
$null = New-Item -ItemType Directory -Force -Path $e2
$mine = "# mine`r`nNEO4J_PASSWORD=keep-this-one`r`nGEMINI_API_KEY=AIzaKeep`r`n"
[System.IO.File]::WriteAllText((Join-Path $e2 '.env'), $mine)
Write-EnvFile $e2 8080
Eq 'existing .env untouched (CRLF too)' $mine ([System.IO.File]::ReadAllText((Join-Path $e2 '.env')))

$e3 = Join-Path $T 'env3'
$null = New-Item -ItemType Directory -Force -Path $e3
Write-TextFile (Join-Path $e3 '.env') 'GEMINI_API_KEY=AIzaKeep'
Write-EnvFile $e3 8080
Eq 'first line kept' 'GEMINI_API_KEY=AIzaKeep' ([System.IO.File]::ReadAllLines((Join-Path $e3 '.env')))[0]
Yes-Test 'password added' ((Get-EnvValue (Join-Path $e3 '.env') 'NEO4J_PASSWORD').Length -ge 40)

$e4 = Join-Path $T 'env4'
$null = New-Item -ItemType Directory -Force -Path $e4
Write-TextFile (Join-Path $e4 '.env') "NEO4J_PASSWORD=change-me`n"
Write-EnvFile $e4 8080
Eq 'existing change-me kept' 'change-me' (Get-EnvValue (Join-Path $e4 '.env') 'NEO4J_PASSWORD')
Write-TextFile (Join-Path $e4 '.env') "A=`"quoted value`"`r`nB=x`n"
Eq 'env value without quotes and CR' 'quoted value' (Get-EnvValue (Join-Path $e4 '.env') 'A')
Eq 'missing env value' '' (Get-EnvValue (Join-Path $e4 '.env') 'MISSING')

# Checksums
$f = Join-Path $T 'f.zip'
Write-TextFile $f "hello`n"
$h = (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant()
Write-TextFile (Join-Path $T 'S1') "$h  f.zip`n"
Yes-Test 'sha256 ok' (Test-Sha256 $f (Join-Path $T 'S1') 'f.zip')
Write-TextFile (Join-Path $T 'S2') "$($h.ToUpperInvariant()) *dist/f.zip`r`n"
Yes-Test 'sha256 upper case, star, folder, CRLF' (Test-Sha256 $f (Join-Path $T 'S2') 'f.zip')
Write-TextFile (Join-Path $T 'S3') "$('0' * 64)  f.zip`n"
Yes-Test 'sha256 mismatch' (-not (Test-Sha256 $f (Join-Path $T 'S3') 'f.zip'))
Yes-Test 'sha256 name not listed' (-not (Test-Sha256 $f (Join-Path $T 'S1') 'other.zip'))

# Copy-Folder merges into folders that already exist (no deploy\deploy), hidden files included.
$cf = Join-Path $T 'cf'
$null = New-Item -ItemType Directory -Force -Path (Join-Path $cf 'from/deploy'), (Join-Path $cf 'to/deploy')
Write-TextFile (Join-Path $cf 'from/deploy/nginx.conf') 'x'
Write-TextFile (Join-Path $cf 'from/.env.example') 'y'
Copy-Folder (Join-Path $cf 'from') (Join-Path $cf 'to')
Yes-Test 'copy merges folders' (Test-Path -LiteralPath ([System.IO.Path]::Combine($cf, 'to', 'deploy', 'nginx.conf')))
Yes-Test 'copy does not nest' (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($cf, 'to', 'deploy', 'deploy'))))
Yes-Test 'copy takes hidden files' (Test-Path -LiteralPath ([System.IO.Path]::Combine($cf, 'to', '.env.example')))

# The AI prompt: names the step, the command, the output, redacted, with the question.
$script:StepNo = 8; $script:StepTotal = 11; $script:StepName = 'Test the download'
function Get-OsDescription { 'Windows 11 Pro 10.0.22631 (AMD64)' }
function Get-DockerDescription { 'Docker version 27.3.1; Docker Compose version v2.29.7' }
Set-LastRun 'docker manifest inspect x' (((1..40 | ForEach-Object { "line $_" }) -join "`n") + "`nkey=sk-abcdefghijk123")
$p = Get-AiPrompt 'Your network or a proxy blocks the download.'
Has 'prompt' $p 'My computer: Windows 11 Pro 10.0.22631 (AMD64).'
Has 'prompt' $p 'The installer stopped at step 8 of 11: "Test the download".'
Has 'prompt' $p 'The command that failed: docker manifest inspect x'
Has 'prompt' $p 'Help me with this one step. Explain it in simple words.'
Has 'prompt last lines' $p "line 40`nkey=[REDACTED]"
Has 'prompt keeps 30 lines' $p "-----`nline 12`n"
Hasnt 'prompt redacted' $p 'sk-abcdefghijk123'

# ---------------------------------------------------------------- whole runs with fakes

function Test-IsWindows { $true }
function Test-WslReady { $script:Fake.Wsl }
function Test-DockerInstalled { $true }
function Start-DockerDesktop { $script:Calls.Add('start docker desktop'); $true }
function Get-TotalMemoryBytes { [int64]$script:Fake.Total }
function Set-WslMemory { $script:Calls.Add('set wsl memory'); $script:Fake.Mem = 6400000000; $true }
function Test-PortInUse([int]$Port) { $script:Fake.Busy -contains $Port }
function Open-Url([string]$Url) { $false }
function Copy-ToClipboard([string]$Text) { $script:Clip = $Text; $true }
function Start-Process { param($FilePath, $ArgumentList, $Verb, [switch]$Wait, [switch]$PassThru)
    $script:Calls.Add("start-process $FilePath $($ArgumentList -join ' ') $Verb")
    [pscustomobject]@{ ExitCode = 0 }
}
function Get-HealthState([int]$Port) {
    switch ($script:Fake.Health) {
        'ok' { if ($script:Fake.Up) { return 'ok' } else { return 'down' } }
        'empty' { if ($script:Fake.Recreated) { return 'ok' } else { return 'empty' } }
        default { return 'down' }
    }
}
function Invoke-Docker([string[]]$Arguments, [switch]$Show, [switch]$NoRecord) {
    $a = $Arguments -join ' '
    $script:Calls.Add($a)
    $code = 0
    $out = ''
    if ($a -eq '--version') { $out = 'Docker version 27.3.1, build fake' }
    elseif ($a -eq 'compose version') { $out = 'Docker Compose version v2.29.7' }
    elseif ($a -like 'info*') {
        if ($script:Fake.InfoDown) { $code = 1; $out = 'error during connect: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.' }
        elseif ($a -like '*MemTotal*') { $out = "$($script:Fake.Mem)" }
        elseif ($a -like '*NCPU*') { $out = '8' }
        else { $out = 'Server Version: 27.3.1' }
    }
    elseif ($a -like 'manifest inspect*') {
        switch ($script:Fake.Manifest) {
            'tls' { $code = 1; $out = 'Get "https://ghcr.io/v2/": tls: failed to verify certificate: x509: certificate signed by unknown authority (proxy token sk-test-abcdefghijkl1234)' }
            'missing' { $code = 1; $out = 'manifest unknown' }
            default { $out = '{"schemaVersion": 2}' }
        }
    }
    elseif ($a -like 'image inspect*') { $code = 1 }
    elseif ($a -like 'compose config*') { if ($a -like '*--services*') { $out = "neo4j`napi`nweb" } }
    elseif ($a -eq 'compose pull') { $out = 'api Pulled' }
    elseif ($a -like 'compose up*') {
        if ($a -like '*force-recreate*') { $script:Fake.Recreated = $true }
        $script:Fake.Up = $true
        $out = 'Container trellis-web-1  Healthy'
    }
    elseif ($a -like 'compose ps*') {
        if ($script:Fake.Up) { if ($a -like '*--services*') { $out = "neo4j`napi`nweb" } else { $out = "NAME            STATUS`ntrellis-web-1   Up 2 minutes" } }
    }
    elseif ($a -like 'compose logs*') {
        $out = "api  | connecting with NEO4J_PASSWORD $(Get-EnvValue (Join-Path (Get-Location).Path '.env') 'NEO4J_PASSWORD')"
    }
    if ($Show -and $out) { foreach ($l in ($out -split "`n")) { Write-Host "    $l" } }
    if (-not $NoRecord) { Set-LastRun "docker $a" $out }
    return [pscustomobject]@{ Code = $code; Output = $out }
}

# A release bundle and a source zip, served with file:// URLs.
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$rel = Join-Path $T 'rel'
$bt = Join-Path $rel 'trellis'
$null = New-Item -ItemType Directory -Force -Path (Join-Path $bt 'deploy'), (Join-Path $bt 'backups')
Write-TextFile (Join-Path $bt 'compose.yaml') "services: {}`n"
Write-TextFile (Join-Path $bt '.env.example') $example
Copy-Item -LiteralPath $setup -Destination (Join-Path $bt 'setup.ps1')
Write-TextFile (Join-Path $bt 'deploy/nginx.conf') ''
Write-TextFile (Join-Path $bt 'backups/.gitkeep') ''
$bundleZip = Join-Path $T 'trellis-bundle.zip'
[System.IO.Compression.ZipFile]::CreateFromDirectory($bt, $bundleZip, [System.IO.Compression.CompressionLevel]::Optimal, $true)
$bh = (Get-FileHash -LiteralPath $bundleZip -Algorithm SHA256).Hash.ToLowerInvariant()
Write-TextFile (Join-Path $T 'SHA256SUMS') "$bh  trellis-bundle.zip`n"
Write-TextFile (Join-Path $T 'BADSUMS') "$('a' * 64)  trellis-bundle.zip`n"
$srcTop = Join-Path $T 'src/Trellis-main'
$null = New-Item -ItemType Directory -Force -Path (Join-Path $srcTop 'backend')
Write-TextFile (Join-Path $srcTop 'compose.yaml') "services: {}`n"
Write-TextFile (Join-Path $srcTop '.env.example') $example
Write-TextFile (Join-Path $srcTop 'backend/Dockerfile.prod') ''
$srcZip = Join-Path $T 'main.zip'
[System.IO.Compression.ZipFile]::CreateFromDirectory($srcTop, $srcZip, [System.IO.Compression.CompressionLevel]::Optimal, $true)
function ConvertTo-FileUrl([string]$Path) { (New-Object System.Uri($Path, [System.UriKind]::Absolute)).AbsoluteUri }
$script:BundleUrl = ConvertTo-FileUrl $bundleZip
$script:SourceZipUrl = ConvertTo-FileUrl $srcZip
$goodSums = ConvertTo-FileUrl (Join-Path $T 'SHA256SUMS')
$script:Tick = 0
$script:DockerStartTries = 2
$script:HealthTries = 8

# Run-Setup @{fake overrides} args... -> sets $script:Out and $script:Stopped ('' when Main finished).
function Run-Setup([hashtable]$Fake, [string]$Folder, [switch]$Report) {
    $script:Fake = @{ Mem = 8333777000; Total = 16GB; Manifest = 'ok'; Health = 'ok'; InfoDown = $false; Wsl = $true; Up = $false; Recreated = $false; Busy = @() }
    foreach ($k in $Fake.Keys) { $script:Fake[$k] = $Fake[$k] }
    $script:Calls = New-Object System.Collections.Generic.List[string]
    $script:Clip = ''
    $script:Stopped = ''
    $script:Out = (& {
            try { Main -Yes -Dir $Folder -Report:$Report } catch { $script:Stopped = "$($_.Exception.Message)" }
        } 6>&1 | Out-String)
    $script:Log = $script:Calls -join "`n"
}
$script:SumsUrl = $goodSums

# A. Fresh install from the release bundle.
$D = [System.IO.Path]::Combine($T, 'a', 'Trellis')
Run-Setup @{} $D
Eq 'A finished' '' $script:Stopped
$steps = @('Step 1 of 11: Welcome', 'Step 2 of 11: Windows Subsystem for Linux (WSL 2)', 'Step 3 of 11: Docker', 'Step 4 of 11: Start Docker',
    'Step 5 of 11: Choose a folder', 'Step 6 of 11: Check memory and disk space', 'Step 7 of 11: Choose a port', 'Step 8 of 11: Test the download',
    'Step 9 of 11: Get the Trellis files', 'Step 10 of 11: Start Trellis', 'Step 11 of 11: Open Trellis',
    'Download checked (SHA256)', 'Trellis is ready.', 'docker compose stop', (Join-Path $D 'backups'))
foreach ($s in $steps) { Has 'A flow' $script:Out $s }
Yes-Test 'A compose.yaml' (Test-Path (Join-Path $D 'compose.yaml'))
Yes-Test 'A .env.example copied' (Test-Path (Join-Path $D '.env.example'))
$pwA = Get-EnvValue (Join-Path $D '.env') 'NEO4J_PASSWORD'
Yes-Test 'A password' ($pwA.Length -ge 40)
Hasnt 'A never shows the password' $script:Out $pwA
Has 'A pulls' $script:Log 'compose pull'
Has 'A starts' $script:Log 'compose up -d --wait'
Hasnt 'A does not build' $script:Log '--build'
Eq 'A remembers the folder' $D (Get-State).dir

# B. Run again: .env untouched, no new download, Trellis already running.
$before = [System.IO.File]::ReadAllText((Join-Path $D '.env'))
Run-Setup @{ Up = $true } $D
Eq 'B finished' '' $script:Stopped
Eq 'B .env unchanged' $before ([System.IO.File]::ReadAllText((Join-Path $D '.env')))
Has 'B' $script:Out 'Trellis is already set up in this folder'
Has 'B' $script:Out 'The Trellis files are already in'
Has 'B' $script:Out 'Trellis is already running.'
Hasnt 'B no pull' $script:Log 'compose pull'

# K. -Report: redacted, saved in the folder.
Run-Setup @{ Up = $true } $D -Report
Has 'K' $script:Out '== docker compose ps'
Has 'K' $script:Out 'Last 50 log lines: api'
Has 'K' $script:Out 'NEO4J_PASSWORD [REDACTED]'
Has 'K' $script:Out '.env settings (names only): NEO4J_PASSWORD'
Hasnt 'K never shows the password' $script:Out $pwA
$rep = Get-ChildItem -LiteralPath $D -Filter 'trellis-report-*.txt' | Select-Object -First 1
Yes-Test 'K report saved' ($null -ne $rep)
if ($rep) { Hasnt 'K saved report has no password' ([System.IO.File]::ReadAllText($rep.FullName)) $pwA }

# C. The network blocks the download: plain reason, the AI box, the clipboard; no further steps.
Run-Setup @{ Manifest = 'tls' } (Join-Path $T 'c/Trellis')
Eq 'C stopped' 'TRELLIS_SETUP_STOPPED' $script:Stopped
Has 'C' $script:Out 'Setup stopped at step 8 of 11: Test the download'
Has 'C' $script:Out 'Your network or a proxy blocks the download.'
Has 'C' $script:Out 'Copy this into ChatGPT, Claude or Copilot:'
Has 'C' $script:Out 'The command that failed: docker manifest inspect ghcr.io/paullaurijssens/trellis-api:latest'
Has 'C' $script:Out 'Help me with this one step. Explain it in simple words.'
Has 'C' $script:Out 'sk-[REDACTED]'
Hasnt 'C' $script:Out 'sk-test-abcdefghijkl1234'
Hasnt 'C' $script:Out 'Step 9 of 11'
Has 'C' $script:Out 'This text is also on your clipboard.'
Has 'C clipboard' $script:Clip 'Help me with this one step. Explain it in simple words.'

# D. Images not published: downloads the source and builds.
Run-Setup @{ Manifest = 'missing' } (Join-Path $T 'd/Trellis')
Eq 'D finished' '' $script:Stopped
Has 'D' $script:Out 'The ready-made Trellis download is not available yet.'
Has 'D' $script:Log 'compose up -d --build --wait'
Hasnt 'D no pull' $script:Log 'compose pull'
Yes-Test 'D backend' (Test-Path (Join-Path $T 'd/Trellis/backend'))

# F. Containers run but the address gives an empty reply: web is recreated.
Run-Setup @{ Health = 'empty' } (Join-Path $T 'f/Trellis')
Eq 'F finished' '' $script:Stopped
Has 'F' $script:Out 'its front door (web) does not answer'
Has 'F' $script:Log 'compose up -d --no-build --force-recreate web'

# G. Checksum mismatch.
$script:SumsUrl = ConvertTo-FileUrl (Join-Path $T 'BADSUMS')
Run-Setup @{} (Join-Path $T 'g/Trellis')
$script:SumsUrl = $goodSums
Eq 'G stopped' 'TRELLIS_SETUP_STOPPED' $script:Stopped
Has 'G' $script:Out 'its checksum does not match'
Has 'G' $script:Out 'Setup stopped at step 9 of 11: Get the Trellis files'
Yes-Test 'G nothing unpacked' (-not (Test-Path (Join-Path $T 'g/Trellis/compose.yaml')))

# H. Too little memory, small computer: stops with the .wslconfig steps.
Run-Setup @{ Mem = 4000000000; Total = 6GB } (Join-Path $T 'h/Trellis')
Eq 'H stopped' 'TRELLIS_SETUP_STOPPED' $script:Stopped
Has 'H' $script:Out 'Trellis needs 6 GB'
Has 'H' $script:Out 'memory=6GB'
Has 'H' $script:Out 'wsl --shutdown'

# H2. Too little memory, big computer: the installer offers to set it, and goes on.
Run-Setup @{ Mem = 4000000000; Total = 16GB } (Join-Path $T 'h2/Trellis')
Eq 'H2 finished' '' $script:Stopped
Has 'H2' $script:Log 'set wsl memory'
Has 'H2' $script:Out 'Docker may use 6 GB of memory now'

# I. Docker Desktop does not start.
Run-Setup @{ InfoDown = $true } (Join-Path $T 'i/Trellis')
Eq 'I stopped' 'TRELLIS_SETUP_STOPPED' $script:Stopped
Has 'I' $script:Log 'start docker desktop'
Has 'I' $script:Out 'Docker did not start within 2 minutes.'
Has 'I' $script:Out 'dockerDesktopLinuxEngine'

# W. WSL missing: installs it as administrator, asks for a restart, and a rerun continues.
Run-Setup @{ InfoDown = $true; Wsl = $false } (Join-Path $T 'w/Trellis')
Eq 'W restart' 'TRELLIS_SETUP_RESTART' $script:Stopped
Has 'W' $script:Log 'start-process wsl.exe --install --no-distribution RunAs'
Has 'W' $script:Out 'restart the computer now'
Yes-Test 'W progress saved' ([bool](Get-State).wslRestart)
Run-Setup @{} (Join-Path $T 'w/Trellis')
Eq 'W2 finished' '' $script:Stopped
Has 'W2' $script:Out 'Welcome back. The installer continues after the restart.'
Yes-Test 'W2 progress cleared' (-not [bool](Get-State).wslRestart)

# P. Port 8080 taken by another program: the next free one goes in .env.
Run-Setup @{ Busy = @(8080) } (Join-Path $T 'p/Trellis')
Eq 'P finished' '' $script:Stopped
Has 'P' $script:Out 'Port 8080 is in use by another program. Trellis uses port 8081 instead.'
Eq 'P port in .env' '8081' (Get-EnvValue (Join-Path $T 'p/Trellis/.env') 'TRELLIS_PORT')

Remove-Item -LiteralPath $T -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ''
Write-Host "$($script:pass) passed, $($script:failed) failed"
if ($script:failed -gt 0) { exit 1 }
exit 0
