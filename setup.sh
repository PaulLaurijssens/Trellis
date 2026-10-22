#!/usr/bin/env bash
# Trellis guided installer for Mac and Linux.
#
#   bash setup.sh             step by step; asks before it changes anything
#   bash setup.sh --report    a diagnostic report for a bug report or an AI chat
#   bash setup.sh --help      all options
#
# Safe to run again: it checks everything, repairs known problems and starts Trellis.
# Windows: setup.ps1 does the same steps with the same texts. Change both together.
# Works with bash 3.2 (macOS): no associative arrays, no ${x,,}, no mapfile.
# Tests: scripts/test-setup.sh sources this file; main only runs when the file is executed.

REPO_URL="https://github.com/PaulLaurijssens/Trellis"
BUNDLE_URL="${TRELLIS_BUNDLE_URL:-$REPO_URL/releases/latest/download/trellis-bundle.zip}"
SUMS_URL="${TRELLIS_SUMS_URL:-$REPO_URL/releases/latest/download/SHA256SUMS}"
SOURCE_ZIP_URL="${TRELLIS_SOURCE_ZIP_URL:-$REPO_URL/archive/refs/heads/main.zip}"
IMAGE_REPO="ghcr.io/paullaurijssens/trellis"
DEFAULT_PORT=8080
MIN_MEM_BYTES=5905580032          # 5.5 GiB: Docker set to 6 GB reports a little less than 6
MIN_DISK_KB=5242880               # 5 GB
DOCKER_START_TRIES="${TRELLIS_SETUP_DOCKER_TRIES:-60}"   # x 2 s = 2 minutes
HEALTH_TRIES="${TRELLIS_SETUP_HEALTH_TRIES:-36}"         # x 5 s = 3 minutes
TICK="${TRELLIS_SETUP_TICK:-}"    # tests: seconds per wait instead of the normal 2 or 5
OS_RELEASE="${TRELLIS_SETUP_OS_RELEASE:-/etc/os-release}"

OPT_YES=0
OPT_DIR=""
OPT_REPORT=0
STEP_NO=0
STEP_TOTAL=10
STEP_NAME="Start"
LAST_CMD=""
LAST_LOG=""
WORK_TMP=""
TTY_IN=0
OS=""
SCRIPT_DIR=""
TRELLIS_DIR=""
PORT=""
IS_CHECKOUT=0      # the folder has the source code (compose.yaml + backend/), so it can build
EXISTING=0         # the folder already had an .env when the installer started
BUILD=0            # build the images here instead of downloading them
GET_SOURCE=0       # download the source zip instead of the release bundle
NEO4J_PW=""
ANSWER=""
B="" G="" Y="" R="" C="" N=""

# ---------------------------------------------------------------- output

setup_colors() {
  if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != "dumb" ]; then
    B=$'\033[1m' G=$'\033[32m' Y=$'\033[33m' R=$'\033[31m' C=$'\033[36m' N=$'\033[0m'
  fi
}

say()  { printf '%s\n' "$*"; }
info() { printf '  %s\n' "$*"; }
ok()   { printf '  %sOK%s  %s\n' "$G" "$N" "$*"; }
warn() { printf '  %sNote:%s %s\n' "$Y" "$N" "$*"; }
cmd()  { printf '      %s%s%s\n' "$C" "$*" "$N"; }

step() {
  STEP_NO=$((STEP_NO + 1))
  STEP_NAME="$1"
  printf '\n%sStep %d of %d: %s%s\n' "$B" "$STEP_NO" "$STEP_TOTAL" "$1" "$N"
}

have() { command -v "$1" >/dev/null 2>&1; }

nap() { sleep "${TICK:-$1}"; }

# ---------------------------------------------------------------- questions

read_answer() {
  if [ "$TTY_IN" = 1 ]; then IFS= read -r "$1" <&3; else IFS= read -r "$1"; fi
}

# ask_yes_no "question" y|n  -> 0 for yes. With --yes it takes the default.
ask_yes_no() {
  local q="$1" def="${2:-y}" hint="[Y/n]" a=""
  [ "$def" = "n" ] && hint="[y/N]"
  if [ "$OPT_YES" = 1 ]; then
    printf '  %s %s %s\n' "$q" "$hint" "$def (--yes)"
    [ "$def" = "y" ]
    return
  fi
  while :; do
    printf '  %s %s ' "$q" "$hint"
    read_answer a || a=""
    case "$a" in
      "") [ "$def" = "y" ]; return ;;
      [Yy]*) return 0 ;;
      [Nn]*) return 1 ;;
    esac
    info "Please type y for yes or n for no."
  done
}

# ask_input "question" "default" -> sets ANSWER. With --yes it takes the default.
ask_input() {
  local a=""
  if [ "$OPT_YES" = 1 ]; then ANSWER="$2"; return; fi
  printf '  %s\n  > ' "$1"
  read_answer a || a=""
  if [ -z "$a" ]; then ANSWER="$2"; else ANSWER="$a"; fi
}

# wait_enter "message" -> 1 with --yes (nobody to wait for) or when the person types q.
wait_enter() {
  local a=""
  [ "$OPT_YES" = 1 ] && return 1
  printf '  %s ' "$1"
  read_answer a || return 1
  case "$a" in [Qq]*) return 1 ;; esac
  return 0
}

# ---------------------------------------------------------------- pure helpers (tested)

