import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_DISABLE_IP_REPUTATION"] = "1"
os.environ["FLASK_DEBUG"] = "0"
os.environ["FLASK_ENV"] = "production"
os.environ["ENV"] = "production"

from app import app

app.run(
    host="0.0.0.0",
    port=5000,
    debug=False,
    use_reloader=False,
    threaded=True
)
