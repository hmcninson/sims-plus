# Phase 2: Session Timeout (30-Minute Inactivity)

**Complexity:** Medium
**Requirements:** UM-008
**Dependencies:** None
**Estimated effort:** 2 days

---

## Summary

Implement a 30-minute inactivity timeout. The frontend tracks user activity (mouse, keyboard, scroll, touch) and sends periodic heartbeats to the server. After 25 minutes of inactivity, a warning dialog appears. At 30 minutes, the user is logged out. The backend provides defense-in-depth by rejecting token refreshes for inactive users.

---

## Design Decision: Frontend-Driven with Server-Side Verification

| Approach | Pros | Cons |
|----------|------|------|
| Pure frontend | Simple; no DB changes | No server enforcement; can be bypassed |
| Pure backend | Can't be bypassed | JWTs are stateless; can't retroactively expire |
| **Hybrid (chosen)** | Frontend UX + server enforcement | Requires heartbeat endpoint |

The frontend is the primary enforcement mechanism (detecting inactivity, showing warnings, auto-logout). The backend provides a `last_activity_at` column and rejects token refreshes when the user has been inactive for 30+ minutes.

---

## Task 1: Add last_activity_at Column to User Model

### File: `backend/app/models/user.py`

**Add near the existing `last_login` field:**

```python
last_activity_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

**Migration handled in combined migration file (see `07-migration-plan.md`).**

---

## Task 2: Add Configuration

### File: `backend/app/config.py`

**Add to the Settings class:**

```python
SESSION_TIMEOUT_MINUTES: int = 30
HEARTBEAT_INTERVAL_MINUTES: int = 5
```

---

## Task 3: Add Heartbeat Endpoint

### File: `backend/app/api/v1/endpoints/auth.py`

```python
@router.post(
    "/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update last activity timestamp",
)
async def heartbeat(
    current_user_id: CurrentUserId,
    db: DatabaseSession,
    tenant: RequestTenant,             # Tenant context for defense-in-depth
    _: ValidatedTokenTenant,           # Cross-tenant token validation
):
    """
    Update the user's last_activity_at timestamp.

    Called by the frontend every 5 minutes when user activity is detected
    (mouse movement, keyboard input, scroll, touch).

    This is a lightweight endpoint — single UPDATE, no SELECT.
    """
    from datetime import datetime, timezone
    await db.execute(
        update(User)
        .where(User.id == current_user_id)
        # Defense-in-depth: ensure user belongs to current tenant
        .where(User.tenant_id == UUID(tenant.tenant_id))
        .values(last_activity_at=datetime.now(timezone.utc))
    )
    await db.flush()
```

**Rate limit:** Set to 20/min for the heartbeat endpoint specifically, since it fires every 5 minutes per active user and shouldn't hit the default 100/min rate limit under normal use, but needs headroom for page refreshes.

---

## Task 4: Enforce Inactivity on Token Refresh

### File: `backend/app/api/v1/endpoints/auth.py` (or `backend/app/services/auth.py`)

**Modify the existing `refresh_tokens()` endpoint/service method.** Find where the refresh token is validated and a new access token is issued. Add an inactivity check:

```python
# After validating the refresh token and loading the user:
from app.config import settings
from datetime import datetime, timezone

if user.last_activity_at:
    inactive_seconds = (
        datetime.now(timezone.utc) - user.last_activity_at
    ).total_seconds()
    inactive_minutes = inactive_seconds / 60

    if inactive_minutes > settings.SESSION_TIMEOUT_MINUTES:
        # Blacklist the refresh token so it can't be retried
        # (use existing token blacklist service)
        raise HTTPException(
            status_code=401,
            detail="Session expired due to inactivity",
            headers={"X-Session-Expired": "inactivity"},
        )
```

**Important:** This is defense-in-depth only. The frontend should handle the timeout gracefully before this check is ever triggered. If a user reaches this check, it means the frontend timeout failed (browser tab kept open, JavaScript frozen, etc.).

**Frontend note:** The `X-Session-Expired: inactivity` response header should be detected by the frontend API client (e.g., in `lib/api.ts` or the auth retry wrapper). On receiving this header, the frontend should redirect to the login page with `?error=session_expired` rather than showing a generic auth error.

---

## Task 5: Update last_activity_at on Login

### File: `backend/app/services/auth.py`

**In the `authenticate()` method, after successful login, set `last_activity_at`:**

```python
# After successful password verification and before returning tokens:
user.last_activity_at = datetime.now(timezone.utc)
await self.db.flush()
```

This ensures the inactivity timer starts from the login time, not from `None`.

---

## Task 6: Frontend — Session Timeout Hook

### New File: `frontend/hooks/use-session-timeout.ts`

```typescript
"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useRouter } from "next/navigation";