# Reads text on stdin and hides secrets: the database password, API keys, tokens, long hex.
redact() {
  local secret="${NEO4J_PW:-}" name
  if [ -z "$secret" ] && [ -n "$TRELLIS_DIR" ]; then secret="$(env_get "$TRELLIS_DIR/.env" NEO4J_PASSWORD 2>/dev/null)"; fi
  name='[A-Za-z0-9_.-]*([Kk][Ee][Yy]|[Pp][Aa][Ss][Ss][Ww]([Oo][Rr])?[Dd]|[Tt][Oo][Kk][Ee][Nn]|[Ss][Ee][Cc][Rr][Ee][Tt])[A-Za-z0-9_.-]*'
  S="$secret" awk 'BEGIN { s = ENVIRON["S"] }
    {
      if (length(s) >= 6) {
        out = ""; line = $0
        while ((i = index(line, s)) > 0) { out = out substr(line, 1, i - 1) "[REDACTED]"; line = substr(line, i + length(s)) }
        $0 = out line
      }
      print
    }' |
  sed -E \
    -e 's/sk-[A-Za-z0-9_-]{8,}/sk-[REDACTED]/g' \
    -e 's/AIza[0-9A-Za-z_-]{20,}/AIza[REDACTED]/g' \
    -e 's/([Bb][Ee][Aa][Rr][Ee][Rr])[[:space:]]+[^[:space:]"]+/\1 [REDACTED]/g' \
    -e "s/(${name})([\"']?[[:space:]]*[:=][[:space:]]*[\"']?)[^[:space:]\"',;}]+/\\1\\4[REDACTED]/g" \
    -e 's/[0-9A-Fa-f]{32,}/[REDACTED-HEX]/g' \
    -e 's/[A-Za-z0-9_-]{40,}/[REDACTED]/g'
}

# Sorts an error text (stdin) into: tls | dns | missing | ratelimit | offline | unknown.
classify_error() {
  local t
  t="$(tr '[:upper:]' '[:lower:]')"
  case "$t" in
    *x509*|*certificate*|*"tls handshake"*|*"tls:"*|*proxyconnect*|*"proxy error"*|*"proxy authentication"*|*"ssl "*|*"ssl_"*|*"ssl:"*)
      echo tls ;;
    *"no such host"*|*"name resolution"*|*"server misbehaving"*|*"could not resolve"*|*"name or service not known"*|*"nodename nor servname"*)
      echo dns ;;
    *"manifest unknown"*|*"name unknown"*|*denied*|*unauthorized*|*"not found"*|*"error: 404"*)
      echo missing ;;
    *toomanyrequests*|*"rate limit"*|*"too many requests"*)
      echo ratelimit ;;
    *"network is unreachable"*|*"i/o timeout"*|*"connection refused"*|*"connection reset"*|*"deadline exceeded"*|*timeout*|*"timed out"*|*"dial tcp"*|*"no route to host"*|*"failed to connect"*)
      echo offline ;;
    *) echo unknown ;;
  esac
}

# env_get FILE KEY -> the value of the first KEY= line that is not a comment.
env_get() {
  local line
  [ -f "$1" ] || return 1
  line="$(grep -E "^[[:space:]]*$2=" "$1" 2>/dev/null | head -n 1)"
  [ -n "$line" ] || return 1
  line="${line#*=}"
  line="${line%$'\r'}"
  case "$line" in
    \"*\") line="${line#\"}"; line="${line%\"}" ;;
    \'*\') line="${line#\'}"; line="${line%\'}" ;;
  esac
  printf '%s' "$line"
}

# env_set FILE KEY VALUE -> replaces the KEY= line, or adds it at the end. Other lines stay as they are.
env_set() {
  local f="$1" tmp="$1.tmp.$$"
  if grep -qE "^[[:space:]]*$2=" "$f" 2>/dev/null; then
    K="$2" V="$3" awk 'BEGIN { k = ENVIRON["K"]; v = ENVIRON["V"]; done = 0 }
      { if (!done && $0 ~ ("^[ \t]*" k "=")) { print k "=" v; done = 1 } else print }' "$f" >"$tmp" &&
      cat "$tmp" >"$f" && rm -f "$tmp"
  else
    if [ -s "$f" ] && [ -n "$(tail -c 1 "$f")" ]; then printf '\n' >>"$f"; fi
    printf '%s=%s\n' "$2" "$3" >>"$f"
  fi
}

random_password() {
  local pw
  pw="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c 48)"
  if [ "${#pw}" -lt 40 ] && have openssl; then pw="$(openssl rand -hex 24)"; fi
  printf '%s' "$pw"
}

# write_env DIR PORT -> makes DIR/.env from .env.example with a random database password.
# An existing .env stays as it is; only missing keys are added (and TRELLIS_PORT when it must change).
write_env() {
  local dir="$1" port="$2" f="$1/.env" created=0 cur
  if [ ! -f "$f" ]; then
    if [ -f "$dir/.env.example" ]; then cp "$dir/.env.example" "$f" || return 1; else : >"$f" || return 1; fi
    created=1
  fi
  cur="$(env_get "$f" NEO4J_PASSWORD)"
  if [ -z "$cur" ] || { [ "$created" = 1 ] && [ "$cur" = "change-me" ]; }; then
    NEO4J_PW="$(random_password)"
    [ "${#NEO4J_PW}" -ge 40 ] || return 1
    env_set "$f" NEO4J_PASSWORD "$NEO4J_PW"
  else
    NEO4J_PW="$cur"
  fi
  cur="$(env_get "$f" TRELLIS_PORT)"
  if [ -n "$port" ] && [ "$cur" != "$port" ] && { [ "$port" != "$DEFAULT_PORT" ] || [ -n "$cur" ]; }; then
    env_set "$f" TRELLIS_PORT "$port"
  fi
  chmod 600 "$f" 2>/dev/null
  return 0
}

port_in_use() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# pick_port START -> the first free port from START on (tries 20).
pick_port() {
  local p="$1" i=0
  while [ "$i" -lt 20 ]; do
    if ! port_in_use "$p"; then echo "$p"; return 0; fi
    p=$((p + 1)); i=$((i + 1))
  done
  return 1
}

sha256_of() {
  if have sha256sum; then sha256sum "$1" | awk '{ print $1 }'
  elif have shasum; then shasum -a 256 "$1" | awk '{ print $1 }'
  else openssl dgst -sha256 "$1" | awk '{ print $NF }'
  fi
}

# verify_sha256 FILE SUMSFILE NAME -> 0 when FILE matches the line for NAME (2: NAME is not listed).
verify_sha256() {
  local want got
  want="$(N="$3" awk '{ f = $2; sub(/\r$/, "", f); sub(/^\*/, "", f); sub(/^.*\//, "", f)
                        if (f == ENVIRON["N"]) { print tolower($1); exit } }' "$2" 2>/dev/null)"
  [ -n "$want" ] || return 2
  got="$(sha256_of "$1" | tr 'A-F' 'a-f')"
  [ "$got" = "$want" ]
}

