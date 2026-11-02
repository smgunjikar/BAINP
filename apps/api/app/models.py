"""Minimal foundation of the future schema. Demo records are always fictional."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def utcnow(): return datetime.now(timezone.utc)

class Participant(Base):
    __tablename__='participants'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(16), default='en')

class AssessmentSession(Base):
    __tablename__='assessment_sessions'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'), index=True)
    task_version: Mapped[str] = mapped_column(String(64), default='attention-target-v0.1')
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    language: Mapped[str] = mapped_column(String(16), default='en')
    device: Mapped[str] = mapped_column(String(50), default='browser')
    correct: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    quality_status: Mapped[str] = mapped_column(String(36))
    mean_response_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    trials: Mapped[list['TaskTrial']] = relationship(back_populates='session', cascade='all, delete-orphan')

class TaskTrial(Base):
    __tablename__='task_trials'
    id: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('assessment_sessions.id'))
    position: Mapped[int] = mapped_column(Integer)
    stimulus: Mapped[str] = mapped_column(String(10))
    pressed: Mapped[bool] = mapped_column(Boolean)
    response_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    correct: Mapped[bool] = mapped_column(Boolean)
    session: Mapped[AssessmentSession] = relationship(back_populates='trials')

class ConsentGrant(Base):
    __tablename__='consent_grants'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    scope: Mapped[str] = mapped_column(String(80))
    allowed: Mapped[bool] = mapped_column(Boolean)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class HealthObservation(Base):
    __tablename__='health_observations'
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey('participants.id'))
    observation_type: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(80))
    measurement_quality: Mapped[str] = mapped_column(String(40))

class CareReview(Base):
    __tablename__='care_reviews'
    case_id: Mapped[str] = mapped_column(String(50),primary_key=True)
    status: Mapped[str] = mapped_column(String(40),default='not_started')
    notes: Mapped[str] = mapped_column(Text,default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class AuditEvent(Base):
    __tablename__='audit_events'
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utcnow)
    event_type: Mapped[str] = mapped_column(String(90))
    object_ref: Mapped[str] = mapped_column(String(100))
    metadata_json: Mapped[dict] = mapped_column(JSON,default=dict)
