import os
from uuid import uuid4
from pathlib import Path

os.environ['RACKET_DATA'] = str(Path(__file__).resolve().parents[2] / 'data' / 'tests' / uuid4().hex)
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(os.environ['RACKET_DATA']) / 'tests.db')
