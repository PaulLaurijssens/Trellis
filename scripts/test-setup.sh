#!/usr/bin/env bash
# Tests for setup.sh without Docker:   bash scripts/test-setup.sh
# 1. Pure functions, with setup.sh sourced (main does not run when sourced).
# 2. Whole runs with --yes against a fake docker, curl, sudo and systemctl on PATH, in a temp folder.
# The real docker is never called: the fake one comes first on PATH.
# Variables set here are read by the sourced setup.sh functions; fakes are written with literal $.
# shellcheck disable=SC2034,SC2016,SC2088,SC2317,SC2012
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETUP="$ROOT/setup.sh"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
REAL_CURL="$(command -v curl)"
PASS=0
FAILED=0

ok_()   { PASS=$((PASS + 1)); }
bad_()  { FAILED=$((FAILED + 1)); printf 'FAIL: %s\n' "$1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/      /' | head -n 40; }
eq()    { if [ "$2" = "$3" ]; then ok_; else bad_ "$1" "expected: [$2]
got:      [$3]"; fi; }
has()   { case "$2" in *"$3"*) ok_ ;; *) bad_ "$1: missing [$3]" "$2" ;; esac; }
hasnt() { case "$2" in *"$3"*) bad_ "$1: should not contain [$3]" "$2" ;; *) ok_ ;; esac; }
yes_()  { if "$@"; then ok_; else bad_ "expected success: $*"; fi; }
no_()   { if "$@"; then bad_ "expected failure: $*"; else ok_; fi; }

# ---------------------------------------------------------------- 1. pure functions
# shellcheck source=setup.sh
. "$SETUP"

r() { printf '%s\n' "$1" | redact; }
NEO4J_PW="" TRELLIS_DIR=""
eq "redact openai key"   "OPENAI_API_KEY=[REDACTED]"          "$(r 'OPENAI_API_KEY=sk-proj-abcdefghijklmnop123')"
eq "redact sk- in text"  "used sk-[REDACTED] here"            "$(r 'used sk-ant-api03-abcdefgh12345 here')"
eq "redact gemini key"   "key AIza[REDACTED] x"               "$(r 'key AIzaSyA1234567890abcdefghijklmnopq x')"
eq "redact json key"     '"api_key": "[REDACTED]"'            "$(r '"api_key": "zzz123"')"
eq "redact bearer"       "Authorization: Bearer [REDACTED]"   "$(r 'Authorization: Bearer abc.def.ghi')"
eq "redact password="    "NEO4J_PASSWORD=[REDACTED]"          "$(r 'NEO4J_PASSWORD=hunter2hunter2')"
eq "redact token:"       "token: [REDACTED]"                  "$(r 'token: ghp_abc')"
eq "redact long hex"     "sha256:[REDACTED-HEX]"              "$(r 'sha256:0123456789abcdef0123456789abcdef0123456789abcdef')"
eq "redact long key"     "azure [REDACTED]"                   "$(r 'azure AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfGhIjKlMn')"
eq "keep normal text"    "unauthorized: authentication required" "$(r 'unauthorized: authentication required')"
NEO4J_PW="Sup3r-Secret.Value"
eq "redact db password"  "pw is [REDACTED] ok"                "$(r 'pw is Sup3r-Secret.Value ok')"
NEO4J_PW=""
mkdir -p "$T/u/redact" && printf 'NEO4J_PASSWORD=FromTheEnvFile99\n' >"$T/u/redact/.env"
TRELLIS_DIR="$T/u/redact"
eq "redact password from .env" "x [REDACTED] y"              "$(r 'x FromTheEnvFile99 y')"
TRELLIS_DIR=""

