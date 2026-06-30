# Confidential user-data store (PostgreSQL + API)

A small but real example of running **your own backend confidentially** on
Privasys: a PostgreSQL database with an HTTP API in front, storing a B2C
product's user records. It runs inside a hardware-attested enclave (Intel TDX),
and Postgres keeps its data on the per-app **sealed `/data` volume** — so every
record is **encrypted at rest under a key only you (the app owner) control**.
The host, the operator, and Privasys never see the plaintext.

This is the "secure your users' data" story made concrete: you keep your stack,
we make it confidential and attestable.

## What it does

| Tool (`privasys.json`) | HTTP | Purpose |
| --- | --- | --- |
| `create_user` | `POST /create_user {name,email}` | Insert a user record |
| `get_user` | `POST /get_user {id}` | Read one record |
| `list_users` | `POST /list_users {}` | List records |
| — | `GET /health` | Liveness (the platform's readiness probe) |

The tools in `privasys.json` are surfaced to agents and the developer portal, so
the API becomes callable as MCP tools over attested RA-TLS.

## The container contract (what makes any app confidential-ready)

This app follows the three rules that let the platform run *any* container
confidentially — the same rules Claude applies when configuring your existing
backend:

1. **Listen on `$PORT`.** The platform runs containers on the host network and
   injects a unique `$PORT`; the app must listen on it (a hardcoded port
   collides with co-located apps and fails its health probe). Here the API reads
   `os.environ["PORT"]`.
2. **Persist to `/data`.** `/data` is the per-app encrypted volume; its key is
   reconstructed from the Enclave Vault constellation at boot. Anything written
   elsewhere is ephemeral. Here `PGDATA=/data/pgdata`, so the whole database is
   on the sealed volume.
3. **Serve `GET /health`.** The manager's readiness probe hits
   `localhost:$PORT/health`; return `200` when ready.

## Data protection

- **Encrypted at rest, key is yours.** The volume DEK is generated in the
  enclave and Shamir-split across the vault constellation; the platform never
  holds it. You can `privasys apps export-key` it at any time.
- **Survives upgrades only when you approve.** Deploy a new version (new code
  measurement) and the data key is *locked* to the old measurement until you
  promote the new one (`privasys apps upgrade`). The platform cannot approve for
  you.
- **Rotatable online.** `privasys apps rotate-key` re-keys the volume without
  re-encrypting the data or stopping the app.

## Build & deploy (your IP stays yours)

You build this image **yourself** — your private repo, your own reproducible
build — and push a **digest-pinned image to your private registry**. Privasys
runs that image confidentially and attests its digest **without ever seeing your
source, the image bytes, or your registry credentials**. The platform never
builds it; the reproducibility proof (source → digest) stays with you.

```sh
# 1. You build + push privately, reproducibly:
docker build -t registry.example.com/userstore:v1 .
docker push registry.example.com/userstore:v1        # note the @sha256:<digest>

# 2. Register the app by digest, with encrypted storage:
privasys apps create my-userstore --source package \
  --container-image registry.example.com/userstore@sha256:<digest> --storage
privasys apps store-listing my-userstore --description "Confidential user store" --category "Developer Tools"

# 3. Give the in-enclave manager a pull credential — it goes straight into the
#    vault; only the attested manager can read it, and only to pull your image.
#    Privasys never sees the token.
privasys registry add my-userstore --token <your-registry-PAT>

# 4. Deploy, then ALWAYS attest before trusting the endpoint:
privasys apps deploy my-userstore
privasys attest my-userstore
privasys apps call my-userstore create_user --data '{"name":"Ada","email":"ada@example.com"}'
```

A public image works too — skip step 3 and use a public `--container-image` ref.

## Run locally

```sh
docker build -t userstore .
docker run --rm -e PORT=8000 -p 8000:8000 -v userstore-data:/data userstore
curl -s localhost:8000/health
curl -s localhost:8000/create_user -d '{"name":"Ada","email":"ada@example.com"}'
```
