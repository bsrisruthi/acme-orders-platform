import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# One worker process on purpose: prometheus_client keeps counters in process
# memory, so several workers would each report their own partial numbers.
# We get concurrency from threads and scale out with replicas instead.
# See docs/decisions.md (D1).
workers = 1
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_class = "gthread"

timeout = 30
graceful_timeout = 30

accesslog = None  # the app writes its own JSON request logs
errorlog = "-"  # gunicorn's own messages go to stderr
loglevel = "info"

worker_tmp_dir = "/dev/shm"  # in-memory heartbeat file; safe with read-only root fs

# Not used; the control socket needs a writable home directory
control_socket_disable = True
