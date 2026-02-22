import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MobileQuickActions } from "@/components/dashboard/mobile-quick-actions";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/dashboard",
  redirect: vi.fn(),
  notFound: vi.fn(),
}));

beforeEach(() => {
  mockPush.mockClear();
});

describe("MobileQuickActions", () => {
  it("renders the FAB toggle button", () => {
    render(<MobileQuickActions />);

    // The FAB button is a toggle
    const fabButton = screen.getByRole("button");
    expect(fabButton).toBeInTheDocument();
  });

  it("does not show action labels initially (closed state)", () => {
    render(<MobileQuickActions />);

    expect(screen.queryByText("Mark Attendance")).not.toBeInTheDocument();
    expect(screen.queryByText("Record Payment")).not.toBeInTheDocument();
    expect(screen.queryByText("Roll Call")).not.toBeInTheDocument();
    expect(screen.queryByText("Notifications")).not.toBeInTheDocument();
  });

  it("shows all 4 quick actions when FAB is clicked", async () => {
    const user = userEvent.setup();
    render(<MobileQuickActions />);

    // Click the FAB to expand
    const fabButton = screen.getByRole("button");
    await user.click(fabButton);

    expect(screen.getByText("Mark Attendance")).toBeInTheDocument();
    expect(screen.getByText("Record Payment")).toBeInTheDocument();
    expect(screen.getByText("Roll Call")).toBeInTheDocument();
    expect(screen.getByText("Notifications")).toBeInTheDocument();
  });

  it("navigates when an action is clicked and collapses the menu", async () => {
    const user = userEvent.setup();
    render(<MobileQuickActions />);

    // Open the FAB
    const fabButton = screen.getByRole("button");
    await user.click(fabButton);

    // Click "Mark Attendance"
    const attendanceButton = screen.getByText("Mark Attendance").closest("button")!;
    await user.click(attendanceButton);

    expect(mockPush).toHaveBeenCalledWith("/attendance/mark");

    // After clicking, the actions should collapse
    expect(screen.queryByText("Mark Attendance")).not.toBeInTheDocument();
  });
});
