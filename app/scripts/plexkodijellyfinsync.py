# ─── Standard Library ──────────────────────────────────────────────────────────
import os
import json
import time
import traceback
import argparse
from pathlib import Path
from datetime import timedelta
from datetime import datetime

# ─── Third-Party Libraries ─────────────────────────────────────────────────────
import requests
import pymysql
from dotenv import load_dotenv, set_key, dotenv_values
from requests.auth import HTTPBasicAuth
from plexapi.server import PlexServer
from collections import defaultdict

# ─── Terminal UI ───────────────────────────────────────────────────────────────
from rich.console import Console
from rich.pretty import Pretty
from rich.panel import Panel
from rich.table import Table
from rich.traceback import install
from rich.columns import Columns
from rich.text import Text
from rich import box, print

# ─── Setup ─────────────────────────────────────────────────────────────────────
install(show_locals=True)
console = (Console(force_terminal=False, color_system="truecolor")
           if os.getenv("PKJSYNC_WEB_LOG") == "1" else Console())

# Load environment from .env
load_dotenv("/config/.env")
env_path = Path("/config/.env")

# ─── Environment Variables ─────────────────────────────────────────────────────

# Plex
PLEX_SERVER = os.getenv("PLEX_SERVER", "")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")
PLEX_MEDIA_ROOT = os.getenv("PLEX_MEDIA_ROOT", "")
PLEX_EXCLUDE_LIBRARIES = [l.strip() for l in os.getenv("PLEX_EXCLUDE_LIBRARIES", "").split(",") if l.strip()]

# Kodi
KODI_DB_HOST = os.getenv("KODI_DB_HOST", "")
KODI_DB_PORT = int(os.getenv("KODI_DB_PORT", "3306"))
KODI_DB_USER = os.getenv("KODI_DB_USER", "")
KODI_DB_PASSWORD = os.getenv("KODI_DB_PASSWORD", "")
KODI_DB_NAME = os.getenv("KODI_DB_NAME", "")
KODI_WEBUI_RPC = os.getenv("KODI_WEBUI_RPC", "")
KODI_WEBUI_RPC_USER = os.getenv("KODI_WEBUI_RPC_USER", "")
KODI_WEBUI_RPC_PASSWORD = os.getenv("KODI_WEBUI_RPC_PASSWORD", "")
KODI_MEDIA_ROOT = os.getenv("KODI_MEDIA_ROOT", "")

# Jellyfin
JELLYFIN_SERVER = os.getenv("JELLYFIN_SERVER", "")
JELLYFIN_TOKEN = os.getenv("JELLYFIN_TOKEN", "")
JELLYFIN_USER_ID = os.getenv("JELLYFIN_USER_ID", "")
JELLYFIN_USER = os.getenv("JELLYFIN_USER", "")
JELLYFIN_PW = os.getenv("JELLYFIN_PW", "")
JELLYFIN_MEDIA_ROOT = os.getenv("JELLYFIN_MEDIA_ROOT", "")

# Misc
SYNC_STATE_FILE = os.getenv("SYNC_STATE_FILE", "")

# ─── Utility Functions ─────────────────────────────────────────────────────────

# Format seconds into a human-readable time string (e.g., 1:23:45 or 12:34)
def format_time(seconds):
    if not seconds:
        return "-"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

# Convert absolute path to relative based on media root directory
def normalize_path(path: str, media_root: str) -> str:
    try:
        return os.path.relpath(path, media_root).replace("\\", "/")
    except Exception:
        return path

# Convert relative path back to absolute based on media root
def denormalize_path(rel_path: str, media_root: str) -> str:
    return os.path.join(media_root.rstrip("/"), rel_path.lstrip("/")).replace("\\", "/")

# Generate a combined display title for an item, handling different media types (episode, show, movie)
def combined_title(item):
    if not item:
        return "-"

    def get(d, k, default=None):
        return d.get(k, default) if isinstance(d, dict) else getattr(d, k, default)

    item_type = (get(item, "type") or get(item, "Type") or "").lower()
    title = get(item, "title") or get(item, "Name") or "-"
    season = get(item, "seasonNumber") or get(item, "season") or get(item, "SeasonNumber")
    episode = get(item, "index") or get(item, "episode") or get(item, "Index")
    show_title = get(item, "grandparentTitle") or get(item, "show") or get(item, "ShowTitle")

    try:
        sxxexx = f"S{int(season):02d}E{int(episode):02d}" if season and episode else ""
    except (ValueError, TypeError):
        sxxexx = ""

    if item_type in ("episode", "show"):
        if show_title and sxxexx:
            return f"{show_title} – {sxxexx} – {title}"
        elif show_title:
            return f"{show_title} – {title}"
        elif sxxexx:
            return f"{sxxexx} – {title}"
        else:
            return title

    return title
    
# Get item id and other info from items
def gather_item_info(item, platform, duration_fallback=0):
    if not item:
        return {
            "item_id": None,
            "resume": 0,
            "duration": duration_fallback,
            "playcount": 0,
            "status": "unwatched",  # default here too
            "media_type": None,
        }

    # Platform-specific item ID
    item_id = None
    if platform == "plex":
        item_id = item.get("ratingKey")
    elif platform == "kodi":
        item_id = item.get("idFile")
    elif platform == "jellyfin":
        item_id = item.get("id")
    else:
        console.print(f"[red]Unknown platform: {platform}")

    # Determine resume
    resume = int(item.get("resume", 0))
    
    # Determine duration (use fallback if necessary)
    raw_duration = item.get("duration", 0)
    try:
        raw_duration = int(raw_duration)
    except Exception:
        raw_duration = 0

    duration = raw_duration if raw_duration > 0 else duration_fallback
    
    # Determine playcount
    # playcount = int(item.get("playcount", 0))
    raw_playcount = item.get("playcount")

    if raw_playcount is None:
        playcount = 0
    else:
        playcount = int(raw_playcount)
    # Determine status
    if resume == 0:
        status = "watched" if playcount else "unwatched"
    elif duration > 0 and resume >= duration:
        status = "watched"
    else:
        status = "in_progress"

    # Normalize status
    if status not in {"unwatched", "watched", "in_progress"}:
        status = "on_deck"
        
    # Determine media_type
    media_type = item.get("media_type")
    
    return {
        "item_id": item_id,
        "resume": resume,
        "duration": duration,
        "playcount": playcount,
        "status": status,
        "media_type": media_type,
    }

# Get previously reported info about items for comparison
def gather_previous_info(entry, platform):
    data = entry.get(platform, {})
    item_id = data.get(
        "ratingKey" if platform == "plex"
        else "idFile" if platform == "kodi"
        else "id"
    )

    return {
        "item_id": item_id,
        "resume": int(data.get("resume", 0) or 0),
        "duration": int(data.get("duration", 0) or 0),
        "playcount": int(data.get("playcount", 0) or 0),
        "status": data.get("status", "unwatched"),
        "media_type": data.get("media_type", ""),
    }
    
# Only playable items belong in resume sync state. Jellyfin may include
# series and season folders in its resume response.
def is_nonplayable_container(entry):
    return any(
        ((entry.get(platform) or {}).get("media_type") or "").lower() in ("series", "season")
        for platform in ("plex", "kodi", "jellyfin")
    )

# Load sync state from the last known state file (for delta syncing)
def load_sync_state():
    if os.path.exists(SYNC_STATE_FILE):
        try:
            with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                return {path: entry for path, entry in state.items()
                        if not is_nonplayable_container(entry)}
        except Exception:
            console.print("[red]No last sync state file detected. Assuming first run...[/]")
    return {}

# Save current sync state to file to be referenced in future runs
def save_sync_state(state):
    try:
        with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({path: entry for path, entry in state.items()
                       if not is_nonplayable_container(entry)}, f, indent=2)
    except Exception:
        console.print("[red]Failed to save sync state[/]")

