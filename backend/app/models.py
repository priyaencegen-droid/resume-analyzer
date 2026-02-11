from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text
from .database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="processing")
    total_files = Column(Integer)
    processed_files = Column(Integer, default=0)

    def __repr__(self):
        return f"<Job(id={self.id}, status={self.status}, processed={self.processed_files}/{self.total_files})>"


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    name = Column(String, default="Unknown")
    score = Column(Float, default=0.0)
    classification = Column(String, default="Partial")
    summary = Column(Text, default="")

    def __repr__(self):
        return f"<Candidate(id={self.id}, name={self.name}, score={self.score}, classification={self.classification})>"
