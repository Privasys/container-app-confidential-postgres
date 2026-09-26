# Contributing

Thank you for your interest in `container-app-confidential-postgres`.

## Filing issues

Use GitHub Issues on this repository. For security issues, see
[SECURITY.md](SECURITY.md) — please do not open public issues for
suspected vulnerabilities.

## Pull requests

1. Fork the repo and create a topic branch from `main`.
2. Keep changes small and focused; separate logically distinct work
   into separate PRs.
3. Build and run locally to confirm the API still starts and serves:
   ```
   docker build -t userstore .
   docker run --rm -e PORT=8000 -p 8000:8000 -v userstore-data:/data userstore
   ```
   The final attestable image is produced by the Privasys reproducible-build
   CI workflow, not locally.
4. The app listens only on the platform-injected `$PORT` (there is no
   hard-coded fallback). Do not reintroduce a fixed listen port — `8080` is
   reserved for the platform.

## Coding conventions

- Listen on `$PORT`. The platform runs containers on the host network and
  allocates a unique port per app; the listen port is the host port.
- Persist state only under the per-app sealed volume at `/data`.
- Read configuration from the environment; never bake secrets into the image.

## Licence and Contributor Licence Agreement

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

Before we can merge your first pull request, you need to accept the
[Privasys Contributor Licence Agreement](https://github.com/Privasys/cla). You
keep the copyright in your work; the agreement lets Privasys also license it
under other terms, and Privasys commits to keeping it available under an
open-source licence. A check on your pull request explains how to accept: one
comment, once, for every Privasys repository. If you contribute as part of your
work for an employer, your employer may need to sign the entity agreement
instead.
