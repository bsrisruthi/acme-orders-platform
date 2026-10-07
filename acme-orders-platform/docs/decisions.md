# Decision log

Each entry: context, decision, trade-off. Entries marked TODO are mine to write.

## D1. App server: gunicorn, 1 worker x 4 threads
Flask's built-in server is a development server and says so on startup.
gunicorn is a production WSGI server. One worker on purpose: prometheus_client
keeps counters in process memory, so with several workers a scrape returns
whichever worker answered, and the numbers jump around.
Trade-off: no per-process CPU parallelism beyond threads. Scale by running more
instances instead. If more workers are ever needed, use prometheus_client's
multiprocess mode.

## D2. Python 3.12 in the image, tests run on 3.12
My laptop runs 3.14. Tests passing on 3.14 prove nothing about 3.12, so tests
and lock files are produced inside the python:3.12 image (see README).
Trade-off: slower than a local venv, but it removes "works on my machine".

## D3. What "ready" means
- Liveness (/healthz): the process can answer. It checks no dependencies. If it
  checked a database, a database outage would restart every instance and make
  the outage worse.
- Readiness (/readyz): this instance should receive traffic. Today that means
  startup has finished. When a datastore is added, readiness must check it.

## D4. State is in memory (known limitation)
Orders live in a Python list. My predictions for what GET /orders returns:
- After a restart: TODO
- Two instances behind one load balancer: TODO
- Two worker processes in one container: TODO

## D5. Metric labels use the route template
`/orders` is a label value; `/orders/12345` or a scanner's junk URL must not
be. Unmatched URLs are all recorded as `route="unmatched"`. Reason: every
distinct label value is a new time series in Prometheus.

## D6. Base image pinned by tag, not digest
Tags can be re-pushed; a digest cannot. I chose the tag for readability and
will revisit digest pinning alongside automated base-image updates.

## D7. Non-root, numeric UID 10001
A compromised process then cannot write to system paths or bind privileged
ports. A numeric UID lets an orchestrator verify the container is non-root,
which it cannot do with a user name.
