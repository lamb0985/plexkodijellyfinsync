import eventlet
eventlet.monkey_patch()
import os
import subprocess
import threading
import json
import secrets
import tempfile
import stat
import hashlib
from io import StringIO
from flask import Flask, request, jsonify, Response, session, render_template_string, make_response
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv, dotenv_values
from dotenv.parser import parse_stream
from pathlib import Path
from collections import OrderedDict
from functools import wraps
from rich.console import Console

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY") or secrets.token_hex(32)
socketio = SocketIO(app, async_mode="eventlet")

LOG_DIR = Path("/logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "flask.log"

# Always-open, line-buffered log writer
log_file_handle = open(LOG_FILE, "a", buffering=1)
console = Console(file=log_file_handle, force_terminal=True, color_system="truecolor", no_color=False)

load_dotenv("/config/.env")
SYNC_SCRIPT_FILE = os.getenv("SYNC_SCRIPT_FILE", "/scripts/plexkodijellyfinsync.py")
SYNC_STATE_FILE = os.getenv("SYNC_STATE_FILE", "/config/.last_sync_state.json")
FLASK_USERNAME = os.getenv("FLASK_USERNAME", "admin")
FLASK_PASSWORD = os.getenv("FLASK_PASSWORD", "changeme")
FLASK_WEBUI_AUTH = os.getenv("FLASK_WEBUI_AUTH", "false").lower() in ("true", "1", "yes", "on")
ENV_PATH = Path("/config/.env")
ENV_CSRF_TOKEN = secrets.token_urlsafe(32)
browser_log_columns = None

@socketio.on("connect")
def authorize_socket(auth=None):
    if FLASK_WEBUI_AUTH and not session.get("webui_authenticated"):
        return False

def valid_log_columns(value):
    try:
        columns = int(value)
    except (TypeError, ValueError):
        return None
    return columns if 60 <= columns <= 240 else None

@socketio.on("log_width")
def set_log_width(value):
    global browser_log_columns
    columns = valid_log_columns(value)
    if columns is not None:
        browser_log_columns = columns

def check_auth(user, pw):
    return (bool(FLASK_USERNAME and FLASK_PASSWORD)
            and (FLASK_USERNAME, FLASK_PASSWORD) != ("admin", "changeme")
            and secrets.compare_digest((user or "").encode("utf-8"), FLASK_USERNAME.encode("utf-8"))
            and secrets.compare_digest((pw or "").encode("utf-8"), FLASK_PASSWORD.encode("utf-8")))

def authenticate():
    return Response("Auth required", 401, {"WWW-Authenticate": 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def wrapper(*a, **k):
        auth = request.authorization
        if not (FLASK_WEBUI_AUTH and session.get("webui_authenticated")) and not (
            auth and check_auth(auth.username, auth.password)
        ):
            return authenticate()
        return f(*a, **k)
    return wrapper

@app.before_request
def protect_optional_webui():
    # Plex webhooks retain their existing unauthenticated POST contract.
    if not FLASK_WEBUI_AUTH or request.path == "/plex":
        return None
    if session.get("webui_authenticated"):
        return None
    auth = request.authorization
    if auth and check_auth(auth.username, auth.password):
        session["webui_authenticated"] = True
        return None
    return authenticate()

def env_page(message="", error="", status=200, proposed_contents=None):
    template = (Path(__file__).resolve().parent / "env.html").read_text(encoding="utf-8")
    current_contents = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    contents = current_contents if proposed_contents is None else proposed_contents
    file_version = hashlib.sha256(current_contents.encode("utf-8")).hexdigest()
    response = make_response(render_template_string(
        template, contents=contents, csrf_token=ENV_CSRF_TOKEN, file_version=file_version,
        message=message, error=error,
    ), status)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.route("/env", methods=["GET", "POST"])
@requires_auth
def edit_env():
    if request.method == "GET":
        return env_page()
    contents = request.form.get("contents")
    submitted_token = request.form.get("csrf_token", "")
    if not secrets.compare_digest(submitted_token, ENV_CSRF_TOKEN):
        return env_page(error="Invalid form token. Reload and try again.", status=403)
    if contents is None or len(contents.encode("utf-8")) > 65536:
        return env_page(error="The configuration is missing or too large.", status=400)
    current_contents = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    file_version = hashlib.sha256(current_contents.encode("utf-8")).hexdigest()
    if not secrets.compare_digest(request.form.get("file_version", ""), file_version):
        return env_page(error="The file changed since you opened this page. Reload before saving.", status=409)
    if any(binding.error for binding in parse_stream(StringIO(contents))):
        return env_page(error="The configuration contains an invalid .env line.", status=400,
                        proposed_contents=contents)
    values = dotenv_values(stream=StringIO(contents))
    if not values.get("FLASK_USERNAME") or not values.get("FLASK_PASSWORD"):
        return env_page(error="Keep FLASK_USERNAME and FLASK_PASSWORD set to use this editor.", status=400,
                        proposed_contents=contents)
    temporary_path = None
    try:
        existing_mode = stat.S_IMODE(ENV_PATH.stat().st_mode)
        fd, temporary_path = tempfile.mkstemp(prefix=".env-", dir=ENV_PATH.parent)
        os.fchmod(fd, existing_mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, ENV_PATH)
    except OSError:
        return env_page(error="Could not save /config/.env. Check its permissions.", status=500)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
    return env_page(message="Saved /config/.env. Restart the container to apply the new settings.")

def run_command_logged(cmd, columns=None):
    env = os.environ.copy()
    env["PKJSYNC_WEB_LOG"] = "1"
    env.pop("NO_COLOR", None)
    width = columns if columns is not None else browser_log_columns
    if width is not None:
        env["COLUMNS"] = str(width)
    with open(LOG_FILE, "a") as f:
        process = subprocess.Popen(["bash", "-c", cmd], stdout=f, stderr=subprocess.STDOUT, env=env)
        process.wait()
    console.print(f"▶ Finished command: {cmd}")

def run_sync_script(columns=None):
    try:
        run_command_logged(f"python {SYNC_SCRIPT_FILE} --fetched", columns)
        console.print("▶ Manual sync triggered")
    except Exception as e:
        console.print(f"[red]Error starting sync:[/red] {e}")

@app.route("/plex", methods=["POST"])
def plex():
    data = (request.get_json(force=True) if request.content_type.startswith("application/json") else json.loads(request.form.get("payload", "{}")) if request.content_type.startswith("multipart/form-data") else {})
    event = data.get("event")
    if event in ("media.pause", "media.stop", "media.scrobble", "media.view"):
        console.print(f"[green]Plex event '{event}' → sync triggered[/green]")
        threading.Thread(target=run_sync_script, daemon=True).start()
    else:
        console.print(f"[yellow]Plex event '{event}' ignored[/yellow]")
    return jsonify({"status": "received", "event": event}), 200

@app.route("/", methods=["GET"])
#@requires_auth
def homepage():
    try:
        # Locates dashboard.html relative to app.py container or local directory
        base_dir = Path(__file__).resolve().parent
        paths_to_check = [base_dir / "dashboard.html", base_dir / "templates" / "dashboard.html"]
        for p in paths_to_check:
            if p.exists():
                return p.read_text(encoding="utf-8")
        return f"Error: 'dashboard.html' not found.", 404
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500

@app.route("/tracker", methods=["GET"])
#@requires_auth
def tracker_homepage():
    try:
        # Locates alt.html directly where app.py lives
        base_dir = Path(__file__).resolve().parent
        paths_to_check = [Path("/scripts/tracker.html"), base_dir / "tracker.html", base_dir / "templates" / "alt.html"]
        
        for p in paths_to_check:
            if p.exists():
                return p.read_text(encoding="utf-8")
                
        return "Error: 'alt.html' not found on application path.", 404
    except Exception as e:
        return f"Error loading tracker dashboard: {str(e)}", 500

@app.route("/sync", methods=["GET", "POST"])
#@requires_auth
def sync():
    threading.Thread(target=run_sync_script, args=(valid_log_columns(request.args.get("columns")),), daemon=True).start()
    return jsonify({"status": "Manual sync started"}), 200

@app.route("/reset", methods=["GET", "POST"])
#@requires_auth
def reset_sync():
    try:
        with open(SYNC_STATE_FILE, "w") as f:
            json.dump({}, f, indent=2)
        console.print("Sync states reset")
        threading.Thread(target=run_sync_script, args=(valid_log_columns(request.args.get("columns")),), daemon=True).start()
        return jsonify({"status": "Sync state reset, sync started"}), 200
    except Exception as e:
        console.print(f"[red]Reset failed:[/red] {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/status", methods=["GET"])
#@requires_auth
def status():
    if os.path.exists(SYNC_STATE_FILE):
        try:
            raw = json.load(open(SYNC_STATE_FILE))
            ordered = OrderedDict()
            for k in sorted(raw):
                ordered[k] = OrderedDict((p, raw[k][p]) for p in ("plex","kodi","jellyfin") if p in raw[k])
            return jsonify({"status": "✅ Sync status loaded", "data": ordered}), 200
        except Exception as e:
            console.print(f"[red]Status read failed:[/red] {e}")
            return jsonify({"status":"❌ Failed to read", "error": str(e)}), 500
    return jsonify({"status":"📭 No sync status", "path": str(SYNC_STATE_FILE)}), 404

@socketio.on("run_cmd")
def handle_run_cmd(cmd):
    try:
        process = subprocess.Popen(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=os.environ.copy())
        def stream_proc():
            for line in process.stdout:
                socketio.emit("cmd_output", line)
                with open(LOG_FILE, "a") as f:
                    f.write(line)
            err = process.stderr.read()
            if err:
                socketio.emit("cmd_output", err)
                with open(LOG_FILE, "a") as f:
                    f.write(err)
        threading.Thread(target=stream_proc, daemon=True).start()
    except Exception as e:
        emit("cmd_output", f"Error: {e}")

def tail_log():
    with open(LOG_FILE) as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                socketio.emit("log_update", line.rstrip())
            else:
                eventlet.sleep(0.2)

if __name__ == "__main__":
    threading.Thread(target=tail_log, daemon=True).start()
    console.print("▶ Flask & SocketIO listening on http://0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000)