c() { printf '%s' "$1" | classify_error; }
eq "class x509"     tls       "$(c 'Get "https://ghcr.io/v2/": tls: failed to verify certificate: x509: certificate signed by unknown authority')"
eq "class proxy"    tls       "$(c 'Get "https://ghcr.io/v2/": proxyconnect tcp: dial tcp: lookup proxy.corp: no such host')"
eq "class curl ssl" tls       "$(c 'curl: (60) SSL certificate problem: unable to get local issuer certificate')"
eq "class dns"      dns       "$(c 'Get "https://ghcr.io/v2/": dial tcp: lookup ghcr.io on 127.0.0.53:53: no such host')"
eq "class curl dns" dns       "$(c 'curl: (6) Could not resolve host: github.com')"
eq "class manifest" missing   "$(c 'manifest unknown')"
eq "class denied"   missing   "$(c 'Error response from daemon: Head "https://ghcr.io/v2/x/manifests/latest": denied')"
eq "class 404"      missing   "$(c 'curl: (22) The requested URL returned error: 404')"
eq "class rate"     ratelimit "$(c 'toomanyrequests: You have reached your pull rate limit.')"
eq "class timeout"  offline   "$(c 'net/http: request canceled while waiting for connection (Client.Timeout exceeded while awaiting headers)')"
eq "class refused"  offline   "$(c 'dial tcp 140.82.1.1:443: connect: network is unreachable')"
eq "class unknown"  unknown   "$(c 'something odd happened')"

