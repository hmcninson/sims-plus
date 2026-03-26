# Phase 1C: Bulk User CSV Import

**Complexity:** Medium
**Requirements:** UM-006
**Dependencies:** None (follows existing staff import pattern)
**Estimated effort:** 1.5-2 days

---

## Summary

Implement bulk user creation via CSV file upload. Users are created with `status=PENDING` and receive a "set your password" welcome email via the existing password reset flow. The admin also receives a downloadable CSV with temporary credentials as a fallback for users without reliable email access.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Max rows per import | 200 | Consistent with bulk SMS limit; prevents memory issues |
| Password handling | Auto-generated temp password + "set your password" email | Admin ≠ end-user; secure distribution |
| User status on import | `PENDING` | User must set their own password via reset link |
| Email notification | Yes — welcome email with password reset link | Fallback: admin downloads CSV with temp credentials |
| Preview mode | Yes — validate before committing | Same UX pattern as staff import |
| Subscription limit check | Yes — checked before import | Prevents exceeding plan limits |

---

## Task 1: Bulk Import Service Method

### File: `backend/app/services/user.py`

**Read the existing staff import method first:** `backend/app/api/v1/endpoints/staff/staff.py` (around lines 192-250) for the CSV parsing pattern.

**Add method to UserService:**

```python
async def import_users_from_file(
    self,
    tenant_id: UUID,
    school_id: UUID | None,
    file_content: bytes,
    file_type: str = "csv",
    preview_only: bool = False,
    created_by_id: UUID | None = None,
) -> dict:
    """
    Import users from CSV file.

    CSV columns:
    - email (required): User email address
    - first_name (required): First name
    - last_name (required): Last name
    - role (required): Must be a valid UserRole value
      (school_admin, academic_head, finance_officer, hr_officer, teacher, house_parent)
    - phone (optional): Phone number

    For each valid row:
    1. Validate email format and uniqueness within tenant
    2. Validate role is a valid staff UserRole
    3. Generate a secure random temporary password (16 chars)
    4. Create user with status=PENDING, email_verified=False
    5. Queue a welcome email with password reset link

    Args:
        tenant_id: Current tenant UUID
        school_id: School to assign users to (for chain tenants)
        file_content: Raw CSV bytes
        file_type: "csv" (only CSV supported)
        preview_only: If True, validate only — don't create users
        created_by_id: ID of the admin performing the import

    Returns:
        {
            "total": int,           # Total rows parsed
            "valid": int,           # Rows that passed validation
            "created": int,         # Users actually created (0 if preview)
            "errors": [             # Rows with errors
                {"row": int, "field": str, "error": str}
            ],
            "preview": [            # Row previews (always returned)
                {
                    "row_number": int,
                    "email": str,
                    "first_name": str,
                    "last_name": str,
                    "role": str,
                    "phone": str | None,
                    "valid": bool,
                    "errors": [str]
                }
            ],
            "credentials": [        # Only on actual import (not preview)
                {"email": str, "temporary_password": str}
            ] | None
        }

    Raises:
        UserServiceError: If file parsing fails or subscription limit exceeded
    """

    # ---- Implementation outline ----

    # 1. Parse CSV
    import csv
    import io
    reader = csv.DictReader(io.StringIO(file_content.decode("utf-8-sig")))
    # Note: utf-8-sig handles BOM from Excel

    # 2. Validate header row
    required_columns = {"email", "first_name", "last_name", "role"}
    optional_columns = {"phone"}
    # Check all required columns are present

    # 3. Enforce max row limit
    MAX_IMPORT_ROWS = 200
    rows = list(reader)
    if len(rows) > MAX_IMPORT_ROWS:
        raise UserServiceError(
            f"Maximum {MAX_IMPORT_ROWS} rows per import",
            "import_limit_exceeded",
        )

    # 4. Check subscription user limit
    # Count current users + valid import rows vs plan max
    # Use existing subscription check pattern

    # 5. Allowed roles for import (staff roles only)
    IMPORTABLE_ROLES = {
        "school_admin", "academic_head", "finance_officer",
        "hr_officer", "teacher", "house_parent",
    }

    # 6. Validate each row
    preview = []
    errors = []
    valid_rows = []
    seen_emails = set()

    for i, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
        row_errors = []
        email = (row.get("email") or "").strip().lower()
        first_name = (row.get("first_name") or "").strip()
        last_name = (row.get("last_name") or "").strip()
        role = (row.get("role") or "").strip().lower()
        phone = (row.get("phone") or "").strip() or None

        # Required field checks
        if not email:
            row_errors.append("Email is required")
        elif not _is_valid_email(email):
            row_errors.append("Invalid email format")
        elif email in seen_emails:
            row_errors.append("Duplicate email in file")

        if not first_name:
            row_errors.append("First name is required")
        if not last_name:
            row_errors.append("Last name is required")

        if not role:
            row_errors.append("Role is required")
        elif role not in IMPORTABLE_ROLES:
            row_errors.append(f"Invalid role. Must be one of: {', '.join(sorted(IMPORTABLE_ROLES))}")

        # Check email uniqueness in database (only if no errors yet)
        if email and not row_errors:
            existing = await self.db.execute(
                select(User.id).where(
                    User.email == email,
                    User.tenant_id == tenant_id,
                    User.deleted_at.is_(None),
                )
            )
            if existing.scalar_one_or_none():
                row_errors.append("Email already exists in this school")

        seen_emails.add(email)

        is_valid = len(row_errors) == 0
        preview.append({
            "row_number": i,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
            "phone": phone,
            "valid": is_valid,
            "errors": row_errors,
        })

        if is_valid:
            valid_rows.append({
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
                "phone": phone,
            })

        for err in row_errors:
            errors.append({"row": i, "field": "row", "error": err})

    # 7. If preview only, return without creating
    if preview_only:
        return {
            "total": len(rows),
            "valid": len(valid_rows),
            "created": 0,
            "errors": errors,
            "preview": preview,
            "credentials": None,
        }

    # 8. Create users
    credentials = []
    created_count = 0
    from app.core.security import hash_password
    import secrets
    import string

    for row_data in valid_rows:
        # Generate 16-char temporary password
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        temp_password = "".join(secrets.choice(alphabet) for _ in range(16))

        user = User(
            tenant_id=tenant_id,
            school_id=school_id,
            email=row_data["email"],
            first_name=row_data["first_name"],
            last_name=row_data["last_name"],
            role=UserRole(row_data["role"]),
            phone=row_data["phone"],
            hashed_password=hash_password(temp_password),
            status=UserStatus.PENDING,
            email_verified=False,
        )
        self.db.add(user)
        credentials.append({
            "email": row_data["email"],
            "temporary_password": temp_password,
        })
        created_count += 1

    await self.db.flush()

    # 9. Queue welcome emails (via existing email service)
    # Each user gets a password reset link email
    # Use the existing password_reset service to generate tokens
    # and send "Welcome to {school_name}" emails
    from app.services.password_reset import PasswordResetService
    # NOTE: email sending should be best-effort — failures don't
    # roll back user creation

    return {
        "total": len(rows),
        "valid": len(valid_rows),
        "created": created_count,
        "errors": errors,
        "preview": preview,
        "credentials": credentials,
    }
```

