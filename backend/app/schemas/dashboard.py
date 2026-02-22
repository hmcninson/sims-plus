"""
SIMS Plus - Dashboard Schemas

Pydantic schemas for the dashboard analytics endpoints.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# =========================
# Dashboard Stats
# =========================


class AttendanceTodayStats(BaseSchema):
    present: int = 0
    absent: int = 0
    rate: float = 0.0


class FinanceSummaryStats(BaseSchema):
    total_billed: float = 0.0
    total_collected: float = 0.0
    collection_rate: float = 0.0
    outstanding: float = 0.0


class DashboardStats(BaseSchema):
    total_students: int = 0
    total_staff: int = 0
    total_classes: int = 0
    attendance_today: AttendanceTodayStats = AttendanceTodayStats()
    finance: FinanceSummaryStats = FinanceSummaryStats()


# =========================
# Trend Data Points
# =========================


class AttendanceTrendPoint(BaseSchema):
    date: date
    present: int = 0
    absent: int = 0
    late: int = 0
    rate: float = 0.0


class FeeCollectionTrendPoint(BaseSchema):
    month: str
    billed: float = 0.0
    collected: float = 0.0


class ClassPerformancePoint(BaseSchema):
    class_name: str
    average: float = 0.0
    highest: float = 0.0
    lowest: float = 0.0


class GenderDistribution(BaseSchema):
    male: int = 0
    female: int = 0


# =========================
# Recent Activity
# =========================


class RecentActivityItem(BaseSchema):
    event_type: str
    description: str
    timestamp: str
    user_name: Optional[str] = None


# =========================
# Composite Response
# =========================


class DashboardResponse(BaseSchema):
    stats: DashboardStats
    recent_activity: list[RecentActivityItem] = []
