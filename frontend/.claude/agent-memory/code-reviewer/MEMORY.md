# Frontend Code Reviewer Memory

## Auth Flow Review (2026-02-16)
- See [auth-flow-review.md](auth-flow-review.md) for detailed findings
- CRITICAL: register/page.tsx checkSubdomainAvailability returns available:true on network error
- CRITICAL: register/page.tsx uses raw fetch() instead of API layer for subdomain check
- server-api.ts has "use server" but exports utility wrappers, not true Server Actions
- requestPasswordReset() never returns failure -- dead code in forgot-password UI error handling
- MeResponse in auth.action.ts duplicates SessionContext from types/index.ts
- Debug console.log found in: staff.action.ts, attendance.action.ts, preschool.action.ts
- "Remember me" checkbox on login page is non-functional (no state, no persistence)
- lib/api.ts uses process.env.API_URL (server-only) without `import "server-only"` guard

## ActionResult Compliance (2026-02-16)
- All 14 action files correctly use discriminated union: `{success:true, data:T} | {success:false, error:string}`
- Pattern is consistent across: auth, school, user, tenant, media, academic, exams, timetable, attendance, students, staff, finance, preschool, users

## Frontend File Size Issues
- register/page.tsx: 1044 lines (should be <300 for components)
- finance.action.ts: 1332 lines
- exams.action.ts: 963 lines
- preschool.action.ts: 776 lines
- types/index.ts: 2016 lines (single file for all types)

## Patterns Observed
- Auth pages use "use client" with React Hook Form + Zod (except forgot-password and reset-password which use raw FormData)
- Dashboard layout is Server Component, fetches session via getCurrentUserContext()
- TenantProvider for auth pages (client-side fetch), SessionProvider for dashboard (server-injected)
- usePermissions() supports wildcard matching: "students.*" matches "students.read"
- Cookie-based auth: access_token (15min), refresh_token (7d), both httpOnly
- Token refresh with single-retry on 401 in both getCurrentUser and getCurrentUserContext
- Email enumeration prevention: requestPasswordReset always returns success
