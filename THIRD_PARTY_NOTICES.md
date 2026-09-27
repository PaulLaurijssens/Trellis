# Third-party notices

Trellis is licensed under the GNU AGPL-3.0 (see `LICENSE`). It contains or embeds the following works
under their own licenses. Their license texts are in `licenses/`.

| Work | Where | License |
|---|---|---|
| **/teach skill** by Matt Pocock (`mattpocock/skills`, commit `3216582`) | `backend/app/teach/vendor/mattpocock-teach/` (unmodified) and the adaptation in `backend/app/teach/skill/` | MIT, `licenses/MIT-mattpocock-teach.txt` |
| **Space Grotesk** by Florian Karsten | `frontend/public/fonts/space-grotesk-*.woff2`, embedded in `backend/app/teach/assets/trellis-lesson/*/fonts.css` | SIL Open Font License 1.1, `licenses/OFL-SpaceGrotesk.txt` |
| **Newsreader** by Production Type | `frontend/public/fonts/newsreader-*.woff2`, embedded in `fonts.css` | SIL Open Font License 1.1, `licenses/OFL-Newsreader.txt` |

Runtime dependencies (installed by Docker, not copied into this repository) are listed with their
versions in `backend/requirements.lock.txt`, `author/requirements.lock.txt` and `frontend/package-lock.json`.
The Docker images used are Neo4j Community (GPLv3), nginx (BSD-2), Node.js (MIT), Python (PSF) and
Microsoft's Playwright image (Apache-2.0, with Chromium under BSD-3).
