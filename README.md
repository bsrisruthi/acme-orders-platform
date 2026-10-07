# Acme Orders Platform

Scenario: I'm the first infra hire at a small startup. The dev team hands over a
small Python API and my job is to build everything around it to production
standard. This repo currently covers the app and its container.

## Layout

```
services/orders/   the API, its tests and its Dockerfile
docs/decisions.md  what I chose, why, and the trade-offs
```

## Run it

All commands run from `services/orders/`.

**1. Generate the pinned lock files.** Done inside the same Python version as
the image, so the pins match what actually runs:

```bash
docker run --rm -v "$PWD":/w -w /w python:3.12.11-slim-bookworm sh -c \
  "pip install -q pip-tools && \
   pip-compile -q requirements.in -o requirements.txt && \
   pip-compile -q requirements-dev.in -o requirements-dev.txt"
```

**2. Run the tests on the image's Python version (3.12):**

```bash
docker run --rm -v "$PWD":/w -w /w python:3.12.11-slim-bookworm sh -c \
  "pip install -q -r requirements.txt -r requirements-dev.txt && pytest -q"
```

**3. Build and inspect the image:**

```bash
docker build -t acme-orders:dev .
docker image ls acme-orders:dev
```

**4. Run it and poke it:**

```bash
docker run -d --name orders -p 8080:8000 acme-orders:dev
curl -i localhost:8080/healthz
curl -i localhost:8080/readyz
curl -i -X POST localhost:8080/orders -H 'Content-Type: application/json' -d '{"product":"coffee"}'
curl -i -X POST localhost:8080/orders -H 'Content-Type: application/json' -d '{"oops":1}'
curl -i localhost:8080/orders
curl -s localhost:8080/metrics | grep -E '^http_'
docker exec orders id          # expect uid=10001
docker logs orders             # JSON lines
docker rm -f orders
```

**5. Prove `PORT` works:** `docker run --rm -e PORT=9000 -p 9000:9000 acme-orders:dev`
and curl port 9000. The container port and the host port are separate things.

## Concepts (draft answers: rewrite in your own words)

**Why run containers as non-root?** If an attacker gets code execution inside
the container, root gives them far more room: writing anywhere in the
filesystem, binding privileged ports, and a shorter path to escaping the
container if there is a kernel or runtime flaw. Non-root limits the blast
radius and costs almost nothing.

**Liveness vs readiness.** Liveness asks "is this process stuck or dead?" and
failure means a restart. Readiness asks "should this instance get traffic right
now?" and failure means it is taken out of the Service's endpoints, with no
restart. A pod that is slow to start or temporarily overloaded should fail
readiness, not liveness.

**What does EXPOSE do?** It documents which port the app listens on and is
metadata only. It publishes nothing. Reaching the container from your laptop
needs `-p host:container` (e.g. `-p 8080:8000`).

**What does a multi-stage build buy us here?** The final image excludes pip's
cache and any build tooling. With pure-Python dependencies the gain is modest.
It matters much more when dependencies need compilers or system headers
(numpy, psycopg2 built from source), where the builder stage can be hundreds of
MB bigger than what you need at runtime.
