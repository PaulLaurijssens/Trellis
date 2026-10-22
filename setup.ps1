<#
Trellis guided installer for Windows.

  powershell -ExecutionPolicy Bypass -File setup.ps1            step by step; asks before it changes anything
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Report    a diagnostic report for a bug report or an AI chat
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Help      all options

Safe to run again: it checks everything, repairs known problems and starts Trellis.
Mac and Linux: setup.sh does the same steps with the same texts. Change both together.
Works in Windows PowerShell 5.1 and PowerShell 7. Keep this file plain ASCII (5.1 reads it as ANSI).
Tests: scripts/test-setup.ps1 dot-sources this file; Main only runs when the file is executed.
#>
param(
    [switch]$Yes,
    [string]$Dir = '',
    [switch]$Report,
    [switch]$Help
)

$script:RepoUrl = 'https://github.com/PaulLaurijssens/Trellis'
$script:BundleUrl = "$($script:RepoUrl)/releases/latest/download/trellis-bundle.zip"
$script:SumsUrl = "$($script:RepoUrl)/releases/latest/download/SHA256SUMS"
$script:SourceZipUrl = "$($script:RepoUrl)/archive/refs/heads/main.zip"
if ($env:TRELLIS_BUNDLE_URL) { $script:BundleUrl = $env:TRELLIS_BUNDLE_URL }
if ($env:TRELLIS_SUMS_URL) { $script:SumsUrl = $env:TRELLIS_SUMS_URL }
if ($env:TRELLIS_SOURCE_ZIP_URL) { $script:SourceZipUrl = $env:TRELLIS_SOURCE_ZIP_URL }
$script:ImageRepo = 'ghcr.io/paullaurijssens/trellis'
$script:DefaultPort = 8080
$script:MinMemBytes = [int64]5905580032     # 5.5 GiB: Docker set to 6 GB reports a little less than 6
$script:MinDiskBytes = [int64]5368709120    # 5 GB
$script:DockerStartTries = 60               # x 2 s = 2 minutes
$script:HealthTries = 36                    # x 5 s = 3 minutes
$script:Tick = -1                           # tests: seconds per wait instead of the normal 2 or 5
if ($env:TRELLIS_SETUP_DOCKER_TRIES) { $script:DockerStartTries = [int]$env:TRELLIS_SETUP_DOCKER_TRIES }
if ($env:TRELLIS_SETUP_HEALTH_TRIES) { $script:HealthTries = [int]$env:TRELLIS_SETUP_HEALTH_TRIES }
if ($env:TRELLIS_SETUP_TICK) { $script:Tick = [int]$env:TRELLIS_SETUP_TICK }

$script:OptYes = $false
$script:OptDir = ''
$script:StepNo = 0
$script:StepTotal = 11
$script:StepName = 'Start'
$script:LastCmd = ''
$script:LastOutput = ''
$script:WorkTmp = ''
$script:TrellisDir = ''
$script:Port = 0
$script:IsCheckout = $false     # the folder has the source code (compose.yaml + backend\), so it can build
$script:Existing = $false       # the folder already had an .env when the installer started
$script:Build = $false          # build the images here instead of downloading them
$script:GetSource = $false      # download the source zip instead of the release bundle
$script:Neo4jPw = ''
$script:UseColor = $true
$script:StopMarker = 'TRELLIS_SETUP_STOPPED'

# ---------------------------------------------------------------- output

function Write-Line([string]$Text = '') { Write-Host $Text }
function Write-Info([string]$Text = '') { Write-Host "  $Text" }
function Write-Color([string]$Text, [string]$Color) {
    if ($script:UseColor) { Write-Host $Text -ForegroundColor $Color } else { Write-Host $Text }
}
function Write-Ok([string]$Text) {
    if ($script:UseColor) { Write-Host '  OK  ' -ForegroundColor Green -NoNewline; Write-Host $Text } else { Write-Host "  OK  $Text" }
}
function Write-Note([string]$Text) {
    if ($script:UseColor) { Write-Host '  Note: ' -ForegroundColor Yellow -NoNewline; Write-Host $Text } else { Write-Host "  Note: $Text" }
}
function Write-Cmd([string]$Text) { Write-Color "      $Text" 'Cyan' }

function Start-Step([string]$Name) {
    $script:StepNo++
    $script:StepName = $Name
    Write-Line ''
    Write-Line "Step $($script:StepNo) of $($script:StepTotal): $Name"
}

function Wait-Tick([int]$Seconds) {
    if ($script:Tick -ge 0) { $Seconds = $script:Tick }
    if ($Seconds -gt 0) { Start-Sleep -Seconds $Seconds }
}

# ---------------------------------------------------------------- questions

# Read-YesNo "question" $true|$false -> $true for yes. With -Yes it takes the default.
function Read-YesNo([string]$Question, [bool]$Default = $true) {
    $hint = '[Y/n]'
    if (-not $Default) { $hint = '[y/N]' }
    if ($script:OptYes) {
        $d = 'n'
        if ($Default) { $d = 'y' }
        Write-Info "$Question $hint $d (-Yes)"
        return $Default
    }
    while ($true) {
        $a = Read-Host "  $Question $hint"
        if ([string]::IsNullOrWhiteSpace($a)) { return $Default }
        if ($a -match '^[Yy]') { return $true }
        if ($a -match '^[Nn]') { return $false }
        Write-Info 'Please type y for yes or n for no.'
    }
}

# Read-Answer "question" "default" -> the answer. With -Yes it takes the default.
function Read-Answer([string]$Question, [string]$Default) {
    if ($script:OptYes) { return $Default }
    Write-Info $Question
    $a = Read-Host '  >'
    if ([string]::IsNullOrWhiteSpace($a)) { return $Default }
    return $a.Trim()
}

# Wait-Enter "message" -> $false with -Yes (nobody to wait for) or when the person types q.
function Wait-Enter([string]$Message) {
    if ($script:OptYes) { return $false }
    $a = Read-Host "  $Message"
    if ($a -match '^[Qq]') { return $false }
    return $true
}

# ---------------------------------------------------------------- pure helpers (tested)

# Hides secrets in a text: the database password, API keys, tokens, long hex.
function Hide-Secrets([string]$Text) {
    if ($null -eq $Text) { return '' }
    $secret = $script:Neo4jPw
    if (-not $secret -and $script:TrellisDir) { $secret = Get-EnvValue (Join-Path $script:TrellisDir '.env') 'NEO4J_PASSWORD' }
    if ($secret -and $secret.Length -ge 6) { $Text = $Text.Replace($secret, '[REDACTED]') }
    $Text = $Text -creplace 'sk-[A-Za-z0-9_-]{8,}', 'sk-[REDACTED]'
    $Text = $Text -creplace 'AIza[0-9A-Za-z_-]{20,}', 'AIza[REDACTED]'
    $Text = $Text -replace '(bearer)[ \t]+[^\s"]+', '$1 [REDACTED]'
    $Text = $Text -replace '([A-Za-z0-9_.-]*(key|passw(or)?d|token|secret)[A-Za-z0-9_.-]*)(["'']?[ \t]*[:=][ \t]*["'']?)[^\s"'',;}]+', '$1$4[REDACTED]'
    $Text = $Text -creplace '[0-9A-Fa-f]{32,}', '[REDACTED-HEX]'
    $Text = $Text -creplace '[A-Za-z0-9_-]{40,}', '[REDACTED]'
    return $Text
}

