"""
SIMS Plus - Staff Services Package

Re-exports all service classes for backward compatibility.
Existing imports like `from app.services.staff import StaffService` continue to work.
"""

from app.services.staff._shared import StaffServiceError
from app.services.staff.staff_service import StaffService
from app.services.staff.department_service import DepartmentService
from app.services.staff.document_service import StaffDocumentService
from app.services.staff.history_service import StaffHistoryService
from app.services.staff.workload_service import StaffWorkloadService

__all__ = [
    "StaffService",
    "DepartmentService",
    "StaffDocumentService",
    "StaffHistoryService",
    "StaffWorkloadService",
    "StaffServiceError",
]
