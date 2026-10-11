"""Windows-friendly local worker or Redis-backed Celery deployment."""
from concurrent.futures import ThreadPoolExecutor
import os
from .config import QUEUE_MODE

local_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='racket-session')

def enqueue(session_id):
    if QUEUE_MODE == 'celery':
        process_session.delay(session_id)
    else:
        from .pipeline import run_session
        local_worker.submit(run_session, session_id)

from celery import Celery
celery = Celery('racket', broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
celery.conf.update(worker_prefetch_multiplier=1, task_acks_late=False, task_serializer='json', accept_content=['json'])

@celery.task(name='racket.process_session')
def process_session(session_id):
    from .pipeline import run_session
    run_session(session_id)
