# Changelog

Changes are listed here with links to the corresponding GitHub commits. This file starts with the restored single-script release; earlier history is available in [GitHub's commit history](https://github.com/lamb0985/plexkodijellyfinsync/commits/main).

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
