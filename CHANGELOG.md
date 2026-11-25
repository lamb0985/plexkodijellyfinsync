# Changelog

Changes are listed here with links to the corresponding GitHub commits. This file starts with the restored single-script release; earlier history is available in [GitHub's commit history](https://github.com/lamb0985/plexkodijellyfinsync/commits/main).

## 2026-11-24 — Add live sync summary to shared header

- Place Continue Watching, On Deck, and Platforms Aligned counts between the linked banner and controls on Dashboard, Logs, Status, and Env. The counts read the existing `/status` saved state, refresh while the page is visible, and use the Dashboard's in-progress and up-next criteria.
- Wrap the header sections in narrower Organizr frames without horizontal clipping. Keep media platform colors and log formatting unchanged.
- Render Dashboard media type icons in Dracula white rather than pink.

Rollback: `a6545e36481f030d686645a268ca7a7fe333f32c` (`rollback/pre-header-summary-20261124`). The previous Docker image remains available as `lamb0985/plexkodijellyfinsync:sha-a6545e36481f030d686645a268ca7a7fe333f32c`.

## 2026-11-24 — Use project banner in every header

- Replace the small icon and text title on Dashboard, Logs, Status, and Env with the supplied banner image.
- Make the banner open the project's GitHub home page in a new tab; scale it without cropping in narrow frames.

Rollback: `05f3d8f96aaecc7c718a5586452b0304f40775db` (`rollback/pre-banner-header-20261124`).

## 2026-11-24 — Compact Dashboard and popup settings

- Put media titles alongside Plex, Kodi, and Jellyfin progress on wide screens; stack the row in narrow Organizr frames.
- Match platform accents to the Logs ANSI palette: Plex yellow, Kodi cyan, Jellyfin purple. Show SYNC in white.
- Give the same navigation and action buttons depth on all four pages.
- Open Status and Env in dialogs from the header. Keep their existing endpoints, status polling, .env form, CSRF and conflict checks available directly and inside dialogs.

Rollback: `347347f4ccf77fe94a9c92262bd57501f7eec9f6` (`rollback/pre-compact-popups-20261124`).

## 2026-11-23 — Refine Dashboard and Web UI surfaces

### Changed

- Apply one shared Dracula UI stylesheet to Dashboard, Logs, Status, and Env. The header, controls, spacing, and workspace surfaces now use the same rules across page endpoints.
- Replace the Dashboard's nested card framing with compact, separated media rows. Keep each platform's color in its label and progress bar, with the time and duration on one line.
- Give Logs a quieter console frame while preserving ANSI log colors, live updates, and automatic log width calculation.
- Remove the unused command input on Logs and its server-side `run_cmd` socket handler. Sync and Reset remain available in the header.

### Rollback

- Previous commit: `96abb92efd54bfa8a7a8cc8fc3be5475ddbaae8c`.

## 2026-11-23 — Make headers consistent across page endpoints

### Fixed

- Give Dashboard, Logs, Status, and Env the same header button dimensions, spacing, and responsive logo size.
- Restore Dracula green for Sync and functional red for Reset on all four pages. Older page-specific CSS rules had overridden those colors outside Logs.
- Keep the platform title accents and log output colors unchanged.

### Rollback

- Previous commit: `6958cc3d71647290ea7290fcdfd0f29ff3a6b53c` (branch `rollback/pre-header-style-consistency-20261123`).

## 2026-11-23 — Refine Web UI header controls

### Changed

- Color the PLEX, KODI, and JELLYFIN title words with their existing platform accents; color SYNC with Dracula green.
- Place Dashboard, Logs, Status, and Env in one group of equal-shape navigation buttons. Keep Sync and Reset together at the far right on every page, with a deliberate wrap for narrow Organizr views.
- Use the Dracula UI palette for header surfaces and floating controls, Current Line borders, Functional Purple for active/focus states, and Functional Red for Reset. Log output and media platform colors are unchanged.

### Rollback

- Previous source/image commit: `15fae812c0d7c5517ea38a795892d753029fc44a` (`sha-15fae812c0d7c5517ea38a795892d753029fc44a`).

## 2026-11-23 — Repair Dashboard route and log layout

### Fixed

- Added the explicit `/dashboard` route and pointed every Dashboard control to it while keeping `/` available. Updated the `FLASK_TRACKER` example URL without renaming the setting.
- Restored the prior Logs page colors and panel styling. Saved Rich tables keep their original line breaks; new manual sync output uses the measured log width, while unattended syncs use a 160-column baseline.
- Published the compact card layout together with all route and visual changes in one image build, avoiding intermediate image revisions with mismatched pages. The playback Dashboard has no file path or percentage line.

### Rollback

- Git branch: `rollback/pre-dashboard-and-log-layout-fix-20261123` at `0b000c6ad1b0c5e432a562725edce777b176e8bf`.
- Previous published image: `lamb0985/plexkodijellyfinsync:sha-e32c4fde4973d1173082a71defdb7ed2cf003a0d`. Preserve mounted `/config`, `/logs`, and `/scripts`.

## 2026-11-23 — Unified Dracula Web UI and compact dashboard

### Changed

- Moved playback tracking to `/` and live logs to `/logs`; updated page navigation and documentation. The old `/tracker` route is intentionally removed.
- Added the same logo, **PLEX KODI JELLYFIN SYNC** heading, and Dashboard, Logs, Sync, Status, Reset, Env controls to each page. The controls wrap on narrow embedded views.
- Removed file paths and repeated percentage text from Dashboard cards. Playback time and total duration now share one line. Retained each platform's existing top border and progress colors.
- Matched the **Continue Watching | In Progress** and **On Deck | Up Next** section heading format.
- Applied Dracula Classic colors to the Web UI chrome while preserving platform colors and ANSI log colors.

### Rollback

- Git branch: `rollback/pre-dracula-unified-header-20261123` at `50a70f16963a3a0a92c31c7e75ac47a795c58381`.
- To restore the prior image, deploy Docker Hub tag `sha-50a70f16963a3a0a92c31c7e75ac47a795c58381` after its workflow has published it, or rebuild from that branch. Preserve mounted `/config`, `/logs`, and `/scripts`.

## 2026-11-23 — Display blank log rows in Dashboard

[Source commit `ff9e051`](https://github.com/lamb0985/plexkodijellyfinsync/commit/ff9e05140b1795666e2e8c7c9451e7057e68f154)

### Changed

- Dashboard's ANSI renderer already created an empty `div` for each blank log line, but those elements collapsed to zero height. Empty log rows now occupy one line height, preserving category spacing in existing saved logs and future sync output. Log colors and horizontal scrolling are unchanged.

### Verification and rollback

- Checked that blank rows use the new line-height rule while the renderer still creates one row per source line. Dashboard inline JavaScript passed `node --check`. A live browser inside Organizr was not available for visual verification.
- [GitHub Actions run 45255586271](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/45255586271) built and pushed Docker Hub `latest` and `sha-ff9e05140b1795666e2e8c7c9451e7057e68f154` at digest `sha256:8f7d45023a96820858d4335034b70c1e281eb7982d51157127d930438e6cb17e`.
- Previous image rollback tag: `sha-b024d2a62f1a0006629c964c026120f2c4500928`.

## 2026-11-23 — Restore spacing between log categories

[Source commit `b024d2a`](https://github.com/lamb0985/plexkodijellyfinsync/commit/b024d2a62f1a0006629c964c026120f2c4500928)

### Changed

- Added one more blank line between Movies, Shows, and On Deck | Next Up in the initial platform report, Sync Comparison, and Sync Results. Each category title remains immediately above its table, and the compact full-width table layout remains in place.

### Verification and rollback

- Python compilation passed. Actual Rich reports rendered at 84 and 120 columns, confirming nine left-aligned section headings, no blank line below each heading, and two blank lines between categories. No live three-server sync was run.
- [GitHub Actions run 45253981460](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/45253981460) built and pushed Docker Hub `latest` and `sha-b024d2a62f1a0006629c964c026120f2c4500928` at digest `sha256:a5c0f14d7cc021d43f5f74ec43faf4bf0e5623416e29de8f39bfabb2aa9492f3`.
- Previous image rollback tag: `sha-3cfae5851406f8c222e3b9b5598650672270fe81`.

## 2026-11-23 — Align log sections and retain measured output width

[Log layout commit `fc596b3`](https://github.com/lamb0985/plexkodijellyfinsync/commit/fc596b3f1888b3fc27116cfaa2fbaead39295d85) · [Cross-page width correction `3cfae58`](https://github.com/lamb0985/plexkodijellyfinsync/commit/3cfae5851406f8c222e3b9b5598650672270fe81)

### Changed

- Removed Dashboard's Activity heading, description, and Live log badge, leaving the Live Logs toolbar and colored log pane.
- Left-aligned the initial Movies, Shows, and On Deck | Next Up headings and platform table titles. Comparison and Results use icon-before-title headings for all three categories, with the full On Deck | Next Up label. Compact Rich tables remove the extra blank line between each section title and its platform columns.
- Fixed a width regression in Sync/Reset controls on Tracker, Environment, and Status. These pages now measure the current viewport's dashboard-equivalent log width and pass `columns` to the existing endpoints. Dashboard still measures its actual log pane. Existing saved output retains its original width; new sync output uses the measured width at action time.

### Verification and rollback

- Python syntax passed. Actual Rich report functions rendered at 84 and 120 columns with left-aligned section headings and no blank line below them. Dashboard log and command controls remained. JavaScript syntax passed for Tracker, Environment, and Status; width calculation was checked at 500, 900, and 1700 pixels. No live Organizr or three-server sync was run.
- [Log layout build 45251229523](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/45251229523) pushed `sha-fc596b3f1888b3fc27116cfaa2fbaead39295d85` at digest `sha256:6af3909e5c653aa2f1969d0ddcaa7805cd47714d5d0e5eb9e13da21f35f70478`.
- [Final GitHub Actions run 45251706016](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/45251706016) pushed Docker Hub `latest` and `sha-3cfae5851406f8c222e3b9b5598650672270fe81` at digest `sha256:b699856596eb446e9ccffda2e1837f98e3576d05e09e6223f966e61595c87d6a`.
- Previous image rollback tag: `sha-fc596b3f1888b3fc27116cfaa2fbaead39295d85`. To roll back both changes, use `sha-191787115be92c38680647255cabe828e18b19e7`.

## 2026-11-23 — Prune cleared movies and align log section icons

[Source commit `1917871`](https://github.com/lamb0985/plexkodijellyfinsync/commit/191787115be92c38680647255cabe828e18b19e7) · [Previous source commit `e9890c1`](https://github.com/lamb0985/plexkodijellyfinsync/commit/e9890c1dce6e668a722998e77796ca33c7cd1a2e)

### Changed

- Fully unwatched movie entries with zero resume on Plex, Kodi, and Jellyfin are removed from saved sync state. Previously their saved IDs caused exact lookups on later runs and they could reappear as all-`-` rows in Sync Results, as reported for Alpha and Ant-Man. The refreshed results also omit these resolved movies after a run. Episodes on deck, in-progress items, mixed watched/unwatched status, and watched cleanup retain their existing behavior.
- Sync Comparison and Sync Results now put `🎬`, `📺`, and `🌱` before Movies, Shows, and On Deck, matching the earlier log sections.

### Verification and rollback

- Python compilation passed. Isolated state load/save checks verified zero-resume unwatched movies are removed and on-deck episodes, in-progress, watched, and mixed states remain. Both report functions were checked for matching icon-before-title headings. The pasted log does not contain Alpha and Ant-Man's saved status fields, so this specific fixture reflects the resolved zero-resume unwatched condition; no live three-server sync was run.
- [GitHub Actions run 45249280749](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/45249280749) built and pushed Docker Hub `latest` and `sha-191787115be92c38680647255cabe828e18b19e7` at digest `sha256:ea1b9dc8aadc70159baf5b543c3b41d1f6dd0dea89e00eebd7a7e3d9fa0da15b`.
- Previous image rollback tag: `sha-9e5e583735d89d584b6ba1a24f32f0be5fa989ed`.

## 2026-11-23 — Move Status into the page navigation

[Source commit `9e5e583`](https://github.com/lamb0985/plexkodijellyfinsync/commit/9e5e583735d89d584b6ba1a24f32f0be5fa989ed) · [Previous source commit `081417c`](https://github.com/lamb0985/plexkodijellyfinsync/commit/081417c8cade0894c2fca259d05e29b1c6cfb2a5)

### Changed

- Dashboard, Tracker, Environment, and Status now appear together in the same navigation bar on every page. The header retains Sync now and Reset. Removed the dashboard's inline status panel and Tracker/Environment status dialogs.
- Added `GET /status-page` for a dedicated status page with the shared header, a Copy control, and automatic five-second refresh. The existing `GET /status` JSON endpoint and its response format remain unchanged.

### Verification and rollback

- Checked all four pages' navigation and header controls, dashboard log/command elements, status data fetch, and Environment form fields. Python compilation and inline JavaScript syntax checks passed. No live Organizr or three-server sync test was run.
- [GitHub Actions run 45247233193](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/45247233193) built and pushed Docker Hub `latest` and `sha-9e5e583735d89d584b6ba1a24f32f0be5fa989ed` at digest `sha256:6642899eac0baf08b995e958c76581c5bf06e9411a447c5a0aa7877f570c000c`.
- Previous image rollback tag: `sha-6fb57caf934c0e59db319b0babe0d369cb473795`.

## 2026-11-23 — Unify page navigation and simplify Dashboard

[Source commit `6fb57ca`](https://github.com/lamb0985/plexkodijellyfinsync/commit/6fb57caf934c0e59db319b0babe0d369cb473795) · [Previous source commit `9703d40`](https://github.com/lamb0985/plexkodijellyfinsync/commit/9703d40edf9b8d11fbcc43a5d2e5ed929e7ad97a)

### Changed

- Tracker and Environment now display the same logo/header area, Dashboard/Tracker/Environment navigation, and Sync now, Reset, and Status controls in the same positions as Dashboard. Status opens an on-page JSON dialog with Copy; Tracker refreshes its entries after a Sync or Reset. The Environment editor and dashboard command field remain available.
- Removed the four summary counters from Dashboard, leaving more space for the colored log. The log pane grows with viewport height and scrolls horizontally for long lines.
- Constrained the dashboard grid and card to the available frame width to prevent long log lines from widening the page and clipping its right margin inside Organizr. Tracker and Environment use the same full-width content gutters.

### Verification and rollback

- HTML structure, navigation, actions, dashboard log and command controls, and Environment form fields were checked. Inline JavaScript passed `node --check` for all three pages. A local Chromium visual check was blocked by this environment; the layout has not been verified in the user's Organizr instance.
- [GitHub Actions run 45245772864](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/45245772864) built and pushed Docker Hub `latest` and `sha-6fb57caf934c0e59db319b0babe0d369cb473795` at digest `sha256:0dad0bfa99db0959fd039f0d6edfaad64d41a5268b1c42a53cae62853e668e19`.
- Previous image rollback tag: `sha-2124859cb3bbe2efb14efb6d4676b1d4b63d08d4`.

## 2026-11-23 — Show saved logs when the dashboard opens

[Source commit `2124859`](https://github.com/lamb0985/plexkodijellyfinsync/commit/2124859cb3bbe2efb14efb6d4676b1d4b63d08d4) · [Previous source commit for rollback `c19324d`](https://github.com/lamb0985/plexkodijellyfinsync/commit/c19324da87a428826e91526343e2469c72d2037f)

### Changed

- The dashboard fetches a bounded tail of the saved `/logs/flask.log` immediately and every five seconds, so previous sync output appears without starting a new sync. The new authenticated `GET /api/logs` returns plain text with caching disabled.
- The existing safe ANSI parser still renders Rich colors. A snapshot refresh avoids duplicate lines, preserves the user's scroll position while reading earlier output, and refreshes summary counts when the log changes. Command execution and its Socket.IO connection remain available.

### Verification and rollback

- Python compilation and dashboard JavaScript syntax checks passed. Isolated route checks covered ANSI bytes, a missing log file, and bounded history. No live browser or three-server sync was run.
- [GitHub Actions run 45243716752](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/45243716752) built and pushed Docker Hub `latest` and `sha-2124859cb3bbe2efb14efb6d4676b1d4b63d08d4` at digest `sha256:5b0cffc8c7828b26a981b84641f453ebe0a2157e25d6574d58a55c908e769c6f`.
- Previous image rollback tag: `sha-18e96b707a02f5b62d7f2d00607699825607e2fa`.

## 2026-11-23 — Restyle Web UI with Plex EPG theme

[Source commit `28b1910`](https://github.com/lamb0985/plexkodijellyfinsync/commit/28b191084579f077131002838fd8e8ca68d5e599) · [Tracker path correction `18e96b7`](https://github.com/lamb0985/plexkodijellyfinsync/commit/18e96b707a02f5b62d7f2d00607699825607e2fa)

### Changed

- Restyled the dashboard, Tracker, and Environment pages using the Plex EPG Dracula palette, card layout, header treatment, and the existing Plex Kodi Jellyfin Sync logo. The logo is embedded in the pages; the source image assets were not altered.
- Kept dashboard Sync, Reset, Status/Copy, live colored logs, measured log width, and command input; kept Tracker's existing status parsing and platform progress; kept the authenticated `/env` editor, CSRF fields, and file contents form.
- Added dashboard summary counts derived from the existing `/status` response. The `/tracker` route now serves the bundled page before a host-mounted fallback, so old `/scripts/tracker.html` copies cannot hide the new design. Route URLs and methods, sync decisions, and API names remain the same.

### Verification and rollback

- HTML IDs, navigation links, dashboard controls, Environment form fields, and embedded logo were checked; the inline dashboard and Tracker JavaScript passed `node --check`. A live browser and three-server sync were not run.
- [Final GitHub Actions run 45242374856](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/45242374856) built and pushed Docker Hub `latest` and `sha-18e96b707a02f5b62d7f2d00607699825607e2fa` at digest `sha256:f319af32c92f8acaad635ff1886fdd2e53fffd1f983d21471c9bf24799754203`. The earlier UI-only build is retained as `sha-28b191084579f077131002838fd8e8ca68d5e599`.
- Previous image rollback tag: `sha-2f18a8c1a53a8867597362f621aa5d2ee2ecf97c`.

## 2026-11-12 — Reuse refreshed Jellyfin token on subsequent syncs

[Source commit `e2e389e`](https://github.com/lamb0985/plexkodijellyfinsync/commit/e2e389ef4b40ee87720fe7133040e9ea55a8dc79) · [Previous commit for rollback `f95e1b1`](https://github.com/lamb0985/plexkodijellyfinsync/commit/f95e1b11032f70b0e219025d14309dc410b56531)

### Changed

- Jellyfin authentication now reads `JELLYFIN_TOKEN` and `JELLYFIN_USER_ID` directly from `/config/.env` at the start of each sync. A Web UI sync no longer reuses token values inherited from the long-running Flask process after the prior sync has reauthenticated.
- The existing 401 reauthentication and `.env` rewrite remain in place. No other authentication, playback sync, Flask routes, or environment variable names changed.

### Verification and release

- Python syntax compilation passed. An isolated authentication test with a stale inherited token confirmed that the file's token is used, a rejected file token is replaced through the existing login flow, and the next attempt uses the newly saved token without another login. No live three-server sync was run.
- [GitHub Actions run 43333182677](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/43333182677) built and pushed Docker Hub `latest` and rollback tag `sha-e2e389ef4b40ee87720fe7133040e9ea55a8dc79` at digest `sha256:0876e202eea90cad3f54a27f10cc8ddef33a938f5256e0a36699c9fab9870f1f`. To return to the previous image, use `sha-4c1e2f5bc5e0414739ccb0697640cff054cedcb6` (the prior source commit `f95e1b1` only changed this changelog, so it did not publish an image).

## 2026-11-10 — Add Web UI environment editor

[Source commit `4c1e2f5`](https://github.com/lamb0985/plexkodijellyfinsync/commit/4c1e2f5bc5e0414739ccb0697640cff054cedcb6)

### Changed

- Added an **Environment** button and a dedicated authenticated `/env` page to view and edit the complete host-mounted `/config/.env`. Saves validate .env syntax, reject stale forms, preserve existing file permissions and layout, and use an atomic replacement. Restart the container after saving to apply edits.
- Added optional `FLASK_WEBUI_AUTH=true` to require the existing `FLASK_USERNAME` and `FLASK_PASSWORD` on the dashboard, tracker, sync/status pages, and Socket.IO command connection. It defaults to off so existing page access stays the same; `/env` always requires configured credentials. Plex webhook `POST /plex` remains available without Basic authentication.
- Documented the security limitation of leaving the dashboard command socket open and the exact steps to enable Web UI authentication. Existing .env names, sync code and logic, log formatting, and existing route paths and methods were not changed.

### Verification

- Python syntax compilation passed. Isolated Flask and Socket.IO tests checked both authentication modes, the editor's read/write access, CSRF rejection, stale-form rejection, invalid syntax rejection, HTML escaping, comment preservation and file permissions, and webhook access. Existing route paths and methods were compared with the previous source. No live sync or browser test on the user's host was run.
- [GitHub Actions run 42935582087](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/42935582087) built and pushed Docker Hub `latest` and `sha-4c1e2f5bc5e0414739ccb0697640cff054cedcb6` at digest `sha256:5d39eb730cf760fa9628c181b566889d1fabf6a81634fb418aaef4c2f70f6d58`.

## 2026-11-10 — Simplify comparison and results headings

[Source commit `5ad62d5`](https://github.com/lamb0985/plexkodijellyfinsync/commit/5ad62d52ca0573ebf7131968a0311d5e1c63904b)

### Changed

- **Sync Comparison** and **Sync Results** now each have one centered main heading. Movies, Shows, and On Deck appear as left-aligned labels above their existing tables, in that order.
- Platform columns, item rows, empty-state wording, status symbols, sync decisions, authentication, `.env` names, and Flask pages/endpoints remain unchanged.

### Verification

- Python syntax compilation passed. The actual Rich report functions rendered offline at 84 and 120 columns with mixed Movies, Shows, On Deck, and empty data; the single heading and labels were checked without overflow. No live three-platform sync was run.
- [GitHub Actions run 42930222234](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/42930222234) built and pushed Docker Hub `latest` and `sha-5ad62d52ca0573ebf7131968a0311d5e1c63904b` at digest `sha256:ad8be5fff7e6a1cbfb1745b5b6a4f841e522872341d3ecb9fb8893148a2270c4`.

## 2026-11-06 — Serve Web UI from image for clean rollback

[Source commit `f4b2083`](https://github.com/lamb0985/plexkodijellyfinsync/commit/f4b208361b3ac1b0436fce1d602b7a586801f948)

### Changed

- Flask now runs from `/app/scripts/flask-webhook.py` in the image, and its dashboard loads the image's `dashboard.html`. Startup still refreshes only the main sync script in the host-mounted `/scripts`; it leaves mounted Flask and dashboard files untouched.
- The tracker route continues to prefer the host-mounted `/scripts/tracker.html`, preserving that page and its existing URL. Existing Flask route paths, methods, `.env` names, and sync logic remain unchanged.
- Changing to an older image tag now changes the image-served Web UI code. If the short-lived `sha-07a8b50dd8e8f81b0162ae53641614421e3d76be` image was already started, it may have overwritten host-mounted web files; restoring those files may be needed before using an older image that launches Flask from `/scripts`.

### Verification

- Shell and Python syntax checks passed. An isolated startup check confirmed only the main script is copied into a populated `/scripts` directory. Flask route paths and methods were checked unchanged, and the tracker lookup still checks the mounted page first.
- [GitHub Actions run 42322384815](https://github.com/lamb0985/plexkodijellyfinsync/actions/runs/42322384815) built and pushed Docker Hub `latest` and `sha-f4b208361b3ac1b0436fce1d602b7a586801f948` at digest `sha256:9f8282a224f74572928e076ff8dcce6ef6266ea030ce9e2e4b596d0d846bbfe5`. No live sync or browser session on the user's host was run from this workspace.

## 2026-11-06 — Color and size Web UI logs

[Source commit `07a8b50`](https://github.com/lamb0985/plexkodijellyfinsync/commit/07a8b50dd8e8f81b0162ae53641614421e3d76be)

### Changed

- Replaced the dashboard's plain log textarea with a monospaced log pane that safely renders Rich ANSI colors, including 24-bit colors, without displaying escape codes. Text remains selectable; narrow windows scroll horizontally.
- The browser reports its log-pane width in character columns. Web-triggered syncs use that width for newly generated Rich tables; resizing does not reflow earlier lines. A webhook uses the last width reported by a connected dashboard, if available. The shared log cannot simultaneously use different widths for multiple viewers.
- Web-triggered syncs enable colored Rich output without terminal cursor animations. The normal shell Console remains unchanged.
- This intermediate image copied `flask-webhook.py` and `dashboard.html` alongside the main script into mounted `/scripts` at startup. **Superseded by the image-served Web UI change above.** If this image was started, those two host files may have been overwritten. Existing Flask routes, request methods, `.env` names, sync decisions, and tracker page remained unchanged.

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
