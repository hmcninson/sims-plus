import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import type { SessionContext, User } from "@/types";
import {
  SessionProvider,
  useSession,
  usePermissions,
} from "@/components/providers/SessionProvider";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const mockUser: User = {
  id: "user-001",
  email: "teacher@presec.edu.gh",
  first_name: "Kwame",
  last_name: "Asante",
  role: "teacher",
  status: "active",
  tenant_id: "tenant-001",
  school_id: "school-001",
  email_verified: true,
  mfa_enabled: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function makeSession(overrides?: Partial<SessionContext>): SessionContext {
  return {
    user: mockUser,
    tenant: {
      id: "tenant-001",
      name: "Presec",
      subdomain: "presec",
      subscription_tier: "professional",
    },
    permissions: ["students.read", "attendance.mark"],
    ...overrides,
  };
}

function wrapper(session: SessionContext) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <SessionProvider session={session}>{children}</SessionProvider>;
  };
}

// ---------------------------------------------------------------------------
// useSession
// ---------------------------------------------------------------------------

describe("useSession", () => {
  it("returns session context when inside provider", () => {
    const session = makeSession();
    const { result } = renderHook(() => useSession(), {
      wrapper: wrapper(session),
    });

    expect(result.current.user).toEqual(mockUser);
    expect(result.current.tenant.subdomain).toBe("presec");
    expect(result.current.permissions).toEqual([
      "students.read",
      "attendance.mark",
    ]);
  });

  it("throws when used outside provider", () => {
    // Suppress React error boundary console noise
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      renderHook(() => useSession());
    }).toThrow("useSession must be used within a SessionProvider");

    spy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// usePermissions
// ---------------------------------------------------------------------------

describe("usePermissions", () => {
  it("returns true for an exact permission match", () => {
    const session = makeSession({
      permissions: ["students.read", "finance.invoices.read"],
    });
    const { result } = renderHook(() => usePermissions(), {
      wrapper: wrapper(session),
    });

    expect(result.current("students.read")).toBe(true);
    expect(result.current("finance.invoices.read")).toBe(true);
  });

  it("returns false for a permission the user does not have", () => {
    const session = makeSession({ permissions: ["students.read"] });
    const { result } = renderHook(() => usePermissions(), {
      wrapper: wrapper(session),
    });

    expect(result.current("finance.invoices.read")).toBe(false);
  });

  it("matches wildcard permission (students.* matches students.read)", () => {
    const session = makeSession({ permissions: ["students.*"] });
    const { result } = renderHook(() => usePermissions(), {
      wrapper: wrapper(session),
    });

    expect(result.current("students.read")).toBe(true);
    expect(result.current("students.write")).toBe(true);
    expect(result.current("finance.read")).toBe(false);
  });

  it("matches nested wildcard (finance.* matches finance.invoices.read)", () => {
    const session = makeSession({ permissions: ["finance.*"] });
    const { result } = renderHook(() => usePermissions(), {
      wrapper: wrapper(session),
    });

    expect(result.current("finance.invoices.read")).toBe(true);
  });

  it("superadmin * permission matches everything", () => {
    const session = makeSession({ permissions: ["*"] });
    const { result } = renderHook(() => usePermissions(), {
      wrapper: wrapper(session),
    });

    expect(result.current("students.read")).toBe(true);
    expect(result.current("finance.invoices.write")).toBe(true);
    expect(result.current("anything.at.all")).toBe(true);
  });
});
