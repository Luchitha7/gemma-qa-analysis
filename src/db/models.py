"""SQLAlchemy ORM models for Multi-Tenant QA Service."""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from src.db.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(50), primary_key=True, index=True)  # e.g., "S-NET", "Company-ABC"
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    documents = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")
    criteria = relationship("CriteriaConfig", back_populates="tenant", cascade="all, delete-orphan")
    evaluations = relationship("EvaluationReport", back_populates="tenant", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    raw_markdown = Column(Text, nullable=False)
    page_count = Column(Integer, default=1)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", back_populates="documents")


class CriteriaConfig(Base):
    __tablename__ = "criteria_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(20), default="All")  # "Call", "Email", "Chat", "All"
    category_weights = Column(JSON, nullable=True)  # {"Soft Skills": 0.25, "Technical": 0.50, ...}
    auto_fail_rules = Column(JSON, nullable=True)  # [{"name": "Discourtesy", "rule": "..."}]
    raw_json = Column(JSON, nullable=False)  # Full parsed criteria structure
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", back_populates="criteria")


class EvaluationReport(Base):
    __tablename__ = "evaluation_reports"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(50), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(20), default="Call")
    agent_name = Column(String(100), default="Agent")
    transcript = Column(Text, nullable=False)
    final_score = Column(Float, nullable=False)
    is_auto_fail = Column(Boolean, default=False)
    scorecard_json = Column(JSON, nullable=True)  # [{name, rating, score, reason}]
    sentiment_json = Column(JSON, nullable=True)  # RoBERTa sentiment line scores & tense moments
    rag_matches_json = Column(JSON, nullable=True)  # Retrieved policy chunks and accuracy
    summary = Column(Text, nullable=True)
    suggestions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", back_populates="evaluations")
