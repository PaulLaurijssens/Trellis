# Install Trellis with an AI assistant

This page is for you if you would rather have an AI assistant guide you through the install, or do
it for you. It works with:

- **An assistant that can run commands on your computer**, such as Claude Code, GitHub Copilot in
  agent mode, or Codex. It can do the steps itself and check the results.
- **A chat assistant**, such as ChatGPT, Claude or Copilot chat. It tells you what to type; you paste
  back what your computer answers.

The easiest way is still the guided installer (see *The short way* below). It does every step for
you and stops with a ready-made question for your AI assistant when something goes wrong. The
prompts on this page are for when you want the assistant in charge from the start.

## Before you start

- **Never paste your AI key into a chat.** You type it only in the Trellis setup screen in your
  browser, at the very end.
- **Never paste the contents of the `.env` file.** It holds the database password. If the assistant
  asks for it, say no. Show it the names of the settings only.
- **Ask before anything is installed.** A good assistant explains each command first. If you do not
  understand a command, ask: "What does this do, in simple words?"
- It takes about 15 minutes, plus the time to download Docker (about 600 MB) if you do not have it.
- You need about 6 GB of free memory for Docker and 5 GB of free disk space.

## The short way: the guided installer

Mac or Linux: open the Terminal app and run:

```bash
curl -fsSL https://github.com/PaulLaurijssens/Trellis/releases/latest/download/setup.sh | bash
```

Windows: open PowerShell (Start menu, type "PowerShell") and run:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://github.com/PaulLaurijssens/Trellis/releases/latest/download/setup.ps1 | iex"
```

Already have the Trellis folder (from the release zip or from git)? Run the installer inside it:
`bash setup.sh` on Mac or Linux, `powershell -ExecutionPolicy Bypass -File setup.ps1` on Windows.

If a step fails, the installer prints a box that starts with **"Copy this into ChatGPT, Claude or
Copilot:"** and puts the same text on your clipboard. Paste it into your assistant. It names your
system, the step, the command and the error, with passwords and keys already removed.

Something wrong later? `bash setup.sh --report` (Windows: `setup.ps1 -Report`) makes a report
you can paste into a chat or a bug report. Secrets are removed from it too.

## The full prompt

Copy everything in the box into your assistant. Change the first line if you are not on the
system it names.

```text
I want to install Trellis on my computer. Trellis is a self-hosted learning app that runs in Docker:
https://github.com/PaulLaurijssens/Trellis
My computer: [Windows 11 / macOS with Apple chip / macOS with Intel chip / Ubuntu 24.04 / ...].
I am not a technical person. Docker is new to me.

Please guide me step by step. Rules:
- One step at a time. Tell me what the step does in one or two simple sentences, then give me the
  exact command, then wait for me to paste the result.
- Ask before you install or change anything.
- Never ask for my AI key or for the contents of my .env file. I add the AI key later in the
  Trellis setup screen in my browser.
- If a step fails, explain the error in simple words and give me one thing to try.

The goal: Trellis runs, and http://localhost:8080/api/health answers {"ok": true, ...}.

The steps:
1. Docker. Check with: docker --version and docker compose version.
   Missing on Windows or Mac: install Docker Desktop from https://www.docker.com/products/docker-desktop/
   (Mac: pick Apple chip or Intel chip). Linux: Docker Engine from https://docs.docker.com/engine/install/
   plus the compose plugin, and add my user to the docker group.
2. Windows only: WSL 2. Check with: wsl --status. Missing: wsl --install --no-distribution in an
   administrator PowerShell, then restart the computer.
3. Docker running. Check with: docker info. If not, start Docker Desktop (Linux: sudo systemctl start docker)
   and wait until docker info works.
4. Memory and disk. docker info --format '{{.MemTotal}}' must be about 6 GB or more. If it is less:
   Docker Desktop > Settings > Resources > Memory (Mac), or on Windows a file %UserProfile%\.wslconfig with
   [wsl2] and memory=6GB, then wsl --shutdown and restart Docker Desktop. Also 5 GB free disk.
5. Port. Trellis uses port 8080 on this computer. If another program uses it, pick 8081 (or the next free
   one) and put TRELLIS_PORT=8081 in the .env file of step 7.
6. Download test: docker manifest inspect ghcr.io/paullaurijssens/trellis-api:latest
   If this fails with certificate, x509, TLS or proxy errors, my network blocks the download: help me
   with that first (another network, or the proxy settings in Docker Desktop).
   If it says "manifest unknown" or "denied", the ready-made images are not published yet: we build
   from the source code instead (git clone of the repository, then docker compose up -d --build --wait).
   That takes 10 to 15 minutes.