# ---------------------------------------------------------------- system facts

detect_os() {
  case "$(uname -s 2>/dev/null)" in
    Darwin) OS=mac ;;
    Linux) OS=linux ;;
    *) OS=other ;;
  esac
}

is_apple_chip() {
  [ "$(uname -m)" = "arm64" ] && return 0
  [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]   # an Intel shell under Rosetta still says x86_64
}

is_wsl() { grep -qi microsoft /proc/version 2>/dev/null; }

os_field() { sed -n "s/^$1=//p" "$OS_RELEASE" 2>/dev/null | head -n 1 | tr -d '"'; }

os_description() {
  case "$OS" in
    mac)
      local chip="Intel"
      is_apple_chip && chip="Apple chip"
      printf 'macOS %s (%s)' "$(sw_vers -productVersion 2>/dev/null)" "$chip" ;;
    linux)
      local name
      name="$(os_field PRETTY_NAME)"
      [ -n "$name" ] || name="Linux"
      printf '%s (%s)' "$name" "$(uname -m)"
      is_wsl && printf ', inside WSL on Windows'
      ;;
    *) uname -sr ;;
  esac
}

docker_description() {
  if have docker; then
    printf '%s; %s' "$(docker --version 2>/dev/null | head -n 1)" "$(docker compose version 2>/dev/null | head -n 1)"
  else
    printf 'not installed'
  fi
}

linux_docker_url() {
  local id like
  id="$(os_field ID)"
  like="$(os_field ID_LIKE)"
  case "$id" in
    ubuntu|debian|fedora|centos|rhel|sles) echo "https://docs.docker.com/engine/install/$id/"; return ;;
    raspbian) echo "https://docs.docker.com/engine/install/raspberry-pi-os/"; return ;;
  esac
  case "$like" in
    *ubuntu*) echo "https://docs.docker.com/engine/install/ubuntu/" ;;
    *debian*) echo "https://docs.docker.com/engine/install/debian/" ;;
    *rhel*|*fedora*|*centos*) echo "https://docs.docker.com/engine/install/fedora/" ;;
    *) echo "https://docs.docker.com/engine/install/" ;;
  esac
}

open_url() {
  [ -n "${TRELLIS_SETUP_NO_BROWSER:-}" ] && return 1
  if [ "$OS" = "mac" ] && have open; then open "$1" >/dev/null 2>&1 && return 0; fi
  if have xdg-open; then (xdg-open "$1" >/dev/null 2>&1 &) && return 0; fi
  if is_wsl && have cmd.exe; then cmd.exe /c start "" "$1" >/dev/null 2>&1 && return 0; fi
  return 1
}

copy_to_clipboard() {
  [ -n "${TRELLIS_SETUP_NO_CLIPBOARD:-}" ] && return 1
  if have pbcopy; then printf '%s\n' "$1" | pbcopy 2>/dev/null
  elif [ -n "${WAYLAND_DISPLAY:-}" ] && have wl-copy; then printf '%s\n' "$1" | wl-copy 2>/dev/null
  elif [ -n "${DISPLAY:-}" ] && have xclip; then printf '%s\n' "$1" | xclip -selection clipboard 2>/dev/null
  elif [ -n "${DISPLAY:-}" ] && have xsel; then printf '%s\n' "$1" | xsel --clipboard --input 2>/dev/null
  elif have clip.exe; then printf '%s\n' "$1" | clip.exe 2>/dev/null
  else return 1
  fi
}

state_file() { printf '%s/trellis/setup-state' "${XDG_CONFIG_HOME:-$HOME/.config}"; }

save_state() {
  local f
  f="$(state_file)"
  mkdir -p "$(dirname "$f")" 2>/dev/null && printf 'dir=%s\n' "$TRELLIS_DIR" >"$f" 2>/dev/null
}

saved_dir() { sed -n 's/^dir=//p' "$(state_file)" 2>/dev/null | head -n 1; }

# ---------------------------------------------------------------- running commands

set_last_cmd() {
  LAST_CMD="$*"
  [ "$1" = "compose" ] && LAST_CMD="docker $* (in $TRELLIS_DIR)"
}

# run_quiet CMD... -> runs it, keeps its output for the help box.
run_quiet() {
  set_last_cmd "$@"
  "$@" >"$LAST_LOG" 2>&1
}

# run_shown CMD... -> runs it, shows its output indented, and keeps it for the help box.
run_shown() {
  set_last_cmd "$@"
  "$@" 2>&1 | tee "$LAST_LOG" | sed 's/^/    /'
  return "${PIPESTATUS[0]}"
}

compose() { (cd "$TRELLIS_DIR" && docker compose "$@"); }

# ---------------------------------------------------------------- failure: what happened, what to try, AI prompt

ai_prompt() {
  local what="$1" lines
  lines="$(tail -n 30 "$LAST_LOG" 2>/dev/null)"
  [ -n "$lines" ] || lines="(no output)"
  {
    say "I am installing Trellis, a learning app that runs in Docker on my own computer. I use its guided installer (setup.sh)."
    say "My computer: $(os_description)."
    say "Docker: $(docker_description)."
    say "The installer stopped at step $STEP_NO of $STEP_TOTAL: \"$STEP_NAME\"."
    say "The command that failed: ${LAST_CMD:-(none)}"
    say "What the installer says: $what"
    say "The last lines of output:"
    say "-----"
    say "$lines"
    say "-----"
    say "I am not a technical person. Help me with this one step. Explain it in simple words."
  } | redact
}

print_box() {
  say ""
  say "  +--------------------------------------------------------------------+"
  say "  |  Copy this into ChatGPT, Claude or Copilot:                        |"
  say "  +--------------------------------------------------------------------+"
  say "$1"
  say "  +------------------------------- end --------------------------------+"
}

