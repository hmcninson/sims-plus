"""
Master permissions catalog.

Defines all available permissions in the system, organized by module.
Used by:
1. CustomRoleService — validates that custom role permissions are valid
2. Frontend permission picker — displays categorized checkboxes
3. ROLE_PERMISSIONS in auth.py — references these same strings

IMPORTANT: Every permission string used in ROLE_PERMISSIONS must appear
here. If you add a new permission to any role, add it to this catalog too.
"""

PERMISSIONS_CATALOG = [
    {
        "module": "Students",
        "permissions": [
            {"key": "students.read", "label": "View students", "description": "View student profiles and enrollment data"},
            {"key": "students.create", "label": "Create students", "description": "Register new students"},
            {"key": "students.update", "label": "Edit students", "description": "Update student profiles"},
            {"key": "students.delete", "label": "Delete students", "description": "Remove student records"},
            {"key": "students.import", "label": "Import students", "description": "Bulk import from CSV"},
            {"key": "students.export", "label": "Export students", "description": "Export student data"},
        ],
    },
    {
        "module": "Staff",
        "permissions": [
            {"key": "staff.read", "label": "View staff", "description": "View staff profiles"},
            {"key": "staff.create", "label": "Create staff", "description": "Add new staff members"},
            {"key": "staff.update", "label": "Edit staff", "description": "Update staff profiles"},
            {"key": "staff.delete", "label": "Delete staff", "description": "Remove staff records"},
        ],
    },
    {
        "module": "Academic",
        "permissions": [
            {"key": "classes.read", "label": "View classes", "description": "View class structure"},
            {"key": "classes.create", "label": "Create classes", "description": "Add new classes"},
            {"key": "classes.update", "label": "Edit classes", "description": "Modify class settings"},
            {"key": "classes.delete", "label": "Delete classes", "description": "Remove classes"},
            {"key": "subjects.read", "label": "View subjects", "description": "View subject catalog"},
            {"key": "subjects.create", "label": "Create subjects", "description": "Add new subjects"},
            {"key": "subjects.update", "label": "Edit subjects", "description": "Modify subjects"},
            {"key": "subjects.delete", "label": "Delete subjects", "description": "Remove subjects"},
            {"key": "academics.read", "label": "View academic settings", "description": "View grading, terms, academic years"},
            {"key": "academics.create", "label": "Create academic records", "description": "Create academic years, terms"},
            {"key": "academics.update", "label": "Edit academic settings", "description": "Modify academic config"},
            {"key": "academics.delete", "label": "Delete academic records", "description": "Remove academic years, terms"},
            {"key": "grading.read", "label": "View grading scales", "description": "View grading configuration"},
            {"key": "grading.create", "label": "Create grading scales", "description": "Add grading scales"},
            {"key": "grading.update", "label": "Edit grading scales", "description": "Modify grading scales"},
            {"key": "grading.delete", "label": "Delete grading scales", "description": "Remove grading scales"},
        ],
    },
    {
        "module": "Attendance",
        "permissions": [
            {"key": "attendance.read", "label": "View attendance", "description": "View attendance records and reports"},
            {"key": "attendance.mark", "label": "Mark attendance", "description": "Record student attendance"},
            {"key": "attendance.create", "label": "Create attendance records", "description": "Create attendance entries"},
            {"key": "attendance.update", "label": "Edit attendance", "description": "Modify attendance records"},
            {"key": "attendance.delete", "label": "Delete attendance", "description": "Remove attendance records"},
        ],
    },
    {
        "module": "Exams & Assessment",
        "permissions": [
            {"key": "exams.read", "label": "View exams", "description": "View exam definitions and schedules"},
            {"key": "exams.create", "label": "Create exams", "description": "Create new exams"},
            {"key": "exams.update", "label": "Edit exams", "description": "Modify exam definitions"},
            {"key": "exams.delete", "label": "Delete exams", "description": "Remove exam records"},
            {"key": "exams.scores.read", "label": "View scores", "description": "View exam scores"},
            {"key": "exams.scores.enter", "label": "Enter scores", "description": "Enter/edit exam scores"},
            {"key": "exams.scores.submit", "label": "Submit scores", "description": "Submit scores for approval"},
            {"key": "exams.ca.read", "label": "View CA scores", "description": "View continuous assessment scores"},
            {"key": "exams.ca.enter", "label": "Enter CA scores", "description": "Enter continuous assessment scores"},
            {"key": "exams.ca.create", "label": "Create CA records", "description": "Create continuous assessments"},
            {"key": "exams.ca.update", "label": "Update CA records", "description": "Update continuous assessments"},
            {"key": "exams.reports", "label": "Generate reports", "description": "Generate report cards and transcripts"},
        ],
    },
    {
        "module": "Finance",
        "permissions": [
            {"key": "finance.read", "label": "View finance", "description": "View fees, invoices, payments"},
            {"key": "finance.create", "label": "Create financial records", "description": "Create invoices, record payments"},
            {"key": "finance.update", "label": "Edit financial records", "description": "Modify invoices, fee structures"},
            {"key": "finance.delete", "label": "Delete financial records", "description": "Remove financial records"},
            {"key": "finance.invoices.read", "label": "View invoices", "description": "View invoice details (parent access)"},
            {"key": "finance.reports", "label": "Financial reports", "description": "Generate financial reports"},
        ],
    },
    {
        "module": "Preschool",
        "permissions": [
            {"key": "preschool.read", "label": "View preschool", "description": "View observations, logs, assessments"},
            {"key": "preschool.create", "label": "Create preschool records", "description": "Add observations, assessments"},
            {"key": "preschool.update", "label": "Edit preschool records", "description": "Modify observations, assessments"},
            {"key": "preschool.delete", "label": "Delete preschool records", "description": "Remove preschool data"},
        ],
    },
    {
        "module": "Boarding",
        "permissions": [
            {"key": "boarding.read", "label": "View boarding", "description": "View dormitories, bed assignments, exeats"},
            {"key": "boarding.write", "label": "Manage boarding", "description": "Manage dormitories, assign beds, create exeats"},
            {"key": "boarding.exeat.approve", "label": "Approve exeats", "description": "Approve or reject student exeat requests"},
        ],
    },
    {
        "module": "Communication",
        "permissions": [
            {"key": "communications.read", "label": "View messages", "description": "View sent messages and history"},
            {"key": "communications.send", "label": "Send messages", "description": "Send SMS and email messages"},
            {"key": "communications.create", "label": "Create messages", "description": "Create announcements and messages"},
            {"key": "communications.update", "label": "Edit messages", "description": "Edit draft messages"},
            {"key": "communications.delete", "label": "Delete messages", "description": "Remove messages"},
        ],
    },
    {
        "module": "Reports",
        "permissions": [
            {"key": "reports.academic", "label": "Academic reports", "description": "Generate academic reports"},
            {"key": "reports.financial", "label": "Financial reports", "description": "Generate financial reports"},
            {"key": "reports.hr", "label": "HR reports", "description": "Generate HR/staff reports"},
        ],
    },
    {
        "module": "User Management",
        "permissions": [
            {"key": "users.read", "label": "View users", "description": "View user accounts"},
            {"key": "users.create", "label": "Create users", "description": "Create new user accounts"},
            {"key": "users.update", "label": "Edit users", "description": "Modify user accounts and roles"},
            {"key": "users.delete", "label": "Delete users", "description": "Deactivate/delete user accounts"},
        ],
    },
    {
        "module": "Admissions",
        "permissions": [
            {"key": "admissions.read", "label": "View admissions", "description": "View applications and admission periods"},
            {"key": "admissions.create", "label": "Create admissions", "description": "Create admission periods and forms"},
            {"key": "admissions.update", "label": "Edit admissions", "description": "Modify admission settings"},
            {"key": "admissions.delete", "label": "Delete admissions", "description": "Remove admission records"},
            {"key": "admissions.review", "label": "Review applications", "description": "Accept/reject applications"},
        ],
    },
    {
        "module": "Curriculum",
        "permissions": [
            {"key": "curriculum.read", "label": "View curriculum", "description": "View curriculum profiles and mappings"},
            {"key": "curriculum.create", "label": "Create curriculum records", "description": "Create curriculum profiles"},
            {"key": "curriculum.update", "label": "Edit curriculum", "description": "Modify curriculum settings"},
            {"key": "curriculum.delete", "label": "Delete curriculum records", "description": "Remove curriculum profiles"},
        ],
    },
    {
        "module": "Transport",
        "permissions": [
            {"key": "transport.read", "label": "View transport", "description": "View routes, vehicles, assignments"},
            {"key": "transport.create", "label": "Create transport records", "description": "Add routes and vehicles"},
            {"key": "transport.update", "label": "Edit transport", "description": "Modify routes and assignments"},
            {"key": "transport.delete", "label": "Delete transport records", "description": "Remove transport data"},
        ],
    },
    {
        "module": "Settings",
        "permissions": [
            {"key": "school.read", "label": "View school settings", "description": "View school configuration"},
            {"key": "school.update", "label": "Edit school settings", "description": "Modify school configuration"},
            {"key": "schools.read", "label": "View schools", "description": "View school list (chain admin)"},
            {"key": "schools.create", "label": "Create schools", "description": "Add schools to chain"},
            {"key": "schools.update", "label": "Edit schools", "description": "Modify school settings (chain admin)"},
            {"key": "schools.delete", "label": "Delete schools", "description": "Remove schools from chain"},
            {"key": "subscription.read", "label": "View subscription", "description": "View plan details"},
            {"key": "subscription.manage", "label": "Manage subscription", "description": "Upgrade/change plan"},
        ],
    },
    {
        "module": "Teacher Portal",
        "permissions": [
            {"key": "teacher.dashboard.read", "label": "Teacher dashboard", "description": "View teacher dashboard"},
            {"key": "teacher.schedule.read", "label": "View schedule", "description": "View teaching schedule"},
            {"key": "teacher.classes.read", "label": "View assigned classes", "description": "View classes assigned to teacher"},
            {"key": "teacher.grading.read", "label": "View grading", "description": "View grades and assessments"},
            {"key": "teacher.grading.write", "label": "Enter grades", "description": "Enter and modify grades"},
            {"key": "teacher.lessons.read", "label": "View lesson plans", "description": "View lesson plans"},
            {"key": "teacher.lessons.write", "label": "Create lesson plans", "description": "Create and edit lesson plans"},
            {"key": "teacher.notes.read", "label": "View notes", "description": "View student/teacher notes"},
            {"key": "teacher.notes.write", "label": "Create notes", "description": "Create and edit notes"},
            {"key": "teacher.attendance.read", "label": "View attendance (teacher)", "description": "View class attendance as teacher"},
            {"key": "teacher.reports.read", "label": "View reports (teacher)", "description": "View report cards"},
            {"key": "teacher.reports.write", "label": "Write reports", "description": "Write report card comments"},
            {"key": "teacher.reports.head_teacher", "label": "Head teacher reports", "description": "Head teacher report approval"},
            {"key": "teacher.performance.read", "label": "View performance", "description": "View performance analytics"},
            {"key": "teacher.communication.write", "label": "Teacher communication", "description": "Send teacher messages"},
            {"key": "teacher.notifications.read", "label": "Teacher notifications", "description": "View teacher notifications"},
        ],
    },
    {
        "module": "Parent Portal",
        "permissions": [
            {"key": "children.read", "label": "View children", "description": "View child profiles"},
            {"key": "parent.children.read", "label": "View children (portal)", "description": "View children in parent portal"},
            {"key": "parent.grades.read", "label": "View grades (parent)", "description": "View child grades"},
            {"key": "parent.finance.read", "label": "View finance (parent)", "description": "View invoices and payments"},
            {"key": "parent.attendance.read", "label": "View attendance (parent)", "description": "View child attendance"},
            {"key": "parent.communication.read", "label": "View communication (parent)", "description": "View teacher messages"},
        ],
    },
    {
        "module": "HR & Leave",
        "permissions": [
            {"key": "hr.leave.read", "label": "View leave data", "description": "View leave types, balances, and requests"},
            {"key": "hr.leave.request", "label": "Request leave", "description": "Submit and cancel own leave requests"},
            {"key": "hr.leave.approve", "label": "Approve leave", "description": "Approve or reject leave requests"},
            {"key": "hr.leave.manage", "label": "Manage leave settings", "description": "Configure leave types, adjust balances"},
        ],
    },
    {
        "module": "Payroll",
        "permissions": [
            {"key": "payroll.read", "label": "View payroll data", "description": "View salary grades, configs, and payroll runs"},
            {"key": "payroll.configure", "label": "Configure payroll", "description": "Manage salary grades, allowance/deduction types, tax brackets"},
            {"key": "payroll.manage", "label": "Manage salaries", "description": "Assign and update staff salary configurations"},
            {"key": "payroll.process", "label": "Process payroll", "description": "Create and calculate payroll runs"},
            {"key": "payroll.approve", "label": "Approve payroll", "description": "Approve or reject payroll runs"},
            {"key": "payroll.audit", "label": "View payroll audit", "description": "View payroll audit trail"},
        ],
    },
    {
        "module": "Loans",
        "permissions": [
            {"key": "payroll.loans.read", "label": "View loan data", "description": "View staff loan records"},
            {"key": "payroll.loans.request", "label": "Request loans", "description": "Submit loan requests"},
            {"key": "payroll.loans.approve", "label": "Approve loans", "description": "Approve or reject loan requests"},
            {"key": "payroll.loans.disburse", "label": "Disburse loans", "description": "Disburse approved loans"},
            {"key": "payroll.loans.manage", "label": "Manage loans", "description": "Full loan management access"},
            {"key": "payroll.loans.write_off", "label": "Write off loans", "description": "Write off outstanding loan balances"},
        ],
    },
    {
        "module": "Personal",
        "permissions": [
            {"key": "self.read", "label": "View own profile", "description": "View own profile information"},
            {"key": "self.update", "label": "Edit own profile", "description": "Update own profile information"},
        ],
    },
    {
        "module": "Applicant Portal",
        "permissions": [
            {"key": "applicant.profile.read", "label": "View applicant profile", "description": "View own applicant profile"},
            {"key": "applicant.profile.update", "label": "Edit applicant profile", "description": "Update applicant profile"},
            {"key": "applicant.applications.read", "label": "View applications", "description": "View own applications"},
            {"key": "applicant.applications.create", "label": "Create applications", "description": "Submit new applications"},
            {"key": "applicant.applications.update", "label": "Edit applications", "description": "Update draft applications"},
            {"key": "applicant.applications.submit", "label": "Submit applications", "description": "Submit applications for review"},
            {"key": "applicant.applications.claim", "label": "Claim applications", "description": "Claim existing applications"},
        ],
    },
]

# Flat set of all valid permission keys (for validation)
ALL_PERMISSION_KEYS: set[str] = set()
for _module in PERMISSIONS_CATALOG:
    for _perm in _module["permissions"]:
        ALL_PERMISSION_KEYS.add(_perm["key"])
