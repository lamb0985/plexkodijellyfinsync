# Changelog

Changes are listed here with links to the corresponding GitHub commits. This file starts with the restored single-script release; earlier history is available in [GitHub's commit history](https://github.com/lamb0985/plexkodijellyfinsync/commits/main).

## 2026-11-06 — Color and size Web UI logs

[Source commit `07a8b50`](https://github.com/lamb0985/plexkodijellyfinsync/commit/07a8b50dd8e8f81b0162ae53641614421e3d76be)

### Changed

- Replaced the dashboard's plain log textarea with a monospaced log pane that safely renders Rich ANSI colors, including 24-bit colors, without displaying escape codes. Text remains selectable; narrow windows scroll horizontally.
- The browser reports its log-pane width in character columns. Web-triggered syncs use that width for newly generated Rich tables; resizing does not reflow earlier lines. A webhook uses the last width reported by a connected dashboard, if available. The shared log cannot simultaneously use different widths for multiple viewers.
- Web-triggered syncs enable colored Rich output without terminal cursor animations. The normal shell Console remains unchanged.
- The entrypoint now refreshes `flask-webhook.py` and `dashboard.html` alongside the main script in the mounted `/scripts` directory at startup. Local changes to those three files are replaced on restart. Existing Flask routes, request methods, `.env` names, sync decisions, and tracker page remain unchanged.

### Verification

- Python and shell syntax checks passed. Offline checks exercised ANSI color and control-code parsing, safe text insertion, browser resize reporting, width validation and subprocess environment, Rich color output at a measured width, and startup copying to a populated `/scripts` mount. Flask route names, paths, and methods were compared with the original.
- [GitHub Actions run 42322070548](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/42322070548) built and pushed Docker Hub `latest` and `sha-07a8b50dd8e8f81b0162ae53641614421e3d76be` at digest `sha256:e891a25218796b711f09449116c8e920364413631293923b5a81d77fb423ffdb`. No live browser or three-platform sync was run on the user's host from this workspace.

## 2026-11-06 — Align Rich report columns

[Source commit `b7014b0`](https://github.com/lamb0985/plexkodijellyfinsync/commit/b7014b0315fdffa0209541b42ac3c01c4fd9126b)

### Changed

- Movies, Shows, On Deck, and empty-state report tables now fill the same terminal width and use the same item, Plex, Kodi, Jellyfin, and status column sizes. Their titles and platform headings align across sections.
- Plex, Kodi, and Jellyfin detail tables now fill the same width with consistent title, relative path, resume, and status columns.
- This is a layout-only change; platform authentication, syncing, TV On Deck selection, Flask pages/endpoints, and `.env` names were not changed.

### Verification

- Python syntax compilation passed. The actual Rich tables were rendered offline at 84 and 100 columns with long episode paths, mixed data, and empty sections. Platform header character positions matched across all report tables without overflow. A live sync was not run.
- [GitHub Actions run 42312326756](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/42312326756) built and pushed Docker Hub `latest` and `sha-b7014b0315fdffa0209541b42ac3c01c4fd9126b` at digest `sha256:b0fb9d30ed44fc69653858d2b06cf371269f2d19f36116add7128f0a65374b09`.

## 2026-11-06 — Group sync logs into Movies, Shows, and On Deck

[Source commit `26daceb`](https://github.com/lamb0985/plexkodijellyfinsync/commit/26daceb88c7c47100627b76212b516020361299b)

### Changed

- The initial Rich output now prints a **Movies** section, then **Shows**, then the TV episode **On Deck | Next Up** table. Original Plex, Kodi, and Jellyfin detail-table titles and item columns are retained.
- Sync Comparison and Sync Results now each print separate **Movies**, **Shows**, and **On Deck** tables in that order. Their Plex, Kodi, and Jellyfin headings are right aligned.
- Empty sections display **No In Progress Movies**, **No In Progress Shows**, or **No On Deck** in the item column. On Deck includes unwatched TV episodes at zero progress with no platform reporting watched; unwatched movies remain in the Movies category.
- The Shows progress section now displays fetched `episode` items as well as `show` items.

### Verification

- Python syntax compilation passed. The actual Rich rendering functions were exercised offline with mixed movie/episode data and with empty inputs; order, empty messages, platform columns, and TV-only On Deck classification were checked.
- The sync and backend functions outside reporting were checked unchanged against the uploaded original. [GitHub Actions run 42311251684](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/42311251684) built and pushed Docker Hub `latest` and `sha-26daceb88c7c47100627b76212b516020361299b` at digest `sha256:5eaf04fa756b22b34309f84b91af6064590211c1d2c60f405d8595ee0b0e6406`. No live Plex/Kodi/Jellyfin sync was run in this workspace.

## 2026-11-04 — Refresh the mounted main script at container startup

[Source commit `2a41d97`](https://github.com/lamb0985/plexkodijellyfinsync/commit/2a41d97369d66b70fb9ffd360ce2fa21515df6f2)

### Changed

- Removed the host `/app` bind mount from `docker-compose.yml`. The application source now comes from the image; the example still mounts `/config`, `/logs`, and `/scripts` from the host.
- The entrypoint now copies `/app/scripts/plexkodijellyfinsync.py` over `/scripts/plexkodijellyfinsync.py` on **every container start**, including when `/scripts` is already populated, and sets the file owner for the configured user.
- Updated the README with the upgrade step: remove any existing `/app` bind mount, pull the new image, then recreate the container. Local edits to the mounted main script are replaced at startup.

### Verification

- The entrypoint passed `sh -n`. An isolated shell check exercised its copy block with both populated and empty `/scripts` directories and confirmed that the image script replaced an older mounted copy.
- The main Python script, Flask server, webpages, log formatting, and `.env` variable names were not changed in this commit. [GitHub Actions run 41770308933](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/41770308933) built and pushed both `latest` and the commit-specific Docker Hub tag. A live three-platform sync and container startup on the user's host were not run from this workspace.

## 2026-11-04 — Restore original script and keep unwatched movies out of Up Next

[Source commit `555f8ee`](https://github.com/lamb0985/plexkodijellyfinsync/commit/555f8ee354b37fa6d3cd5e3dcdce5128e9bfa1cf)

### Changed

- Restored `app/scripts/plexkodijellyfinsync.py` from the uploaded original, single-file script and removed the five `sync_*.py` modules from the prior rewrite.
- In the Rich **Sync Comparison** and **Sync Results** tables, zero-progress movies now show the normal matching status (`✔` or `✅`) instead of the `🌱` On Deck marker. Unwatched TV episodes retain `🌱`.
- In `app/scripts/tracker.html`, **Up Next** requires an unwatched episode and excludes unwatched movies and watched episodes. Episode detection uses the reported `media_type`. Movie badges at zero progress say **Unwatched**; qualifying episode badges say **Up Next**.
- Corrected the README's host-mounted `/scripts` upgrade instructions to point to the restored single script.

### Scope and verification

- The Flask server, dashboard, setup pages, Dockerfile, Compose file, entrypoint, dependencies, and `.env` setting names were not changed in this release.
- Python syntax compilation passed. Offline checks exercised the original Rich reporting functions and the tracker JavaScript with sample movie and episode data. The Docker image build and push workflow succeeded. A live sync against Plex, Kodi, and Jellyfin was not run from this workspace.
- For installations that mount host `/scripts`, copy the updated `app/scripts/plexkodijellyfinsync.py` into that host directory. Pulling the image alone does not replace files behind the mount.
