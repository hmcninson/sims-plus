"""
SIMS Plus - API v1 Router

Aggregates all API endpoints under /api/v1.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, tenant, onboarding, academic, schools, media, users, students, staff, attendance, exams, preschool, timetable, finance, notifications, audit, dashboard, boarding, transport, push, parent, teacher, chain, communication_settings, messaging

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
# Staff
# =========================
api_router.include_router(staff.router, prefix="/staff", tags=["Staff"])


# =========================
# Attendance
# =========================
api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])


# =========================
# Exams
# =========================
api_router.include_router(exams.router, prefix="/exams", tags=["Exams"])


# =========================
# Preschool
# =========================
api_router.include_router(preschool.router, tags=["Preschool"])


# =========================
# Timetable
# =========================
api_router.include_router(timetable.router, prefix="/timetable", tags=["Timetable"])


# =========================
# Finance
# =========================
api_router.include_router(finance.router, prefix="/finance", tags=["Finance"])


# =========================
# Notifications
# =========================
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])


# =========================
# Audit Logs
# =========================
api_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit"])


# =========================
# Dashboard
# =========================
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])


# =========================
# Boarding
# =========================
api_router.include_router(boarding.router, prefix="/boarding", tags=["Boarding"])


# =========================
# Transport
# =========================
api_router.include_router(transport.router, prefix="/transport", tags=["Transport"])


# =========================
# Push Notifications
# =========================
api_router.include_router(push.router, prefix="/push", tags=["Push Notifications"])


# =========================
# Parent Portal
# =========================
api_router.include_router(parent.router, prefix="/parent", tags=["Parent Portal"])


# =========================
# Teacher Portal
# =========================
api_router.include_router(teacher.router, prefix="/teacher", tags=["Teacher Portal"])


# =========================
# School Chain Management
# =========================
api_router.include_router(chain.router, prefix="/chain", tags=["Chain Management"])


# =========================
# Communication Settings
# =========================
api_router.include_router(communication_settings.router, prefix="/communication-settings", tags=["Communication"])


# =========================
# Messaging (SMS, Email, Recipients)
# =========================
api_router.include_router(messaging.router, prefix="/messaging", tags=["Messaging"])
