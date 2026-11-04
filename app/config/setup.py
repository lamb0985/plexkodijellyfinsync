#!/usr/bin/env python3

import sys
import shutil
import getpass
from pathlib import Path

import requests
import pymysql

from plexapi.server import PlexServer
from dotenv import set_key, dotenv_values


# ============================================================
# Paths
# ============================================================

CONFIG_DIR = Path("/config")

TEMPLATE_ENV = CONFIG_DIR / ".env-template"
PENDING_ENV = CONFIG_DIR / ".env-pending"
FINAL_ENV = CONFIG_DIR / ".env"


# ============================================================
# .env Helpers
# ============================================================

def initialize_pending_env():
    if not TEMPLATE_ENV.exists():
        print(f"❌ Missing template: {TEMPLATE_ENV}")
        sys.exit(1)

    shutil.copy2(
        TEMPLATE_ENV,
        PENDING_ENV
    )

    print(f"✅ Created {PENDING_ENV}")


def update_env_value(key, value):
    set_key(
        str(PENDING_ENV),
        key,
        value,
        quote_mode="auto"
    )


def load_pending_env():
    return dotenv_values(
        str(PENDING_ENV)
    )


def display_pending_env():
    print("\n" + "=" * 70)
    print("Contents of /config/.env-pending")
    print("=" * 70)

    with open(PENDING_ENV, "r") as f:
        print(f.read())

    print("=" * 70)


# ============================================================
# Prompt Helpers
# ============================================================

def prompt_text(key, description, default=None):
    while True:

        if default is not None:
            value = input(
                f"{key} ({description}) [{default}]: "
            ).strip()

            if not value:
                return default

        else:

            value = input(
                f"{key} ({description}): "
            ).strip()

        if value:
            return value

        print("❌ Value cannot be blank.")


def prompt_password(key, description, default=None):

    while True:

        if default:

            value = getpass.getpass(
                f"{key} ({description}) [{default}]: "
            )

            if not value:
                return default

        else:

            value = getpass.getpass(
                f"{key} ({description}): "
            )

        if value:
            return value

        print("❌ Value cannot be blank.")


def prompt_ip(key, description):

    while True:

        value = input(
            f"{key} ({description}): "
        ).strip()

        parts = value.split(".")

        if len(parts) == 4:

            try:
                if all(
                    0 <= int(x) <= 255
                    for x in parts
                ):
                    return value

            except ValueError:
                pass

        print("❌ Invalid IP address.")


def prompt_port(key, description, default):

    value = input(
        f"{key} ({description}) [{default}]: "
    ).strip()

    if not value:
        return str(default)

    return value


# ============================================================
# Configuration Prompts
# ============================================================

def populate_configuration():

    print("\n========== Plex Configuration ==========")

    plex_ip = prompt_ip(
        "PLEX_SERVER",
        "Plex server IP"
    )

    plex_port = prompt_port(
        "PLEX_SERVER",
        "Plex server port",
        32400
    )

    update_env_value(
        "PLEX_SERVER",
        f"http://{plex_ip}:{plex_port}"
    )

    update_env_value(
        "PLEX_TOKEN",
        prompt_text(
            "PLEX_TOKEN",
            "Plex token"
        )
    )

    update_env_value(
        "PLEX_MEDIA_ROOT",
        prompt_text(
            "PLEX_MEDIA_ROOT",
            "Plex media root",
            "/data/media"
        )
    )

    update_env_value(
        "PLEX_EXCLUDE_LIBRARIES",
        prompt_text(
            "PLEX_EXCLUDE_LIBRARIES",
            "Excluded Plex libraries (separated by comma)",
            ""
        )
    )


    print("\n========== Kodi Configuration ==========")

    update_env_value(
        "KODI_DB_USER",
        prompt_text(
            "KODI_DB_USER",
            "Kodi DB username",
            "kodi"
        )
    )

    update_env_value(
        "KODI_DB_PASSWORD",
        prompt_password(
            "KODI_DB_PASSWORD",
            "Kodi DB password",
            "kodi"
        )
    )

    update_env_value(
        "KODI_DB_HOST",
        prompt_ip(
            "KODI_DB_HOST",
            "Kodi DB host"
        )
    )

    update_env_value(
        "KODI_DB_PORT",
        prompt_port(
            "KODI_DB_PORT",
            "Kodi DB port",
            3306
        )
    )

    update_env_value(
        "KODI_DB_NAME",
        prompt_text(
            "KODI_DB_NAME",
            "Kodi DB name",
            "MyVideos131"
        )
    )
    kodi_ip = prompt_ip(
        "KODI_WEBUI_RPC",
        "Kodi WebUI IP"
    )

    kodi_port = prompt_port(
        "KODI_WEBUI_RPC",
        "Kodi WebUI port",
        8080
    )

    update_env_value(
        "KODI_WEBUI_RPC",
        f"http://{kodi_ip}:{kodi_port}/jsonrpc"
    )


    update_env_value(
        "KODI_WEBUI_RPC_USER",
        prompt_text(
            "KODI_WEBUI_RPC_USER",
            "Kodi WebUI username",
            "kodi"
        )
    )

    update_env_value(
        "KODI_WEBUI_RPC_PASSWORD",
        prompt_password(
            "KODI_WEBUI_RPC_PASSWORD",
            "Kodi WebUI password",
            "kodi"
        )
    )


    update_env_value(
        "KODI_MEDIA_ROOT",
        prompt_text(
            "KODI_MEDIA_ROOT",
            "Kodi media root",
            "nfs://192.168.1.15/mnt/user/data/media"
        )
    )


    print("\n========== Jellyfin Configuration ==========")


    jf_ip = prompt_ip(
        "JELLYFIN_SERVER",
        "Jellyfin server IP"
    )

    jf_port = prompt_port(
        "JELLYFIN_SERVER",
        "Jellyfin server port",
        8096
    )

    update_env_value(
        "JELLYFIN_SERVER",
        f"http://{jf_ip}:{jf_port}"
    )


    update_env_value(
        "JELLYFIN_USER",
        prompt_text(
            "JELLYFIN_USER",
            "Jellyfin username"
        )
    )

    update_env_value(
        "JELLYFIN_PW",
        prompt_password(
            "JELLYFIN_PW",
            "Jellyfin password"
        )
    )

    update_env_value(
        "JELLYFIN_TOKEN",
        prompt_text(
            "JELLYFIN_TOKEN",
            "Jellyfin API token"
        )
    )

    update_env_value(
        "JELLYFIN_USER_ID",
        prompt_text(
            "JELLYFIN_USER_ID",
            "Jellyfin user ID"
        )
    )

    update_env_value(
        "JELLYFIN_MEDIA_ROOT",
        prompt_text(
            "JELLYFIN_MEDIA_ROOT",
            "Jellyfin media root",
            "/data/media"
        )
    )



