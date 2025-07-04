from sqlalchemy import Column, Integer, String, Date, JSON
from myapi.database import Base


class AiAnalysisModel(Base):
    __tablename__ = "ai_analysis"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True)
    value = Column(JSON, nullable=False)
