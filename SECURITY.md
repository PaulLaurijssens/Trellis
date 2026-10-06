# Security

Trellis stores your notes, your learning memory and an AI provider key. Please report security
problems privately, so they can be fixed before others learn about them.

## How to report

Use GitHub's private vulnerability reporting: open the **Security** tab of this repository and choose
**Report a vulnerability**. Describe what you found, how to reproduce it, and what an attacker could
do with it. Please do not open a public issue for a security problem.

This is a personal project maintained in spare time. You will get an answer as soon as possible, and
you will hear how a fix is going.

## Supported versions

Only the latest version on `main` gets security fixes.

## In scope

- Getting into a Trellis install without its password, or into another account on the same install.
- Reading or changing the stored AI key, the graph or the learning memory without being logged in.
- A generated lesson escaping its sandbox: reaching the network, the host page, cookies or storage.
- Anything in the default `docker compose` setup that exposes Trellis or its database beyond
  `127.0.0.1`.

## Out of scope

- Attacks that need someone who already controls the machine Trellis runs on.
- Installs that were exposed to the internet without HTTPS, against the advice in the README.