# fail "what went wrong (one sentence)" "what to try (lines)" -> prints the help and stops.
fail() {
  local what="$1" try="$2" prompt
  printf '\n  %s%sSetup stopped at step %d of %d: %s%s\n' "$R" "$B" "$STEP_NO" "$STEP_TOTAL" "$STEP_NAME" "$N"
  info "What went wrong: $what"
  say ""
  info "What to try:"
  printf '%s\n' "$try" | sed 's/^/    /'
  prompt="$(ai_prompt "$what")"
  print_box "$prompt"
  if copy_to_clipboard "$prompt"; then
    info "This text is also on your clipboard. Paste it into the chat."
  else
    info "Select the text between the lines, copy it and paste it into the chat."
  fi
  info "When it is fixed, run this installer again. It continues where it stopped."
  exit 1
}

# Explains a download failure (kind from classify_error) and stops.
fail_download() {
  case "$1" in
    tls) fail "Your network or a proxy blocks the download." \
"On a work or school network, try a home network or a phone hotspot.
If your organization uses a proxy, set it in Docker Desktop > Settings > Resources > Proxies.
Then run the installer again." ;;
    dns) fail "This computer cannot find the download server. It may not be connected to the internet." \
"Check that you are online: open https://github.com in your browser.
Then restart Docker Desktop and run the installer again." ;;
    ratelimit) fail "The download server says there are too many downloads right now." \
"Wait 10 minutes and run the installer again." ;;
    offline) fail "The download server did not answer in time." \
"Check your internet connection, then run the installer again.
A VPN or firewall can also block it: try without the VPN." ;;
    *) fail "The download failed." \
"Run the installer again. If it fails again, use the text below with an AI assistant." ;;
  esac
}

# ---------------------------------------------------------------- the steps

step_welcome() {
  step "Welcome"
  info "This installer sets up Trellis on this computer, one step at a time."
  say ""
  info "- It takes about 15 minutes, plus the time to download Docker if you do not have it yet."
  info "- Nothing is installed or changed without asking you first."
  info "- You do not need your AI key now. You add it in the setup screen in your browser at the end."
  info "- If a step goes wrong, the installer tells you what to try. It also gives you a text"
  info "  to paste into an AI assistant (ChatGPT, Claude or Copilot) that can help with that step."
  say ""
  wait_enter "Press Enter to start, or Ctrl+C to stop." || true
}

step_docker_installed() {
  step "Docker"
  if [ "$OS" = "mac" ] && ! have docker && [ -x "/Applications/Docker.app/Contents/Resources/bin/docker" ]; then
    PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"   # installed, but never opened yet
  fi
  if ! have docker; then
    local url
    info "Trellis needs Docker. Docker is a free program that runs Trellis in a sealed box on your computer."
    if [ "$OS" = "mac" ]; then
      if is_apple_chip; then
        url="https://desktop.docker.com/mac/main/arm64/Docker.dmg"
        info "Your Mac has an Apple chip. You need Docker Desktop for Mac with Apple chip."
      else
        url="https://desktop.docker.com/mac/main/amd64/Docker.dmg"
        info "Your Mac has an Intel chip. You need Docker Desktop for Mac with Intel chip."
      fi
      info "1. Download it: $url"
      info "2. Open the downloaded file Docker.dmg and drag Docker to Applications."
      info "3. Open Docker from Applications. Accept the terms. You can skip the sign-in."
    elif is_wsl; then
      url="https://docs.docker.com/desktop/setup/install/windows-install/"
      info "You run Linux inside Windows (WSL). Install Docker Desktop for Windows,"
      info "and turn on Settings > Resources > WSL integration. Or run setup.ps1 in PowerShell."
      info "Instructions: $url"
    else
      url="$(linux_docker_url)"
      info "Follow the official instructions for your Linux: $url"
      info "Use the part \"Install using the apt repository\" (or the one for your system)."
      info "Then let your user run Docker, and log out and in again:"
      cmd "sudo usermod -aG docker \$USER"
    fi
    if ask_yes_no "Open this page in your browser now?" y; then open_url "$url" || info "Open it yourself: $url"; fi
    while ! have docker; do
      if [ "$OS" = "mac" ] && [ -x "/Applications/Docker.app/Contents/Resources/bin/docker" ]; then
        PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"
        break
      fi
      LAST_CMD="command -v docker"
      wait_enter "Press Enter when Docker is installed (or type q to stop)." ||
        fail "Docker is not installed yet." "Install Docker with the steps above: $url
Then run the installer again."
      hash -r
      have docker || info "Docker is not found yet. Finish the install, then press Enter again."
    done
  fi
  ok "Docker is installed: $(docker --version 2>/dev/null | head -n 1)"

  if ! run_quiet docker compose version; then
    if [ "$OS" = "linux" ]; then
      fail "Docker Compose, a part of Docker that Trellis needs, is missing." \
"Install it (Ubuntu or Debian):
  sudo apt-get install docker-compose-plugin
Other systems: https://docs.docker.com/compose/install/linux/"
    fi
    fail "Docker Compose, a part of Docker Desktop that Trellis needs, does not work." \
"Update Docker Desktop: open it, then Settings > Software updates. Then run the installer again."
  fi
  ok "Docker Compose works: $(head -n 1 "$LAST_LOG")"
  for t in curl unzip; do
    have "$t" && continue
    LAST_CMD="command -v $t"
    fail "The program $t is missing. The installer needs it to download Trellis." \
"Install it (Ubuntu or Debian):
  sudo apt-get install curl unzip
Then run the installer again."
  done
}

docker_desktop_linux() { have systemctl && systemctl --user cat docker-desktop.service >/dev/null 2>&1; }

