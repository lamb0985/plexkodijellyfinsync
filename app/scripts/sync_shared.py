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
from dotenv import load_dotenv, set_key
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
console = Console()

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
    
# Load sync state from the last known state file (for delta syncing)
def load_sync_state():
    if os.path.exists(SYNC_STATE_FILE):
        try:
            with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            console.print("[red]No last sync state file detected. Assuming first run...[/]")
    return {}

# Save current sync state to file to be referenced in future runs
def save_sync_state(state):
    try:
        with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
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
    def authenticate():
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Emby-Authorization": (
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
    if not JELLYFIN_TOKEN or not JELLYFIN_USER_ID:
        console.print("[yellow]⚠️ No Jellyfin token/user ID. Authenticating...[/]")
        return authenticate()

    try:
        r = requests.get(f"{JELLYFIN_SERVER}/Users/Me", headers={"X-Emby-Token": JELLYFIN_TOKEN}, timeout=5)
        if r.status_code == 200:
            return JELLYFIN_TOKEN, JELLYFIN_USER_ID
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
