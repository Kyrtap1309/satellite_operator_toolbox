import uuid
from datetime import datetime
from typing import override

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

Base = declarative_base()


class TLEDataModel(Base):
    """PostgreSQL model for TLE data."""

    __tablename__ = "tle_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    norad_id = Column(String(10), nullable=False, index=True)
    satellite_name = Column(String(255), nullable=False)
    tle_line1 = Column(Text, nullable=False)
    tle_line2 = Column(Text, nullable=False)
    epoch = Column(DateTime, nullable=False, index=True)
    mean_motion = Column(Float, nullable=True)
    eccentricity = Column(Float, nullable=True)
    inclination = Column(Float, nullable=True)
    arg_of_perigee = Column(Float, nullable=True)
    raan = Column(Float, nullable=True)
    mean_anomaly = Column(Float, nullable=True)
    rev_at_epoch = Column(Integer, nullable=True)
    bstar = Column(Float, nullable=True)
    element_set_no = Column(Integer, nullable=True)
    classification = Column(String(1), nullable=True)
    international_designator = Column(String(11), nullable=True)
    ephemeris_type = Column(Integer, nullable=True)
    source = Column(String(50), nullable=True)  # 'celestrak', 'spacetrack', etc.
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @override
    def __repr__(self) -> str:
        return f"<TLEDataModel(norad_id='{self.norad_id}', satellite_name='{self.satellite_name}', epoch='{self.epoch}')>"


class DatabaseManager:
    """Database connection and session manager."""

    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self) -> None:
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """Get database session."""
        return self.SessionLocal()
