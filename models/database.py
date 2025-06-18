import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

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
    mean_motion = Column(Float)
    eccentricity = Column(Float)
    inclination = Column(Float)
    arg_of_perigee = Column(Float)
    raan = Column(Float)
    mean_anomaly = Column(Float)
    rev_at_epoch = Column(Integer)
    bstar = Column(Float)
    element_set_no = Column(Integer)
    classification = Column(String(1))
    international_designator = Column(String(11))
    ephemeris_type = Column(Integer)
    source = Column(String(50))  # 'celestrak', 'spacetrack', etc.
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<TLEDataModel(norad_id='{self.norad_id}', satellite_name='{self.satellite_name}', epoch='{self.epoch}')>"
        )


class DatabaseManager:
    """Database connection and session manager."""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self):
        """Get database session."""
        return self.SessionLocal()