# Port picking with a fake "in use" list, then the real check against a listening socket.
port_in_use() { case " $BUSY " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
BUSY="8080 8081"; eq "pick next free port" 8082 "$(pick_port 8080)"
BUSY="";          eq "pick first port"     8080 "$(pick_port 8080)"
BUSY="$(seq 9000 9019 | tr '\n' ' ')"; no_ pick_port 9000
# shellcheck source=setup.sh
. "$SETUP"   # restore the real port_in_use
if command -v python3 >/dev/null 2>&1; then
  python3 -c 'import socket,time,sys
s=socket.socket(); s.bind(("127.0.0.1",0)); s.listen(5); print(s.getsockname()[1]); sys.stdout.flush(); time.sleep(20)' >"$T/port" &
  LISTENER=$!
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$T/port" ] && break; sleep 0.2; done
  LPORT="$(cat "$T/port")"
  yes_ port_in_use "$LPORT"
  kill "$LISTENER" 2>/dev/null; wait "$LISTENER" 2>/dev/null
  no_ port_in_use "$LPORT"
fi

# .env writing
E="$T/u/env1"; mkdir -p "$E"; cp "$ROOT/.env.example" "$E/"
yes_ write_env "$E" 8080
PW="$(env_get "$E/.env" NEO4J_PASSWORD)"
yes_ [ "${#PW}" -ge 40 ]
eq "password is letters and digits" "" "$(printf '%s' "$PW" | tr -d 'A-Za-z0-9')"
eq "no port line for 8080" "" "$(env_get "$E/.env" TRELLIS_PORT)"
eq "rest of .env.example kept" "$(grep -v '^NEO4J_PASSWORD=' "$ROOT/.env.example")" "$(grep -v '^NEO4J_PASSWORD=' "$E/.env")"
eq ".env is private" 600 "$(stat -c %a "$E/.env" 2>/dev/null || stat -f %Lp "$E/.env")"
B1="$(cat "$E/.env")"; yes_ write_env "$E" 8080; eq "second write changes nothing" "$B1" "$(cat "$E/.env")"
yes_ write_env "$E" 8081; eq "port written" 8081 "$(env_get "$E/.env" TRELLIS_PORT)"
eq "password kept on port change" "$PW" "$(env_get "$E/.env" NEO4J_PASSWORD)"
yes_ write_env "$E" 8090; eq "port replaced" 8090 "$(env_get "$E/.env" TRELLIS_PORT)"
eq "one port line" 1 "$(grep -c '^TRELLIS_PORT=' "$E/.env")"

E="$T/u/env2"; mkdir -p "$E"; cp "$ROOT/.env.example" "$E/"
printf '# mine\nNEO4J_PASSWORD=keep-this-one\nGEMINI_API_KEY=AIzaKeep\n' >"$E/.env"
B1="$(cat "$E/.env")"; yes_ write_env "$E" 8080
eq "existing .env untouched" "$B1" "$(cat "$E/.env")"

E="$T/u/env3"; mkdir -p "$E"
printf 'GEMINI_API_KEY=AIzaKeep' >"$E/.env"     # no newline at the end, no password
yes_ write_env "$E" 8080
eq "first line kept" "GEMINI_API_KEY=AIzaKeep" "$(head -n 1 "$E/.env")"
PW="$(env_get "$E/.env" NEO4J_PASSWORD)"; yes_ [ "${#PW}" -ge 40 ]

E="$T/u/env4"; mkdir -p "$E"; printf 'NEO4J_PASSWORD=change-me\n' >"$E/.env"
yes_ write_env "$E" 8080
eq "existing change-me kept (the database may use it)" change-me "$(env_get "$E/.env" NEO4J_PASSWORD)"

E="$T/u/env5"; mkdir -p "$E"; printf 'A="quoted value"\r\nB=x\n' >"$E/.env"
eq "env_get strips quotes and CR" "quoted value" "$(env_get "$E/.env" A)"
no_ env_get "$E/.env" MISSING

# Checksums
printf 'hello\n' >"$T/u/f.zip"
H="$(sha256_of "$T/u/f.zip")"
printf '%s  f.zip\n' "$H" >"$T/u/SUMS1";                                 yes_ verify_sha256 "$T/u/f.zip" "$T/u/SUMS1" f.zip
printf '%s *dist/f.zip\r\n' "$(printf '%s' "$H" | tr 'a-f' 'A-F')" >"$T/u/SUMS2"; yes_ verify_sha256 "$T/u/f.zip" "$T/u/SUMS2" f.zip
printf '%s  f.zip\n' "$(printf '0%.0s' $(seq 1 64))" >"$T/u/SUMS3";     no_ verify_sha256 "$T/u/f.zip" "$T/u/SUMS3" f.zip
verify_sha256 "$T/u/f.zip" "$T/u/SUMS1" other.zip; eq "name not listed" 2 "$?"

# Linux download page per distribution
osr() { printf '%s\n' "$@" >"$T/u/os-release"; OS_RELEASE="$T/u/os-release" linux_docker_url; }
eq "ubuntu" "https://docs.docker.com/engine/install/ubuntu/" "$(osr 'ID=ubuntu')"
eq "mint"   "https://docs.docker.com/engine/install/ubuntu/" "$(osr 'ID=linuxmint' 'ID_LIKE="ubuntu debian"')"
eq "fedora" "https://docs.docker.com/engine/install/fedora/" "$(osr 'ID="fedora"')"
eq "arch"   "https://docs.docker.com/engine/install/"        "$(osr 'ID=arch')"

eq "abs ~"        "$HOME/Trellis" "$(abs_path '~/Trellis')"
eq "abs relative" "$PWD/x"         "$(abs_path 'x/')"

# Docker missing: explains Docker, shows the page, and stops with the AI box (--yes cannot wait).
OUT="$( (have() { [ "$1" != docker ] && command -v "$1" >/dev/null 2>&1; }
         OS=linux OPT_YES=1 STEP_NO=1 TRELLIS_SETUP_NO_BROWSER=1 TRELLIS_SETUP_NO_CLIPBOARD=1
         OS_RELEASE="$T/u/os-release"; printf 'ID=ubuntu\n' >"$OS_RELEASE"
         LAST_LOG="$T/u/last"; : >"$LAST_LOG"
         step_docker_installed) 2>&1)"; RC=$?
eq "docker missing stops" 1 "$RC"
has "docker missing" "$OUT" "Step 2 of 10: Docker"
has "docker missing" "$OUT" "a free program that runs Trellis in a sealed box on your computer"
has "docker missing" "$OUT" "https://docs.docker.com/engine/install/ubuntu/"
has "docker missing" "$OUT" "Copy this into ChatGPT, Claude or Copilot:"

# ---------------------------------------------------------------- 2. whole runs against fakes