# Sorts an error text into: tls | dns | missing | ratelimit | offline | unknown.
function Get-ErrorKind([string]$Text) {
    $t = "$Text".ToLowerInvariant()
    if ($t -match 'x509|certificate|tls handshake|tls:|proxyconnect|proxy error|proxy authentication|ssl |ssl_|ssl:|ssl/tls|trust relationship') { return 'tls' }
    if ($t -match 'no such host|name resolution|server misbehaving|could not resolve|name or service not known|nodename nor servname|remote name could not be resolved') { return 'dns' }
    if ($t -match 'manifest unknown|name unknown|denied|unauthorized|not found|error: 404|\(404\)') { return 'missing' }
    if ($t -match 'toomanyrequests|rate limit|too many requests') { return 'ratelimit' }
    if ($t -match 'network is unreachable|i/o timeout|connection refused|connection reset|deadline exceeded|timeout|timed out|dial tcp|no route to host|failed to connect|unable to connect') { return 'offline' }
    return 'unknown'
}

# The value of the first KEY= line that is not a comment, or '' when there is none.
function Get-EnvValue([string]$Path, [string]$Key) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match "^\s*$([regex]::Escape($Key))=(.*)$") {
            $v = $Matches[1].TrimEnd("`r")
            if ($v.Length -ge 2 -and (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'")))) {
                $v = $v.Substring(1, $v.Length - 2)
            }
            return $v
        }
    }
    return ''
}

