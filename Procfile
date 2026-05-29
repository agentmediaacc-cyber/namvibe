web: gunicorn app:app --bind 0.0.0.0:$PORT
worker: python scripts/rq_worker.py
cleanup: python scripts/chain_worker.py
