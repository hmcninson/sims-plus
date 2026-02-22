import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "@/app/(auth)/login/page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockPush = vi.fn();
const mockSearchParams = new URLSearchParams();

// Override the global next/navigation mock for per-test control
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => mockSearchParams,
  usePathname: () => "/login",
  redirect: vi.fn(),
  notFound: vi.fn(),
}));

// Mock the login server action
const mockLogin = vi.fn();
vi.mock("@/actions/auth.action", () => ({
  login: (...args: unknown[]) => mockLogin(...args),
}));

// Mock the TenantProvider — default: no tenant (main site)
const mockUseTenant = vi.fn();
vi.mock("@/components/providers/TenantProvider", () => ({
  useTenant: () => mockUseTenant(),
  TenantProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockPush.mockClear();
  mockLogin.mockClear();
  mockUseTenant.mockReturnValue({
    tenant: null,
    isLoading: false,
    error: null,
    subdomain: null,
    isTenantContext: false,
    refreshTenant: vi.fn(),
  });
  // Reset search params to empty
  for (const key of [...mockSearchParams.keys()]) {
    mockSearchParams.delete(key);
  }
});

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("LoginPage", () => {
  it("renders email and password fields", () => {
    render(<LoginPage />);

    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sign in/i })
    ).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Validation
  // -----------------------------------------------------------------------

  it("shows validation error for invalid email", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/email address/i);
    const submitBtn = screen.getByRole("button", { name: /sign in/i });

    await user.type(emailInput, "not-an-email");
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/please enter a valid email/i)).toBeInTheDocument();
    });

    // Login action should NOT have been called
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it("shows validation error when password is empty", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/email address/i);
    const submitBtn = screen.getByRole("button", { name: /sign in/i });

    await user.type(emailInput, "valid@school.edu.gh");
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });

    expect(mockLogin).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // Differentiated error display
  // -----------------------------------------------------------------------

  it("shows 'Login failed' alert on 401 error", async () => {
    mockLogin.mockResolvedValue({
      success: false,
      error: "Invalid email or password",
      code: 401,
    });

    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/email address/i), "user@school.edu.gh");
    await user.type(screen.getByLabelText(/password/i), "wrongpass");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Login failed")).toBeInTheDocument();
    });
  });

  it("shows 'Account locked' alert on 403 error", async () => {
    mockLogin.mockResolvedValue({
      success: false,
      error: "Account locked for 30 minutes",
      code: 403,
    });

    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/email address/i), "user@school.edu.gh");
    await user.type(screen.getByLabelText(/password/i), "somepass");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Account locked")).toBeInTheDocument();
      expect(
        screen.getByText("Account locked for 30 minutes")
      ).toBeInTheDocument();
    });
  });

  it("shows 'Too many attempts' alert on 429 error", async () => {
    mockLogin.mockResolvedValue({
      success: false,
      error: "Rate limit exceeded. Try again later.",
      code: 429,
    });

    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/email address/i), "user@school.edu.gh");
    await user.type(screen.getByLabelText(/password/i), "somepass");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Too many attempts")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // URL error whitelist
  // -----------------------------------------------------------------------

  it("shows warning for whitelisted ?error=session_expired", () => {
    mockSearchParams.set("error", "session_expired");
    render(<LoginPage />);

    expect(screen.getByText("Session expired")).toBeInTheDocument();
    expect(
      screen.getByText(/your session has expired/i)
    ).toBeInTheDocument();
  });

  it("shows error for whitelisted ?error=unauthorized", () => {
    mockSearchParams.set("error", "unauthorized");
    render(<LoginPage />);

    expect(screen.getByText("Access denied")).toBeInTheDocument();
    expect(screen.getByText(/please sign in to continue/i)).toBeInTheDocument();
  });

  it("ignores arbitrary URL error params", () => {
    mockSearchParams.set("error", "you_have_been_hacked");
    render(<LoginPage />);

    // Should NOT render any alert for unrecognized error codes
    expect(screen.queryByText(/you_have_been_hacked/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Successful login
  // -----------------------------------------------------------------------

  it("navigates to /dashboard on successful login", async () => {
    mockLogin.mockResolvedValue({
      success: true,
      data: {
        id: "user-001",
        email: "user@school.edu.gh",
        first_name: "Kwame",
        last_name: "Asante",
        role: "teacher",
        status: "active",
        email_verified: true,
        mfa_enabled: false,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    });

    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/email address/i), "user@school.edu.gh");
    await user.type(screen.getByLabelText(/password/i), "Password1!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard");
    });
  });
});