step_docker_running() {
  step "Start Docker"
  if run_quiet docker info; then ok "Docker is running."; return; fi
  if [ "$OS" = "linux" ] && grep -qi "permission denied" "$LAST_LOG"; then
    fail "Docker runs, but your user may not use it yet." \
"Give your user access, then log out and log in again (or restart the computer):
  sudo usermod -aG docker \$USER
Then run the installer again."
  fi
  if [ "$OS" = "mac" ]; then
    info "Docker Desktop is not running. The installer starts it now."
    info "If Docker Desktop shows its terms or a sign-in, accept the terms. You can skip the sign-in."
    open -a Docker >/dev/null 2>&1 || true
  elif docker_desktop_linux; then
    info "Docker Desktop is not running. The installer starts it now."
    systemctl --user start docker-desktop >/dev/null 2>&1 || true
  else
    info "Docker is not running. It starts with this command:"
    cmd "sudo systemctl start docker"
    if ask_yes_no "Start Docker now? It may ask for your computer password." y; then
      if [ "$OPT_YES" = 1 ]; then sudo -n systemctl start docker >/dev/null 2>&1 || true
      else sudo systemctl start docker || true
      fi
    fi
  fi
  printf '  Waiting for Docker (up to 2 minutes) '
  local i=0
  while [ "$i" -lt "$DOCKER_START_TRIES" ]; do
    if run_quiet docker info; then printf '\n'; ok "Docker is running."; return; fi
    printf '.'
    nap 2
    i=$((i + 1))
  done
  printf '\n'
  if [ "$OS" = "linux" ] && ! docker_desktop_linux; then
    fail "Docker did not start within 2 minutes." \
"Start it yourself and check that it runs:
  sudo systemctl start docker
  docker info
Then run the installer again."
  fi
  fail "Docker did not start within 2 minutes." \
"Open Docker Desktop yourself and wait until it says \"Engine running\".
Then run the installer again."
}

