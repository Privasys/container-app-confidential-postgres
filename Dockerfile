# Confidential user-data store: PostgreSQL + a small HTTP API in one container.
#
# Postgres keeps its data directory on the per-app sealed /data volume, so every
# user record is encrypted at rest under a key only the app owner controls — the
# host, the operator, and Privasys never see the plaintext. The platform builds
# this image reproducibly from the Git commit, so the running measurement is
# verifiable from source.
FROM postgres:16-bookworm

# A tiny stdlib HTTP API (no web framework) sits in front of the local Postgres;
# it is what the platform exposes. python3-psycopg2 comes from Debian so the
# build stays deterministic.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends python3 python3-psycopg2; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

# The platform runs containers on the host network and injects a unique $PORT;
# the API binds it (the manager's health probe hits localhost:$PORT/health).
# No fixed PORT is baked and no port is EXPOSEd — $PORT is required at runtime
# (host networking makes EXPOSE a no-op anyway).

ENTRYPOINT ["/app/entrypoint.sh"]