# Writes text as UTF-8 without a byte order mark and with LF line ends (Docker reads it like that).
function Write-TextFile([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

# Replaces the KEY= line, or adds it at the end. Other lines stay as they are.
function Set-EnvValue([string]$Path, [string]$Key, [string]$Value) {
    $text = ''
    if (Test-Path -LiteralPath $Path) { $text = [System.IO.File]::ReadAllText($Path) }
    $lines = New-Object System.Collections.Generic.List[string]
    if ($text.Length -gt 0) { foreach ($l in ($text -split "`n")) { $lines.Add($l) } }
    if ($lines.Count -gt 0 -and $lines[$lines.Count - 1] -eq '') { $lines.RemoveAt($lines.Count - 1) }
    $done = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if (-not $done -and $lines[$i] -match "^\s*$([regex]::Escape($Key))=") {
            $lines[$i] = "$Key=$Value"
            $done = $true
        }
    }
    if (-not $done) { $lines.Add("$Key=$Value") }
    Write-TextFile $Path (($lines -join "`n") + "`n")
}

function New-RandomPassword([int]$Length = 48) {
    $chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $sb = New-Object System.Text.StringBuilder
    $buf = New-Object byte[] 1
    while ($sb.Length -lt $Length) {
        $rng.GetBytes($buf)
        if ($buf[0] -lt 248) { [void]$sb.Append($chars[$buf[0] % 62]) }   # 248 = 4 x 62: no bias
    }
    return $sb.ToString()
}

# Makes DIR\.env from .env.example with a random database password.
# An existing .env stays as it is; only missing keys are added (and TRELLIS_PORT when it must change).
function Write-EnvFile([string]$Folder, [int]$Port) {
    $f = Join-Path $Folder '.env'
    $created = $false
    if (-not (Test-Path -LiteralPath $f)) {
        $example = Join-Path $Folder '.env.example'
        if (Test-Path -LiteralPath $example) {
            Write-TextFile $f (([System.IO.File]::ReadAllText($example)) -replace "`r`n", "`n")
        } else {
            Write-TextFile $f ''
        }
        $created = $true
    }
    $cur = Get-EnvValue $f 'NEO4J_PASSWORD'
    if (-not $cur -or ($created -and $cur -eq 'change-me')) {
        $script:Neo4jPw = New-RandomPassword 48
        Set-EnvValue $f 'NEO4J_PASSWORD' $script:Neo4jPw
    } else {
        $script:Neo4jPw = $cur
    }
    $curPort = Get-EnvValue $f 'TRELLIS_PORT'
    if ($Port -gt 0 -and $curPort -ne "$Port" -and ($Port -ne $script:DefaultPort -or $curPort)) {
        Set-EnvValue $f 'TRELLIS_PORT' "$Port"
    }
}

function Test-PortInUse([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(700)) { return $false }
        try { $client.EndConnect($iar); return $true } catch { return $false }
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

# The first free port from Start on (tries 20), or 0.
function Select-Port([int]$Start) {
    for ($p = $Start; $p -lt $Start + 20; $p++) {
        if (-not (Test-PortInUse $p)) { return $p }
    }
    return 0
}

# $true when File matches the line for Name in the sums file.
function Test-Sha256([string]$File, [string]$SumsFile, [string]$Name) {
    $want = ''
    foreach ($line in [System.IO.File]::ReadAllLines($SumsFile)) {
        $parts = $line.Trim() -split '\s+', 2
        if ($parts.Count -lt 2) { continue }
        $n = $parts[1].TrimStart('*')
        $n = ($n -split '[\\/]')[-1]
        if ($n -eq $Name) { $want = $parts[0].ToLowerInvariant(); break }
    }
    if (-not $want) { return $false }
    $got = (Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash.ToLowerInvariant()
    return ($got -eq $want)
}

# ---------------------------------------------------------------- system facts (replaced in tests)

function Test-IsWindows {
    if ($PSVersionTable.PSEdition -eq 'Desktop') { return $true }
    return [bool]$IsWindows
}

function Get-OsDescription {
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        return "$($os.Caption) $($os.Version) ($($env:PROCESSOR_ARCHITECTURE))"
    } catch {
        return [System.Environment]::OSVersion.VersionString
    }
}

function Get-DockerDescription {
    if (-not (Test-DockerInstalled)) { return 'not installed' }
    $v = (Invoke-Docker @('--version') -NoRecord).Output
    $c = (Invoke-Docker @('compose', 'version') -NoRecord).Output
    return "$(($v -split "`n")[0]); $(($c -split "`n")[0])"
}

function Get-DockerDesktopExe { Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe' }

function Test-DockerInstalled {
    if (Get-Command docker -ErrorAction SilentlyContinue) { return $true }
    # Installed after this window opened: the window still has the old PATH.
    if ($env:ProgramFiles) {
        $bin = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin'
        if (Test-Path -LiteralPath (Join-Path $bin 'docker.exe')) {
            $env:PATH = "$env:PATH;$bin"
            return $true
        }
    }
    return $false
}

function Start-DockerDesktop {
    $exe = Get-DockerDesktopExe
    if (Test-Path -LiteralPath $exe) { Start-Process -FilePath $exe; return $true }
    return $false
}

function Test-WslReady {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return $false }
    $r = Invoke-Native 'wsl.exe' @('--status')
    return ($r.Code -eq 0)
}

function Get-TotalMemoryBytes {
    try { return [int64](Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).TotalPhysicalMemory } catch { return [int64]0 }
}

function Get-FreeDiskBytes([string]$Path) {
    try {
        $root = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($Path))
        return [int64](New-Object System.IO.DriveInfo($root)).AvailableFreeSpace
    } catch { return [int64]-1 }
}

function Open-Url([string]$Url) {
    if ($env:TRELLIS_SETUP_NO_BROWSER) { return $false }
    try { Start-Process $Url; return $true } catch { return $false }
}

function Copy-ToClipboard([string]$Text) {
    if ($env:TRELLIS_SETUP_NO_CLIPBOARD) { return $false }
    try { Set-Clipboard -Value $Text -ErrorAction Stop; return $true } catch { }
    try {
        if (Get-Command clip.exe -ErrorAction SilentlyContinue) { $Text | clip.exe; return $true }
    } catch { }
    return $false
}

# A full path; a relative one counts from the current PowerShell folder.
function Resolve-FullPath([string]$Path) {
    if ($Path.StartsWith('~')) { $Path = $HOME + $Path.Substring(1) }
    return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Get-StatePath {
    $base = $env:LOCALAPPDATA
    if (-not $base) { $base = Join-Path $HOME '.config' }
    return (Join-Path (Join-Path $base 'Trellis') 'setup-state.json')
}

function Get-State {
    $p = Get-StatePath
    try { if (Test-Path -LiteralPath $p) { return (Get-Content -LiteralPath $p -Raw | ConvertFrom-Json) } } catch { }
    return $null
}

function Save-State([string]$Folder, [bool]$WslRestart = $false) {
    $p = Get-StatePath
    try {
        $null = New-Item -ItemType Directory -Force -Path (Split-Path $p)
        Write-TextFile $p ((@{ dir = $Folder; wslRestart = $WslRestart } | ConvertTo-Json))
    } catch { }
}

# ---------------------------------------------------------------- running commands

function Set-LastRun([string]$Cmd, [string]$Output) {
    $script:LastCmd = $Cmd
    $script:LastOutput = $Output
}

# Runs a program; returns Code and Output (stdout and stderr). -Show prints the output while it runs.
function Invoke-Native([string]$Exe, [string[]]$Arguments, [switch]$Show, [string]$WorkDir = '', [switch]$NoRecord) {
    $lines = New-Object System.Collections.Generic.List[string]
    $code = 0
    if (-not (Get-Command $Exe -ErrorAction SilentlyContinue)) {
        $lines.Add("The program $Exe was not found.")
        $code = 127
        if (-not $NoRecord) { Set-LastRun "$Exe $($Arguments -join ' ')" ($lines -join "`n") }
        return [pscustomobject]@{ Code = $code; Output = ($lines -join "`n") }
    }
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    if ($WorkDir) { Push-Location -LiteralPath $WorkDir }
    try {
        $global:LASTEXITCODE = 0
        & $Exe @Arguments 2>&1 | ForEach-Object {
            $l = "$_"
            $lines.Add($l)
            if ($Show) { Write-Host "    $l" }
        }
        $code = $LASTEXITCODE
    } catch {
        $lines.Add("$($_.Exception.Message)")
        $code = 1
    } finally {
        if ($WorkDir) { Pop-Location }
        $ErrorActionPreference = $eap
    }
    if ($null -eq $code) { $code = 0 }
    $out = $lines -join "`n"
    if (-not $NoRecord) {
        $cmd = "$Exe $($Arguments -join ' ')"
        if ($WorkDir) { $cmd = "$cmd (in $WorkDir)" }
        Set-LastRun $cmd $out
    }
    return [pscustomobject]@{ Code = $code; Output = $out }
}

function Invoke-Docker([string[]]$Arguments, [switch]$Show, [switch]$NoRecord) {
    return (Invoke-Native 'docker' $Arguments -Show:$Show -NoRecord:$NoRecord)
}

# docker compose ... in the Trellis folder.
function Invoke-Compose([string[]]$Arguments, [switch]$Show, [switch]$NoRecord) {
    Push-Location -LiteralPath $script:TrellisDir
    try { $r = Invoke-Docker (@('compose') + $Arguments) -Show:$Show -NoRecord:$NoRecord } finally { Pop-Location }
    if (-not $NoRecord) { $script:LastCmd = "$($script:LastCmd) (in $($script:TrellisDir))" }
    return $r
}

function Get-CurlExe {
    $c = Get-Command curl.exe -CommandType Application -ErrorAction SilentlyContinue
    if (-not $c) { $c = Get-Command curl -CommandType Application -ErrorAction SilentlyContinue }
    if ($c) { return ($c | Select-Object -First 1).Source }
    return ''
}

# ok | empty (connected, no answer) | bad (answered, not ok) | down
function Get-HealthState([int]$Port) {
    $url = "http://127.0.0.1:$Port/api/health"
    $curl = Get-CurlExe
    if ($curl) {
        $r = Invoke-Native $curl @('-sS', '-m', '5', $url) -NoRecord
        if ($r.Code -eq 0 -and $r.Output -match '"ok"\s*:\s*true') { return 'ok' }
        if ($r.Code -eq 52) { return 'empty' }
        if ($r.Code -eq 0) { return 'bad' }
        return 'down'
    }
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        if ($resp.Content -match '"ok"\s*:\s*true') { return 'ok' }
        return 'bad'
    } catch {
        $m = "$($_.Exception.Message) $($_.Exception.InnerException)"
        if ($m -match 'closed unexpectedly|ended prematurely|empty reply') { return 'empty' }
        return 'down'
    }
}

# Downloads Url to File. Returns $true, or $false with the error kept for the help box.
function Save-Download([string]$Url, [string]$File) {
    $script:LastCmd = "download $Url"
    try {
        if ($Url -like 'file://*') {
            Copy-Item -LiteralPath ([Uri]$Url).LocalPath -Destination $File -ErrorAction Stop
        } else {
            $old = $ProgressPreference
            $ProgressPreference = 'SilentlyContinue'   # the progress bar makes 5.1 downloads very slow
            try { Invoke-WebRequest -Uri $Url -OutFile $File -UseBasicParsing -ErrorAction Stop } finally { $ProgressPreference = $old }
        }
        $script:LastOutput = ''
        return $true
    } catch {
        $script:LastOutput = "$($_.Exception.Message) $($_.Exception.InnerException)"
        return $false
    }
}

# ---------------------------------------------------------------- failure: what happened, what to try, AI prompt

function Get-AiPrompt([string]$What) {
    $lines = @("$($script:LastOutput)" -split "`n")
    if ($lines.Count -gt 30) { $lines = $lines[($lines.Count - 30)..($lines.Count - 1)] }
    $tail = ($lines -join "`n").Trim()
    if (-not $tail) { $tail = '(no output)' }
    $cmd = $script:LastCmd
    if (-not $cmd) { $cmd = '(none)' }
    $text = @(
        'I am installing Trellis, a learning app that runs in Docker on my own computer. I use its guided installer (setup.ps1 in PowerShell).'
        "My computer: $(Get-OsDescription). PowerShell $($PSVersionTable.PSVersion)."
        "Docker: $(Get-DockerDescription)."
        "The installer stopped at step $($script:StepNo) of $($script:StepTotal): `"$($script:StepName)`"."
        "The command that failed: $cmd"
        "What the installer says: $What"
        'The last lines of output:'
        '-----'
        $tail
        '-----'
        'I am not a technical person. Help me with this one step. Explain it in simple words.'
    ) -join "`n"
    return (Hide-Secrets $text)
}

function Write-Box([string]$Text) {
    Write-Line ''
    Write-Line '  +--------------------------------------------------------------------+'
    Write-Line '  |  Copy this into ChatGPT, Claude or Copilot:                        |'
    Write-Line '  +--------------------------------------------------------------------+'
    Write-Line $Text
    Write-Line '  +------------------------------- end --------------------------------+'
}

# Stop-Setup "what went wrong (one sentence)" "what to try (lines)" -> prints the help and stops.
function Stop-Setup([string]$What, [string]$Try) {
    Write-Line ''
    Write-Color "  Setup stopped at step $($script:StepNo) of $($script:StepTotal): $($script:StepName)" 'Red'
    Write-Info "What went wrong: $What"
    Write-Line ''
    Write-Info 'What to try:'
    foreach ($l in ($Try -split "`n")) { Write-Line "    $l" }
    $prompt = Get-AiPrompt $What
    Write-Box $prompt
    if (Copy-ToClipboard $prompt) {
        Write-Info 'This text is also on your clipboard. Paste it into the chat.'
    } else {
        Write-Info 'Select the text between the lines, copy it and paste it into the chat.'
    }
    Write-Info 'When it is fixed, run this installer again. It continues where it stopped.'
    throw $script:StopMarker
}

# Explains a download failure (kind from Get-ErrorKind) and stops.
function Stop-Download([string]$Kind) {
    switch ($Kind) {
        'tls' { Stop-Setup 'Your network or a proxy blocks the download.' "On a work or school network, try a home network or a phone hotspot.`nIf your organization uses a proxy, set it in Docker Desktop > Settings > Resources > Proxies.`nThen run the installer again." }
        'dns' { Stop-Setup 'This computer cannot find the download server. It may not be connected to the internet.' "Check that you are online: open https://github.com in your browser.`nThen restart Docker Desktop and run the installer again." }
        'ratelimit' { Stop-Setup 'The download server says there are too many downloads right now.' 'Wait 10 minutes and run the installer again.' }
        'offline' { Stop-Setup 'The download server did not answer in time.' "Check your internet connection, then run the installer again.`nA VPN or firewall can also block it: try without the VPN." }
        default { Stop-Setup 'The download failed.' 'Run the installer again. If it fails again, use the text below with an AI assistant.' }
    }
}

function Get-RerunCommand {
    $p = Join-Path $script:TrellisDir 'setup.ps1'
    return "powershell -ExecutionPolicy Bypass -File `"$p`""
}

# ---------------------------------------------------------------- the steps

function Step-Welcome {
    Start-Step 'Welcome'
    Write-Info 'This installer sets up Trellis on this computer, one step at a time.'
    Write-Line ''
    Write-Info '- It takes about 15 minutes, plus the time to download Docker if you do not have it yet.'
    Write-Info '- Nothing is installed or changed without asking you first.'
    Write-Info '- You do not need your AI key now. You add it in the setup screen in your browser at the end.'
    Write-Info '- If a step goes wrong, the installer tells you what to try. It also gives you a text'
    Write-Info '  to paste into an AI assistant (ChatGPT, Claude or Copilot) that can help with that step.'
    Write-Line ''
    $state = Get-State
    if ($state -and $state.wslRestart) { Write-Info 'Welcome back. The installer continues after the restart.' }
    $null = Wait-Enter 'Press Enter to start, or Ctrl+C to stop.'
}

function Step-Wsl {
    Start-Step 'Windows Subsystem for Linux (WSL 2)'
    if ((Test-DockerInstalled) -and (Invoke-Docker @('info') -NoRecord).Code -eq 0) {
        Write-Ok 'Docker runs, so WSL 2 is ready.'
        return
    }
    if (Test-WslReady) {
        Write-Ok 'WSL 2 is installed.'
        $state = Get-State
        if ($state -and $state.wslRestart) { Save-State "$($state.dir)" $false }
        return
    }
    $state = Get-State
    if ($state -and $state.wslRestart) {
        Write-Note 'WSL 2 was installed, but it does not answer yet.'
        Stop-Setup 'WSL 2 does not work yet, even after the install.' "Restart the computer if you did not do that yet.`nOtherwise open PowerShell as administrator and run:`n  wsl --update`nThen run the installer again."
    }
    Write-Info 'Docker on Windows needs WSL 2. WSL 2 is a part of Windows that runs Linux programs.'
    Write-Info 'Windows installs it for free. It needs administrator rights and a restart of the computer.'
    Write-Info 'The command is:'
    Write-Cmd 'wsl --install --no-distribution'
    if (-not (Read-YesNo 'Install WSL 2 now? Windows asks for permission.' $true)) {
        Stop-Setup 'WSL 2 is not installed, and Docker needs it.' "Open PowerShell as administrator (right-click Start > Terminal (Admin)) and run:`n  wsl --install --no-distribution`nRestart the computer, then run the installer again."
    }
    $script:LastCmd = 'wsl --install --no-distribution (as administrator)'
    $code = 1
    try {
        $p = Start-Process -FilePath 'wsl.exe' -ArgumentList '--install', '--no-distribution' -Verb RunAs -Wait -PassThru
        $code = $p.ExitCode
        if ($code -ne 0) {
            # Older Windows 10 does not know --no-distribution.
            $p = Start-Process -FilePath 'wsl.exe' -ArgumentList '--install' -Verb RunAs -Wait -PassThru
            $code = $p.ExitCode
        }
    } catch {
        $script:LastOutput = "$($_.Exception.Message)"
    }
    if ($code -ne 0) {
        Stop-Setup 'Installing WSL 2 did not work.' "Open PowerShell as administrator (right-click Start > Terminal (Admin)) and run:`n  wsl --install --no-distribution`nRestart the computer, then run the installer again."
    }
    Save-State $script:OptDir $true
    Write-Line ''
    Write-Ok 'WSL 2 is installed. Windows needs a restart to finish it.'
    Write-Info 'Save your work and restart the computer now.'
    Write-Info 'Then run this installer again. It continues where it stopped:'
    Write-Cmd 'powershell -ExecutionPolicy Bypass -File setup.ps1'
    throw 'TRELLIS_SETUP_RESTART'
}

function Step-DockerInstalled {
    Start-Step 'Docker'
    if (-not (Test-DockerInstalled)) {
        Write-Info 'Trellis needs Docker. Docker is a free program that runs Trellis in a sealed box on your computer.'
        $url = 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe'
        if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { $url = 'https://desktop.docker.com/win/main/arm64/Docker%20Desktop%20Installer.exe' }
        Write-Info "1. Download Docker Desktop for Windows: $url"
        Write-Info '2. Open the downloaded file "Docker Desktop Installer.exe". Keep "Use WSL 2" ticked.'
        Write-Info '3. When it is done, open Docker Desktop from the Start menu.'
        Write-Info '   Accept the terms. You can skip the sign-in.'
        if (Read-YesNo 'Start the download in your browser now?' $true) {
            if (-not (Open-Url $url)) { Write-Info "Open it yourself: $url" }
        }
        while (-not (Test-DockerInstalled)) {
            $script:LastCmd = 'Get-Command docker'
            if (-not (Wait-Enter 'Press Enter when Docker is installed (or type q to stop).')) {
                Stop-Setup 'Docker is not installed yet.' "Install Docker Desktop with the steps above:`n  $url`nThen run the installer again."
            }
            if (-not (Test-DockerInstalled)) { Write-Info 'Docker is not found yet. Finish the install, then press Enter again.' }
        }
    }
    $v = (Invoke-Docker @('--version') -NoRecord).Output
    Write-Ok "Docker is installed: $(($v -split "`n")[0])"
    $r = Invoke-Docker @('compose', 'version')
    if ($r.Code -ne 0) {
        Stop-Setup 'Docker Compose, a part of Docker Desktop that Trellis needs, does not work.' 'Update Docker Desktop: open it, then Settings > Software updates. Then run the installer again.'
    }
    Write-Ok "Docker Compose works: $(($r.Output -split "`n")[0])"
}

function Step-DockerRunning {
    Start-Step 'Start Docker'
    if ((Invoke-Docker @('info')).Code -eq 0) { Write-Ok 'Docker is running.'; return }
    Write-Info 'Docker Desktop is not running. The installer starts it now.'
    Write-Info 'If Docker Desktop shows its terms or a sign-in, accept the terms. You can skip the sign-in.'
    if (-not (Start-DockerDesktop)) { Write-Note 'Docker Desktop was not found in Program Files. Start it from the Start menu.' }
    Write-Host '  Waiting for Docker (up to 2 minutes) ' -NoNewline
    for ($i = 0; $i -lt $script:DockerStartTries; $i++) {
        if ((Invoke-Docker @('info')).Code -eq 0) { Write-Line ''; Write-Ok 'Docker is running.'; return }
        Write-Host '.' -NoNewline
        Wait-Tick 2
    }
    Write-Line ''
    Stop-Setup 'Docker did not start within 2 minutes.' "Open Docker Desktop yourself and wait until it says `"Engine running`".`nThen run the installer again."
}

function Step-Folder {
    Start-Step 'Choose a folder'
    $state = Get-State
    if ($script:OptDir) {
        $script:TrellisDir = Resolve-FullPath $script:OptDir
        Write-Info "Trellis goes in this folder (from -Dir): $($script:TrellisDir)"
    } elseif ($PSScriptRoot -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'compose.yaml'))) {
        $script:TrellisDir = $PSScriptRoot
        Write-Info 'You run the installer from a Trellis folder, so Trellis uses this folder:'
        Write-Info $script:TrellisDir
    } else {
        $def = Join-Path $HOME 'Trellis'
        if ($state -and $state.dir -and (Test-Path -LiteralPath (Join-Path "$($state.dir)" 'compose.yaml'))) { $def = "$($state.dir)" }
        $answer = Read-Answer "Trellis goes in this folder: $def`n  Press Enter to accept, or type another folder." $def
        $script:TrellisDir = Resolve-FullPath $answer
        if ((Test-Path -LiteralPath $script:TrellisDir) -and -not (Test-Path -LiteralPath (Join-Path $script:TrellisDir 'compose.yaml')) -and
            @(Get-ChildItem -LiteralPath $script:TrellisDir -Force -ErrorAction SilentlyContinue).Count -gt 0) {
            Write-Note 'This folder already has other files in it. Trellis adds its own files next to them.'
            if (-not (Read-YesNo 'Use this folder anyway?' $true)) {
                Stop-Setup "You chose not to use the folder $($script:TrellisDir)." "Run the installer again and type another folder, or start it like this:`n  powershell -ExecutionPolicy Bypass -File setup.ps1 -Dir `"$HOME\Trellis`""
            }
        }
    }
    $script:TrellisDir = $script:TrellisDir.TrimEnd('\', '/')
    try {
        $null = New-Item -ItemType Directory -Force -Path $script:TrellisDir -ErrorAction Stop
    } catch {
        Set-LastRun "New-Item -ItemType Directory $($script:TrellisDir)" "$($_.Exception.Message)"
        Stop-Setup "The installer cannot make the folder $($script:TrellisDir)." "Choose a folder in your user folder, for example:`n  powershell -ExecutionPolicy Bypass -File setup.ps1 -Dir `"$HOME\Trellis`""
    }
    if ((Test-Path -LiteralPath (Join-Path $script:TrellisDir 'compose.yaml')) -and (Test-Path -LiteralPath (Join-Path $script:TrellisDir 'backend'))) { $script:IsCheckout = $true }
    if (Test-Path -LiteralPath (Join-Path $script:TrellisDir '.env')) { $script:Existing = $true }
    Save-State $script:TrellisDir $false
    if ($script:Existing) { Write-Ok 'Trellis is already set up in this folder. The installer checks it and starts it.' }
    else { Write-Ok "Folder: $($script:TrellisDir)" }
}

# Sets [wsl2] memory=6GB in %UserProfile%\.wslconfig. Only when the file has no memory line yet.
function Set-WslMemory {
    $f = Join-Path $HOME '.wslconfig'
    $text = ''
    if (Test-Path -LiteralPath $f) { $text = [System.IO.File]::ReadAllText($f) }
    if ($text -match '(?im)^\s*memory\s*=') { return $false }
    if ($text -match '(?im)^\s*\[wsl2\]\s*$') {
        $text = $text -replace '(?im)^(\s*\[wsl2\]\s*)$', "`$1`nmemory=6GB"
    } else {
        if ($text.Length -gt 0 -and -not $text.EndsWith("`n")) { $text += "`r`n" }
        $text += "[wsl2]`r`nmemory=6GB`r`n"
    }
    Write-TextFile $f $text
    return $true
}

function Step-Room {
    Start-Step 'Check memory and disk space'
    $r = Invoke-Docker @('info', '--format', '{{.MemTotal}}')
    $mem = [int64]0
    if ($r.Code -eq 0 -and $r.Output -match '(\d+)') { $mem = [int64]$Matches[1] }
    if ($mem -gt 0) {
        $gb = [math]::Round($mem / 1GB, 1)
        if ($mem -lt $script:MinMemBytes) {
            Write-Note "Docker may use $gb GB of memory. Trellis needs at least 6 GB."
            $how = "Docker on Windows gets half of the computer's memory by default. To give it 6 GB:`n" +
                "1. Open Notepad. Type these two lines:`n     [wsl2]`n     memory=6GB`n" +
                "2. Save the file as .wslconfig in your user folder ($HOME), with Save as type: All files.`n" +
                "3. In PowerShell, run:  wsl --shutdown`n" +
                "4. Start Docker Desktop again, then run the installer again.`n" +
                "If Docker Desktop shows Settings > Resources > Memory, set it to 6 GB there instead."
            $total = Get-TotalMemoryBytes
            $wslcfg = Join-Path $HOME '.wslconfig'
            $canFix = ($total -ge 8GB) -and -not ((Test-Path -LiteralPath $wslcfg) -and ([System.IO.File]::ReadAllText($wslcfg) -match '(?im)^\s*memory\s*='))
            if ($canFix -and (Read-YesNo "The installer can give Docker 6 GB for you (it writes $wslcfg and restarts Docker). Do that now?" $true)) {
                if (Set-WslMemory) {
                    $null = Invoke-Native 'wsl.exe' @('--shutdown')
                    $null = Start-DockerDesktop
                    Write-Host '  Waiting for Docker (up to 2 minutes) ' -NoNewline
                    for ($i = 0; $i -lt $script:DockerStartTries; $i++) {
                        Wait-Tick 2
                        if ((Invoke-Docker @('info') -NoRecord).Code -eq 0) { break }
                        Write-Host '.' -NoNewline
                    }
                    Write-Line ''
                    $r = Invoke-Docker @('info', '--format', '{{.MemTotal}}')
                    if ($r.Code -eq 0 -and $r.Output -match '(\d+)') { $mem = [int64]$Matches[1]; $gb = [math]::Round($mem / 1GB, 1) }
                }
            }
            if ($mem -lt $script:MinMemBytes) {
                foreach ($l in ($how -split "`n")) { Write-Line "    $l" }
                if (-not (Read-YesNo 'Continue anyway? Trellis may be slow or stop.' $false)) {
                    Stop-Setup "Docker may use only $gb GB of memory; Trellis needs 6 GB." $how
                }
            } else {
                Write-Ok "Docker may use $gb GB of memory now (6 GB needed)."
            }
        } else {
            Write-Ok "Docker may use $gb GB of memory (6 GB needed)."
        }
    } else {
        Write-Note 'The installer could not read how much memory Docker may use. It continues.'
    }
    $free = Get-FreeDiskBytes $script:TrellisDir
    if ($free -ge 0) {
        $fgb = [math]::Round($free / 1GB, 1)
        if ($free -lt $script:MinDiskBytes) {
            Set-LastRun "free disk space of $($script:TrellisDir)" "$fgb GB free"
            Stop-Setup "There is not enough free disk space: $fgb GB free, Trellis needs 5 GB." "Free up disk space (empty the Recycle Bin, remove large files you do not need),`nor put Trellis on another disk:`n  powershell -ExecutionPolicy Bypass -File setup.ps1 -Dir D:\Trellis"
        }
        Write-Ok "$fgb GB free on the disk of $($script:TrellisDir) (5 GB needed)."
    }
}

function Test-WebRunning {
    if (-not (Test-Path -LiteralPath (Join-Path $script:TrellisDir 'compose.yaml'))) { return $false }
    $r = Invoke-Compose @('ps', '--status', 'running', '--services') -NoRecord
    return ($r.Code -eq 0 -and (($r.Output -split "`n") | ForEach-Object { $_.Trim() }) -contains 'web')
}

function Step-Port {
    Start-Step 'Choose a port'
    $want = $script:DefaultPort
    $v = Get-EnvValue (Join-Path $script:TrellisDir '.env') 'TRELLIS_PORT'
    if ($v -match '^\d+$') { $want = [int]$v }
    if (-not (Test-PortInUse $want)) {
        $script:Port = $want
        Write-Ok "Port $want is free. Trellis will be at http://localhost:$want"
    } elseif ((Test-WebRunning) -or (Get-HealthState $want) -eq 'ok') {
        $script:Port = $want
        Write-Ok "Trellis already uses port $want."
    } else {
        $script:LastCmd = "Select-Port $($want + 1)"
        $script:Port = Select-Port ($want + 1)
        if ($script:Port -eq 0) {
            Stop-Setup "Ports $want to $($want + 20) are all in use by other programs." 'Close programs you do not need, or restart the computer. Then run the installer again.'
        }
        Write-Info "Port $want is in use by another program. Trellis uses port $($script:Port) instead."
        Write-Ok "Trellis will be at http://localhost:$($script:Port)"
    }
}

function Step-DownloadTest {
    Start-Step 'Test the download'
    $tag = Get-EnvValue (Join-Path $script:TrellisDir '.env') 'TRELLIS_VERSION'
    if (-not $tag) { $tag = 'latest' }
    $img = "$($script:ImageRepo)-api:$tag"
    Write-Info 'The installer checks that this computer can download Trellis.'
    $r = Invoke-Docker @('manifest', 'inspect', $img)
    if ($r.Code -eq 0) { Write-Ok 'The download works.'; return }
    $kind = Get-ErrorKind $r.Output
    $haveFiles = Test-Path -LiteralPath (Join-Path $script:TrellisDir 'compose.yaml')
    if ($kind -eq 'missing') {
        if ($script:IsCheckout) {
            $script:Build = $true
            Write-Info 'The ready-made Trellis download is not available yet.'
            Write-Ok 'This folder has the source code. The installer builds Trellis from it (10 to 15 minutes).'
            return
        }
        if ($haveFiles -and (Invoke-Docker @('image', 'inspect', $img) -NoRecord).Code -eq 0) {
            Write-Ok 'Trellis is already on this computer. No download needed.'
            return
        }
        Write-Info 'The ready-made Trellis download is not available yet.'
        Write-Info 'The installer can download the source code instead and build Trellis on this computer.'
        Write-Info 'That takes 10 to 15 minutes, and needs a good internet connection.'
        if (Read-YesNo 'Download the source code and build Trellis?' $true) {
            $script:Build = $true
            $script:GetSource = $true
            $script:IsCheckout = $true
            Write-Ok 'The installer builds Trellis from the source code.'
            return
        }
        Stop-Setup 'The ready-made download is not available, and you chose not to build Trellis.' 'Try again later, or run the installer again and answer y to build from the source code.'
    }
    if ($r.Output -match 'is not a docker command|unknown command|unknown flag') {
        Write-Note 'This Docker cannot run the download test. The installer continues; the download comes later.'
        return
    }
    if ($haveFiles -and (Invoke-Docker @('image', 'inspect', $img) -NoRecord).Code -eq 0) {
        Write-Note 'The download server cannot be reached, but Trellis is already on this computer. The installer continues.'
        return
    }
    Stop-Download $kind
}

# Copies everything in From (hidden files too) into To, file by file: Copy-Item -Recurse puts a
# folder inside the existing one with the same name.
function Copy-Folder([string]$From, [string]$To) {
    $base = (Get-Item -LiteralPath $From -Force).FullName.TrimEnd('\', '/')
    foreach ($item in (Get-ChildItem -LiteralPath $From -Recurse -Force -File)) {
        $dest = Join-Path $To $item.FullName.Substring($base.Length).TrimStart('\', '/')
        $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest)
        Copy-Item -LiteralPath $item.FullName -Destination $dest -Force
    }
}

function Step-Files {
    Start-Step 'Get the Trellis files'
    $d = $script:TrellisDir
    if (Test-Path -LiteralPath (Join-Path $d 'compose.yaml')) {
        Write-Ok "The Trellis files are already in $d"
    } elseif ($script:GetSource) {
        Write-Info 'Downloading the source code...'
        $zip = Join-Path $script:WorkTmp 'source.zip'
        if (-not (Save-Download $script:SourceZipUrl $zip)) { Stop-Download (Get-ErrorKind $script:LastOutput) }
        $src = Join-Path $script:WorkTmp 'src'
        try { Expand-Archive -LiteralPath $zip -DestinationPath $src -Force -ErrorAction Stop } catch {
            Set-LastRun 'Expand-Archive source.zip' "$($_.Exception.Message)"
            Stop-Setup 'The downloaded source code is damaged.' 'Run the installer again. It downloads it again.'
        }
        $top = Get-ChildItem -LiteralPath $src -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'compose.yaml') } | Select-Object -First 1
        if (-not $top) { Stop-Setup 'The downloaded source code does not look like Trellis.' 'Run the installer again.' }
        Copy-Folder $top.FullName $d
        Write-Ok "Source code unpacked in $d"
    } else {
        Write-Info 'Downloading Trellis...'
        $zip = Join-Path $script:WorkTmp 'trellis-bundle.zip'
        $sums = Join-Path $script:WorkTmp 'SHA256SUMS'
        if (-not (Save-Download $script:BundleUrl $zip)) { Stop-Download (Get-ErrorKind $script:LastOutput) }
        if (-not (Save-Download $script:SumsUrl $sums)) { Stop-Download (Get-ErrorKind $script:LastOutput) }
        if (-not (Test-Sha256 $zip $sums 'trellis-bundle.zip')) {
            $want = (Get-Content -LiteralPath $sums | Where-Object { $_ -match 'trellis-bundle.zip' }) -join ' '
            Set-LastRun 'SHA256 check of trellis-bundle.zip against SHA256SUMS' "expected: $want`ngot: $((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant())"
            Stop-Setup 'The downloaded file is damaged or not the real Trellis file (its checksum does not match).' "Run the installer again. If this happens again, do not use that network, and report it:`n  $($script:RepoUrl)/issues"
        }
        Write-Ok 'Download checked (SHA256).'
        $out = Join-Path $script:WorkTmp 'bundle'
        try { Expand-Archive -LiteralPath $zip -DestinationPath $out -Force -ErrorAction Stop } catch {
            Set-LastRun 'Expand-Archive trellis-bundle.zip' "$($_.Exception.Message)"
            Stop-Setup 'The downloaded file could not be unpacked.' 'Run the installer again.'
        }
        if (-not (Test-Path -LiteralPath (Join-Path $out 'trellis\compose.yaml'))) {
            Stop-Setup 'The downloaded file does not look like Trellis.' "Run the installer again, or report it: $($script:RepoUrl)/issues"
        }
        Copy-Folder (Join-Path $out 'trellis') $d
        Write-Ok "Files unpacked in $d"
    }
    if (Test-Path -LiteralPath (Join-Path $d 'backend')) { $script:IsCheckout = $true }
    $hadEnv = Test-Path -LiteralPath (Join-Path $d '.env')
    try {
        Write-EnvFile $d $script:Port
    } catch {
        Set-LastRun "write $d\.env" "$($_.Exception.Message)"
        Stop-Setup "The installer could not write the settings file $d\.env" "Check that you may write in that folder, or choose another one:`n  powershell -ExecutionPolicy Bypass -File setup.ps1 -Dir `"$HOME\Trellis`""
    }
    if ($hadEnv) { Write-Ok 'Settings file .env kept (missing settings added).' }
    else { Write-Ok 'Settings file .env made. It holds a random database password. You never need to type it.' }
}

# Recreates the nginx container: the fix for "containers run, but the address gives an empty reply".
function Repair-Web {
    Write-Info 'Trellis runs, but its front door (web) does not answer. The installer restarts it.'
    $null = Invoke-Compose @('up', '-d', '--no-build', '--force-recreate', 'web') -Show
}

function Step-Start {
    Start-Step 'Start Trellis'
    $s = Get-HealthState $script:Port
    if ($s -eq 'ok') { Write-Ok 'Trellis is already running.'; return }
    if ($s -eq 'empty' -and (Test-WebRunning)) { Repair-Web }
    $r = Invoke-Compose @('config', '-q')
    if ($r.Code -ne 0) {
        Stop-Setup 'The Trellis settings (.env or compose.yaml) have an error.' "Look at the last lines below. A setting in $($script:TrellisDir)\.env may be wrong.`nNever share the values of passwords or keys."
    }
    if ($script:Build) {
        if (-not $script:Existing) {
            Write-Info 'Building Trellis from the source code. The first time takes 10 to 15 minutes.'
            $r = Invoke-Compose @('up', '-d', '--build', '--wait') -Show
        } else {
            Write-Info 'Starting Trellis. Parts that are missing are built first (10 to 15 minutes).'
            $r = Invoke-Compose @('up', '-d', '--wait') -Show
        }
        if ($r.Code -ne 0) { Resolve-StartFailure $r.Output }
    } else {
        if (-not $script:Existing) {
            Write-Info 'Downloading Trellis. This is a large download (1 to 3 GB) and can take a few minutes.'
            $r = Invoke-Compose @('pull') -Show
            if ($r.Code -ne 0) {
                $kind = Get-ErrorKind $r.Output
                if ($kind -ne 'unknown' -and $kind -ne 'missing') { Stop-Download $kind }
                Stop-Setup 'Downloading Trellis failed.' 'Run the installer again. If it fails again, use the text below with an AI assistant.'
            }
        }
        Write-Info 'Starting Trellis. This can take a minute or two.'
        $r = Invoke-Compose @('up', '-d', '--wait') -Show
        if ($r.Code -ne 0) { Resolve-StartFailure $r.Output }
    }
    Wait-Health
}

