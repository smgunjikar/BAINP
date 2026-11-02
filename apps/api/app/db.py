"""Demo-only local persistence; real patient use requires security/consent implementation."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

class Base(DeclarativeBase):
    pass

def make_engine(url: str):
    if url in ('sqlite://', 'sqlite:///:memory:'):
        return create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    return create_engine(url, connect_args={'check_same_thread': False} if url.startswith('sqlite') else {})

def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
