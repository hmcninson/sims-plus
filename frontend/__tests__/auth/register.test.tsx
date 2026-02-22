import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RegisterPage from "@/app/(auth)/register/page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockPush = vi.fn();
const mockSearchParams = new URLSearchParams();

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
  usePathname: () => "/register",
  redirect: vi.fn(),
  notFound: vi.fn(),
}));

const mockRegister = vi.fn();
vi.mock("@/actions/auth.action", () => ({
  register: (...args: unknown[]) => mockRegister(...args),
}));

// Mock sonner toast
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

// Mock fetch for subdomain availability checks
const mockFetch = vi.fn();
global.fetch = mockFetch;

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockPush.mockClear();
  mockRegister.mockClear();
  mockFetch.mockClear();
  for (const key of [...mockSearchParams.keys()]) {
    mockSearchParams.delete(key);
  }
  // Default: subdomain check returns available
  mockFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ available: true }),
  });
});

// ---------------------------------------------------------------------------
// Step 1: School Information (initial render)
// ---------------------------------------------------------------------------

describe("RegisterPage - Step 1", () => {
  it("renders step 1 (School Info) by default", () => {
    render(<RegisterPage />);

    expect(screen.getByText("School Information")).toBeInTheDocument();
    expect(screen.getByLabelText(/school name/i)).toBeInTheDocument();
    // School type label exists (use getAllByText since label + placeholder both match)
    expect(screen.getAllByText(/school type/i).length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: /next/i })
    ).toBeInTheDocument();
  });

  it("does not show step 2 fields initially", () => {
    render(<RegisterPage />);

    expect(screen.queryByText("Administrator Account")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/first name/i)).not.toBeInTheDocument();
  });

  it("renders the 3-step progress indicator", () => {
    render(<RegisterPage />);

    // All three step labels should be present
    expect(screen.getByText("School Info")).toBeInTheDocument();
    expect(screen.getByText("Admin Account")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("generates subdomain automatically from school name", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    const schoolNameInput = screen.getByLabelText(/school name/i);
    await user.type(schoolNameInput, "Bright Future Academy");

    // The subdomain field should auto-populate (label is "Choose Your School's Web Address")
    await waitFor(() => {
      const subdomainInput = screen.getByLabelText(/web address/i);
      expect(subdomainInput).toHaveValue("brightfutureacademy");
    });
  });

  it("checks subdomain availability via fetch", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    const schoolNameInput = screen.getByLabelText(/school name/i);
    await user.type(schoolNameInput, "Test School");

    // Wait for debounced fetch to fire
    await waitFor(
      () => {
        expect(mockFetch).toHaveBeenCalled();
      },
      { timeout: 2000 }
    );

    // Should show available status
    await waitFor(
      () => {
        expect(screen.queryByText(/is available/i)).toBeInTheDocument();
      },
      { timeout: 2000 }
    );
  });

  it("shows unavailable when subdomain check returns false", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ available: false }),
    });

    const user = userEvent.setup();
    render(<RegisterPage />);

    const schoolNameInput = screen.getByLabelText(/school name/i);
    await user.type(schoolNameInput, "Taken School");

    await waitFor(
      () => {
        expect(mockFetch).toHaveBeenCalled();
      },
      { timeout: 2000 }
    );

    await waitFor(
      () => {
        const unavailableText = screen.queryByText(/already taken|not available|unavailable/i);
        expect(unavailableText).toBeInTheDocument();
      },
      { timeout: 2000 }
    );
  });

  it("shows safe default when subdomain check fails", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    const user = userEvent.setup();
    render(<RegisterPage />);

    const schoolNameInput = screen.getByLabelText(/school name/i);
    await user.type(schoolNameInput, "Error School");

    await waitFor(
      () => {
        expect(mockFetch).toHaveBeenCalled();
      },
      { timeout: 2000 }
    );

    // On error, should show "unable to verify" or similar (safe default)
    await waitFor(
      () => {
        const errorText = screen.queryByText(/unable to verify|not available|unavailable/i);
        expect(errorText).toBeInTheDocument();
      },
      { timeout: 2000 }
    );
  });
});

// ---------------------------------------------------------------------------
// Step 1 validation
// ---------------------------------------------------------------------------

describe("RegisterPage - Step 1 Validation", () => {
  it("prevents advancing to step 2 when school name is empty", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    // Click Next without filling anything
    await user.click(screen.getByRole("button", { name: /next/i }));

    // Should still be on step 1
    await waitFor(() => {
      expect(screen.getByText("School Information")).toBeInTheDocument();
      expect(screen.queryByText("Administrator Account")).not.toBeInTheDocument();
    });
  });
});