mkdir -p "$T/bin"
cat >"$T/bin/docker" <<'EOF'
#!/usr/bin/env bash
# Fake docker. FAKE_INFO=down, FAKE_MEM, FAKE_MANIFEST=ok|tls|missing; calls are logged to FAKE_LOG.
echo "docker $*" >>"$FAKE_LOG"
case "$1" in
  --version) echo "Docker version 27.3.1, build fake" ;;
  version) echo "27.3.1" ;;
  info)
    if [ "${FAKE_INFO:-up}" = down ]; then
      echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?" >&2; exit 1
    fi
    case "$*" in *MemTotal*) echo "${FAKE_MEM:-8333777000}" ;; *NCPU*) echo 8 ;; *) echo "Server Version: 27.3.1" ;; esac ;;
  manifest)
    case "${FAKE_MANIFEST:-ok}" in
      ok) echo '{"schemaVersion": 2}' ;;
      tls) echo 'Get "https://ghcr.io/v2/": tls: failed to verify certificate: x509: certificate signed by unknown authority (proxy token sk-test-abcdefghijkl1234)' >&2; exit 1 ;;
      missing) echo "manifest unknown" >&2; exit 1 ;;
    esac ;;
  image) exit 1 ;;
  compose)
    shift
    case "$1" in
      version) echo "Docker Compose version v2.29.7" ;;
      config)
        [ -f compose.yaml ] || { echo "no configuration file provided: not found" >&2; exit 1; }
        [ "${2:-}" = "--services" ] && printf 'neo4j\napi\nweb\n'
        exit 0 ;;
      pull) echo "api Pulled" ;;
      up)
        case "$*" in *force-recreate*) touch "$FAKE_STATE/recreated" ;; esac
        touch "$FAKE_STATE/up"; echo " Container trellis-web-1  Healthy" ;;
      ps)
        [ -f "$FAKE_STATE/up" ] || exit 0
        case "$*" in *--services*) printf 'neo4j\napi\nweb\n' ;; *) echo "NAME            STATUS"; echo "trellis-web-1   Up 2 minutes" ;; esac ;;
      logs) echo "api  | connecting with NEO4J_PASSWORD $(sed -n 's/^NEO4J_PASSWORD=//p' .env)" ;;
    esac ;;
esac
exit 0
EOF
cat >"$T/bin/curl" <<EOF
#!/usr/bin/env bash
# Fake curl for the health URL (FAKE_HEALTH=ok|empty|down); everything else goes to the real curl.
for a in "\$@"; do
  case "\$a" in */api/health)
    case "\${FAKE_HEALTH:-ok}" in
      ok) [ -f "\$FAKE_STATE/up" ] || { echo "curl: (7) Failed to connect" >&2; exit 7; }
          echo '{"ok": true, "setup_needed": true}'; exit 0 ;;
      empty) [ -f "\$FAKE_STATE/recreated" ] && { echo '{"ok":true}'; exit 0; }
          echo "curl: (52) Empty reply from server" >&2; exit 52 ;;
      *) echo "curl: (7) Failed to connect" >&2; exit 7 ;;
    esac ;;
  esac
done
exec "$REAL_CURL" "\$@"
EOF
printf '#!/bin/sh\necho "sudo $*" >>"$FAKE_LOG"\nexit 1\n' >"$T/bin/sudo"
printf '#!/bin/sh\nexit 1\n' >"$T/bin/systemctl"
printf '#!/bin/sh\ncat >"$FAKE_CLIP"\n' >"$T/bin/xclip"
chmod +x "$T/bin/"*

# A release bundle and a source zip, served with file:// URLs.
mkdir -p "$T/rel/trellis/deploy" "$T/rel/trellis/db" "$T/rel/trellis/backups"
printf 'services: {}\n' >"$T/rel/trellis/compose.yaml"
cp "$ROOT/.env.example" "$T/rel/trellis/"
cp "$SETUP" "$T/rel/trellis/setup.sh"
: >"$T/rel/trellis/deploy/nginx.conf"; : >"$T/rel/trellis/backups/.gitkeep"
(cd "$T/rel" && zip -qr trellis-bundle.zip trellis && sha256sum trellis-bundle.zip >SHA256SUMS)
printf '%s  trellis-bundle.zip\n' "$(printf 'a%.0s' $(seq 1 64))" >"$T/rel/BADSUMS"
mkdir -p "$T/src/Trellis-main/backend"
printf 'services: {}\n' >"$T/src/Trellis-main/compose.yaml"
cp "$ROOT/.env.example" "$SETUP" "$T/src/Trellis-main/"
: >"$T/src/Trellis-main/backend/Dockerfile.prod"
(cd "$T/src" && zip -qr main.zip Trellis-main)

