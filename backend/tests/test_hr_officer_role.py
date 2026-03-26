"""
Tests for HR Officer role permissions.

Phase 1A: Verify the hr_officer role exists in UserRole enum and has
the correct permissions in AuthService.ROLE_PERMISSIONS.
"""

import pytest
from app.models.user import UserRole
from app.services.auth import AuthService


class TestHROfficerPermissions:
    """Verify HR Officer has correct permissions."""

    def test_hr_officer_exists_in_user_role_enum(self):
        """hr_officer should be a valid UserRole enum value."""
        assert UserRole.HR_OFFICER.value == "hr_officer"

    def test_hr_officer_in_role_permissions(self):
        """AuthService.ROLE_PERMISSIONS should have hr_officer entry."""
        assert "hr_officer" in AuthService.ROLE_PERMISSIONS

    def test_hr_officer_has_staff_permissions(self):
        """HR Officer should have staff.* permissions."""
        perms = AuthService.ROLE_PERMISSIONS["hr_officer"]
        assert "staff.*" in perms

    def test_hr_officer_can_read_students(self):
        """HR Officer has students.read (read-only)."""
        perms = AuthService.ROLE_PERMISSIONS["hr_officer"]
        assert "students.read" in perms

    def test_hr_officer_cannot_create_students(self):
        """HR Officer should NOT have students.create."""
        perms = AuthService.ROLE_PERMISSIONS["hr_officer"]
        assert "students.create" not in perms
        assert "students.update" not in perms
        assert "students.delete" not in perms

    def test_hr_officer_cannot_access_finance(self):
        """HR Officer should NOT have any finance permissions."""
        perms = AuthService.ROLE_PERMISSIONS["hr_officer"]
        finance_perms = [p for p in perms if p.startswith("finance")]
        assert finance_perms == []

    def test_hr_officer_cannot_access_exams(self):
        """HR Officer should NOT have any exam permissions."""
        perms = AuthService.ROLE_PERMISSIONS["hr_officer"]
        exam_perms = [p for p in perms if p.startswith("exam")]
        assert exam_perms == []

    def test_hr_officer_can_read_attendance(self):
        """HR Officer has attendance.read."""
        perms = AuthService.ROLE_PERMISSIONS["hr_officer"]
        assert "attendance.read" in perms

    def test_hr_officer_cannot_mark_attendance(self):
        """HR Officer should NOT be able to mark attendance."""
        perms = AuthService.ROLE_PERMISSIONS["hr_officer"]
        assert "attendance.mark" not in perms

    def test_hr_officer_jwt_permissions(self):
        """get_role_permissions returns correct list for hr_officer."""
        perms = AuthService.get_role_permissions("hr_officer")
        expected = ["staff.*", "students.read", "attendance.read", "reports.hr",
                    "users.read", "boarding.read"]
        assert set(perms) == set(expected)