# Establish a MySQL connection to the Kodi media database
def connect_kodi_db():
    return pymysql.connect(
        host=KODI_DB_HOST,
        port=KODI_DB_PORT,
        user=KODI_DB_USER,
        password=KODI_DB_PASSWORD,
        database=KODI_DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

# Send a JSON-RPC command to Kodi's API (used for refreshing or triggering actions)
def kodi_rpc(method, params=None):
    try:
        auth = HTTPBasicAuth(KODI_WEBUI_RPC_USER, KODI_WEBUI_RPC_PASSWORD) if KODI_WEBUI_RPC_USER else None
        r = requests.post(
            url=KODI_WEBUI_RPC,
            json={"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1},
            timeout=5,
            auth=auth
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        traceback.print_exc()
        console.print("[red]❌ Kodi RPC failed[/]")
        return None

# Authenticate against Jellyfin and retrieve a valid token and user ID (or refresh if expired)
def get_jellyfin_token():
    # Read the persisted credentials directly; Web UI child processes can inherit
    # stale values from Flask's environment after a previous reauthentication.
    saved_env = dotenv_values(env_path)
    saved_token = saved_env.get("JELLYFIN_TOKEN") or ""
    saved_user_id = saved_env.get("JELLYFIN_USER_ID") or ""

    def authenticate():
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": (
                    'MediaBrowser Client="pkjsync", Device="sync-client", '
                    'DeviceId="sync-001", Version="0.1", Token=""'
                )
            }
            payload = {"Username": JELLYFIN_USER, "Pw": JELLYFIN_PW}
            r = requests.post(f"{JELLYFIN_SERVER}/Users/AuthenticateByName", json=payload, headers=headers, timeout=5)
            r.raise_for_status()
            data = r.json()
            token = data.get("AccessToken")
            user_id = data.get("User", {}).get("Id")
            if not token or not user_id:
                raise ValueError("Missing AccessToken or User ID in response")
            set_key(env_path, "JELLYFIN_TOKEN", token)
            set_key(env_path, "JELLYFIN_USER_ID", user_id)
            os.environ["JELLYFIN_TOKEN"] = token
            os.environ["JELLYFIN_USER_ID"] = user_id
            console.print("[green]✅ Jellyfin authentication successful[/]")
            return token, user_id
        except Exception as e:
            console.print(f"[red]❌ Jellyfin authentication failed: {e}")
            raise

    # If missing token or user ID, authenticate
    if not saved_token or not saved_user_id:
        console.print("[yellow]⚠️ No Jellyfin token/user ID. Authenticating...[/]")
        return authenticate()

    try:
        r = requests.get(
            f"{JELLYFIN_SERVER}/Users/Me",
            headers={"Authorization": f'MediaBrowser Token="{saved_token}"'},
            timeout=5)
        if r.status_code == 200:
            return saved_token, saved_user_id
        console.print(f"[yellow]⚠️ Invalid Jellyfin token (status {r.status_code}), reauthenticating...[/]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Token check failed: {e}, reauthenticating...[/]")

    return authenticate()

# Simple connection wrapper object for Jellyfin with server, token, and user ID
class JellyfinConnection:
    def __init__(self, server, token, user_id):
        self.server = server
        self.token = token
        self.user_id = user_id


# Resolve an existing tracked item by its saved platform ID, without library scans.
def fetch_previous_item(platform, rel_path, previous_entry, plex=None, jellyfin=None):
    prior = previous_entry.get(platform) or {}
    item_id = prior.get("ratingKey" if platform == "plex" else "id")
    if not item_id:
        return None

    if platform == "plex":
        item = plex.fetchItem(item_id)
        if not item.media or not item.media[0].parts:
            raise RuntimeError(f"Saved Plex item {item_id} has no media path: {rel_path}")
        abs_path = item.media[0].parts[0].file
        if normalize_path(abs_path, PLEX_MEDIA_ROOT) != rel_path:
            raise RuntimeError(f"Saved Plex ID {item_id} no longer matches path: {rel_path}")
        return {
            "platform": "plex", "item_id": item.ratingKey,
            "ratingKey": item.ratingKey, "title": item.title or "-",
            "combined_title": combined_title(item), "media_type": item.type,
            "resume": int(item.viewOffset or 0) // 1000,
            "duration": int(item.duration or 0) // 1000,
            "playcount": item.viewCount or 0,
            "abs_path": abs_path, "rel_path": rel_path,
        }

    if platform == "jellyfin":
        response = requests.get(
            f"{jellyfin.server}/Users/{jellyfin.user_id}/Items/{item_id}",
            headers={"Authorization": f'MediaBrowser Token="{jellyfin.token}"'},
            timeout=10,
        )
        response.raise_for_status()
        item = response.json()
        abs_path = item.get("Path")
        if not abs_path or normalize_path(abs_path, JELLYFIN_MEDIA_ROOT) != rel_path:
            raise RuntimeError(f"Saved Jellyfin ID {item_id} no longer matches path: {rel_path}")
        userdata = item.get("UserData") or {}
        return {
            "platform": "jellyfin", "item_id": item.get("Id"),
            "id": item.get("Id"), "title": item.get("Name") or "-",
            "combined_title": combined_title(item),
            "media_type": (item.get("Type") or "").lower(),
            "resume": int((userdata.get("PlaybackPositionTicks") or 0) // 10_000_000),
            "duration": int((item.get("RunTimeTicks") or 0) // 10_000_000),
            "playcount": userdata.get("PlayCount") or 0,
            "abs_path": abs_path, "rel_path": rel_path,
        }
    return None


# Initialize and return an active connection to Jellyfin using the token and user ID
def connect_jellyfin():
    token, user_id = get_jellyfin_token()
    return JellyfinConnection(JELLYFIN_SERVER, token, user_id)
    
# Welcome Message
def welcome(env_path="/config/.env"):
    if not os.path.exists(env_path):
        console.print(Panel(f"[bold red]❌ .env file not found at {env_path}[/]"))
        exit(1)
    console.print("")
    console.log("")
    table = Table(
        title="\n🧪 Environment Variables from /config/.env\n",
        show_header=False,
        box=box.SIMPLE_HEAD,       # Minimal lines for table, no outer panel border
        # show_edge=True,       # Keep edges so it looks like a table
        # border_style=None
    )    
    
    # table.width = 120
    
    table.add_column("ENV Variables", style="bold magenta")#, no_wrap=True)
    table.add_column("ENV Values", style="bold magenta")# no_wrap=True)
    
    def style_key(k):
        if k.startswith("PLEX_"): return "yellow"
        if k.startswith("KODI_"): return "cyan"
        if k.startswith("JELLYFIN_"): return "blue"
        return "magenta"

    with open(env_path) as f:
        for line in f:
            line = line.strip()

            # Skip blank lines or comment-only lines
            if not line or line.startswith("#"):
                table.add_row("", "")  # <-- This adds a blank row visually separating sections
                continue

            # Optional: Handle "export VAR=value"
            if line.startswith("export "):
                line = line[len("export "):]

            # Parse key=value
            if "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'").strip('"')
                
                # Hides passwords from logs
                if "PASSWORD" in k.upper() or "PW" in k.upper() or "TOKEN" in k.upper():
                    v = "***********"
                
                style = style_key(k)
                table.add_row(f"[{style}]{k}[/]", f"[{style}]{v}[/]")
            else:
                table.add_row("[bold dim]Malformed Input[/]", f"[red]{line}[/]")

    console.print((table))

    # Now try to connect and **return** the clients
    try:
        console.print("[yellow]🎬 Connecting to Plex...")
        plex = PlexServer(os.getenv("PLEX_SERVER"), os.getenv("PLEX_TOKEN"))
        console.print(f"[yellow]✅ Connected to Plex {os.getenv('PLEX_SERVER')}")
    except Exception as e:
        console.print(f"[red]❌ Plex connection failed: {e}")
        exit(1)

    try:
        console.print("[magenta]📺 Connecting to Kodi DB...")
        kodi_db = connect_kodi_db()
        console.print(f"[magenta]✅ Connected to Kodi MariaDB at {os.getenv('KODI_DB_HOST')}:{os.getenv('KODI_DB_PORT')}")
    except Exception as e:
        console.print(f"[red]❌ Kodi DB connection failed: {e}")
        exit(1)

    console.print("[cyan]📺 Connecting to Kodi WebUI RPC...")
    ping = kodi_rpc("JSONRPC.Ping")
    if ping and ping.get("result") == "pong":
        console.print(f"[cyan]✅ Kodi WebUI RPC connected at {os.getenv('KODI_WEBUI_RPC')}")
    else:
        console.print("[red]❌ Kodi RPC failed")
        exit(1)

    try:
        console.print("[blue]🍇 Connecting to Jellyfin...")
        jellyfin = connect_jellyfin()
        console.print(f"[blue]✅ Connected to Jellyfin at {os.getenv('JELLYFIN_SERVER')}")
    except Exception as e:
        console.print(f"[red]❌ Jellyfin connection failed: {e}")
        exit(1)

    console.print("")
    return plex, kodi_db, jellyfin

##################################################
################ FETCH FUNCTIONS #################
##################################################

def fetch_items(
    platform,
    plex=None,
    plex_media_root=None,
    kodi_db=None,
    kodi_media_root=None,
    jellyfin=None,
    jellyfin_media_root=None,
    target_rel_path=None,
    media_type=None,
):
    def build_item_data(item, platform, media_root):
        abs_path = item["abs_path"]
        rel_path = normalize_path(abs_path, media_root)

        # Use your gather_item_info here to get item_id, resume, duration, playcount, status
        gathered = gather_item_info(item, platform, duration_fallback=0)

        title = item.get("title") or item.get("Name") or "-"
        combined = item.get("combined_title") or combined_title(item)

        return {
            "platform": platform,
            "item_id": gathered["item_id"],
            "rel_path": rel_path,
            "abs_path": abs_path,
            "duration": gathered["duration"],
            "resume": gathered["resume"],
            "playcount": gathered["playcount"],
            "status": gathered["status"],
            "title": title,
            "combined_title": combined,
            **item,
        }

    results = {}

    if platform == "plex":
        if not plex or not plex_media_root:
            return {}

        results = {}

        if target_rel_path:
            # Index Plex paths once per sync run instead of scanning the entire
            # library again for every missing item. Keep original library order,
            # exclusions, media-type filter and matching behavior.
            cache_key = (id(plex), plex_media_root, media_type, tuple(PLEX_EXCLUDE_LIBRARIES))
            cache = getattr(fetch_items, "_plex_target_index", {})
            if cache_key not in cache:
                index = {}
                for lib in plex.library.sections():
                    if lib.title in PLEX_EXCLUDE_LIBRARIES:
                        continue
                    if media_type and lib.type != media_type:
                        continue

                    try:
                        # Handle TV shows
                        if lib.type == "show":
                            for show in lib.all():
                                for ep in show.episodes():
                                    if not ep or not ep.media or not ep.media[0].parts:
                                        continue
                                    abs_path = ep.media[0].parts[0].file
                                    rel_path = normalize_path(abs_path, plex_media_root)
                                    index.setdefault(rel_path, ("show", ep, abs_path))

                        # Handle Movies
                        elif lib.type == "movie":
                            for movie in lib.all():
                                if not movie or not movie.media or not movie.media[0].parts:
                                    continue
                                abs_path = movie.media[0].parts[0].file
                                rel_path = normalize_path(abs_path, plex_media_root)
                                index.setdefault(rel_path, ("movie", movie, abs_path))

                    except Exception as e:
                        console.print(f"[yellow]⚠️ Plex scan failed in {lib.title}: {e}")
                cache[cache_key] = index
                fetch_items._plex_target_index = cache

            match = cache[cache_key].get(target_rel_path)
            if match:
                item_type, item, abs_path = match
                if item_type == "show":
                    built = {
                        "ratingKey": item.ratingKey,
                        "title": item.title or "-",
                        "combined_title": combined_title(item),
                        "media_type": item.type,
                        "season": item.seasonNumber,
                        "episode": item.index,
                        "resume": int(item.viewOffset or 0) // 1000,
                        "duration": int(item.duration or 0) // 1000,
                        "playcount": item.viewCount or 0,
                        "abs_path": abs_path,
                    }
                else:
                    built = {
                        "ratingKey": item.ratingKey,
                        "title": item.title or "-",
                        "combined_title": combined_title(item),
                        "media_type": item.type,
                        "resume": int(item.viewOffset or 0) // 1000,
                        "duration": int(item.duration or 0) // 1000,
                        "playcount": item.viewCount or 0,
                        "abs_path": abs_path,
                    }
                enriched = build_item_data(built, "plex", plex_media_root)
                results[enriched["rel_path"]] = enriched
                return results

        else:
            # Fetch continue watching from On Deck
            for lib in plex.library.sections():
                if lib.title in PLEX_EXCLUDE_LIBRARIES:
                    continue
                try:
                    for item in lib.onDeck():
                        if not item.media or not item.media[0].parts:
                            continue
                        resume = int(item.viewOffset or 0) // 1000
                        abs_path = item.media[0].parts[0].file
                        built = {
                            "ratingKey": item.ratingKey,
                            "title": item.title or "-",
                            "duration": int(item.duration or 0) // 1000,
                            "resume": resume,
                            "playcount": item.viewCount or 0,
                            "combined_title": combined_title(item),
                            "media_type": item.type,
                            "abs_path": abs_path,
                        }
                        enriched = build_item_data(built, "plex", plex_media_root)
                        results[enriched["rel_path"]] = enriched

                except Exception as e:
                    console.print(f"[yellow]⚠️ Plex library {lib.title} skipped: {e}")

            return results

        return results

    elif platform == "kodi":
        if not kodi_db or not kodi_media_root:
            return {}

        with kodi_db.cursor() as cursor:
            if target_rel_path:
                search_abs_path = denormalize_path(target_rel_path, kodi_media_root)
                cursor.execute("""
                    SELECT f.idFile, f.strFilename, p.strPath
                    FROM files f
                    JOIN path p ON f.idPath = p.idPath
                    WHERE CONCAT(p.strPath, f.strFilename) = %s
                """, (search_abs_path,))
                file_row = cursor.fetchone()
                if file_row:
                    idFile = file_row["idFile"]
                    abs_path = os.path.join(file_row["strPath"], file_row["strFilename"]).replace("\\", "/")

                    # Try movie first
                    cursor.execute("""
                        SELECT
                            m.c00 AS title,
                            m.c11 AS duration,
                            f.playCount,
                            bm.timeInSeconds AS resume,
                            m.idMovie
                        FROM movie m
                        JOIN files f ON m.idFile = f.idFile
                        LEFT JOIN bookmark bm
                            ON bm.idFile = f.idFile
                           AND bm.type = 1
                        WHERE m.idFile = %s
                    """, (idFile,))
                    row = cursor.fetchone()
                    if row:
                        built = {
                            "idFile": idFile,
                            "idMovie": row["idMovie"],
                            "title": row["title"] or "-",
                            "duration": int(row["duration"] or 0),
                            "resume": int(round(row["resume"])) if row["resume"] else 0,
                            "playcount": row["playCount"] or 0,
                            "abs_path": abs_path,
                            "media_type": "movie",
                        }
                        enriched = build_item_data(built, "kodi", kodi_media_root)
                        results[enriched["rel_path"]] = enriched
                        return results

                    # Try episode if not a movie
                    cursor.execute("""
                        SELECT
                            e.c00 AS episode_title,
                            e.c12 AS season,
                            e.c13 AS episode,
                            s.c00 AS show_title,
                            f.playCount,
                            bm.timeInSeconds AS resume,
                            e.idEpisode
                        FROM episode e
                        JOIN tvshow s ON e.idShow = s.idShow
                        JOIN files f ON e.idFile = f.idFile
                        LEFT JOIN bookmark bm
                            ON bm.idFile = f.idFile
                           AND bm.type = 1
                        WHERE e.idFile = %s
                    """, (idFile,))
                    row = cursor.fetchone()
                    if row:
                        combined = f"{row['show_title']} S{int(row['season']):02}E{int(row['episode']):02} – {row['episode_title']}"
                        built = {
                            "idFile": idFile,
                            "idEpisode": row["idEpisode"],
                            "title": row["episode_title"] or "-",
                            "duration": 0,
                            "resume": int(round(row["resume"])) if row["resume"] else 0,
                            "playcount": row["playCount"] or 0,
                            "abs_path": abs_path,
                            "media_type": "episode",
                            "combined_title": combined,
                        }
                        enriched = build_item_data(built, "kodi", kodi_media_root)
                        results[enriched["rel_path"]] = enriched
                        return results

            else:
                # Movies with resume
                cursor.execute("""
                    SELECT m.idMovie, m.c00 AS title, f.idFile, m.c22 AS folderPath, f.strFilename,
                           bm.timeInSeconds AS resume, f.playCount
                    FROM movie m
                    JOIN files f ON m.idFile = f.idFile
                    JOIN bookmark bm ON bm.idFile = f.idFile AND bm.type = 1 AND bm.timeInSeconds > 0
                    WHERE m.c22 LIKE %s
                """, (f'%{kodi_media_root}%',))
                for row in cursor.fetchall():
                    resume = int(round(row["resume"])) if row["resume"] else 0
                    abs_path = os.path.join(row["folderPath"].rstrip("/"), row["strFilename"]).replace("\\", "/")
                    built = {
                        "idFile": row["idFile"],
                        "idMovie": row["idMovie"],
                        "title": row["title"] or "-",
                        "duration": 0,
                        "resume": resume,
                        "playcount": row["playCount"] or 0,
                        "abs_path": abs_path,
                        "media_type": "movie",
                    }
                    enriched = build_item_data(built, "kodi", kodi_media_root)
                    results[enriched["rel_path"]] = enriched

                # Episodes with resume
                cursor.execute("""
                    SELECT e.idEpisode, e.c00 AS title, f.idFile, s.c00 AS showTitle, e.c12 AS season,
                           e.c13 AS episode, f.strFilename, p.strPath, bm.timeInSeconds AS resume, f.playCount
                    FROM episode e
                    JOIN files f ON e.idFile = f.idFile
                    JOIN path p ON f.idPath = p.idPath
                    JOIN tvshow s ON e.idShow = s.idShow
                    JOIN bookmark bm ON bm.idFile = f.idFile AND bm.type = 1 AND bm.timeInSeconds > 0
                    WHERE p.strPath LIKE %s
                """, (f'%{kodi_media_root}%',))
                for row in cursor.fetchall():
                    resume = int(round(row["resume"])) if row["resume"] else 0
                    abs_path = os.path.join(row["strPath"].rstrip("/"), row["strFilename"]).replace("\\", "/")
                    combined = f"{row['showTitle']} S{int(row['season']):02}E{int(row['episode']):02} – {row['title']}"
                    built = {
                        "idFile": row["idFile"],
                        "idEpisode": row["idEpisode"],
                        "title": row["title"] or "-",
                        "duration": 0,
                        "resume": resume,
                        "playcount": row["playCount"] or 0,
                        "abs_path": abs_path,
                        "media_type": "episode",
                        "combined_title": combined,
                    }
                    enriched = build_item_data(built, "kodi", kodi_media_root)
                    results[enriched["rel_path"]] = enriched

                return results

            return results

    elif platform == "jellyfin":
        if not jellyfin or not jellyfin_media_root:
            return {}

        token = jellyfin.token
        user_id = jellyfin.user_id
        server = jellyfin.server
        headers = {"Authorization": f'MediaBrowser Token="{token}"'}
        results = {}

        try:
            if target_rel_path:
                # Handling specific target_rel_path search
                search_abs_path = denormalize_path(target_rel_path, jellyfin_media_root)
                url = f"{server}/Items"
                params = {
                    "UserId": user_id,
                    "Recursive": "true",
                    "IncludeItemTypes": "Movie,Episode",
                    "Fields": "Path,UserData,RunTimeTicks",
                }
                r = requests.get(url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                items = r.json().get("Items", [])

                for item in items:
                    if item.get("Type") not in ("Movie", "Episode"):
                        continue

                    # if int(item.get("UserData", {}).get("PlaybackPositionTicks", 0) // 10_000_000) <= 0:
                        # continue  # Skip if there's no valid resume data

                    abs_path = item.get("Path")
                    if abs_path == search_abs_path:
                        # Directly access fields inside the built dictionary
                        built = {
                            "id": item.get("Id"),
                            "title": item.get("Name") or "-",
                            "duration": int(item.get("RunTimeTicks", 0) // 10_000_000),
                            "resume": int(item.get("UserData", {}).get("PlaybackPositionTicks", 0) // 10_000_000),
                            "playcount": item.get("UserData", {}).get("PlayCount", 0),
                            "abs_path": abs_path,
                            "media_type": item.get("Type", "").lower(),
                        }
                        enriched = build_item_data(built, "jellyfin", jellyfin_media_root)
                        results[enriched["rel_path"]] = enriched
                        return results  # Return immediately after finding the match

            else:

                # Handling resume items if no target_rel_path
                url = f"{server}/UserItems/Resume"
                params = {
                    "userId": user_id,
                    "enableUserData": "true",
                    "Limit": 1000,
                    "Fields": "Path,UserData,RunTimeTicks",
                }
                r = requests.get(url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                items = r.json().get("Items", [])

                for item in items:
                    if item.get("Type") not in ("Movie", "Episode"):
                        continue
                    built = {
                        "id": item.get("Id"),
                        "title": item.get("Name") or "-",
                        "duration": int(item.get("RunTimeTicks", 0) // 10_000_000),
                        "resume": int(item.get("UserData", {}).get("PlaybackPositionTicks", 0) // 10_000_000),
                        "playcount": item.get("UserData", {}).get("PlayCount", 0),
                        "abs_path": item.get("Path"),
                        "media_type": item.get("Type", "").lower(),
                    }
                    enriched = build_item_data(built, "jellyfin", jellyfin_media_root)
                    results[enriched["rel_path"]] = enriched

                # Also fetch "Next Up" episodes
                url = f"{server}/Shows/NextUp"
                params = {
                    "userId": user_id,
                    "enableUserData": "true",
                    "Limit": 1000,
                    "Fields": "Path,UserData,RunTimeTicks",
                }
                r = requests.get(url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                items = r.json().get("Items", [])

                for item in items:
                    if item.get("Type") not in ("Movie", "Episode"):
                        continue
                    built = {
                        "id": item.get("Id"),
                        "title": item.get("Name") or "-",
                        "duration": int(item.get("RunTimeTicks", 0) // 10_000_000),
                        "resume": int(item.get("UserData", {}).get("PlaybackPositionTicks", 0) // 10_000_000),
                        "playcount": item.get("UserData", {}).get("PlayCount", 0),
                        "abs_path": item.get("Path"),
                        "media_type": item.get("Type", "").lower(),
                    }
                    enriched = build_item_data(built, "jellyfin", jellyfin_media_root)
                    results[enriched["rel_path"]] = enriched
                return results

            # Targeted Jellyfin lookup completed without finding a match.
            return results
        except Exception as e:
            console.print(f"[blue]⚠️ Jellyfin fallback search failed: {e}")
            return {}



    else:
        return {}

##################################################
############# SYNC LOGIC FUNCTIONS ###############
##################################################
    
def sync_logic(
    plex_items,
    kodi_items,
    jellyfin_items,
    plex,
    kodi_db,
    jellyfin,
    plex_media_root=None,
    kodi_media_root=None,
    jellyfin_media_root=None,
    show_fetched=False,
):
    previous_sync_state = load_sync_state() or {}
    jellyfin_items = {path: item for path, item in jellyfin_items.items()
                      if item.get("media_type") in ("movie", "episode")}
    updated_sync_state = {}  # New sync state we'll return
    sync_actions = []
    
    # Collect fetched items for reporting at the end of loop
    fetched_items_report = {
        "plex": {},
        "kodi": {},
        "jellyfin": {},
    }

    all_rel_paths = set(plex_items) | set(kodi_items) | set(jellyfin_items) | set(previous_sync_state)

    for rel_path in all_rel_paths:
        previous_entry = previous_sync_state.get(rel_path, {})

        # Fetch current items
        plex_item = plex_items.get(rel_path)
        kodi_item = kodi_items.get(rel_path)
        jellyfin_item = jellyfin_items.get(rel_path)
        
        # A prior item's saved ID is an exact lookup; no Plex-wide enumeration.
        # These lookups also detect watched/unwatched changes after an item
        # disappears from the initial Continue Watching / resume feeds.
        if previous_entry and not plex_item and (previous_entry.get("plex") or {}).get("ratingKey"):
            plex_item = fetch_previous_item("plex", rel_path, previous_entry, plex=plex)
            plex_items[rel_path] = plex_item
        if previous_entry and not jellyfin_item and (previous_entry.get("jellyfin") or {}).get("id"):
            jellyfin_item = fetch_previous_item("jellyfin", rel_path, previous_entry, jellyfin=jellyfin)
            jellyfin_items[rel_path] = jellyfin_item
        if previous_entry and not kodi_item and (previous_entry.get("kodi") or {}).get("idFile"):
            fetched = fetch_items("kodi", kodi_db=kodi_db, kodi_media_root=kodi_media_root, target_rel_path=rel_path)
            kodi_item = fetched.get(rel_path)
            if not kodi_item:
                raise RuntimeError(f"Saved Kodi item could not be resolved: {rel_path}")
            kodi_items[rel_path] = kodi_item

        # Gather previous info
        prev_plex_info = gather_previous_info(previous_entry, "plex")
        prev_kodi_info = gather_previous_info(previous_entry, "kodi")
        prev_jellyfin_info = gather_previous_info(previous_entry, "jellyfin")

        # Gather current info
        plex_info = gather_item_info(plex_item, "plex")
        kodi_info = gather_item_info(kodi_item, "kodi", duration_fallback=plex_info["duration"])
        jellyfin_info = gather_item_info(jellyfin_item, "jellyfin")

        # An unchanged path previously confirmed absent from a platform has no
        # saved ID to resolve. Do not rescan the entire library each run unless
        # a known platform's current state has changed since the last run.
        def needs_missing_lookup(platform):
            if not previous_entry or (previous_entry.get(platform) or {}).get(
                "ratingKey" if platform == "plex" else "idFile" if platform == "kodi" else "id"
            ):
                return True
            for name, item in (("plex", plex_item), ("kodi", kodi_item), ("jellyfin", jellyfin_item)):
                if not item:
                    continue
                current = gather_item_info(item, name)
                previous = gather_previous_info(previous_entry, name)
                if (current["resume"], current["playcount"], current["status"]) != (
                    previous["resume"], previous["playcount"], previous["status"]
                ):
                    return True
            return False

        # Fallback fetches if needed (Ensure we're handling fetching here)
        with console.status("[bold green]Fetching fallback items...[/bold green]"):

            # Fetch Plex if needed
            if not plex_item and needs_missing_lookup("plex") and any(item and info["status"] in ["in_progress", "unwatched", "on_deck"] for item, info in [(kodi_item, kodi_info), (jellyfin_item, jellyfin_info)]):
                fetched = fetch_items("plex", plex=plex, plex_media_root=plex_media_root, target_rel_path=rel_path)
                plex_item = fetched.get(rel_path)
                plex_info = gather_item_info(plex_item, "plex")
                if plex_item:
                    plex_items[rel_path] = plex_item  # Preserve full fetched metadata
                if plex_item:
                    fetched_items_report["plex"][rel_path] = plex_item
                else: 
                    console.print(f"[red]Unable to fallback fetch!")

            # Fetch Kodi if needed
            if not kodi_item and needs_missing_lookup("kodi") and any(item and info["status"] in ["in_progress", "unwatched", "on_deck"] for item, info in [(plex_item, plex_info), (jellyfin_item, jellyfin_info)]):
                fetched = fetch_items("kodi", kodi_db=kodi_db, kodi_media_root=kodi_media_root, target_rel_path=rel_path)
                kodi_item = fetched.get(rel_path)
                kodi_info = gather_item_info(kodi_item, "kodi", duration_fallback=plex_info["duration"])
                if kodi_item:
                    kodi_items[rel_path] = kodi_item  # Preserve full fetched metadata
                if kodi_item:
                    fetched_items_report["kodi"][rel_path] = kodi_item
                else:
                    console.print(f"[red]Unable to fallback fetch!")


            # Fetch Jellyfin if needed
            if not jellyfin_item and needs_missing_lookup("jellyfin") and any(item and info["status"] in ["in_progress", "unwatched", "on_deck"] for item, info in [(plex_item, plex_info), (kodi_item, kodi_info)]):
                fetched = fetch_items("jellyfin", jellyfin=jellyfin, jellyfin_media_root=jellyfin_media_root, target_rel_path=rel_path)
                jellyfin_item = fetched.get(rel_path)
                jellyfin_info = gather_item_info(jellyfin_item, "jellyfin")
                if jellyfin_item:
                    jellyfin_items[rel_path] = jellyfin_item  # Preserve full fetched metadata
                if jellyfin_item:
                    fetched_items_report["jellyfin"][rel_path] = jellyfin_item
                else:
                    console.print(f"[red]Unable to fallback fetch!")

        # === SYNC LOGIC ===

        # Save the current platform info into updated_sync_state for this rel_path.
        def persist_state(rel_path, plex_info, kodi_info, jellyfin_info):
            updated_sync_state[rel_path] = {
                "plex": {
                    "resume": plex_info["resume"],
                    "duration": plex_info["duration"],
                    "playcount": plex_info["playcount"],
                    "status": plex_info["status"],
                    "ratingKey": plex_info["item_id"],
                    "media_type": plex_info["media_type"],
                },
                "kodi": {
                    "resume": kodi_info["resume"],
                    "duration": plex_info["duration"],  # Kodi duration fallback uses Plex duration
                    "playcount": kodi_info["playcount"],
                    "status": kodi_info["status"],
                    "idFile": kodi_info["item_id"],
                    "media_type": kodi_info["media_type"],
                },
                "jellyfin": {
                    "resume": jellyfin_info["resume"],
                    "duration": jellyfin_info["duration"],
                    "playcount": jellyfin_info["playcount"],
                    "status": jellyfin_info["status"],
                    "id": jellyfin_info["item_id"],
                    "media_type": jellyfin_info["media_type"],
                },
            }

        platform_data_list = [
            {
                "platform": platform,
                "item": item,
                **current,  # unpack current resume, duration, playcount, and status
                "previous_resume": previous["resume"],
                "previous_duration": previous["duration"],
                "previous_playcount": previous["playcount"],
                "previous_status": previous["status"],
                "media_type": previous.get("media_type") or current.get("media_type")
            }
            for platform, current, previous, item in [
                ("plex", plex_info, prev_plex_info, plex_item),
                ("kodi", kodi_info, prev_kodi_info, kodi_item),
                ("jellyfin", jellyfin_info, prev_jellyfin_info, jellyfin_item),
            ]
        ]

        # Determine if this item existed in previous sync state
        has_prev = bool(previous_entry)
        # has_prev = any([
            # prev_plex_info,
            # prev_kodi_info,
            # prev_jellyfin_info,
        # ])


        # Current + Previous statuses
        curr_statuses = [p["status"] for p in platform_data_list]
        prev_statuses = [p["previous_status"] or "unwatched" for p in platform_data_list]

        if not has_prev:
            # === No previous sync entry ===
            if any(s == "in_progress" for s in curr_statuses):
                # If any currently in progress → mark all as in_progress with latest resume
                latest_resume = max(p["resume"] or 0 for p in platform_data_list)
                for p in platform_data_list:
                    sync_actions.append({
                        "action": "update_resume",
                        "platform": p["platform"],
                        "item_id": p["item_id"],
                        "item": p["item"],
                        "resume": latest_resume,
                        "duration": plex_info["duration"] if p["platform"] == "kodi" else p.get("duration", 0),
                        "status": "in_progress",
                    })
                persist_state(rel_path, plex_info, kodi_info, jellyfin_info)
            elif any(s == "unwatched" for s in curr_statuses):
               # All currently unwatched → mark on_deck only recognized media_types
                for p in platform_data_list:
                    if p.get("media_type") == "episode":
                        sync_actions.append({
                            "action": "mark_on_deck",
                            "platform": p["platform"],
                            "item_id": p["item_id"],
                            "item": p["item"],
                            "duration": plex_info["duration"] if p["platform"] == "kodi" else p.get("duration", 0),
                            "status": "on_deck",
                        })
                    persist_state(rel_path, plex_info, kodi_info, jellyfin_info)
            elif any(s == "on_deck" for s in curr_statuses):
               ## All currently on_deck → mark on_deck only recognized media_types
                for p in platform_data_list:
                    if p.get("media_type") == "episode":
                        sync_actions.append({
                            "action": "mark_on_deck",
                            "platform": p["platform"],
                            "item_id": p["item_id"],
                            "item": p["item"],
                            "duration": plex_info["duration"] if p["platform"] == "kodi" else p.get("duration", 0),
                            "status": "on_deck",
                        })
                    persist_state(rel_path, plex_info, kodi_info, jellyfin_info)

        else:
            # === Previous sync state exists ===
            if all(s in ["unwatched", "on_deck"] for s in prev_statuses):
                if all(s in ["unwatched", "on_deck"] for s in curr_statuses):
                    for p in platform_data_list:
                    # if p.get("media_type") == "episode":
                        # sync_actions.append({
                            # "action": "mark_on_deck",
                            # "platform": p["platform"],
                            # "item_id": p["item_id"],
                            # "item": p["item"],
                            # "duration": plex_info["duration"] if p["platform"] == "kodi" else p.get("duration", 0),
                            # "status": "on_deck",
                        # })
                    # No change → persist
                        persist_state(rel_path, plex_info, kodi_info, jellyfin_info)

                elif any(s in ["in_progress", "watched"] for s in curr_statuses):
                    # One changed to in_progress or watched → sync all to that
                    changed = next(
                        (p for p in platform_data_list if p["status"] in ["in_progress", "watched"]),
                        None
                    )
                    if changed:
                        for p in platform_data_list:
                            if changed["status"] == "in_progress":
                                sync_actions.append({
                                    "action": "update_resume",
                                    "platform": p["platform"],
                                    "item_id": p["item_id"],
                                    "item": p["item"],
                                    "resume": changed["resume"],
                                    "duration": plex_info["duration"] if p["platform"] == "kodi" else p.get("duration", 0),
                                    "status": "in_progress",
                                })
                            elif changed["status"] == "watched":
                                sync_actions.append({
                                    "action": "mark_watched",
                                    "platform": p["platform"],
                                    "item_id": p["item_id"],
                                    "item": p["item"],
                                    "duration": plex_info["duration"] if p["platform"] == "kodi" else p.get("duration", 0),
                                    "status": "watched",
                                })
                        persist_state(rel_path, plex_info, kodi_info, jellyfin_info)

            elif all(s == "in_progress" for s in prev_statuses):
                if any(s == "unwatched" for s in curr_statuses):
                    # If any currently unwatched → mark all as unwatched
                    for p in platform_data_list:
                        sync_actions.append({
                            "action": "mark_unwatched",
                            "platform": p["platform"],
                            "item_id": p["item_id"],
                            "item": p["item"],
                            "duration": plex_info["duration"] if p["platform"] == "kodi" else p.get("duration", 0),
                            "status": "unwatched",
                        })
                    persist_state(rel_path, plex_info, kodi_info, jellyfin_info)

                elif any(s == "watched" for s in curr_statuses):
                    # If any currently watched → mark all as watched
                    for p in platform_data_list:
                        sync_actions.append({
                            "action": "mark_watched",
                            "platform": p["platform"],
                            "item_id": p["item_id"],
                            "item": p["item"],
                            "duration": plex_info["duration"] if p["platform"] == "kodi" else p.get("duration", 0),
                            "status": "watched",
                        })
                    persist_state(rel_path, plex_info, kodi_info, jellyfin_info)

                elif all(s == "in_progress" for s in curr_statuses):
                    # All still in progress → check for resume delta
                    resume_deltas = [
                        p for p in platform_data_list
                        if p["resume"] != p["previous_resume"]
                    ]
                    if resume_deltas:
                        new_resume = max(p["resume"] or 0 for p in resume_deltas)
                        for p in platform_data_list:
                            sync_actions.append({
                                "action": "update_resume",
                                "platform": p["platform"],
                                "item_id": p["item_id"],
                                "item": p["item"],
                                "resume": new_resume,
                                "duration": plex_info["duration"] if p["platform"] == "kodi" else p.get("duration", 0),
                                "status": "in_progress",
                            })
                        persist_state(rel_path, plex_info, kodi_info, jellyfin_info)
                    else:
                        # Resume unchanged → just persist
                        persist_state(rel_path, plex_info, kodi_info, jellyfin_info)

                else:
                    # Mixed or unexpected → just persist
                    persist_state(rel_path, plex_info, kodi_info, jellyfin_info)

            elif all(p["status"] == p["previous_status"] for p in platform_data_list):
                # No state change → just persist
                persist_state(rel_path, plex_info, kodi_info, jellyfin_info)

            else:
                # Unknown or mixed state
                console.print(f"[red]Unknown sync condition for {rel_path}, check sync logic![/red]")
                persist_state(rel_path, plex_info, kodi_info, jellyfin_info)

    # After processing all items, report fetched items:
    platform_order = ["plex", "kodi", "jellyfin"]

    if show_fetched:
        for platform in platform_order:
            items = fetched_items_report.get(platform, {})
            if items:
                console.print(f"\n[bold magenta]{platform.capitalize()} items fetched:[/bold magenta]")
                for rel_path in sorted(items.keys()):
                    item = items[rel_path]
                    console.print(f"  [dim]{rel_path}[/dim]:")
                    title = item.get("combined_title") or item.get("title") or "No title"
                    console.print(f"    [italic]{title}[/italic]")

    return sync_actions, updated_sync_state

##################################################
############### RESUME FUNCTIONS #################
##################################################

def sync_items(sync_instructions, plex=None, kodi_db=None, jellyfin=None):
    if not sync_instructions:
        console.print(f"\n[bold green]No sync actions to perform at this time.", justify="center")
        return 0

    def plex_set_resume(item, resume, duration, status):
        try:
            title = item.get("title", "Unknown") if item else "Unknown"
            ratingKey = item.get("ratingKey") or "N/A"
            # time = format_time(int(resume))

            if ratingKey == "N/A":
                console.print(f"[red]❌ Plex: Missing ratingKey for '{title}'")
                return False

            plex_obj = plex.fetchItem(ratingKey)

            if status == "on_deck":
                console.print(f"[green]🌱 Plex: Marked {title} as on deck")
                return True

            elif status == "watched":
                plex_obj.markWatched()
                console.print(f"[yellow]👀 Plex: Marked '{title}' as watched")
                plex_obj.reload()
                return True

            elif status == "unwatched":
                plex_obj.markUnwatched()
                console.print(f"[yellow]🙈 Plex: Marked '{title}' as unwatched")
                plex_obj.reload()
                return True

            elif status == "in_progress":
                plex_obj.updateProgress(int(resume * 1000), state="stopped")
                console.print(f"[yellow]▶ Plex: Updated resume point for '{title}' to {resume}s")
                plex_obj.reload()
                return True

            else:
                console.print(f"[red]❌ Plex: Unknown status '{status}' for '{title}'")
                return False

        except Exception as e:
            traceback.print_exc()
            console.print(f"[red]❌ Plex: Failed to update '{title}' – {e}")
            return False

    def kodi_set_resume(item, resume, status, duration=0):
        try:
            title = item.get("title", "Unknown") if item else "Unknown"
            resume = int(round(resume))
            duration = int(round(duration))
            idFile = item.get("idFile") or "N/A"
            idMovie = item.get("idMovie")
            idEpisode = item.get("idEpisode")
            media_type = item.get("media_type")  # "movie" or "episode"

            if idFile == "N/A":
                console.print(f"[red]❌ Kodi: Missing idFile for '{title}'")
                return False

            with kodi_db.cursor(pymysql.cursors.DictCursor) as cursor:

                if status == "on_deck":
                    console.print(f"[cyan]🌱 Kodi:  Marked {title} as on deck")
                    return True

                elif status == "watched":
                    cursor.execute("DELETE FROM bookmark WHERE idFile = %s AND type = 1", (idFile,))
                    cursor.execute("UPDATE files SET playCount = 1, lastPlayed = NOW() WHERE idFile = %s", (idFile,))
                    console.print(f"[cyan]👀 Kodi: Marked '{title}' as watched")
                    kodi_db.commit()
                    return True

                elif status == "unwatched":
                    cursor.execute("DELETE FROM bookmark WHERE idFile = %s AND type = 1", (idFile,))
                    cursor.execute("UPDATE files SET playCount = NULL, lastPlayed = NULL WHERE idFile = %s", (idFile,))
                    console.print(f"[cyan]🙈 Kodi: Marked '{title}' as unwatched")
                    kodi_db.commit()
                    return True

                elif status == "in_progress":
                    cursor.execute("SELECT * FROM bookmark WHERE idFile = %s AND type = 1", (idFile,))
                    bookmark = cursor.fetchone()

                    console.print(f"[cyan]▶ Kodi: Updated resume point for '{title}' to {resume}s")

                    if bookmark:
                        cursor.execute(
                            "UPDATE bookmark SET timeInSeconds = %s, totalTimeInSeconds = %s WHERE idBookmark = %s",
                            (resume, duration, bookmark["idBookmark"])
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO bookmark (idFile, timeInSeconds, totalTimeInSeconds, type, player, playerState, thumbNailImage) "
                            "VALUES (%s, %s, %s, 1, '', '', '')",
                            (idFile, resume, duration)
                        )

                    kodi_db.commit()

                    # 🔁 Refresh Kodi library item
                    if media_type in ["movie", "episode"]:
                        kodi_rpc(
                            "VideoLibrary.RefreshMovie" if media_type == "movie" else "VideoLibrary.RefreshEpisode",
                            {"idMovie": idMovie} if media_type == "movie" else {"idEpisode": idEpisode}
                        )

                    return True

                else:
                    console.print(f"[red]❌ Kodi: Unknown status '{status}' for '{title}'")
                    return False

        except Exception as e:
            traceback.print_exc()
            console.print(f"[red]❌ Kodi: Failed to update '{item.get('title', 'Unknown')}' – {e}")
            return False

    def jellyfin_set_resume(item, resume, duration, status):
        try:
            title = item.get("title", "Unknown") if item else "Unknown"
            item_id = item.get("id") or "N/A"

            if item_id == "N/A":
                console.print(f"[red]❌ Jellyfin: Missing item ID for '{title}'")
                return False

            server = jellyfin.server
            token = jellyfin.token
            user_id = jellyfin.user_id
            headers = {"Authorization": f'MediaBrowser Token="{token}"'}

            # Fetch current user data
            get_url = f"{server}/Users/{user_id}/Items/{item_id}"
            get_response = requests.get(get_url, headers=headers, timeout=10)

            if get_response.status_code != 200:
                console.print(f"[red]❌ Jellyfin: Failed to fetch current user data for '{title}' – {get_response.status_code}")
                return False

            current_data = get_response.json().get("UserData", {})
            if not current_data:
                console.print(f"[red]❌ Jellyfin: No user data found for '{title}'")
                return False

            # Start with current user data as base payload
            payload = {
                "PlaybackPositionTicks": current_data.get("PlaybackPositionTicks", 0),
                "PlayCount": current_data.get("PlayCount", 0),
                "Played": current_data.get("Played", False),
                "IsFavorite": current_data.get("IsFavorite", False),
                "Likes": current_data.get("Likes"),
                "Rating": current_data.get("Rating"),
                "LastPlayedDate": current_data.get("LastPlayedDate")
            }

            if status == "on_deck":
                console.print(f"[blue]🌱 Jellyfin: Marked {title} as on deck")
                return True

            elif status == "watched":
                payload["PlaybackPositionTicks"] = 0
                payload["Played"] = True
                payload["PlayCount"] = max(1, payload.get("PlayCount", 0))
                console.print(f"[blue]👀 Jellyfin: Marked '{title}' as watched")

            elif status == "unwatched":
                payload["PlaybackPositionTicks"] = 0
                payload["Played"] = False
                payload["PlayCount"] = 0
                console.print(f"[blue]🙈 Jellyfin: Marked '{title}' as unwatched")

            elif status == "in_progress":
                payload["PlaybackPositionTicks"] = int(resume * 10_000_000)
                payload["Played"] = True
                payload["PlayCount"] = 0
                console.print(f"[blue]▶ Jellyfin: Updated resume point for '{title}' to {resume}s")

            else:
                console.print(f"[red]❌ Jellyfin: Unknown status '{status}' for '{title}'")
                return False

            post_url = f"{server}/UserItems/{item_id}/UserData?userId={user_id}"
            response = requests.post(post_url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                return True
            else:
                console.print(f"[red]❌ Jellyfin: Failed to update '{title}' – {response.status_code} {response.text}")
                return False

        except requests.RequestException as e:
            traceback.print_exc()
            console.print(f"[red]❌ Jellyfin: Exception updating '{title or item_id}' – {e}")
            return False


    success_count = 0
    
    for action in sync_instructions:
        platform = action["platform"]
        item = action.get("item")
        resume = action.get("resume", 0)
        duration = action.get("duration", 0)
        status = action["status"]

        with console.status(f"[magenta]Processing {platform.upper()} → {status}: {item.get('title', 'Unknown') if item else 'Unknown'}"):

            try:
                if platform == "plex" and plex and item:
                    if plex_set_resume(item, resume, duration, status):
                        success_count += 1
                elif platform == "kodi" and kodi_db and item:
                    if kodi_set_resume(item, resume, status, duration):
                        success_count += 1
                elif platform == "jellyfin" and jellyfin and item:
                    if jellyfin_set_resume(item, resume, duration, status):
                        success_count += 1
            except Exception as e:
                traceback.print_exc()
                console.print(f"[red]❌ Exception syncing '{platform}' – {e}")
                
    # console.print(f"[green]✅ Sync complete: {success_count} action(s) applied.")
    return success_count

###################################################
############# PRINT TABLE FUNCTIONS ###############
###################################################

def add_platform_label_row(tbl):
    tbl.add_row(
        "",
        "[dim yellow]Plex[/dim yellow]",
        "[dim cyan]Kodi[/dim cyan]",
        "[dim blue]Jellyfin[/dim blue]",
        "",
    )


def add_aligned_platform_columns(tbl, item_label, item_style="white"):
    tbl.add_column(item_label, style=item_style, ratio=1)
    tbl.add_column("Plex", justify="right", style="yellow", width=9, no_wrap=True)
    tbl.add_column("Kodi", justify="right", style="cyan", width=9, no_wrap=True)
    tbl.add_column("Jellyfin", justify="right", style="blue", width=9, no_wrap=True)
    tbl.add_column("Status", justify="center", style="magenta", width=3, no_wrap=True)


def is_on_deck_display_path(plex_item, kodi_item, jellyfin_item):
    items = [item for item in (plex_item, kodi_item, jellyfin_item) if item]
    return (
        any(item.get("media_type") == "episode" for item in items)
        and any(item.get("status") == "unwatched" for item in items)
        and all(item.get("status") != "watched" and int(item.get("resume", 0) or 0) == 0
                for item in items)
    )


def print_paths(plex_items, kodi_items, jellyfin_items):
    def split_by_type(items):
        movies = {k: v for k, v in items.items() if v.get("media_type") == "movie"}
        shows = {k: v for k, v in items.items() if v.get("media_type") in ("show", "episode")}
        return movies, shows

    plex_movies, plex_shows = split_by_type(plex_items)
    kodi_movies, kodi_shows = split_by_type(kodi_items)
    jelly_movies, jelly_shows = split_by_type(jellyfin_items)

    def make_on_deck_table(title, plex_items, kodi_items, jellyfin_items):
        table = Table(box=box.SIMPLE_HEAD, title=title, title_style="bold green")
        table.add_column("Movie", style="green", no_wrap=False)
        table.add_column("Plex", justify="right", style="yellow", no_wrap=True)
        table.add_column("Kodi", justify="right", style="cyan", no_wrap=True)
        table.add_column("Jellyfin", justify="right", style="blue", no_wrap=True)
        table.add_column("Status", justify="center", style="magenta", no_wrap=True)

        all_paths = sorted(set(plex_items) | set(kodi_items) | set(jellyfin_items))

        for idx, path in enumerate(all_paths):
            p = plex_items.get(path)
            k = kodi_items.get(path)
            j = jellyfin_items.get(path)

            if not ((p and p.get("status") == "unwatched") or
                    (k and k.get("status") == "unwatched") or
                    (j and j.get("status") == "unwatched")):
                continue

            movie_title = (p or k or j).get("combined_title") or (p or k or j).get("title") or "-"
            plex_resume = format_time(int(p.get("resume", 0))) if p else "-"
            kodi_resume = format_time(int(k.get("resume", 0))) if k else "-"
            jelly_resume = format_time(int(j.get("resume", 0))) if j else "-"
            status = "🌱"

            row = [
                movie_title,
                f"[yellow]{plex_resume}[/yellow]" if p else "-",
                f"[cyan]{kodi_resume}[/cyan]" if k else "-",
                f"[blue]{jelly_resume}[/blue]" if j else "-",
                f"[magenta]{status}[/magenta]"
            ]
            if idx % 2:
                row = [f"[dim]{cell}[/dim]" for cell in row]
            table.add_row(*row)

        return table

    def make_on_deck_table_shows(title, plex_items, kodi_items, jellyfin_items):
        table = Table(box=box.SIMPLE_HEAD, title=title, title_style="bold green", show_header=False, expand=True)
        add_aligned_platform_columns(table, "Show", "bold green")

        add_platform_label_row(table)  # 👈 added

        all_paths = sorted(set(plex_items) | set(kodi_items) | set(jellyfin_items))

        for idx, path in enumerate(all_paths):
            p = plex_items.get(path)
            k = kodi_items.get(path)
            j = jellyfin_items.get(path)

            if not is_on_deck_display_path(p, k, j):
                continue

            show_title = (p or k or j).get("combined_title") or (p or k or j).get("title") or "-"
            plex_resume = format_time(int(p.get("resume", 0))) if p else "-"
            kodi_resume = format_time(int(k.get("resume", 0))) if k else "-"
            jelly_resume = format_time(int(j.get("resume", 0))) if j else "-"
            status = "🌱"

            row = [
                show_title,
                f"[yellow]{plex_resume}[/yellow]" if p else "-",
                f"[cyan]{kodi_resume}[/cyan]" if k else "-",
                f"[blue]{jelly_resume}[/blue]" if j else "-",
                f"[magenta]{status}[/magenta]"
            ]
            if idx % 2:
                row = [f"[dim]{cell}[/dim]" for cell in row]
            table.add_row(*row)

        if table.row_count == 1:
            table.add_row("No On Deck", "", "", "", "")

        return table

    def make_continue_watching_table_platform(platform_name, items, media_type, color):
        if platform_name == "Plex":
            status_label = "Continue Watching"
        elif platform_name == "Kodi":
            status_label = "In Progress"
        elif platform_name == "Jellyfin":
            status_label = "Continue Watching"
        else:
            status_label = "Watching"

        table = Table(
            box=box.SIMPLE_HEAD,
            title=f"▶ {platform_name.capitalize()} {status_label}",
            title_style=f"bold {color}",
            show_header=False,
            header_style="bold",
            expand=True,
        )

        table.add_column("Title", style=f"bold {color}", width=max(18, min(30, console.width // 3)))
        table.add_column("Relative Path", style=color, ratio=1)
        table.add_column("Resume", style="cyan", justify="right", width=9, no_wrap=True)
        table.add_column("Status", style="white", justify="center", width=3, no_wrap=True)

        filtered_items = {
            k: v for k, v in items.items()
            if (v.get("media_type") == "movie" if media_type == "movie"
                else v.get("media_type") in ("show", "episode"))
            and v.get("status") != "unwatched" and v.get("resume", 0) > 0
        }

        for idx, path in enumerate(sorted(filtered_items)):
            item = filtered_items[path]
            title_str = item.get("combined_title") or item.get("title") or "-"
            rel_path = item.get("rel_path") or "-"
            resume_time = format_time(int(item.get("resume", 0)))
            status = "▶"

            row = [
                title_str,
                f"[{color}]{rel_path}[/{color}]",
                f"[{color}]{resume_time}[/{color}]",
                f"[{color}]{status}[/{color}]"
            ]
            if idx % 2:
                row = [f"[dim]{cell}[/dim]" for cell in row]
            table.add_row(*row)

        return table

    def make_empty_progress_table(label):
        table = Table(box=box.SIMPLE_HEAD, show_header=False, expand=True)
        add_aligned_platform_columns(table, "Title")
        add_platform_label_row(table)
        table.add_row(f"No In Progress {label}", "", "", "", "")
        return table

    plex_continue_movies_table = make_continue_watching_table_platform("Plex", plex_movies, "movie", "yellow")
    kodi_continue_movies_table = make_continue_watching_table_platform("Kodi", kodi_movies, "movie", "cyan")
    jelly_continue_movies_table = make_continue_watching_table_platform("Jellyfin", jelly_movies, "movie", "blue")

    plex_continue_shows_table = make_continue_watching_table_platform("Plex", plex_shows, "show", "yellow")
    kodi_continue_shows_table = make_continue_watching_table_platform("Kodi", kodi_shows, "show", "cyan")
    jelly_continue_shows_table = make_continue_watching_table_platform("Jellyfin", jelly_shows, "show", "blue")

    on_deck_shows_table = make_on_deck_table_shows("🌱 On Deck | Next Up", plex_shows, kodi_shows, jelly_shows)

    console.rule("")
    console.print()

    for label, tables in (
        ("Movies", (plex_continue_movies_table, kodi_continue_movies_table, jelly_continue_movies_table)),
        ("Shows", (plex_continue_shows_table, kodi_continue_shows_table, jelly_continue_shows_table)),
    ):
        console.print(f"[bold white]{'🎬' if label == 'Movies' else '📺'} {label}[/]", justify="center")
        filled = [table for table in tables if table.row_count > 0]
        for table in filled or [make_empty_progress_table(label)]:
            console.print(table)
            console.print()

    console.print(on_deck_shows_table)
    console.print()


def print_sync_comparison(plex_items, kodi_items, jellyfin_items):
    console.print()

    def split_by_type(items):
        movies = {k: v for k, v in items.items() if v.get("media_type") == "movie"}
        shows = {k: v for k, v in items.items() if v.get("media_type") in ("show", "episode")}
        return movies, shows

    plex_movies, plex_shows = split_by_type(plex_items)
    kodi_movies, kodi_shows = split_by_type(kodi_items)
    jelly_movies, jelly_shows = split_by_type(jellyfin_items)

    on_deck_paths = {
        path for path in set(plex_shows) | set(kodi_shows) | set(jelly_shows)
        if is_on_deck_display_path(plex_shows.get(path), kodi_shows.get(path), jelly_shows.get(path))
    }

    def make_sync_table(items_plex, items_kodi, items_jelly, media_type, on_deck=False):
        tbl = Table(box=box.SIMPLE_HEAD, show_header=False, expand=True)
        col_name = "Movie" if media_type == "movie" else "Show"
        add_aligned_platform_columns(tbl, col_name)

        add_platform_label_row(tbl)  # 👈 added

        all_paths = sorted(set(items_plex) | set(items_kodi) | set(items_jelly))
        if not all_paths:
            tbl.add_row(
                "No On Deck" if on_deck else f"No In Progress {'Movies' if media_type == 'movie' else 'Shows'}",
                "", "", "", ""
            )

        for idx, path in enumerate(all_paths):
            pi = items_plex.get(path)
            ki = items_kodi.get(path)
            ji = items_jelly.get(path)

            base = pi or ki or ji or {}
            title_str = base.get("combined_title") or base.get("title") or "-"
            pres = int(pi.get("resume", 0)) if pi else 0
            kres = int(ki.get("resume", 0)) if ki else 0
            jres = int(ji.get("resume", 0)) if ji else 0

            plex_time = format_time(pres)
            kodi_time = format_time(kres)
            jelly_time = format_time(jres)

            if pres == kres == jres:
                action = "🌱" if on_deck else "✔"
            else:
                action = "🔄"

            row = [
                title_str,
                f"[yellow]{plex_time}[/yellow]" if pi else "-",
                f"[cyan]{kodi_time}[/cyan]" if ki else "-",
                f"[blue]{jelly_time}[/blue]" if ji else "-",
                action,
            ]

            if idx % 2:
                row = [f"[dim]{c}[/dim]" for c in row]

            tbl.add_row(*row)

        return tbl

    movie_table = make_sync_table(plex_movies, kodi_movies, jelly_movies, "movie")
    show_table = make_sync_table(
        {path: item for path, item in plex_shows.items() if path not in on_deck_paths},
        {path: item for path, item in kodi_shows.items() if path not in on_deck_paths},
        {path: item for path, item in jelly_shows.items() if path not in on_deck_paths},
        "show",
    )
    on_deck_table = make_sync_table(
        {path: item for path, item in plex_shows.items() if path in on_deck_paths},
        {path: item for path, item in kodi_shows.items() if path in on_deck_paths},
        {path: item for path, item in jelly_shows.items() if path in on_deck_paths},
        "show", on_deck=True,
    )

    console.print("[bold white]🔄 Sync Comparison[/]", justify="center")
    console.print()
    for label, table in (("Movies", movie_table), ("Shows", show_table), ("On Deck", on_deck_table)):
        console.print(f"  [bold white]{label}[/]")
        console.print(table)
        console.print()


def print_sync_results(plex_items, kodi_items, jellyfin_items, actions):
    console.print()

    def split_by_type(items):
        movies = {k: v for k, v in items.items() if v.get("media_type") == "movie"}
        shows = {k: v for k, v in items.items() if v.get("media_type") in ("show", "episode")}
        return movies, shows

    plex_movies, plex_shows = split_by_type(plex_items)
    kodi_movies, kodi_shows = split_by_type(kodi_items)
    jelly_movies, jelly_shows = split_by_type(jellyfin_items)

    on_deck_paths = {
        path for path in set(plex_shows) | set(kodi_shows) | set(jelly_shows)
        if is_on_deck_display_path(plex_shows.get(path), kodi_shows.get(path), jelly_shows.get(path))
    }

    def make_sync_table(items_plex, items_kodi, items_jelly, media_type, on_deck=False):
        tbl = Table(box=box.SIMPLE_HEAD, show_header=False, expand=True)
        col_name = "Movie" if media_type == "movie" else "Show"
        add_aligned_platform_columns(tbl, col_name)

        add_platform_label_row(tbl)  # 👈 added

        all_paths = sorted(set(items_plex) | set(items_kodi) | set(items_jelly))
        if not all_paths:
            tbl.add_row(
                "No On Deck" if on_deck else f"No In Progress {'Movies' if media_type == 'movie' else 'Shows'}",
                "", "", "", ""
            )

        for idx, path in enumerate(all_paths):
            pi = items_plex.get(path)
            ki = items_kodi.get(path)
            ji = items_jelly.get(path)

            base = pi or ki or ji or {}
            title_str = base.get("combined_title") or base.get("title") or "-"
            pres = int(pi.get("resume", 0)) if pi else 0
            kres = int(ki.get("resume", 0)) if ki else 0
            jres = int(ji.get("resume", 0)) if ji else 0

            plex_time = format_time(pres)
            kodi_time = format_time(kres)
            jelly_time = format_time(jres)

            if pres == kres == jres:
                action = "🌱" if on_deck else "✅"
            else:
                action = "⚠"

            row = [
                title_str,
                f"[yellow]{plex_time}[/yellow]" if pi else "-",
                f"[cyan]{kodi_time}[/cyan]" if ki else "-",
                f"[blue]{jelly_time}[/blue]" if ji else "-",
                action,
            ]

            if idx % 2:
                row = [f"[dim]{c}[/dim]" for c in row]

            tbl.add_row(*row)

        return tbl

    movie_table = make_sync_table(plex_movies, kodi_movies, jelly_movies, "movie")
    show_table = make_sync_table(
        {path: item for path, item in plex_shows.items() if path not in on_deck_paths},
        {path: item for path, item in kodi_shows.items() if path not in on_deck_paths},
        {path: item for path, item in jelly_shows.items() if path not in on_deck_paths},
        "show",
    )
    on_deck_table = make_sync_table(
        {path: item for path, item in plex_shows.items() if path in on_deck_paths},
        {path: item for path, item in kodi_shows.items() if path in on_deck_paths},
        {path: item for path, item in jelly_shows.items() if path in on_deck_paths},
        "show", on_deck=True,
    )

    console.print("[bold white]✅ Sync Results[/]", justify="center")
    console.print()
    for label, table in (("Movies", movie_table), ("Shows", show_table), ("On Deck", on_deck_table)):
        console.print(f"  [bold white]{label}[/]")
        console.print(table)
        console.print()

###################################################
############# PREVIOUS PRINT TABLE FUNCTIONS ###############
###################################################

# def print_paths_tables(plex_items, kodi_items, jellyfin_items):
    # #On Deck Table
    # on_deck_table = Table(
        # box=box.SIMPLE_HEAD,
        # title="[magenta]🌱 On Deck / Next Up Items",
        # title_style="bold magenta"
    # )
    # on_deck_table.add_column("Type", style="bold magenta", no_wrap=True)
    # on_deck_table.add_column("Item ID", style="magenta", no_wrap=True)
    # on_deck_table.add_column("Relative Path", style="white")
    # on_deck_table.add_column("Resume", style="magenta", justify="right")

   # # Collect unwatched items (only shown in On Deck)
    # for i, (rel_path, item) in enumerate(plex_items.items()):
        # if item.get("status") != "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("ratingKey") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[magenta]{media_type}[/magenta]",
            # f"[magenta]{item_id}[/magenta]",
            # f"[magenta]{rel_path}[/magenta]",
            # f"[magenta]{resume_str}[/magenta]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # on_deck_table.add_row(*row)

    # for i, (rel_path, item) in enumerate(kodi_items.items()):
        # if item.get("status") != "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("idFile") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[magenta]{media_type}[/magenta]",
            # f"[magenta]{item_id}[/magenta]",
            # f"[magenta]{rel_path}[/magenta]",
            # f"[magenta]{resume_str}[/magenta]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # on_deck_table.add_row(*row)

    # for i, (rel_path, item) in enumerate(jellyfin_items.items()):
        # if item.get("status") != "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("id") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[magenta]{media_type}[/magenta]",
            # f"[magenta]{item_id}[/magenta]",
            # f"[magenta]{rel_path}[/magenta]",
            # f"[magenta]{resume_str}[/magenta]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # on_deck_table.add_row(*row)

    # #Plex Table
    # plex_table = Table(
        # box=box.SIMPLE_HEAD,
        # title="[yellow]🎬 Plex Continue Watching Items",
        # title_style="white"
    # )
    # plex_table.add_column("Type", style="bold green", no_wrap=True)
    # plex_table.add_column("Item ID", style="yellow", no_wrap=True)
    # plex_table.add_column("Relative Path", style="white")
    # plex_table.add_column("Resume", style="yellow", justify="right")

    # for i, (rel_path, item) in enumerate(plex_items.items()):
        # if item.get("status") == "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # if resume <= 0:
            # continue
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("ratingKey") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[yellow]{media_type}[/yellow]",
            # f"[yellow]{item_id}[/yellow]",
            # f"[yellow]{rel_path}[/yellow]",
            # f"[yellow]{resume_str}[/yellow]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # plex_table.add_row(*row)

    # #Kodi Table
    # kodi_table = Table(
        # box=box.SIMPLE_HEAD,
        # title="[cyan]📺 Kodi In Progress Items",
        # title_style="white"
    # )
    # kodi_table.add_column("Type", style="cyan", no_wrap=True)
    # kodi_table.add_column("Item ID", style="cyan", no_wrap=True)
    # kodi_table.add_column("Relative Path", style="white")
    # kodi_table.add_column("Resume", style="cyan", justify="right")

    # for i, (rel_path, item) in enumerate(kodi_items.items()):
        # if item.get("status") == "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # if resume <= 0:
            # continue
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("idFile") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[cyan]{media_type}[/cyan]",
            # f"[cyan]{item_id}[/cyan]",
            # f"[cyan]{rel_path}[/cyan]",
            # f"[cyan]{resume_str}[/cyan]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # kodi_table.add_row(*row)

    # #Jellyfin Table
    # jelly_table = Table(
        # box=box.SIMPLE_HEAD,
        # title="[blue]🍇 Jellyfin Continue Watching Items",
        # title_style="blue"
    # )
    # jelly_table.add_column("Type", style="blue", no_wrap=True)
    # jelly_table.add_column("Item ID", style="blue", no_wrap=True)
    # jelly_table.add_column("Relative Path", style="white")
    # jelly_table.add_column("Resume", style="blue", justify="right")

    # for i, (rel_path, item) in enumerate(jellyfin_items.items()):
        # if item.get("status") == "unwatched":
            # continue
        # resume = int(item.get("resume", 0))
        # if resume <= 0:
            # continue
        # media_type = item.get("media_type", "unknown").capitalize()
        # item_id = item.get("id") or "N/A"
        # resume_str = format_time(resume)
        # row = [
            # f"[blue]{media_type}[/blue]",
            # f"[blue]{item_id}[/blue]",
            # f"[blue]{rel_path}[/blue]",
            # f"[blue]{resume_str}[/blue]",
        # ]
        # if i % 2 != 0:
            # row = [f"[dim]{cell}[/dim]" for cell in row]
        # jelly_table.add_row(*row)

   # # Display Tables
    # console.rule("")
    # console.print("")

    # if on_deck_table.row_count > 0:
        # console.print(on_deck_table, style="magenta")
        # console.print("")

    # console.print(plex_table, style="yellow")
    # console.print(kodi_table, style="cyan")
    # console.print(jelly_table, style="blue")

# #Sync comparison results table
# def print_sync_comparison(plex_items, kodi_items, jellyfin_items):
    # console.print()
    # tbl = Table(box=box.SIMPLE_HEAD, title="[white]🔄 Pre-Sync Comparison", title_style="white")
    # tbl.add_column("[green]Type", style="green")
    # tbl.add_column("Title", style="white")
    # tbl.add_column("[yellow]Plex", justify="right", style="yellow")
    # tbl.add_column("[cyan]Kodi", justify="right", style="cyan")
    # tbl.add_column("[blue]Jellyfin", justify="right", style="blue")
    # tbl.add_column("[magenta]Action", style="magenta", justify="center")

    # #Filter only items with a resume >= 0
    # pd = {k: v for k, v in plex_items.items() if v.get("resume", 0) >= 0}
    # kd = {k: v for k, v in kodi_items.items() if v.get("resume", 0) >= 0}
    # jd = {k: v for k, v in jellyfin_items.items() if v.get("resume", 0) >= 0}

    # all_paths = sorted(set(pd) | set(kd) | set(jd))

    # for idx, rel_path in enumerate(all_paths):
        # pi = pd.get(rel_path)
        # ki = kd.get(rel_path)
        # ji = jd.get(rel_path)

       # # Use the first available title/metadata
        # base = pi or ki or ji or {}
        # title = base.get("combined_title") or base.get("title") or "-"
        # media_type = base.get("media_type", "Unknown").capitalize()

        # pres = int(pi.get("resume", 0)) if pi else 0
        # kres = int(ki.get("resume", 0)) if ki else 0
        # jres = int(ji.get("resume", 0)) if ji else 0

        # plex_time = format_time(pres) 
        # kodi_time = format_time(kres)        
        # jelly_time = format_time(jres)        
        
        # if pres == kres == jres:
            # action = "✔" if pres > 0 else "🌱"
        # else:
            # action = "🔄"

        # row = [media_type, title, plex_time, kodi_time, jelly_time, action]

      #  # Alternate row shading
        # if idx % 2:
            # row = [f"[dim]{c}[/dim]" for c in row]

        # tbl.add_row(*row)

    # console.print(tbl)
    
# #Final sync results table
# def print_final_sync_table(plex_items, kodi_items, jellyfin_items, actions):
    # console.print()
    # tbl = Table(box=box.SIMPLE_HEAD, title="[white]✅ Post-Sync State", title_style="white")
    # tbl.add_column("[green]Type", style="green")
    # tbl.add_column("Title", style="white")
    # tbl.add_column("[yellow]Plex", justify="right", style="yellow")
    # tbl.add_column("[cyan]Kodi", justify="right", style="cyan")
    # tbl.add_column("[blue]Jellyfin", justify="right", style="blue")
    # tbl.add_column("[magenta]Action", style="magenta", justify="center")

   # # Filter only items with a resume >= 0
    # pd = {k: v for k, v in plex_items.items() if v.get("resume", 0) >= 0}
    # kd = {k: v for k, v in kodi_items.items() if v.get("resume", 0) >= 0}
    # jd = {k: v for k, v in jellyfin_items.items() if v.get("resume", 0) >= 0}

    # all_paths = sorted(set(pd) | set(kd) | set(jd))

    # for idx, rel_path in enumerate(all_paths):
        # pi = pd.get(rel_path)
        # ki = kd.get(rel_path)
        # ji = jd.get(rel_path)

       # # Use the first available title/metadata
        # base = pi or ki or ji or {}
        # title = base.get("combined_title") or base.get("title") or "-"
        # media_type = base.get("media_type", "Unknown").capitalize()

        # pres = int(pi.get("resume", 0)) if pi else 0
        # kres = int(ki.get("resume", 0)) if ki else 0
        # jres = int(ji.get("resume", 0)) if ji else 0

        # plex_time = format_time(pres)
        # kodi_time = format_time(kres)
        # jelly_time = format_time(jres)

        # if pres == kres == jres:
            # action = "✅" if pres > 0 else "🌱"
        # else:
            # action = "⚠"

        # row = [media_type, title, plex_time, kodi_time, jelly_time, action]

     #  # Alternate row shading
        # if idx % 2:
            # row = [f"[dim]{c}[/dim]" for c in row]

        # tbl.add_row(*row)

    # console.print(tbl)
    
###################################################
################# MAIN FUNCTION ###################
###################################################

def main():
    try:
        load_dotenv("/config/.env")

        plex, kodi_db, jellyfin = welcome("/config/.env")

        # Keep the Plex lookup index across both sync passes in this execution.
        fetch_items._plex_target_index = {}

        with console.status("[bold green]Fetching initial resume items...[/bold green]"):
            plex_items = fetch_items(
                "plex",
                plex=plex,
                plex_media_root=PLEX_MEDIA_ROOT
            )
            kodi_items = fetch_items(
                "kodi",
                kodi_db=kodi_db,
                kodi_media_root=KODI_MEDIA_ROOT
            )
            jellyfin_items = fetch_items(
                "jellyfin",
                jellyfin=jellyfin,
                jellyfin_media_root=JELLYFIN_MEDIA_ROOT
            )

        print_paths(plex_items, kodi_items, jellyfin_items)
        print_sync_comparison(plex_items, kodi_items, jellyfin_items)

        parser = argparse.ArgumentParser(
            description="Sync playback progress across Plex, Kodi, and Jellyfin."
        )
        parser.add_argument(
            "-fetched",
            "--fetched",
            action="store_true",
            help="Show items fetched during fallback lookups."
        )
        args = parser.parse_args()

        # Determine sync actions
        actions, _ = sync_logic(
            plex_items,
            kodi_items,
            jellyfin_items,
            plex,
            kodi_db,
            jellyfin,
            plex_media_root=PLEX_MEDIA_ROOT,
            kodi_media_root=KODI_MEDIA_ROOT,
            jellyfin_media_root=JELLYFIN_MEDIA_ROOT,
            show_fetched=args.fetched,
        )

        # Apply sync changes
        sync_items(
            sync_instructions=actions,
            plex=plex,
            kodi_db=kodi_db,
            jellyfin=jellyfin,
        )

        # IMPORTANT:
        # Fetch everything again after updates so the JSON represents
        # the actual final state, not the planned state.
        with console.status("[bold green]Refreshing final sync state...[/bold green]"):
            final_plex_items = fetch_items(
                "plex",
                plex=plex,
                plex_media_root=PLEX_MEDIA_ROOT
            )
            final_kodi_items = fetch_items(
                "kodi",
                kodi_db=kodi_db,
                kodi_media_root=KODI_MEDIA_ROOT
            )
            final_jellyfin_items = fetch_items(
                "jellyfin",
                jellyfin=jellyfin,
                jellyfin_media_root=JELLYFIN_MEDIA_ROOT
            )

        # Rebuild state from real platform values
        _, final_sync_state = sync_logic(
            final_plex_items,
            final_kodi_items,
            final_jellyfin_items,
            plex,
            kodi_db,
            jellyfin,
            plex_media_root=PLEX_MEDIA_ROOT,
            kodi_media_root=KODI_MEDIA_ROOT,
            jellyfin_media_root=JELLYFIN_MEDIA_ROOT,
            show_fetched=False,
        )

        # Fully watched items have finished synchronization and are no longer tracked.
        # Only remove them after all three platforms report watched.
        completed_paths = {
            rel_path for rel_path, entry in final_sync_state.items()
            if all(
                (entry.get(platform) or {}).get("status") == "watched"
                and (entry.get(platform) or {}).get(item_key)
                for platform, item_key in (
                    ("plex", "ratingKey"),
                    ("kodi", "idFile"),
                    ("jellyfin", "id"),
                )
            )
        }
        for rel_path in completed_paths:
            final_sync_state.pop(rel_path, None)
            final_plex_items.pop(rel_path, None)
            final_kodi_items.pop(rel_path, None)
            final_jellyfin_items.pop(rel_path, None)

        # Save actual post-sync state
        save_sync_state(final_sync_state)

        # Print results using refreshed data
        print_sync_results(
            final_plex_items,
            final_kodi_items,
            final_jellyfin_items,
            actions
        )

        console.print(
            "[green]🏁 Sync Completed 🏁[/]",
            justify="center"
        )

    except KeyboardInterrupt:
        console.print("[yellow]Interrupted by user[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Fatal error: {e}[/red]")
        traceback.print_exc()


if __name__ == "__main__":
    main()
