FROM python:3.11-slim

# Install needed tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    nano curl procps passwd && \
    mkdir -p /app /config /scripts /logs

# Copy app source
COPY app/ /app/
COPY requirements.txt /app/requirements.txt
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Install Python dependencies
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# Set entrypoint with dynamic umask support
ENTRYPOINT ["sh", "-c", "umask ${UMASK:-0002} && exec /entrypoint.sh"]

# Optional: expose Flask port
EXPOSE 5000
