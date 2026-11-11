![Plex Kodi Jellyfin Sync banner](assets/banner.svg)

# Plex Kodi Jellyfin Sync

Sync movie and TV playback progress and watched status among **Plex, Kodi, and Jellyfin**. The container runs a periodic sync every 15 minutes and serves the existing Flask dashboard, webhook, status, and tracker pages on port 5000.

![Sync icon](assets/icon.svg) Plex, Kodi, and Jellyfin use the same media files. The sync script matches items by relative media path, compares each platform against its previous snapshot, and applies a single detected change to the others. Conflicting changes are reported and left for review. On Deck / Up Next is reserved for unwatched TV episodes; an unwatched movie is not labeled Up Next.

## Connections

| Platform | Authentication and read/write methods |
| --- | --- |
| Plex | Server URL and `PLEX_TOKEN`; PlexAPI reads library items and On Deck, with Plex progress endpoints for updates. |
| Kodi | MariaDB credentials for video items and bookmarks, plus authenticated JSON-RPC for the Kodi WebUI. |
| Jellyfin | Server URL and `JELLYFIN_TOKEN` / `JELLYFIN_USER_ID`; an invalid token can be refreshed with `JELLYFIN_USER` and `JELLYFIN_PW`. Jellyfin user item and user-data endpoints read and update playback state. |

All setting names remain in [`app/config/.env-template`](app/config/.env-template). Copy it to a host-mounted `/config/.env`, fill in your own credentials, and set the three media roots so the same file resolves to the same relative path on each platform. Keep `/config/.env` and the state JSON out of Git.

## Docker Compose

Edit the host paths in [`docker-compose.yml`](docker-compose.yml), then run:

```sh
docker compose up -d
docker logs -f plexkodijellyfinsync
```

The example Compose file mounts only host `/config`, `/logs`, and `/scripts` directories; `/app` comes from the image. On each container start, the entrypoint refreshes `/scripts/plexkodijellyfinsync.py` from the image. The Flask server and dashboard run from `/app/scripts`, so pulling an older image restores their earlier versions without overwriting host-mounted web files. Local edits to the mounted main script will be overwritten on startup; edits to `/scripts/flask-webhook.py` or `/scripts/dashboard.html` do not affect the image-served Web UI. If an existing container mounts `/app`, remove that mount before updating. After pulling an image, recreate the container to use it. Preserve your own `/config/.env` and `/config/.last_sync_state.json`.

The Flask server exposes `/`, `/plex`, `/sync`, `/reset`, `/status`, `/tracker`, and `/env`. Configure the Plex webhook to point to the container's reachable `http://YOUR_HOST:5000/plex` address if you use Plex webhooks.

## Edit the environment file in the Web UI

Click **Environment** on the main dashboard, or open `/env` directly. The page displays the complete mounted `/config/.env` file for editing, including passwords and tokens, and saves it without rearranging comments or blank lines. It requires HTTP Basic authentication using the existing `FLASK_USERNAME` and `FLASK_PASSWORD` from `/config/.env`. Set both to your own nonempty values before opening the editor; the built-in `admin` / `changeme` fallback cannot access it. Restart the container after saving to apply the settings. Keep the page private and use HTTPS through a reverse proxy if accessing it beyond your trusted network.

By default, the other Web UI pages and its live command socket retain their existing access behavior. **Protecting only `/env` does not protect the file**: the dashboard's command box can run shell commands. To require the same username and password across the dashboard, tracker, sync/status pages, and command socket, add this line to your host's `/config/.env` alongside `FLASK_USERNAME` and `FLASK_PASSWORD`:

```dotenv
FLASK_WEBUI_AUTH=true
```

Then restart the container. Your browser will prompt for those credentials when visiting `/`. The Plex webhook at `/plex` remains available to Plex without Basic authentication. To return to the previous Web UI access behavior, set `FLASK_WEBUI_AUTH=false` and restart; `/env` always requires credentials. Do not expose port 5000 directly to untrusted networks: when Web UI authentication is off, the command socket can access files and run commands inside the container.

See the [Changelog](CHANGELOG.md) for the exact edits and verification in each documented update.

## Notes

- The Rich console output retains the connection messages, On Deck / Next Up, each platform's Continue Watching or In Progress table, comparison, and results.
- The Web UI renders the Rich colors from web-triggered syncs and sizes new output to the current log panel width. Resizing does not reflow earlier log lines; narrow windows can scroll horizontally.
- Sync state is stored at `SYNC_STATE_FILE` (normally `/config/.last_sync_state.json`).
- The source here excludes private `.env` files and runtime logs; the template retains the original key names.
- See [LICENSE](LICENSE) for the MIT license. Plex, Kodi, and Jellyfin names and logos belong to their respective owners; this independent project is not affiliated with them.
