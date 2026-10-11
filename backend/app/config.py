"""Runtime paths and deployment settings."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv('RACKET_DATA', str(ROOT / 'data')))
WEIGHTS = Path(os.getenv('RACKET_WEIGHTS', str(ROOT / 'weights')))
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA / "sessions.db"}')
QUEUE_MODE = os.getenv('QUEUE_MODE', 'local')
for directory in (DATA, DATA / 'uploads', DATA / 'sessions', WEIGHTS):
    directory.mkdir(parents=True, exist_ok=True)