# The installer as a person downloads it: a lone file, not inside a checkout.
mkdir -p "$T/dl" && cp "$SETUP" "$T/dl/setup.sh"

# run_setup NAME [args...]  (env vars before the call are passed on). Sets OUT and RC.
run_setup() {
  local name="$1"; shift
  mkdir -p "$T/home-$name" "$T/state-$name"
  OUT="$(HOME="$T/home-$name" PATH="$T/bin:$PATH" FAKE_LOG="$T/docker-$name.log" FAKE_STATE="$T/state-$name" \
         FAKE_CLIP="$T/clip-$name.txt" DISPLAY=:99 WAYLAND_DISPLAY='' XDG_CONFIG_HOME='' \
         TRELLIS_SETUP_TICK=0 TRELLIS_SETUP_HEALTH_TRIES=8 TRELLIS_SETUP_DOCKER_TRIES=2 TRELLIS_SETUP_NO_BROWSER=1 \
         TRELLIS_BUNDLE_URL="${BUNDLE:-file://$T/rel/trellis-bundle.zip}" TRELLIS_SUMS_URL="${SUMS:-file://$T/rel/SHA256SUMS}" \
         TRELLIS_SOURCE_ZIP_URL="file://$T/src/main.zip" \
         bash "${SCRIPT:-$T/dl/setup.sh}" "$@" </dev/null 2>&1)"
  RC=$?
  LOG="$(cat "$T/docker-$name.log" 2>/dev/null)"
}

# A. Fresh install from the release bundle.
D="$T/a/Trellis"
run_setup a --yes --dir "$D"
eq "A exit" 0 "$RC"
for s in "Step 1 of 10: Welcome" "Step 2 of 10: Docker" "Step 3 of 10: Start Docker" "Step 4 of 10: Choose a folder" \
         "Step 5 of 10: Check memory and disk space" "Step 6 of 10: Choose a port" "Step 7 of 10: Test the download" \
         "Step 8 of 10: Get the Trellis files" "Step 9 of 10: Start Trellis" "Step 10 of 10: Open Trellis" \
         "Download checked (SHA256)" "Trellis is ready." "docker compose stop" "$D/backups"; do
  has "A flow" "$OUT" "$s"
done
yes_ [ -f "$D/compose.yaml" ]
yes_ [ -x "$D/setup.sh" ]
PW="$(env_get "$D/.env" NEO4J_PASSWORD)"; yes_ [ "${#PW}" -ge 40 ]
hasnt "A never shows the password" "$OUT" "$PW"
has "A pulls" "$LOG" "docker compose pull"
has "A starts" "$LOG" "docker compose up -d --wait"
hasnt "A does not build" "$LOG" "--build"
eq "A remembers the folder" "dir=$D" "$(cat "$T/home-a/.config/trellis/setup-state")"

# B. Run again: .env untouched, no new download, Trellis already running.
SUM_BEFORE="$(cat "$D/.env")"
rm -f "$T/docker-a.log"
run_setup a --yes --dir "$D"
eq "B exit" 0 "$RC"
eq "B .env unchanged" "$SUM_BEFORE" "$(cat "$D/.env")"
has "B" "$OUT" "Trellis is already set up in this folder"
has "B" "$OUT" "The Trellis files are already in"
has "B" "$OUT" "Trellis is already running."
hasnt "B no pull" "$LOG" "compose pull"