# up --wait failed: go on when the front door runs (Wait-Health decides), stop otherwise.
function Resolve-StartFailure([string]$Output) {
    $kind = Get-ErrorKind $Output
    if ($kind -eq 'tls' -or $kind -eq 'dns' -or $kind -eq 'ratelimit') { Stop-Download $kind }
    if (Test-WebRunning) { return }
    $cmd = $script:LastCmd
    $ps = (Invoke-Compose @('ps', '-a') -NoRecord).Output
    Set-LastRun $cmd "$Output`n$ps"
    Stop-Setup 'Trellis did not start.' "See what runs, and the messages of the app:`n  cd `"$($script:TrellisDir)`"`n  docker compose ps`n  docker compose logs --tail 50 api`nOr make a full report:  $(Get-RerunCommand) -Report"
}

function Wait-Health {
    $empties = 0
    $repaired = $false
    $s = ''
    Write-Host '  Waiting for Trellis to answer (up to 3 minutes) ' -NoNewline
    for ($i = 0; $i -lt $script:HealthTries; $i++) {
        $s = Get-HealthState $script:Port
        if ($s -eq 'ok') { Write-Line ''; Write-Ok "Trellis answers at http://localhost:$($script:Port)"; return }
        if ($s -eq 'empty') { $empties++ } else { $empties = 0 }
        if ($empties -ge 4 -and -not $repaired -and (Test-WebRunning)) {
            Write-Line ''
            Repair-Web
            $repaired = $true
            $empties = 0
            Write-Host '  Waiting ' -NoNewline
        }
        Write-Host '.' -NoNewline
        Wait-Tick 5
    }
    Write-Line ''
    $ps = (Invoke-Compose @('ps', '-a') -NoRecord).Output
    $logs = (Invoke-Compose @('logs', '--tail', '15', 'web', 'api') -NoRecord).Output
    Set-LastRun "curl http://localhost:$($script:Port)/api/health" "health check result: $s`n$ps`n$logs"
    Stop-Setup "Trellis started, but it does not answer at http://localhost:$($script:Port)" "Wait a minute and run the installer again. It repairs known problems.`nTo see what is wrong:`n  cd `"$($script:TrellisDir)`"`n  docker compose ps`n  $(Get-RerunCommand) -Report"
}

function Step-Done {
    Start-Step 'Open Trellis'
    $url = "http://localhost:$($script:Port)"
    if (Open-Url $url) { Write-Info "Your browser opens $url" } else { Write-Info "Open this address in your browser: $url" }
    Write-Line ''
    Write-Color '  Trellis is ready.' 'Green'
    Write-Info 'In the browser: choose your name and language, add your AI key, and set a password.'
    Write-Line ''
    Write-Info 'Good to know:'
    Write-Info '- Start later: Trellis starts by itself when Docker Desktop runs.'
    Write-Info '  If it does not, run this installer again:'
    Write-Cmd (Get-RerunCommand)
    Write-Info '- Stop Trellis:'
    Write-Cmd "cd `"$($script:TrellisDir)`"; docker compose stop"
    Write-Info "- Backups: every night, in $(Join-Path $script:TrellisDir 'backups')"
    Write-Info '  Copy that folder to another place now and then.'
    Write-Info '- Something wrong? Make a report for a bug report or an AI chat:'
    Write-Cmd "$(Get-RerunCommand) -Report"
}