**Helper function (add to the same file or a utils module):**

```python
import re

def _is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

---

## Task 2: Import Endpoint

### File: `backend/app/api/v1/endpoints/users.py`

```python
@router.get(
    "/import/template",
    summary="Download user import CSV template",
    dependencies=[Depends(require_permissions("users.create"))],
)
async def download_import_template():
    """Return a CSV template file for bulk user import."""
    import io
    import csv
    from starlette.responses import StreamingResponse

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "first_name", "last_name", "role", "phone"])
    writer.writerow(["john.doe@example.com", "John", "Doe", "teacher", "+233241234567"])
    writer.writerow(["jane.smith@example.com", "Jane", "Smith", "finance_officer", ""])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=user_import_template.csv"},
    )


@router.post(
    "/import",
    summary="Import users from CSV file",
    dependencies=[Depends(require_permissions("users.create"))],
)
async def import_users(
    request: Request,
    tenant: RequestTenant,          # Existing dependency for tenant context
    db: DatabaseSession,
    current_user: ValidatedUser,
    file: UploadFile = File(...),
    preview: bool = Form(default=False),
    school_id: Optional[UUID] = Form(default=None),
):
    """
    Import users from CSV file.

    Query params:
    - preview=true: Validate only, return preview without creating users
    - school_id: (Optional) School to assign users to (for chain tenants)

    CSV format:
    - email (required)
    - first_name (required)
    - last_name (required)
    - role (required): school_admin, academic_head, finance_officer,
      hr_officer, teacher, house_parent
    - phone (optional)

    Returns:
    - total: Total rows in file
    - valid: Rows that passed validation
    - created: Users created (0 if preview)
    - errors: List of validation errors per row
    - preview: Row-by-row preview with validation status
    - credentials: List of {email, temporary_password} — ONLY on actual
      import (not preview). One-time response, not stored.

    Rate limit: 10/min (bulk operation category)
    Max rows: 200
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    # Validate file size (max 1MB)
    content = await file.read()
    if len(content) > 1_048_576:
        raise HTTPException(status_code=400, detail="File too large (max 1MB)")

    user_service = UserService(db)
    try:
        result = await user_service.import_users_from_file(
            tenant_id=tenant.tenant_id,
            school_id=school_id,
            file_content=content,
            preview_only=preview,
            created_by_id=UUID(current_user["user_id"]),
        )
    except UserServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)

    # Audit log (only on actual import)
    if not preview and result["created"] > 0:
        from app.services.audit import AuditService, AuditEventType
        audit = AuditService(db)
        await audit.log(
            event_type=AuditEventType.USER_CREATED,
            tenant_id=UUID(tenant.tenant_id),
            user_id=UUID(current_user["user_id"]),
            target_type="user",
            target_id=None,
            details={
                "action": "bulk_import",
                "total": result["total"],
                "created": result["created"],
                "errors": len(result["errors"]),
            },
        )

    return result
```

---

## Task 3: Import Schemas

### File: `backend/app/schemas/user.py` (add to existing file)

```python
class UserImportRow(BaseModel):
    """Single row preview from CSV import."""
    row_number: int
    email: str
    first_name: str
    last_name: str
    role: str
    phone: str | None = None
    valid: bool
    errors: list[str] = []


class UserImportCredential(BaseModel):
    """One-time credential for a newly imported user."""
    email: str
    temporary_password: str


class UserImportResult(BaseModel):
    """Result of a bulk user import operation."""
    total: int
    valid: int
    created: int
    errors: list[dict]
    preview: list[UserImportRow]
    credentials: list[UserImportCredential] | None = None
```

---

## Task 4: Frontend — Import Users Dialog

### File: `frontend/app/(dashboard)/settings/users/users-management.tsx`

**Add an "Import Users" button** next to the existing "Add User" / "Invite User" buttons in the page header.

The import dialog follows a 4-step wizard pattern:

```tsx
function ImportUsersDialog({ open, onClose, onSuccess }) {
  const [step, setStep] = useState<"upload" | "preview" | "importing" | "result">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState(null);
  const [importResult, setImportResult] = useState(null);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-sm:max-w-full">
        <DialogHeader>
          <DialogTitle>Import Users from CSV</DialogTitle>
        </DialogHeader>

        {step === "upload" && (
          {/* Step 1: Upload */}
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Upload a CSV file with user details. Maximum 200 rows.
            </p>

            {/* Download template link */}
            <Button variant="link" onClick={handleDownloadTemplate}>
              Download CSV template
            </Button>

            {/* File upload dropzone */}
            <div className="border-2 border-dashed rounded-lg p-8 text-center">
              <input type="file" accept=".csv" onChange={handleFileSelect} />
              <p>Drop a CSV file here or click to browse</p>
            </div>

            {/* Column format reference */}
            <div className="text-xs text-muted-foreground">
              <p>Required columns: email, first_name, last_name, role</p>
              <p>Optional columns: phone</p>
              <p>Valid roles: school_admin, academic_head, finance_officer,
                 hr_officer, teacher, house_parent</p>
            </div>

            <Button onClick={handlePreview} disabled={!file}>
              Preview Import
            </Button>
          </div>
        )}

        {step === "preview" && (
          {/* Step 2: Preview */}
          <div className="space-y-4">
            <div className="flex gap-4 text-sm">
              <Badge variant="outline">{previewData.total} total</Badge>
              <Badge variant="success">{previewData.valid} valid</Badge>
              <Badge variant="destructive">
                {previewData.total - previewData.valid} errors
              </Badge>
            </div>

            {/* Preview table */}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Row</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewData.preview.map((row) => (
                  <TableRow key={row.row_number}>
                    <TableCell>{row.row_number}</TableCell>
                    <TableCell>{row.email}</TableCell>
                    <TableCell>{row.first_name} {row.last_name}</TableCell>
                    <TableCell>{row.role}</TableCell>
                    <TableCell>
                      {row.valid ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      ) : (
                        <Tooltip content={row.errors.join(", ")}>
                          <XCircle className="h-4 w-4 text-red-500" />
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep("upload")}>
                Back
              </Button>
              <Button
                onClick={handleImport}
                disabled={previewData.valid === 0}
              >
                Import {previewData.valid} Users
              </Button>
            </div>
          </div>
        )}

        {step === "result" && (
          {/* Step 4: Result */}
          <div className="space-y-4">
            <div className="text-center">
              <CheckCircle className="mx-auto h-12 w-12 text-green-500" />
              <p className="mt-2 text-lg font-medium">
                {importResult.created} users imported successfully
              </p>
            </div>

            {/* Download credentials button */}
            <Button onClick={handleDownloadCredentials} className="w-full">
              Download Credentials CSV
            </Button>
            <p className="text-xs text-muted-foreground text-center">
              Save this file — credentials cannot be retrieved again.
              Users will also receive a welcome email with a password reset link.
            </p>

            <Button variant="outline" onClick={handleClose} className="w-full">
              Done
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

**Credentials CSV download (client-side, from response data):**

```typescript
const handleDownloadCredentials = () => {
  if (!importResult?.credentials) return;

  const csv = [
    "email,temporary_password",
    ...importResult.credentials.map(
      (c) => `${c.email},${c.temporary_password}`
    ),
  ].join("\n");

  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `user_credentials_${new Date().toISOString().split("T")[0]}.csv`;
  a.click();
  URL.revokeObjectURL(url);
};
```

---

## Task 5: Frontend — Server Actions

### File: `frontend/actions/users.action.ts` (add to existing file)

```typescript
/**
 * Preview a bulk user import (validation only, no creation).
 */
export async function previewUserImport(
  formData: FormData,
): Promise<ActionResult<UserImportResult>> {
  try {
    formData.append("preview", "true");
    const response = await apiPostForm<UserImportResult>("/users/import", formData);
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Preview failed",
    };
  }
}

/**
 * Execute a bulk user import (creates users).
 *
 * IMPORTANT: The credentials field in the response is one-time only.
 * It is NOT stored anywhere. If the admin misses the download,
 * they must use individual password reset per user.
 */
export async function importUsers(
  formData: FormData,
): Promise<ActionResult<UserImportResult>> {
  try {
    const response = await apiPostForm<UserImportResult>("/users/import", formData);
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Import failed",
    };
  }
}
```

**Note:** If `apiPostForm` doesn't exist in `frontend/lib/api.ts`, create it as a concrete subtask: follow the same pattern as `apiPost` but using `FormData` instead of JSON body, and not setting `Content-Type` header (let the browser set multipart/form-data with boundary). This is a prerequisite for the import actions.

---

## Task 6: Frontend — Types

### File: `frontend/types/index.ts` (or relevant types file)

```typescript
interface UserImportRow {
  row_number: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  phone: string | null;
  valid: boolean;
  errors: string[];
}

interface UserImportCredential {
  email: string;
  temporary_password: string;
}

interface UserImportResult {
  total: number;
  valid: number;
  created: number;
  errors: { row: number; field: string; error: string }[];
  preview: UserImportRow[];
  credentials: UserImportCredential[] | null;
}
```

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Credentials in response | One-time only; not logged; not stored in DB. Response includes `Cache-Control: no-store` header to prevent credential caching. |
| Credentials CSV in transit | HTTPS only (TLS 1.3) |
| File size attack | 1MB limit on upload |
| CSV injection | Roles validated against allowlist; no formula execution |
| Subscription bypass | User count checked against plan limits before import |
| Privilege escalation | Only staff roles importable (no platform_admin, chain_admin) |
| Email spam | Welcome emails rate-limited by existing email service |

---

## Verification Checklist

- [ ] CSV template downloads correctly with example rows
- [ ] Preview mode validates all rows without creating users
- [ ] Invalid rows show clear error messages per row
- [ ] Duplicate emails (within file) are caught
- [ ] Duplicate emails (in database) are caught
- [ ] Invalid roles are rejected with list of valid options
- [ ] Max 200 rows enforced
- [ ] Subscription user limit checked before import
- [ ] Users created with status=PENDING
- [ ] Temporary passwords meet complexity requirements
- [ ] Credentials CSV downloadable from result screen
- [ ] Welcome emails sent to imported users
- [ ] Audit log records bulk import event
- [ ] `users.create` permission required
- [ ] platform_admin and chain_admin roles NOT importable