7. The Trellis folder. Use a folder named Trellis in my home folder. Download
   https://github.com/PaulLaurijssens/Trellis/releases/latest/download/trellis-bundle.zip and SHA256SUMS
   from the same place, check the SHA256 of the zip against SHA256SUMS, and unzip it (it has a folder
   named trellis inside). Copy .env.example to .env and set NEO4J_PASSWORD to a random string of 40 or
   more letters and digits. Make that string with a command; do not show it to me and do not ask me
   to type it. If .env already exists, do not change it.
8. Start, in the Trellis folder: docker compose pull, then docker compose up -d --wait.
9. Check: open http://localhost:8080/api/health (or my port). It must show "ok": true. If the
   containers run but the page gives an empty reply, run: docker compose up -d --no-build --force-recreate web
10. Open http://localhost:8080 in my browser. The Trellis setup screen asks for my name, my AI key and a
   password. I do that part myself.

At the end, tell me:
- how to start Trellis later (it starts by itself when Docker Desktop runs),
- how to stop it (docker compose stop in the Trellis folder),
- where the backups are (the backups folder inside the Trellis folder).
```

## Prompts for one step

Use these when one step is not clear, or when the installer stopped at a step. Put your system in
place of the part in brackets. For an installer stop, the box text from the installer is better:
it already has the details.

**Docker is not installed**

```text
I am on [Windows 11 / macOS with Apple chip / Ubuntu 24.04]. I want to install Docker so I can run
Trellis (a self-hosted app that runs with docker compose). Docker is new to me. Tell me what Docker
is in one sentence, where to download the right version for my computer, and what to click during
the install. Help me with this one step. Explain it in simple words.
```

**Windows: WSL 2**

```text
I am on Windows [10 / 11]. Docker Desktop needs WSL 2. When I run "wsl --status" I get:
[paste the result]
How do I install or fix WSL 2? Tell me when I need administrator rights and when I need to restart.
Help me with this one step. Explain it in simple words.
```

**Docker does not start**

```text
I am on [system]. Docker Desktop is installed, but "docker info" gives this error:
[paste the error]
What do I do to get Docker running? Help me with this one step. Explain it in simple words.
```

**Not enough memory for Docker**

```text
I am on [system] with [8 / 16] GB of memory. "docker info --format '{{.MemTotal}}'" says [number].
The app I want to run needs about 6 GB for Docker. Where do I change how much memory Docker may use,
and how do I check it worked? Help me with this one step. Explain it in simple words.
```

**Port 8080 is in use**

```text
I am on [system]. I want to run an app on port 8080, but another program already uses that port.
How do I find which program it is? Or how do I tell the app to use port 8081? The app reads
TRELLIS_PORT from a file named .env. Help me with this one step. Explain it in simple words.
```

**The download test fails**

```text
I am on [system]. This command fails:
docker manifest inspect ghcr.io/paullaurijssens/trellis-api:latest
The error is:
[paste the error, without any passwords]
Is my network or a proxy blocking it, is there no internet, or does the image not exist?
What can I try? Help me with this one step. Explain it in simple words.
```

**Getting the files and the .env file**

```text
I am on [system]. I want to download the Trellis release zip from
https://github.com/PaulLaurijssens/Trellis/releases/latest/download/trellis-bundle.zip,
check its SHA256 against the SHA256SUMS file next to it, and unzip it into a folder named Trellis
in my home folder. Then I need a .env file made from .env.example, with NEO4J_PASSWORD set to a
random string of 40 or more letters and digits that I never see. Give me the commands for my system.
Help me with this one step. Explain it in simple words.
```

**Trellis does not start**

```text
I am on [system]. In my Trellis folder, "docker compose up -d --wait" fails. "docker compose ps" shows:
[paste]
and "docker compose logs --tail 50 api" shows:
[paste, and remove any passwords or keys]
What is wrong, and what do I try first? Help me with this one step. Explain it in simple words.
```

**The page stays empty**

```text
I am on [system]. The Trellis containers run (docker compose ps shows them as Up), but
http://localhost:8080/api/health gives an empty reply or does not load. What can I check?
I read that this can help: docker compose up -d --no-build --force-recreate web
Help me with this one step. Explain it in simple words.
```

**After the install**

```text
Trellis runs on my computer in Docker, in the folder [path]. How do I stop it, how do I start it
again tomorrow, and how do I make a copy of my backups (the backups folder in that folder)?
Explain it in simple words.
```