# K. --report: redacted, saved in the folder.
run_setup a --report --dir "$D"
eq "K exit" 0 "$RC"
has "K" "$OUT" "== docker compose ps"
has "K" "$OUT" "Last 50 log lines: api"
has "K" "$OUT" "NEO4J_PASSWORD [REDACTED]"
has "K" "$OUT" ".env settings (names only): NEO4J_PASSWORD"
has "K" "$OUT" '"ok": true'
hasnt "K never shows the password" "$OUT" "$PW"
REPORT="$(ls "$D"/trellis-report-*.txt 2>/dev/null | head -n 1)"
yes_ [ -s "$REPORT" ]
hasnt "K saved report has no password" "$(cat "$REPORT")" "$PW"

# C. The network blocks the download: plain reason, the AI box, the clipboard; no further steps.
FAKE_MANIFEST=tls run_setup c --yes --dir "$T/c/Trellis"
eq "C exit" 1 "$RC"
has "C" "$OUT" "Setup stopped at step 7 of 10: Test the download"
has "C" "$OUT" "Your network or a proxy blocks the download."
has "C" "$OUT" "Docker Desktop > Settings > Resources > Proxies"
has "C" "$OUT" "Copy this into ChatGPT, Claude or Copilot:"
has "C" "$OUT" "The command that failed: docker manifest inspect ghcr.io/paullaurijssens/trellis-api:latest"
has "C" "$OUT" "x509: certificate signed by unknown authority"
has "C" "$OUT" "Help me with this one step. Explain it in simple words."
has "C" "$OUT" "sk-[REDACTED]"
hasnt "C" "$OUT" "sk-test-abcdefghijkl1234"
hasnt "C" "$OUT" "Step 8 of 10"
has "C" "$OUT" "This text is also on your clipboard."
has "C clipboard" "$(cat "$T/clip-c.txt" 2>/dev/null)" "Help me with this one step. Explain it in simple words."
has "C clipboard" "$(cat "$T/clip-c.txt" 2>/dev/null)" "My computer: $(detect_os; os_description)."

# D. Images not published, lone installer: downloads the source and builds.
FAKE_MANIFEST=missing run_setup d --yes --dir "$T/d/Trellis"
eq "D exit" 0 "$RC"
has "D" "$OUT" "The ready-made Trellis download is not available yet."
has "D" "$OUT" "Download the source code and build Trellis?"
has "D" "$LOG" "docker compose up -d --build --wait"
hasnt "D no pull" "$LOG" "compose pull"
yes_ [ -d "$T/d/Trellis/backend" ]

# E. Run from inside a source checkout (dev path), images not published: builds there.
mkdir -p "$T/e" && cp -R "$T/src/Trellis-main" "$T/e/checkout"
FAKE_MANIFEST=missing SCRIPT="$T/e/checkout/setup.sh" run_setup e --yes
eq "E exit" 0 "$RC"
has "E" "$OUT" "You run the installer from a Trellis folder"
has "E" "$OUT" "This folder has the source code."
has "E" "$LOG" "docker compose up -d --build --wait"
yes_ [ -f "$T/e/checkout/.env" ]

# F. Containers run but the address gives an empty reply: web is recreated.
FAKE_HEALTH=empty run_setup f --yes --dir "$T/f/Trellis"
eq "F exit" 0 "$RC"
has "F" "$OUT" "its front door (web) does not answer"
has "F" "$LOG" "docker compose up -d --no-build --force-recreate web"

# G. Checksum mismatch.
SUMS="file://$T/rel/BADSUMS" run_setup g --yes --dir "$T/g/Trellis"
eq "G exit" 1 "$RC"
has "G" "$OUT" "its checksum does not match"
has "G" "$OUT" "Setup stopped at step 8 of 10: Get the Trellis files"
yes_ [ ! -f "$T/g/Trellis/compose.yaml" ]

# H. Too little memory for Docker.
FAKE_MEM=4000000000 run_setup h --yes --dir "$T/h/Trellis"
eq "H exit" 1 "$RC"
has "H" "$OUT" "Setup stopped at step 5 of 10: Check memory and disk space"
has "H" "$OUT" "Trellis needs 6 GB"

# I. Docker does not start: suggests the command, waits, stops with help.
FAKE_INFO=down run_setup i --yes --dir "$T/i/Trellis"
eq "I exit" 1 "$RC"
has "I" "$OUT" "sudo systemctl start docker"
has "I" "$OUT" "Docker did not start within 2 minutes."
has "I" "$OUT" "Cannot connect to the Docker daemon"
has "I tried sudo -n" "$LOG" "sudo -n systemctl start docker"

