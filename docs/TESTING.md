# Testing a release by hand

The goal: a new person gets from nothing to the first concept on the map in under 20 minutes, and a
wrong key, endpoint or quota is caught on the setup screen with a plain reason. Use a computer (or a
virtual machine) that has never run Trellis. Write down what you see, not what you expected.

## What to record

For every scenario:

- **Version**: the release (for example `0.4.0`), from `docker compose images` or the release page.
- **Computer**: operating system and version, processor (Intel, AMD or Apple), memory.
- **Docker**: Docker Desktop or Docker Engine, and its version (`docker version`).
- **Network**: home, office, school, VPN, proxy.
- **Time**: start time, and the time at each step below.
- **Result**: pass or fail. For a fail: the exact error text (copy it, or take a screenshot), and
  what you did just before.
- **Report**: when something fails, run the installer with `--report` (Windows: `-Report`) and attach
  the file. It hides passwords and keys.

Never paste an API key, a password or the contents of `.env` in an issue.

Report problems with the [bug report form](https://github.com/PaulLaurijssens/Trellis/issues/new/choose).

## Scenarios

### 1. Fresh install with the installer

- [ ] Install Docker Desktop and start it (record the time this takes).
- [ ] Run the one-line installer from the README (Windows: PowerShell; Mac or Linux: Terminal).
- [ ] Each question of the installer is clear. Note any word you did not understand.
- [ ] The installer ends with the address, and <http://localhost:8080> opens the setup screen.
- [ ] Record the time from the installer start to the setup screen.

### 2. Setup with a good key

- [ ] Choose a provider and paste a working key.
- [ ] The key test passes for all three models.
- [ ] Finish the setup and log in.
- [ ] Add a source (for example a Topic or a YouTube link) and accept the concepts.
- [ ] The first concept is on the map. Record the total time since the start of scenario 1.

### 3. Setup with a wrong key or a wrong provider

Try each one that you can. The setup screen must stop you with a plain reason, in the language you
chose, and must not show the key.

- [ ] A key with a typo.
- [ ] A key from another provider (for example a Gemini key under OpenAI).
- [ ] An Azure or Microsoft Foundry key under the OpenAI preset. The screen suggests **Other**.
- [ ] A key without credit or on a free plan (for example a Gemini free key for the Pro model). The
      screen explains it, and for Gemini offers the Flash model.
- [ ] **Other** with a wrong model id or a wrong endpoint.
- [ ] **Other** with a wrong embedding size. The screen tells the real size.

### 4. Change the provider after setup

- [ ] *My profile → Settings → AI provider* shows the current provider and the last characters of
      the key, never the whole key.
- [ ] Change the key to a wrong one: the test fails and the old key stays.
- [ ] Change it back to a good key: the test passes and the mentor answers.

### 5. Errors during use

- [ ] When the provider is busy or the quota is used up, the message says so in the language of the
      interface (not "HTTP 500").

### 6. Restart, sleep and repair

- [ ] Restart the computer. Trellis comes back when Docker runs.
- [ ] Let the computer sleep for 30 minutes or more. Trellis still opens. If it does not, run
      `docker compose up -d --force-recreate web` or the installer again, and record which one helped.
- [ ] Run the installer a second time. It says Trellis is installed and running, and changes nothing.
- [ ] Run the installer with `--report` (Windows: `-Report`). The report has no password or key.

### 7. Your memory: export, import, connect an AI

- [ ] After a few conversations, open *My profile → Memory*. Search, filter and open a concept. Correct
      something (your assessment, the summary, a difficulty) and check that the Learn view shows it.
- [ ] *Your data → Download memory*. Open the zip: `README.md` explains it, `concepts/` opens as an
      Obsidian vault, `memory.json` has no password or API key.
- [ ] *Import memory* with the same file: the preview says everything is already there.
- [ ] On a second install (or a second learner), import the file: the preview lists what is new;
      after *Import*, the Memory tab shows the concepts and the mentor knows what you discussed.
- [ ] *Connect an AI*: create a key, add it to Claude Code or another MCP client (docs/MCP.md) and ask
      "what do I understand about <a concept>?". Revoke the key: the client gets refused.

### 8. Optional: a filtered network

- [ ] On an office, school or VPN network: does the installer download Trellis? If not, is the
      message clear about what to check?