# ============================================================
# Connectivity Tests
# ============================================================

def run_setup_tests():

    env = load_pending_env()

    results = {}


    # Plex
    try:

        print("\n🎬 Connecting to Plex...")

        PlexServer(
            env["PLEX_SERVER"],
            env["PLEX_TOKEN"]
        )

        print(
            "✅ Plex connection successful."
        )

        results["Plex"] = True


    except Exception as e:

        print(
            f"❌ Plex connection failed: {e}"
        )

        results["Plex"] = False



    # Kodi MariaDB
    try:

        print("\n📺 Connecting to Kodi MariaDB...")

        connection = pymysql.connect(
            host=env["KODI_DB_HOST"],
            user=env["KODI_DB_USER"],
            password=env["KODI_DB_PASSWORD"],
            database=env["KODI_DB_NAME"],
            port=int(env["KODI_DB_PORT"]),
            connect_timeout=5
        )

        connection.close()

        print(
            "✅ Kodi MariaDB connection successful."
        )

        results["Kodi Database"] = True


    except Exception as e:

        print(
            f"❌ Kodi MariaDB connection failed: {e}"
        )

        results["Kodi Database"] = False



    # Kodi RPC
    try:

        print("\n📺 Connecting to Kodi WebUI RPC...")

        response = requests.post(
            env["KODI_WEBUI_RPC"],
            json={
                "jsonrpc": "2.0",
                "method": "JSONRPC.Ping",
                "id": 1
            },
            auth=(
                env["KODI_WEBUI_RPC_USER"],
                env["KODI_WEBUI_RPC_PASSWORD"]
            ),
            timeout=5
        )


        if response.json().get("result") == "pong":

            print(
                "✅ Kodi WebUI RPC connection successful."
            )

            results["Kodi WebUI RPC"] = True


        else:

            print(
                "❌ Kodi WebUI RPC failed."
            )

            results["Kodi WebUI RPC"] = False


    except Exception as e:

        print(
            f"❌ Kodi WebUI RPC failed: {e}"
        )

        results["Kodi WebUI RPC"] = False



    # Jellyfin
    try:

        print("\n🍇 Connecting to Jellyfin...")

        response = requests.get(
            f"{env['JELLYFIN_SERVER']}/Users/{env['JELLYFIN_USER_ID']}",
            headers={
                "X-Emby-Token": env["JELLYFIN_TOKEN"]
            },
            timeout=5
        )

        response.raise_for_status()

        print(
            "✅ Jellyfin connection successful."
        )

        results["Jellyfin"] = True


    except Exception as e:

        print(
            f"❌ Jellyfin connection failed: {e}"
        )

        results["Jellyfin"] = False



    print(
        "\n========== Connectivity Summary =========="
    )

    for name, status in results.items():

        print(
            f"{name:<25} {'PASS' if status else 'FAIL'}"
        )

    return results
# ============================================================
# Final Actions
# ============================================================

def finalize_configuration():

    if FINAL_ENV.exists():
        FINAL_ENV.unlink()

    PENDING_ENV.rename(
        FINAL_ENV
    )

    print(
        "✅ Configuration finalized."
    )



def start_over():

    if PENDING_ENV.exists():
        PENDING_ENV.unlink()

    initialize_pending_env()

    populate_configuration()



def abort_configuration():

    if PENDING_ENV.exists():
        PENDING_ENV.unlink()

    print(
        "❌ Setup aborted."
    )

    sys.exit(1)



# ============================================================
# Main
# ============================================================

def setup():

    print(
        "=== Plex / Kodi / Jellyfin Setup ==="
    )

    initialize_pending_env()

    populate_configuration()


    print(
        "\n========== Connectivity Tests =========="
    )

    run_setup_tests()


    display_pending_env()


    while True:

        print(
            """
Choose an option:

1) Finalize configuration
2) Start over
3) Abort
"""
        )

        choice = input(
            "Selection: "
        ).strip()


        if choice == "1":

            finalize_configuration()
            break


        elif choice == "2":

            start_over()
            break


        elif choice == "3":

            abort_configuration()


        else:

            print(
                "❌ Invalid selection."
            )



if __name__ == "__main__":
    setup()