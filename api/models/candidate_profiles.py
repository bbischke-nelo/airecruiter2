"""CandidateProfile model for storing rich candidate data from Workday.

This model stores candidate background information that can be reused
across multiple applications from the same candidate. Data includes:
- Contact information (email, phone, location)
- Work history from Workday
- Education history
- Skills

The profile is linked by external_candidate_id from Workday.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship

from api.config.database import Base


class CandidateProfile(Base):
    """Candidate profile with background data from Workday."""

    __tablename__ = "candidate_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Workday identifiers
    external_candidate_id = Column(String(255), unique=True, nullable=False, index=True)
    candidate_wid = Column(String(100), nullable=True)  # Workday WID

    # Contact information
    primary_email = Column(String(255), nullable=True)
    secondary_email = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)

    # Background data (stored as JSON strings)
    work_history = Column(Text, nullable=True)  # JSON array of work experiences
    education = Column(Text, nullable=True)     # JSON array of education entries
    skills = Column(Text, nullable=True)        # JSON array of skills

    # Metadata
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    applications = relationship("Application", back_populates="candidate_profile")

    def __repr__(self):
        return f"<CandidateProfile {self.external_candidate_id}>"
