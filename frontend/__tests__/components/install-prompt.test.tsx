import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InstallPrompt } from "@/components/pwa/install-prompt";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

const DISMISS_KEY = "sims-pwa-install-dismissed";

beforeEach(() => {
  localStorage.clear();
});

describe("InstallPrompt", () => {
  it("does not render when no beforeinstallprompt event has fired", () => {
    render(<InstallPrompt />);

    // The banner text should not be present
    expect(screen.queryByText("Install SIMS Plus")).not.toBeInTheDocument();
  });

  it("renders the install banner after beforeinstallprompt event", () => {
    render(<InstallPrompt />);

    // Simulate the browser firing the beforeinstallprompt event
    act(() => {
      const event = new Event("beforeinstallprompt", { cancelable: true });
      (event as any).prompt = vi.fn();
      (event as any).userChoice = Promise.resolve({ outcome: "dismissed" });
      window.dispatchEvent(event);
    });

    expect(screen.getByText("Install SIMS Plus")).toBeInTheDocument();
    expect(screen.getByText(/add to your home screen/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /install/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /not now/i })).toBeInTheDocument();
  });

  it("hides the banner and saves dismiss timestamp when 'Not now' is clicked", async () => {
    const user = userEvent.setup();
    render(<InstallPrompt />);

    act(() => {
      const event = new Event("beforeinstallprompt", { cancelable: true });
      (event as any).prompt = vi.fn();
      (event as any).userChoice = Promise.resolve({ outcome: "dismissed" });
      window.dispatchEvent(event);
    });

    // Banner is visible
    expect(screen.getByText("Install SIMS Plus")).toBeInTheDocument();

    // Click "Not now"
    await user.click(screen.getByRole("button", { name: /not now/i }));

    // Banner should disappear
    expect(screen.queryByText("Install SIMS Plus")).not.toBeInTheDocument();

    // localStorage should have the dismiss timestamp
    const dismissed = localStorage.getItem(DISMISS_KEY);
    expect(dismissed).not.toBeNull();
  });

  it("does not render if dismissed within the last 7 days", () => {
    // Set dismiss timestamp to 3 days ago
    const threeDaysAgo = Date.now() - 3 * 24 * 60 * 60 * 1000;
    localStorage.setItem(DISMISS_KEY, threeDaysAgo.toString());

    render(<InstallPrompt />);

    // Even after the event, the dismiss check in useEffect should prevent showing
    act(() => {
      const event = new Event("beforeinstallprompt", { cancelable: true });
      (event as any).prompt = vi.fn();
      (event as any).userChoice = Promise.resolve({ outcome: "dismissed" });
      window.dispatchEvent(event);
    });

    expect(screen.queryByText("Install SIMS Plus")).not.toBeInTheDocument();
  });

  it("calls prompt() when Install button is clicked", async () => {
    const user = userEvent.setup();
    const mockPrompt = vi.fn().mockResolvedValue(undefined);
    const mockUserChoice = Promise.resolve({ outcome: "accepted" as const });

    render(<InstallPrompt />);

    act(() => {
      const event = new Event("beforeinstallprompt", { cancelable: true });
      (event as any).prompt = mockPrompt;
      (event as any).userChoice = mockUserChoice;
      window.dispatchEvent(event);
    });

    await user.click(screen.getByRole("button", { name: /install/i }));

    expect(mockPrompt).toHaveBeenCalled();
  });
});