# J. The saved port is taken by another program: the next free one goes in .env.
if [ -n "${LPORT:-}" ]; then
  python3 -c 'import socket,time,sys
s=socket.socket(); s.bind(("127.0.0.1",0)); s.listen(5); print(s.getsockname()[1]); sys.stdout.flush(); time.sleep(30)' >"$T/port2" &
  LISTENER=$!
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$T/port2" ] && break; sleep 0.2; done
  P="$(cat "$T/port2")"
  mkdir -p "$T/j/Trellis" && cp "$T/rel/trellis/compose.yaml" "$T/j/Trellis/"
  printf 'NEO4J_PASSWORD=abcdefghijabcdefghijabcdefghijabcdefghij\nTRELLIS_PORT=%s\n' "$P" >"$T/j/Trellis/.env"
  run_setup j --yes --dir "$T/j/Trellis"
  kill "$LISTENER" 2>/dev/null; wait "$LISTENER" 2>/dev/null
  eq "J exit" 0 "$RC"
  has "J" "$OUT" "Port $P is in use by another program."
  NEWP="$(env_get "$T/j/Trellis/.env" TRELLIS_PORT)"
  yes_ [ "$NEWP" -gt "$P" ]
  eq "J password kept" "abcdefghijabcdefghijabcdefghijabcdefghij" "$(env_get "$T/j/Trellis/.env" NEO4J_PASSWORD)"

  # J2. The port is taken by Trellis itself (web runs): keep it.
  python3 -c 'import socket,time,sys
s=socket.socket(); s.bind(("127.0.0.1",0)); s.listen(5); print(s.getsockname()[1]); sys.stdout.flush(); time.sleep(30)' >"$T/port3" &
  LISTENER=$!
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$T/port3" ] && break; sleep 0.2; done
  P="$(cat "$T/port3")"
  mkdir -p "$T/j2/Trellis" "$T/state-j2" && cp "$T/rel/trellis/compose.yaml" "$T/j2/Trellis/" && touch "$T/state-j2/up"
  printf 'NEO4J_PASSWORD=abcdefghijabcdefghijabcdefghijabcdefghij\nTRELLIS_PORT=%s\n' "$P" >"$T/j2/Trellis/.env"
  run_setup j2 --yes --dir "$T/j2/Trellis"
  kill "$LISTENER" 2>/dev/null; wait "$LISTENER" 2>/dev/null
  eq "J2 exit" 0 "$RC"
  has "J2" "$OUT" "Trellis already uses port $P."
  eq "J2 port kept" "$P" "$(env_get "$T/j2/Trellis/.env" TRELLIS_PORT)"
fi

# L. Help, a wrong option, and running from a pipe (curl ... | bash).
run_setup l --help; eq "L help exit" 0 "$RC"; has "L" "$OUT" "--report"
run_setup l --nonsense; eq "L wrong option" 2 "$RC"
mkdir -p "$T/state-p" "$T/home-p"
OUT="$(HOME="$T/home-p" PATH="$T/bin:$PATH" FAKE_LOG="$T/docker-p.log" FAKE_STATE="$T/state-p" DISPLAY='' \
       TRELLIS_SETUP_TICK=0 TRELLIS_SETUP_NO_BROWSER=1 TRELLIS_SETUP_NO_CLIPBOARD=1 \
       TRELLIS_BUNDLE_URL="file://$T/rel/trellis-bundle.zip" TRELLIS_SUMS_URL="file://$T/rel/SHA256SUMS" \
       bash -s -- --yes --dir "$T/p/Trellis" <"$SETUP" 2>&1)"; RC=$?
eq "piped exit" 0 "$RC"
has "piped" "$OUT" "Trellis is ready."

# ---------------------------------------------------------------- result
printf '\n%d passed, %d failed\n' "$PASS" "$FAILED"
[ "$FAILED" -eq 0 ]
