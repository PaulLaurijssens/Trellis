# Trellis on a server, or reachable from your phone

The default install listens only on the machine itself (`127.0.0.1:8080`). Trellis has a password
but no HTTPS of its own, so before you open it to other devices you put HTTPS in front of it. Pick
one of the two paths below. Both keep Trellis's own port private.

## Path A: your own computer + Tailscale (private, 10 minutes)

Tailscale gives your devices a private network with HTTPS. Nothing is exposed to the internet.

1. Install Tailscale on the computer that runs Trellis and on your phone: <https://tailscale.com/download>.
   Log in with the same account on both.
2. In the Tailscale admin console (<https://login.tailscale.com/admin/dns>) enable **MagicDNS** and
   **HTTPS Certificates**.
3. On the computer that runs Trellis:
   ```bash
   tailscale serve --bg 8080
   ```
   It prints an address like `https://my-laptop.tail1234.ts.net/`. Open that on your phone.
4. Optional: **Add to Home Screen** on the phone installs Trellis as an app.

The computer must be on for Trellis to work. If it sleeps, the phone gets "cannot connect" until it
wakes. A small always-on box (a Raspberry Pi 5 with 8 GB, a mini PC, or path B) solves that.

## Path B: a rented server + a domain name (reachable from anywhere)

You need: a VPS with at least 4 GB RAM (8 GB is comfortable; the lesson workbench runs a browser),
Ubuntu 24.04 or newer, and a domain name pointing at the server's IP.

1. **Install Docker** on the server (as root or with sudo):
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
2. **Get Trellis and set the database password**, exactly as in the README steps 2 and 3.
3. **Keep Trellis on the loopback address** (the default). Do not set `TRELLIS_BIND=0.0.0.0`.
4. **Put Caddy in front** for HTTPS. Caddy gets and renews the certificate by itself.
   ```bash
   sudo apt install -y caddy
   sudo tee /etc/caddy/Caddyfile >/dev/null <<'CADDY'
   trellis.example.com {
       reverse_proxy 127.0.0.1:8080
       encode gzip
   }
   CADDY
   sudo systemctl reload caddy
   ```
   Replace `trellis.example.com` with your domain. Open ports 80 and 443 in your provider's firewall;
   nothing else.
5. `docker compose up -d`, then open `https://trellis.example.com` and finish the setup screen.

### Hardening that is worth the ten minutes

- SSH: key-only login, no root login (`/etc/ssh/sshd_config`: `PasswordAuthentication no`,
  `PermitRootLogin no`).
- Automatic security updates: `sudo apt install unattended-upgrades`.
- Keep the `backups/` folder somewhere else too: `rsync -a server:trellis/backups/ ~/trellis-backups/`
  from your laptop now and then, or a cron on the server that copies it to object storage.
- Trellis's login has a rate limit (10 attempts per 10 minutes per address). Use a long password.
- The model key lives in the Trellis database on this server. Anyone who can read the server's disk
  can read it. Treat the server as you treat your laptop.

### Updating

```bash
cd trellis && git pull && docker compose up -d --build
```

A new version can add fields to the database; it never removes data. Make a backup first anyway
(*My profile → Settings → Make a backup now*).

## What Trellis does not do

- No multi-user accounts yet: one password, one learner per install. A second learner is on the roadmap.
- No e-mail, no password-reset link: the owner resets it on the server (`README: Reset a password`).
- No outbound traffic except to your model provider and to YouTube (for transcripts). The lesson
  workbench has no network access at all.
