"""Durable snapshots; a single worker owns each session's processing state."""
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, JSON, update, delete
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
Base = declarative_base()

class SessionRow(Base):
    __tablename__ = 'sessions'
    id = Column(String, primary_key=True)
    payload = Column(JSON, nullable=False)

Base.metadata.create_all(engine)
Database = sessionmaker(engine)

class ConcurrentUpdate(RuntimeError):
    pass


def save(payload):
    previous = payload.get('updated_at')
    payload['updated_at'] = datetime.now(timezone.utc).isoformat()
    with Database.begin() as db:
        if previous is None:
            db.add(SessionRow(id=payload['id'], payload=payload))
        else:
            result = db.execute(update(SessionRow).where(SessionRow.id == payload['id'],
                SessionRow.payload['updated_at'].as_string() == previous).values(payload=payload))
            if result.rowcount != 1:
                payload['updated_at'] = previous
                raise ConcurrentUpdate('Session changed or was deleted. Refresh and try again.')

def get(session_id):
    with Database() as db:
        row = db.get(SessionRow, session_id)
        return row.payload if row else None

def recent():
    with Database() as db:
        rows = db.query(SessionRow).all()
        return sorted((row.payload for row in rows), key=lambda x: x['updated_at'], reverse=True)

def transition(payload, expected):
    """Compare-and-set the job state so duplicate starts cannot claim one session."""
    previous = payload.get('updated_at')
    payload['updated_at'] = datetime.now(timezone.utc).isoformat()
    with Database.begin() as db:
        result = db.execute(update(SessionRow).where(SessionRow.id == payload['id'],
            SessionRow.payload['status'].as_string().in_(expected),
            SessionRow.payload['updated_at'].as_string() == previous).values(payload=payload))
        if result.rowcount != 1:
            payload['updated_at'] = previous
        return result.rowcount == 1


def remove_claimed(session_id):
    with Database.begin() as db:
        result = db.execute(delete(SessionRow).where(SessionRow.id == session_id,
            SessionRow.payload['status'].as_string() == 'deleting'))
        if result.rowcount != 1:
            raise ConcurrentUpdate('Session deletion claim was lost.')


def source_references(source, excluding):
    return any(row['id'] != excluding and row.get('source') == source for row in recent())