# Makes a path absolute and expands a leading ~.
abs_path() {
  local d="$1"
  # shellcheck disable=SC2088  # a literal ~ typed by the person
  case "$d" in
    "~") d="$HOME" ;;
    "~/"*) d="$HOME/${d#\~/}" ;;
  esac
  case "$d" in /*) ;; *) d="$PWD/$d" ;; esac
  printf '%s' "${d%/}"
}

step_folder() {
  step "Choose a folder"
  local saved
  saved="$(saved_dir)"
  if [ -n "$OPT_DIR" ]; then
    TRELLIS_DIR="$(abs_path "$OPT_DIR")"
    info "Trellis goes in this folder (from --dir): $TRELLIS_DIR"
  elif [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/compose.yaml" ]; then
    TRELLIS_DIR="$SCRIPT_DIR"
    info "You run the installer from a Trellis folder, so Trellis uses this folder:"
    info "$TRELLIS_DIR"
  else
    local def="$HOME/Trellis"
    if [ -n "$saved" ] && [ -f "$saved/compose.yaml" ]; then def="$saved"; fi
    ask_input "Trellis goes in this folder: $def
  Press Enter to accept, or type another folder." "$def"
    TRELLIS_DIR="$(abs_path "$ANSWER")"
    if [ -d "$TRELLIS_DIR" ] && [ ! -f "$TRELLIS_DIR/compose.yaml" ] && [ -n "$(ls -A "$TRELLIS_DIR" 2>/dev/null)" ]; then
      warn "This folder already has other files in it. Trellis adds its own files next to them."
      ask_yes_no "Use this folder anyway?" y || fail "You chose not to use the folder $TRELLIS_DIR." \
"Run the installer again and type another folder, or start it like this:
  bash setup.sh --dir ~/Trellis"
    fi
  fi
  LAST_CMD="mkdir -p $TRELLIS_DIR"
  mkdir -p "$TRELLIS_DIR" 2>"$LAST_LOG" ||
    fail "The installer cannot make the folder $TRELLIS_DIR." \
"Choose a folder in your home folder, for example:
  bash setup.sh --dir ~/Trellis"
  [ -f "$TRELLIS_DIR/compose.yaml" ] && [ -d "$TRELLIS_DIR/backend" ] && IS_CHECKOUT=1
  [ -f "$TRELLIS_DIR/.env" ] && EXISTING=1
  save_state
  if [ "$EXISTING" = 1 ]; then ok "Trellis is already set up in this folder. The installer checks it and starts it."
  else ok "Folder: $TRELLIS_DIR"
  fi
}

step_room() {
  step "Check memory and disk space"
  local mem gb kb free
  mem=""
  run_quiet docker info --format '{{.MemTotal}}' && mem="$(tr -dc '0-9' <"$LAST_LOG")"
  if [ -n "$mem" ]; then
    gb="$(awk -v m="$mem" 'BEGIN { printf "%.1f", m / 1073741824 }')"
    if [ "$mem" -lt "$MIN_MEM_BYTES" ]; then
      warn "Docker may use $gb GB of memory. Trellis needs at least 6 GB."
      local how
      if [ "$OS" = "mac" ] || docker_desktop_linux; then
        how="Open Docker Desktop. Click the gear icon (Settings), then Resources.
Set Memory limit to 6 GB or more. Click Apply & restart.
Then run the installer again."
      else
        how="Docker may use all the memory of this computer: $gb GB.
Close other programs, or use a computer with 8 GB of memory or more."
      fi
      printf '%s\n' "$how" | sed 's/^/    /'
      ask_yes_no "Continue anyway? Trellis may be slow or stop." n ||
        fail "Docker may use only $gb GB of memory; Trellis needs 6 GB." "$how"
    else
      ok "Docker may use $gb GB of memory (6 GB needed)."
    fi
  else
    warn "The installer could not read how much memory Docker may use. It continues."
  fi
  kb="$(df -Pk "$TRELLIS_DIR" 2>/dev/null | awk 'NR == 2 { print $4 }')"
  if [ -n "$kb" ]; then
    free="$(awk -v k="$kb" 'BEGIN { printf "%.1f", k / 1048576 }')"
    if [ "$kb" -lt "$MIN_DISK_KB" ]; then
      LAST_CMD="df -Pk $TRELLIS_DIR"
      df -Pk "$TRELLIS_DIR" >"$LAST_LOG" 2>&1
      fail "There is not enough free disk space: $free GB free, Trellis needs 5 GB." \
"Free up disk space (empty the trash, remove large files you do not need),
or put Trellis on another disk:
  bash setup.sh --dir /path/to/another/disk/Trellis"
    fi
    ok "$free GB free on the disk of $TRELLIS_DIR (5 GB needed)."
  fi
}

web_running() {
  [ -f "$TRELLIS_DIR/compose.yaml" ] || return 1
  compose ps --status running --services 2>/dev/null | grep -qx web
}

# health_probe PORT -> ok | empty (connected, no answer) | bad (answered, not ok) | down
health_probe() {
  local body rc
  body="$(curl -sS -m 5 "http://127.0.0.1:$1/api/health" 2>&1)"
  rc=$?
  if [ "$rc" -eq 0 ] && printf '%s' "$body" | grep -Eq '"ok"[[:space:]]*:[[:space:]]*true'; then echo ok
  elif [ "$rc" -eq 52 ]; then echo empty
  elif [ "$rc" -eq 0 ]; then echo bad
  else echo down
  fi
}

step_port() {
  step "Choose a port"
  local want
  want="$(env_get "$TRELLIS_DIR/.env" TRELLIS_PORT)"
  [ -n "$want" ] || want="$DEFAULT_PORT"
  if ! port_in_use "$want"; then
    PORT="$want"
    ok "Port $PORT is free. Trellis will be at http://localhost:$PORT"
  elif web_running || [ "$(health_probe "$want")" = "ok" ]; then
    PORT="$want"
    ok "Trellis already uses port $PORT."
  else
    LAST_CMD="pick_port $((want + 1))"
    PORT="$(pick_port $((want + 1)))" ||
      fail "Ports $want to $((want + 20)) are all in use by other programs." \
"Close programs you do not need, or restart the computer. Then run the installer again."
    info "Port $want is in use by another program. Trellis uses port $PORT instead."
    ok "Trellis will be at http://localhost:$PORT"
  fi
}

step_download_test() {
  step "Test the download"
  local tag img kind
  tag="$(env_get "$TRELLIS_DIR/.env" TRELLIS_VERSION)"
  [ -n "$tag" ] || tag="latest"
  img="$IMAGE_REPO-api:$tag"
  info "The installer checks that this computer can download Trellis."
  if run_quiet docker manifest inspect "$img"; then
    ok "The download works."
    return
  fi
  kind="$(classify_error <"$LAST_LOG")"
  if [ "$kind" = "missing" ]; then
    if [ "$IS_CHECKOUT" = 1 ]; then
      BUILD=1
      info "The ready-made Trellis download is not available yet."
      ok "This folder has the source code. The installer builds Trellis from it (10 to 15 minutes)."
      return
    fi
    if [ -f "$TRELLIS_DIR/compose.yaml" ] && docker image inspect "$img" >/dev/null 2>&1; then
      ok "Trellis is already on this computer. No download needed."
      return
    fi
    info "The ready-made Trellis download is not available yet."
    info "The installer can download the source code instead and build Trellis on this computer."
    info "That takes 10 to 15 minutes, and needs a good internet connection."
    if ask_yes_no "Download the source code and build Trellis?" y; then
      BUILD=1
      GET_SOURCE=1
      IS_CHECKOUT=1
      ok "The installer builds Trellis from the source code."
      return
    fi
    fail "The ready-made download is not available, and you chose not to build Trellis." \
"Try again later, or run the installer again and answer y to build from the source code."
  fi
  if grep -qiE "is not a docker command|unknown command|unknown flag" "$LAST_LOG"; then
    warn "This Docker cannot run the download test. The installer continues; the download comes later."
    return
  fi
  if [ -f "$TRELLIS_DIR/compose.yaml" ] && docker image inspect "$img" >/dev/null 2>&1; then
    warn "The download server cannot be reached, but Trellis is already on this computer. The installer continues."
    return
  fi
  fail_download "$kind"
}

# download URL FILE -> curl with the output kept for the help box.
download() { run_quiet curl -fsSL --retry 2 -o "$2" "$1"; }

step_files() {
  step "Get the Trellis files"
  if [ -f "$TRELLIS_DIR/compose.yaml" ]; then
    ok "The Trellis files are already in $TRELLIS_DIR"
  elif [ "$GET_SOURCE" = 1 ]; then
    info "Downloading the source code..."
    download "$SOURCE_ZIP_URL" "$WORK_TMP/source.zip" || fail_download "$(classify_error <"$LAST_LOG")"
    mkdir -p "$WORK_TMP/src"
    run_quiet unzip -q "$WORK_TMP/source.zip" -d "$WORK_TMP/src" ||
      fail "The downloaded source code is damaged." "Run the installer again. It downloads it again."
    local top
    top="$(find "$WORK_TMP/src" -mindepth 2 -maxdepth 2 -name compose.yaml | head -n 1)"
    [ -n "$top" ] || fail "The downloaded source code does not look like Trellis." "Run the installer again."
    cp -R "$(dirname "$top")/." "$TRELLIS_DIR/"
    ok "Source code unpacked in $TRELLIS_DIR"
  else
    info "Downloading Trellis..."
    download "$BUNDLE_URL" "$WORK_TMP/trellis-bundle.zip" || fail_download "$(classify_error <"$LAST_LOG")"
    download "$SUMS_URL" "$WORK_TMP/SHA256SUMS" || fail_download "$(classify_error <"$LAST_LOG")"
    LAST_CMD="sha256 check of trellis-bundle.zip against SHA256SUMS"
    if ! verify_sha256 "$WORK_TMP/trellis-bundle.zip" "$WORK_TMP/SHA256SUMS" trellis-bundle.zip; then
      { echo "expected: $(grep trellis-bundle.zip "$WORK_TMP/SHA256SUMS")"; echo "got: $(sha256_of "$WORK_TMP/trellis-bundle.zip")"; } >"$LAST_LOG"
      fail "The downloaded file is damaged or not the real Trellis file (its checksum does not match)." \
"Run the installer again. If this happens again, do not use that network, and report it:
  $REPO_URL/issues"
    fi
    ok "Download checked (SHA256)."
    mkdir -p "$WORK_TMP/bundle"
    run_quiet unzip -q "$WORK_TMP/trellis-bundle.zip" -d "$WORK_TMP/bundle" ||
      fail "The downloaded file could not be unpacked." "Run the installer again."
    [ -f "$WORK_TMP/bundle/trellis/compose.yaml" ] ||
      fail "The downloaded file does not look like Trellis." "Run the installer again, or report it: $REPO_URL/issues"
    cp -R "$WORK_TMP/bundle/trellis/." "$TRELLIS_DIR/"
    chmod +x "$TRELLIS_DIR/setup.sh" 2>/dev/null
    ok "Files unpacked in $TRELLIS_DIR"
  fi
  [ -d "$TRELLIS_DIR/backend" ] && IS_CHECKOUT=1
  local had_env=0
  [ -f "$TRELLIS_DIR/.env" ] && had_env=1
  LAST_CMD="write $TRELLIS_DIR/.env"
  write_env "$TRELLIS_DIR" "$PORT" 2>"$LAST_LOG" ||
    fail "The installer could not write the settings file $TRELLIS_DIR/.env" \
"Check that you may write in that folder, or choose another one:
  bash setup.sh --dir ~/Trellis"
  if [ "$had_env" = 1 ]; then ok "Settings file .env kept (missing settings added)."
  else ok "Settings file .env made. It holds a random database password. You never need to type it."
  fi
}

# Recreates the nginx container: the fix for "containers run, but the address gives an empty reply".
repair_web() {
  info "Trellis runs, but its front door (web) does not answer. The installer restarts it."
  run_shown compose up -d --no-build --force-recreate web || true
}

step_start() {
  step "Start Trellis"
  local s
  s="$(health_probe "$PORT")"
  if [ "$s" = "ok" ]; then ok "Trellis is already running."; return; fi
  if [ "$s" = "empty" ] && web_running; then repair_web; fi

  LAST_CMD="docker compose config"
  if ! compose config -q >"$LAST_LOG" 2>&1; then
    fail "The Trellis settings (.env or compose.yaml) have an error." \
"Look at the last lines below. A setting in $TRELLIS_DIR/.env may be wrong.
Never share the values of passwords or keys."
  fi
  if [ "$BUILD" = 1 ]; then
    if [ "$EXISTING" = 0 ]; then
      info "Building Trellis from the source code. The first time takes 10 to 15 minutes."
      if ! run_shown compose up -d --build --wait; then start_failed; fi
    else
      info "Starting Trellis. Parts that are missing are built first (10 to 15 minutes)."
      if ! run_shown compose up -d --wait; then start_failed; fi
    fi
  else
    if [ "$EXISTING" = 0 ]; then
      info "Downloading Trellis (about 1.5 GB). This can take a few minutes."
      if ! run_shown compose pull; then
        local kind
        kind="$(classify_error <"$LAST_LOG")"
        [ "$kind" = "unknown" ] || [ "$kind" = "missing" ] || fail_download "$kind"
        fail "Downloading Trellis failed." "Run the installer again. If it fails again, use the text below with an AI assistant."
      fi
    fi
    info "Starting Trellis. This can take a minute or two."
    if ! run_shown compose up -d --wait; then start_failed; fi
  fi
  wait_health
}

# up --wait failed: go on when the front door runs (wait_health decides), stop otherwise.
start_failed() {
  local kind
  kind="$(classify_error <"$LAST_LOG")"
  case "$kind" in tls|dns|ratelimit) fail_download "$kind" ;; esac
  web_running && return 0
  { compose ps -a 2>&1; } >>"$LAST_LOG"
  fail "Trellis did not start." \
"See what runs, and the messages of the app:
  cd \"$TRELLIS_DIR\"
  docker compose ps
  docker compose logs --tail 50 api
Or make a full report:  bash setup.sh --report"
}

wait_health() {
  local i=0 empties=0 repaired=0 s=""
  printf '  Waiting for Trellis to answer (up to 3 minutes) '
  while [ "$i" -lt "$HEALTH_TRIES" ]; do
    s="$(health_probe "$PORT")"
    if [ "$s" = "ok" ]; then printf '\n'; ok "Trellis answers at http://localhost:$PORT"; return 0; fi
    if [ "$s" = "empty" ]; then empties=$((empties + 1)); else empties=0; fi
    if [ "$empties" -ge 4 ] && [ "$repaired" = 0 ] && web_running; then
      printf '\n'
      repair_web
      repaired=1
      empties=0
      printf '  Waiting '
    fi
    printf '.'
    nap 5
    i=$((i + 1))
  done
  printf '\n'
  LAST_CMD="curl http://localhost:$PORT/api/health"
  {
    echo "health check result: $s"
    compose ps -a 2>&1
    compose logs --tail 15 web api 2>&1
  } >"$LAST_LOG"
  fail "Trellis started, but it does not answer at http://localhost:$PORT" \
"Wait a minute and run the installer again. It repairs known problems.
To see what is wrong:
  cd \"$TRELLIS_DIR\"
  docker compose ps
  bash setup.sh --report"
}

step_done() {
  step "Open Trellis"
  local url="http://localhost:$PORT"
  if open_url "$url"; then info "Your browser opens $url"
  else info "Open this address in your browser: $url"
  fi
  say ""
  say "  ${G}${B}Trellis is ready.${N}"
  info "In the browser: choose your name and language, add your AI key, and set a password."
  say ""
  info "Good to know:"
  info "- Start later: Trellis starts by itself when Docker Desktop runs."
  info "  If it does not, run this installer again:"
  cmd "bash \"$TRELLIS_DIR/setup.sh\""
  info "- Stop Trellis:"
  cmd "cd \"$TRELLIS_DIR\" && docker compose stop"
  info "- Backups: every night, in $TRELLIS_DIR/backups"
  info "  Copy that folder to another place now and then."
  info "- Something wrong? Make a report for a bug report or an AI chat:"
  cmd "bash \"$TRELLIS_DIR/setup.sh\" --report"
}

# ---------------------------------------------------------------- --report

report_dir() {
  if [ -n "$OPT_DIR" ]; then abs_path "$OPT_DIR"; return; fi
  if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/compose.yaml" ]; then printf '%s' "$SCRIPT_DIR"; return; fi
  local saved
  saved="$(saved_dir)"
  if [ -n "$saved" ] && [ -f "$saved/compose.yaml" ]; then printf '%s' "$saved"; return; fi
  printf '%s' "$HOME/Trellis"
}

make_report() {
  local out port svc mem keys
  TRELLIS_DIR="$(report_dir)"
  port="$(env_get "$TRELLIS_DIR/.env" TRELLIS_PORT)"
  [ -n "$port" ] || port="$DEFAULT_PORT"
  out="$WORK_TMP/report.txt"
  {
    echo "Trellis setup report, made $(date '+%Y-%m-%d %H:%M:%S %z')"
    echo "Passwords, keys and tokens are replaced by [REDACTED]."
    echo
    echo "== System"
    echo "OS: $(os_description)"
    echo "Shell: bash $BASH_VERSION"
    echo "Docker: $(docker_description)"
    if have docker; then
      echo "Docker engine: $(docker version --format '{{.Server.Version}}' 2>&1 | head -n 1)"
      mem="$(docker info --format '{{.MemTotal}}' 2>/dev/null | tr -dc '0-9')"
      [ -n "$mem" ] && echo "Docker memory: $(awk -v m="$mem" 'BEGIN { printf "%.1f GB", m / 1073741824 }')"
      echo "Docker CPUs: $(docker info --format '{{.NCPU}}' 2>&1 | head -n 1)"
    fi
    echo
    echo "== Trellis folder"
    echo "Folder: $TRELLIS_DIR"
    for f in compose.yaml .env .env.example deploy/nginx.conf backend; do
      if [ -e "$TRELLIS_DIR/$f" ]; then echo "  $f: yes"; else echo "  $f: no"; fi
    done
    if [ -f "$TRELLIS_DIR/.env" ]; then
      keys="$(grep -E '^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=' "$TRELLIS_DIR/.env" | sed 's/=.*//' | tr -d ' ' | tr '\n' ' ')"
      echo "  .env settings (names only): $keys"
    fi
    echo "Disk free: $(df -Pk "$TRELLIS_DIR" 2>/dev/null | awk 'NR == 2 { printf "%.1f GB", $4 / 1048576 }')"
    echo "Port: $port"
    if have docker && [ -f "$TRELLIS_DIR/compose.yaml" ]; then
      echo
      echo "== docker compose ps"
      compose ps -a 2>&1
      for svc in $(compose config --services 2>/dev/null); do
        echo
        echo "== Last 50 log lines: $svc"
        compose logs --no-color --tail 50 "$svc" 2>&1
      done
    fi
    echo
    echo "== Health: http://localhost:$port/api/health"
    curl -sS -m 5 "http://127.0.0.1:$port/api/health" 2>&1 || echo "(curl exit code $?)"
    echo
  } 2>&1 | redact >"$out"
  cat "$out"
  local dest
  if [ -d "$TRELLIS_DIR" ]; then dest="$TRELLIS_DIR/trellis-report-$(date '+%Y%m%d-%H%M%S').txt"
  else dest="$PWD/trellis-report-$(date '+%Y%m%d-%H%M%S').txt"
  fi
  if cp "$out" "$dest" 2>/dev/null; then
    say ""
    say "Report saved: $dest"
    say "Paste it in a bug report ($REPO_URL/issues) or an AI chat. Secrets are already hidden."
  fi
}

