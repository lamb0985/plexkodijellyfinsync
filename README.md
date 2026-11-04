# plexkodijellyfinsync

**Sync watch progress between Plex, Kodi and Jellyfin**  

This Docker container runs a Python script that automatically synchronizes movie resume positions and watch status between a Plex media server and a Kodi client. It ensures your viewing progress stays consistent whether you watch on Plex or Kodi. By default, it runs the plexkodisync.py script every 900 seconds (can be adjusted by editing the sleep time in seconds inside entrypoint.sh inside the container)

Plex webhook (Plex Premium Feature): copy the http://ipaddress:5000/plex to Plex Webhook in settings to have it sync automatically when using a Plex client.

WebUI with sync, reset, status and tracker endpoints @ http://ipaddress:5000/

------

## Features

- Connects to Plex, Kodi and Jellyfin via API and database
- Syncs watch/unwatch status between platforms, resume points and up next.
- Supports multiple Plex movie libraries (option to exlude unwanted libraries in .env)
- Runs periodically (every 15 mins), on demand, or via webhook (plex only) to keep sync up to date
- Logs sync activity for easy debugging

---

## Requirements

- Plex Media Server with API access token
- Kodi with JSON-RPC (webui) enabled and accessible (I use a headless-kodi container)
- Access to Kodi's MariaDB (MySQL) database (used for multiple client syncs)
- Jellyfin Server with necessary tokens.
- Docker (for container usage)

---

## Setup Instructions

1. **Modify the `/config/.env` file**

   There will be a .env-template file you can use to build the .env inside 
   the /config/ folder on your docker host. Option available to use
   /config/setup.py from inside the container to populate .env file.   
   
**If you want to view what logs from the container, run from host terminal: 
sudo docker logs -f plexkodijellyfinsync