# ---------------------------------------------------------------- -Report

function Get-ReportDir {
    if ($script:OptDir) { return (Resolve-FullPath $script:OptDir) }
    if ($PSScriptRoot -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'compose.yaml'))) { return $PSScriptRoot }
    $state = Get-State
    if ($state -and $state.dir -and (Test-Path -LiteralPath (Join-Path "$($state.dir)" 'compose.yaml'))) { return "$($state.dir)" }
    return (Join-Path $HOME 'Trellis')
}

function New-Report {
    $script:TrellisDir = Get-ReportDir
    $d = $script:TrellisDir
    $port = Get-EnvValue (Join-Path $d '.env') 'TRELLIS_PORT'
    if (-not $port) { $port = "$($script:DefaultPort)" }
    $sb = New-Object System.Text.StringBuilder
    $add = { param($l) [void]$sb.AppendLine("$l") }
    & $add "Trellis setup report, made $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
    & $add 'Passwords, keys and tokens are replaced by [REDACTED].'
    & $add ''
    & $add '== System'
    & $add "OS: $(Get-OsDescription)"
    & $add "PowerShell: $($PSVersionTable.PSVersion) ($($PSVersionTable.PSEdition))"
    & $add "Docker: $(Get-DockerDescription)"
    $hasDocker = Test-DockerInstalled
    if ($hasDocker) {
        & $add "Docker engine: $((Invoke-Docker @('version', '--format', '{{.Server.Version}}') -NoRecord).Output)"
        $m = (Invoke-Docker @('info', '--format', '{{.MemTotal}}') -NoRecord).Output
        if ($m -match '^\s*(\d+)\s*$') { & $add "Docker memory: $([math]::Round([int64]$Matches[1] / 1GB, 1)) GB" }
        & $add "Docker CPUs: $((Invoke-Docker @('info', '--format', '{{.NCPU}}') -NoRecord).Output)"
    }
    if (Test-IsWindows) {
        $w = Invoke-Native 'wsl.exe' @('--status') -NoRecord
        & $add "WSL status exit code: $($w.Code)"
    }
    & $add ''
    & $add '== Trellis folder'
    & $add "Folder: $d"
    foreach ($f in @('compose.yaml', '.env', '.env.example', 'deploy\nginx.conf', 'backend')) {
        $yn = 'no'
        if (Test-Path -LiteralPath (Join-Path $d $f)) { $yn = 'yes' }
        & $add "  $($f): $yn"
    }
    $envFile = Join-Path $d '.env'
    if (Test-Path -LiteralPath $envFile) {
        $keys = @(Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*[A-Za-z_][A-Za-z0-9_]*=' } | ForEach-Object { ($_ -split '=', 2)[0].Trim() }) -join ' '
        & $add "  .env settings (names only): $keys"
    }
    $free = Get-FreeDiskBytes $d
    if ($free -ge 0) { & $add "Disk free: $([math]::Round($free / 1GB, 1)) GB" }
    & $add "Port: $port"
    if ($hasDocker -and (Test-Path -LiteralPath (Join-Path $d 'compose.yaml'))) {
        & $add ''
        & $add '== docker compose ps'
        & $add (Invoke-Compose @('ps', '-a') -NoRecord).Output
        $services = (Invoke-Compose @('config', '--services') -NoRecord).Output -split "`n" | Where-Object { $_.Trim() }
        foreach ($svc in $services) {
            & $add ''
            & $add "== Last 50 log lines: $($svc.Trim())"
            & $add (Invoke-Compose @('logs', '--no-color', '--tail', '50', $svc.Trim()) -NoRecord).Output
        }
    }
    & $add ''
    & $add "== Health: http://localhost:$port/api/health"
    $curl = Get-CurlExe
    if ($curl) {
        $h = Invoke-Native $curl @('-sS', '-m', '5', "http://127.0.0.1:$port/api/health") -NoRecord
        & $add "$($h.Output) (curl exit code $($h.Code))"
    } else {
        & $add "health state: $(Get-HealthState ([int]$port))"
    }
    $text = Hide-Secrets $sb.ToString()
    Write-Line $text
    $name = "trellis-report-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"
    $dest = Join-Path (Get-Location).Path $name
    if (Test-Path -LiteralPath $d) { $dest = Join-Path $d $name }
    try {
        Write-TextFile $dest $text
        Write-Line ''
        Write-Line "Report saved: $dest"
        Write-Line "Paste it in a bug report ($($script:RepoUrl)/issues) or an AI chat. Secrets are already hidden."
    } catch { }
}

# ---------------------------------------------------------------- main

function Show-Usage {
    Write-Line 'Trellis guided installer (Windows)'
    Write-Line ''
    Write-Line '  powershell -ExecutionPolicy Bypass -File setup.ps1 [options]'
    Write-Line ''
    Write-Line 'Options:'
    Write-Line '  -Yes            Do not ask; take the default answer every time (for scripts and CI).'
    Write-Line '  -Dir FOLDER     Put Trellis in FOLDER (default: your user folder\Trellis, or this folder for a source checkout).'
    Write-Line '  -Report         Print a diagnostic report (secrets hidden) and save it in the Trellis folder.'
    Write-Line '  -Help           Show this help.'
    Write-Line ''
    Write-Line 'Safe to run again: it checks everything, repairs known problems and starts Trellis.'
}

function Main([switch]$Yes, [string]$Dir = '', [switch]$Report, [switch]$Help) {
    if ($Help) { Show-Usage; return }
    $script:OptYes = [bool]$Yes
    $script:OptDir = $Dir
    $script:StepNo = 0
    $script:StepName = 'Start'
    $script:LastCmd = ''
    $script:LastOutput = ''
    $script:TrellisDir = ''
    $script:Port = 0
    $script:IsCheckout = $false
    $script:Existing = $false
    $script:Build = $false
    $script:GetSource = $false
    $script:Neo4jPw = ''
    $script:UseColor = -not $env:NO_COLOR
    try { if ([Console]::IsOutputRedirected) { $script:UseColor = $false } } catch { }
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }
    $script:WorkTmp = Join-Path ([System.IO.Path]::GetTempPath()) ("trellis-setup-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
    $null = New-Item -ItemType Directory -Force -Path $script:WorkTmp
    try {
        if ($Report) { New-Report; return }
        if (-not (Test-IsWindows)) {
            Write-Line 'This installer is for Windows. On Mac and Linux, run setup.sh:'
            Write-Line '  bash setup.sh'
            return
        }
        Write-Line ''
        Write-Color 'Trellis installer' 'White'
        Step-Welcome
        Step-Wsl
        Step-DockerInstalled
        Step-DockerRunning
        Step-Folder
        Step-Room
        Step-Port
        Step-DownloadTest
        Step-Files
        Step-Start
        Step-Done
    } finally {
        Remove-Item -LiteralPath $script:WorkTmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Run Main only when executed (-File, & .\setup.ps1, or irm ... | iex), not when dot-sourced by the tests.
if ($MyInvocation.InvocationName -ne '.') {
    $exitCode = 0
    try {
        Main -Yes:$Yes -Dir $Dir -Report:$Report -Help:$Help
    } catch {
        $msg = "$($_.Exception.Message)"
        if ($msg -eq 'TRELLIS_SETUP_RESTART') {
            $exitCode = 0
        } elseif ($msg -eq $script:StopMarker) {
            $exitCode = 1
        } else {
            # An error the installer did not expect: still give the person something to work with.
            Set-LastRun $script:LastCmd "$msg`n$($_.ScriptStackTrace)"
            Write-Line ''
            Write-Color "  The installer hit an unexpected error at step $($script:StepNo) of $($script:StepTotal): $($script:StepName)" 'Red'
            $prompt = Get-AiPrompt "Unexpected error in the installer: $msg"
            Write-Box $prompt
            if (Copy-ToClipboard $prompt) { Write-Info 'This text is also on your clipboard. Paste it into the chat.' }
            $exitCode = 1
        }
    }
    # Run as a file: set the exit code. Under irm | iex there is no file; keep the window open.
    if ($MyInvocation.MyCommand.Path) { exit $exitCode }
}
