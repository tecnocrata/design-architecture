import multiprocessing
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

load_dotenv(override=True)

max_requests = 1000
max_requests_jitter = 50
log_file = "-"
bind = "0.0.0.0:50505"

if not os.getenv("RUNNING_IN_PRODUCTION"):
    reload = True

num_cpus = multiprocessing.cpu_count()
workers = (num_cpus * 2) + 1
worker_class = "uvicorn.workers.UvicornWorker"

timeout = 120