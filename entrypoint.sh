#!/bin/sh
set -e

# Set defaults
PUID=${PUID:-1000}
PGID=${PGID:-100}
UMASK=${UMASK:-0002}

# Validate UMASK
case "$UMASK" in
  [0-7][0-7][0-7][0-7]) ;;
  *) echo "❌ Invalid UMASK: $UMASK"; exit 1 ;;
esac

echo "🔐 Applying UMASK: $UMASK"
umask "$UMASK"

# Create group if it doesn't exist
if ! getent group "$PGID" >/dev/null; then
  echo "👥 Creating group with GID $PGID"
  addgroup --gid "$PGID" appgroup
fi

# Create user if it doesn't exist
if ! getent passwd "$PUID" >/dev/null; then
  echo "👤 Creating user with UID $PUID"
  adduser --uid "$PUID" --gid "$PGID" --disabled-password --gecos "" appuser
fi

echo "📁 Setting ownership for /app /config /scripts /logs"
chown -R "$PUID:$PGID" /app /config /scripts /logs || true

echo "🛠️ Checking and populating /config..."
if [ -z "$(ls -A /config 2>/dev/null)" ]; then
  echo "📁 /config is empty, copying default config from /app/config..."
  cp -rv /app/config/. /config/
else
  echo "✅ /config already populated"
fi

echo "🛠️ Checking and populating /scripts..."
if [ -z "$(ls -A /scripts 2>/dev/null)" ]; then
  echo "📁 /scripts is empty, copying default scripts from /app/scripts..."
  cp -rv /app/scripts/* /scripts/
else
  echo "✅ /scripts already populated"
fi

echo "🚀 Starting Flask webhook server in background..."
su appuser -c "umask $UMASK && python3 /scripts/flask-webhook.py &"

echo "🔁 Starting main sync loop every 15 minutes..."
while true; do
  su appuser -c "umask $UMASK && python3 /scripts/plexkodijellyfinsync.py"
  sleep 900
done

wait
