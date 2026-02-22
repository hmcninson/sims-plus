"""
SIMS Plus - Staff Services Package

Re-exports all service classes for backward compatibility.
Existing imports like `from app.services.staff import StaffService` continue to work.
"""

from app.services.staff._shared import StaffServiceError
from app.services.staff.staff_service import StaffService
from app.services.staff.department_service import DepartmentService

__all__ = [
    "StaffService",
    "DepartmentService",
    "StaffServiceError",
]