interface UseSessionTimeoutOptions {
  timeoutMinutes?: number;       // Default: 30
  warningMinutes?: number;       // Default: 25 (show warning at this point)
  heartbeatIntervalMinutes?: number;  // Default: 5
}

interface UseSessionTimeoutReturn {
  showWarning: boolean;           // True when warning dialog should be visible
  remainingSeconds: number;       // Seconds until auto-logout
  continueSession: () => void;    // Call to dismiss warning and reset timer
}

export function useSessionTimeout(
  options: UseSessionTimeoutOptions = {},
): UseSessionTimeoutReturn {
  const {
    timeoutMinutes = 30,
    warningMinutes = 25,
    heartbeatIntervalMinutes = 5,
  } = options;

  const router = useRouter();
  const lastActivityRef = useRef<number>(Date.now());
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const warningTimerRef = useRef<NodeJS.Timeout | null>(null);
  const logoutTimerRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  const [showWarning, setShowWarning] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(0);

  // ---- Activity tracking ----

  const onActivity = useCallback(() => {
    lastActivityRef.current = Date.now();

    // If warning is showing, don't reset (user must click "Continue")
    if (!showWarning) {
      resetTimers();
    }
  }, [showWarning]);

  // ---- Heartbeat ----

  const sendHeartbeat = useCallback(async () => {
    // Only send if there was recent activity
    const msSinceActivity = Date.now() - lastActivityRef.current;
    const minutesSinceActivity = msSinceActivity / 1000 / 60;

    if (minutesSinceActivity < heartbeatIntervalMinutes) {
      try {
        // Call heartbeat endpoint
        const { heartbeat } = await import("@/actions/auth.action");
        await heartbeat();
      } catch {
        // Silently fail — heartbeat is best-effort
      }
    }
  }, [heartbeatIntervalMinutes]);

  // ---- Timer management ----

  const resetTimers = useCallback(() => {
    // Clear existing timers
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);

    setShowWarning(false);

    // Set warning timer (at warningMinutes)
    warningTimerRef.current = setTimeout(
      () => {
        setShowWarning(true);
        const totalRemaining = (timeoutMinutes - warningMinutes) * 60;
        setRemainingSeconds(totalRemaining);

        // Start countdown
        countdownRef.current = setInterval(() => {
          setRemainingSeconds((prev) => {
            if (prev <= 1) {
              // Time's up — logout
              handleLogout();
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      },
      warningMinutes * 60 * 1000,
    );
  }, [warningMinutes, timeoutMinutes]);

  // ---- Continue session ----

  const continueSession = useCallback(() => {
    lastActivityRef.current = Date.now();
    setShowWarning(false);
    if (countdownRef.current) clearInterval(countdownRef.current);
    resetTimers();
    sendHeartbeat(); // Immediately update server
  }, [resetTimers, sendHeartbeat]);

  // ---- Logout ----

  const handleLogout = useCallback(async () => {
    // Clear all timers
    if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);

    try {
      const { logout } = await import("@/actions/auth.action");
      await logout();
    } catch {
      // Force redirect even if logout API fails
    }

    // Clear offline data
    if (typeof indexedDB !== "undefined") {
      try {
        const { clearAllOfflineData } = await import("@/lib/offline/db");
        await clearAllOfflineData();
      } catch {
        // Best effort
      }
    }

    router.push("/login?error=session_expired");
  }, [router]);

  // ---- Setup ----

  useEffect(() => {
    // Register activity listeners
    const events = ["mousedown", "keydown", "scroll", "touchstart", "mousemove"];
    // Throttle mousemove to avoid excessive calls
    let mouseMoveTimeout: NodeJS.Timeout | null = null;
    const throttledMouseMove = () => {
      if (!mouseMoveTimeout) {
        mouseMoveTimeout = setTimeout(() => {
          onActivity();
          mouseMoveTimeout = null;
        }, 5000); // Throttle to once per 5 seconds
      }
    };

    events.forEach((event) => {
      if (event === "mousemove") {
        window.addEventListener(event, throttledMouseMove, { passive: true });
      } else {
        window.addEventListener(event, onActivity, { passive: true });
      }
    });

    // Start heartbeat interval
    heartbeatTimerRef.current = setInterval(
      sendHeartbeat,
      heartbeatIntervalMinutes * 60 * 1000,
    );

    // Start initial timers
    resetTimers();

    // Cleanup
    return () => {
      events.forEach((event) => {
        if (event === "mousemove") {
          window.removeEventListener(event, throttledMouseMove);
        } else {
          window.removeEventListener(event, onActivity);
        }
      });
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
      if (mouseMoveTimeout) clearTimeout(mouseMoveTimeout);
    };
  }, []);

  return { showWarning, remainingSeconds, continueSession };
}
```

---

## Task 7: Frontend — Session Timeout Warning Dialog

### New File: `frontend/components/session-timeout-dialog.tsx`

```tsx
"use client";

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogAction,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { Clock } from "lucide-react";

interface SessionTimeoutDialogProps {
  open: boolean;
  remainingSeconds: number;
  onContinue: () => void;
  onLogout: () => void;
}

export function SessionTimeoutDialog({
  open,
  remainingSeconds,
  onContinue,
  onLogout,
}: SessionTimeoutDialogProps) {
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;

  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-amber-500" />
            <AlertDialogTitle>Session Expiring</AlertDialogTitle>
          </div>
          <AlertDialogDescription>
            Your session will expire due to inactivity in{" "}
            <span className="font-mono font-bold text-foreground">
              {minutes}:{seconds.toString().padStart(2, "0")}
            </span>
            . Click &quot;Continue&quot; to stay logged in.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onLogout}>Log Out</AlertDialogCancel>
          <AlertDialogAction onClick={onContinue}>
            Continue Session
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
```

---

## Task 8: Integrate into Dashboard Layout

### File: `frontend/app/(dashboard)/layout.tsx`

Add the session timeout hook and dialog to the dashboard layout:

```tsx
"use client";

import { useSessionTimeout } from "@/hooks/use-session-timeout";
import { SessionTimeoutDialog } from "@/components/session-timeout-dialog";

// Inside the layout component:
const { showWarning, remainingSeconds, continueSession } = useSessionTimeout();

// In the JSX (add before or after the main content):
<SessionTimeoutDialog
  open={showWarning}
  remainingSeconds={remainingSeconds}
  onContinue={continueSession}
  onLogout={() => {
    // Call logout action and redirect
    logout().then(() => {
      window.location.href = "/login?error=session_expired";
    });
  }}
/>
```

**Note:** If the dashboard layout is currently a Server Component, you'll need to extract the session timeout logic into a client component wrapper that wraps the content. Example:

```tsx
// app/(dashboard)/layout.tsx (Server Component)
export default function DashboardLayout({ children }) {
  return (
    <SessionTimeoutProvider>
      {/* existing layout structure */}
      {children}
    </SessionTimeoutProvider>
  );
}

// components/providers/session-timeout-provider.tsx (Client Component)
"use client";
export function SessionTimeoutProvider({ children }) {
  const { showWarning, remainingSeconds, continueSession } = useSessionTimeout();
  return (
    <>
      {children}
      <SessionTimeoutDialog ... />
    </>
  );
}
```

---

## Task 9: Frontend — Heartbeat Server Action

### File: `frontend/actions/auth.action.ts` (add to existing file)

```typescript
/**
 * Send heartbeat to update server-side last_activity_at.
 * Called every 5 minutes by the session timeout hook when user is active.
 * Failures are silently ignored — heartbeat is best-effort.
 */
export async function heartbeat(): Promise<void> {
  try {
    await apiPost("/auth/heartbeat", {});
  } catch {
    // Silently fail — heartbeat is best-effort
  }
}
```

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Heartbeat abuse | Rate limited to 20/min |
| Client-side bypass | Server rejects token refresh after 30min inactivity |
| Timer manipulation | Server-side `last_activity_at` is authoritative |
| Tab kept open (no JS) | Token expiry (15min access token) still applies |
| Multiple tabs | Activity in any tab sends heartbeat (shared cookie/token) |

---

## Verification Checklist

- [ ] `last_activity_at` updated on login
- [ ] `last_activity_at` updated via heartbeat endpoint
- [ ] Heartbeat only fires when user is actually active (not on idle tabs)
- [ ] Warning dialog appears at 25 minutes of inactivity
- [ ] Countdown timer displays correctly (MM:SS)
- [ ] "Continue" button resets all timers and sends heartbeat
- [ ] "Log Out" button cleanly logs out and redirects
- [ ] Auto-logout at 30 minutes redirects to login with `session_expired` message
- [ ] Token refresh rejected after 30 minutes of server-side inactivity
- [ ] Multiple tabs: activity in one tab prevents timeout in all
- [ ] Offline data (IndexedDB) cleared on session timeout logout
- [ ] Warning dialog is not dismissible by clicking outside (only via buttons)
