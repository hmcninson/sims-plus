"""
SIMS Plus - API v1 Router

Aggregates all API endpoints under /api/v1.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, tenant, onboarding, academic, schools, media, users, students

api_router = APIRouter()


# =========================
# Health / Status
# =========================
@api_router.get("/status", tags=["Status"])
async def api_status() -> dict[str, str]:
    """API v1 status endpoint."""
    return {
        "status": "operational",
        "version": "v1",
        "message": "SIMS Plus API is running",
    }


# =========================
# Authentication
# =========================
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])


# =========================
# Tenant / Multi-tenancy
# =========================
api_router.include_router(tenant.router, prefix="/tenant", tags=["Tenant"])


# =========================
# Onboarding
# =========================
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])


# =========================
# Academic (Sprint 6)
# =========================
api_router.include_router(academic.router, prefix="/academic", tags=["Academic"])


# =========================
# Schools
# =========================
api_router.include_router(schools.router, prefix="/schools", tags=["Schools"])


# =========================
# Media / File Uploads
# =========================
api_router.include_router(media.router, prefix="/media", tags=["Media"])


# =========================
# User Management
# =========================
api_router.include_router(users.router, prefix="/users", tags=["Users"])


# =========================
# Students
# =========================
api_router.include_router(students.router, prefix="/students", tags=["Students"])
api_router.include_router(students.guardians_router, prefix="/guardians", tags=["Guardians"])


# =========================
# Future Route Imports
# =========================
# These will be added as modules are implemented:
#
# from app.api.v1.endpoints import auth, schools, students, staff, classes
# from app.api.v1.endpoints import subjects, attendance, exams, finance
#
# api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# api_router.include_router(schools.router, prefix="/schools", tags=["Schools"])
# api_router.include_router(students.router, prefix="/students", tags=["Students"])
# api_router.include_router(staff.router, prefix="/staff", tags=["Staff"])
# api_router.include_router(classes.router, prefix="/classes", tags=["Classes"])
# api_router.include_router(subjects.router, prefix="/subjects", tags=["Subjects"])
# api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])
# api_router.include_router(exams.router, prefix="/exams", tags=["Exams"])
# api_router.include_router(finance.router, prefix="/finance", tags=["Finance"])