# ---------------------------------------------------------------- main

usage() {
  cat <<EOF
Trellis guided installer (Mac and Linux)

  bash setup.sh [options]

Options:
  --yes, -y        Do not ask; take the default answer every time (for scripts and CI).
  --dir FOLDER     Put Trellis in FOLDER (default: ~/Trellis, or this folder for a source checkout).
  --report         Print a diagnostic report (secrets hidden) and save it in the Trellis folder.
  --help, -h       Show this help.

Safe to run again: it checks everything, repairs known problems and starts Trellis.
EOF
}

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --yes|-y) OPT_YES=1 ;;
      --report) OPT_REPORT=1 ;;
      --dir) shift; [ $# -gt 0 ] || { usage; exit 2; }; OPT_DIR="$1" ;;
      --dir=*) OPT_DIR="${1#--dir=}" ;;
      --help|-h) usage; exit 0 ;;
      *) say "Unknown option: $1"; usage; exit 2 ;;
    esac
    shift
  done
}

cleanup() { [ -n "$WORK_TMP" ] && rm -rf "$WORK_TMP"; }

interrupted() {
  printf '\n\n  Stopped. Nothing is lost. Run the installer again at any time; it continues where it stopped.\n'
  cleanup
  exit 130
}

main() {
  parse_args "$@"
  setup_colors
  detect_os
  WORK_TMP="$(mktemp -d 2>/dev/null || mktemp -d -t trellis-setup)"
  LAST_LOG="$WORK_TMP/last-output.txt"
  : >"$LAST_LOG"
  trap cleanup EXIT
  trap interrupted INT TERM
  case "${BASH_SOURCE[0]:-}" in
    */*) SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" ;;
    ?*) SCRIPT_DIR="$PWD" ;;
  esac
  [ -f "${BASH_SOURCE[0]:-/nonexistent}" ] || SCRIPT_DIR=""   # piped from curl: no folder of its own
  if [ "$OPT_REPORT" = 1 ]; then make_report; return 0; fi
  if [ "$OS" = "other" ]; then
    say "This installer is for Mac and Linux. On Windows, run setup.ps1 in PowerShell:"
    say "  powershell -ExecutionPolicy Bypass -File setup.ps1"
    exit 1
  fi
  if [ "$OPT_YES" != 1 ] && (exec </dev/tty) 2>/dev/null; then exec 3</dev/tty && TTY_IN=1; fi

  say ""
  say "${B}Trellis installer${N}"
  step_welcome
  step_docker_installed
  step_docker_running
  step_folder
  step_room
  step_port
  step_download_test
  step_files
  step_start
  step_done
}

# Run main only when executed (bash setup.sh, or piped from curl), not when sourced by the tests.
if [ -z "${BASH_SOURCE[0]:-}" ] || [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
