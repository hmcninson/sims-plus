"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useRouter } from "next/navigation";

interface UseSessionTimeoutOptions {
  timeoutMinutes?: number;
  warningMinutes?: number;
  heartbeatIntervalMinutes?: number;
}

interface UseSessionTimeoutReturn {
  /** True when the warning dialog should be visible */
  showWarning: boolean;
  /** Seconds remaining until auto-logout */
  remainingSeconds: number;
  /** Dismiss warning and reset all timers */
  continueSession: () => void;
}

/**
 * Tracks user activity and enforces a 30-minute inactivity timeout.
 *
 * - Sends a heartbeat to the server every `heartbeatIntervalMinutes` when
 *   activity is detected (mousedown, keydown, scroll, touchstart, mousemove).
 * - Shows a warning dialog at `warningMinutes` of inactivity.
 * - Auto-logs out at `timeoutMinutes` of inactivity.
 * - Clears IndexedDB offline data on timeout logout.
 */
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
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Track whether the warning is showing via ref to avoid stale closures
  const showWarningRef = useRef(false);

  const [showWarning, setShowWarning] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(0);

  // ---- Logout handler ----

  const handleLogout = useCallback(async () => {
    // Clear all timers
    if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);

    try {
      const { logout } = await import("@/actions/auth.action");
      await logout();
    } catch {
      // Force redirect even if the logout API call fails
    }

    // Clear IndexedDB offline data to prevent stale data on next login
    if (typeof indexedDB !== "undefined") {
      try {
        const { clearOfflineData } = await import("@/lib/offline/db");
        await clearOfflineData();
      } catch {
        // Best effort -- don't block the redirect
      }
    }

    router.push("/login?error=session_expired");
  }, [router]);

  // ---- Timer management ----

  const resetTimers = useCallback(() => {
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);

    setShowWarning(false);
    showWarningRef.current = false;

    // Show warning after warningMinutes of inactivity
    warningTimerRef.current = setTimeout(
      () => {
        setShowWarning(true);
        showWarningRef.current = true;

        const totalRemaining = (timeoutMinutes - warningMinutes) * 60;
        setRemainingSeconds(totalRemaining);

        // Tick countdown every second
        countdownRef.current = setInterval(() => {
          setRemainingSeconds((prev) => {
            if (prev <= 1) {
              handleLogout();
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      },
      warningMinutes * 60 * 1000,
    );
  }, [warningMinutes, timeoutMinutes, handleLogout]);

  // ---- Heartbeat ----

  const sendHeartbeat = useCallback(async () => {
    // Only send if the user was recently active (within the heartbeat interval)
    const msSinceActivity = Date.now() - lastActivityRef.current;
    const minutesSinceActivity = msSinceActivity / 1000 / 60;

    if (minutesSinceActivity < heartbeatIntervalMinutes) {
      try {
        const { heartbeat } = await import("@/actions/auth.action");
        await heartbeat();
      } catch {
        // Silently fail -- heartbeat is best-effort
      }
    }
  }, [heartbeatIntervalMinutes]);

  // ---- Continue session (dismiss warning) ----

  const continueSession = useCallback(() => {
    lastActivityRef.current = Date.now();
    setShowWarning(false);
    showWarningRef.current = false;
    if (countdownRef.current) clearInterval(countdownRef.current);
    resetTimers();
    // Immediately update the server so the backend session timeout resets
    sendHeartbeat();
  }, [resetTimers, sendHeartbeat]);

  // ---- Activity tracking ----

  const onActivity = useCallback(() => {
    lastActivityRef.current = Date.now();

    // If warning is showing, user must explicitly click "Continue Session"
    if (!showWarningRef.current) {
      resetTimers();
    }
  }, [resetTimers]);

  // ---- Setup event listeners and timers ----

  useEffect(() => {
    const events = ["mousedown", "keydown", "scroll", "touchstart"];

    // Throttle mousemove to once per 5 seconds to avoid excessive calls
    let mouseMoveTimeout: ReturnType<typeof setTimeout> | null = null;
    const throttledMouseMove = () => {
      if (!mouseMoveTimeout) {
        mouseMoveTimeout = setTimeout(() => {
          onActivity();
          mouseMoveTimeout = null;
        }, 5000);
      }
    };

    events.forEach((event) => {
      window.addEventListener(event, onActivity, { passive: true });
    });
    window.addEventListener("mousemove", throttledMouseMove, { passive: true });

    // Start heartbeat interval
    heartbeatTimerRef.current = setInterval(
      sendHeartbeat,
      heartbeatIntervalMinutes * 60 * 1000,
    );

    // Start initial warning/logout timers
    resetTimers();

    return () => {
      events.forEach((event) => {
        window.removeEventListener(event, onActivity);
      });
      window.removeEventListener("mousemove", throttledMouseMove);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
      if (mouseMoveTimeout) clearTimeout(mouseMoveTimeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { showWarning, remainingSeconds, continueSession };
}
