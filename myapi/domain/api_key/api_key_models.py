"""SQLAlchemy models for API key management"""

from datetime import date, datetime
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    TIMESTAMP,
    func,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from myapi.database import Base


class APIKey(Base):
    """API key storage table with encryption"""

    __tablename__ = "api_keys"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)  # 'GEMINI', 'OPENAI', 'PERPLEXITY'
    api_key_encrypted = Column(Text, nullable=False)
    api_key_hash = Column(String(64), unique=True, nullable=False)
    quota_limit = Column(Integer, nullable=False)  # Daily quota limit
    priority = Column(Integer, default=1)  # Lower = higher priority
    is_active = Column(Boolean, default=True)
    note = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    usage_records = relationship(
        "APIKeyUsage", back_populates="api_key", cascade="all, delete-orphan"
    )


class APIKeyUsage(Base):
    """Daily API key usage tracking"""

    __tablename__ = "api_key_usage"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True)
    api_key_id = Column(
        Integer, ForeignKey("crypto.api_keys.id", ondelete="CASCADE"), nullable=False
    )
    usage_date = Column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    last_request_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    api_key = relationship("APIKey", back_populates="usage_records")
