import { render, screen, act } from "@testing-library/react";
import { OfflineBanner } from "@/components/offline/offline-banner";

// ---------------------------------------------------------------------------
// Mock the useNetworkStatus hook
// ---------------------------------------------------------------------------

const mockUseNetworkStatus = vi.fn();
vi.mock("@/hooks/use-network-status", () => ({
  useNetworkStatus: () => mockUseNetworkStatus(),
}));

beforeEach(() => {
  mockUseNetworkStatus.mockReturnValue({ isOnline: true, checkConnection: vi.fn() });
});

describe("OfflineBanner", () => {
  it("does not render when online", () => {
    mockUseNetworkStatus.mockReturnValue({ isOnline: true, checkConnection: vi.fn() });
    render(<OfflineBanner />);

    expect(screen.queryByText(/you are offline/i)).not.toBeInTheDocument();
  });

  it("renders warning banner when offline", () => {
    mockUseNetworkStatus.mockReturnValue({ isOnline: false, checkConnection: vi.fn() });
    render(<OfflineBanner />);

    expect(screen.getByText(/you are offline/i)).toBeInTheDocument();
    expect(
      screen.getByText(/some features may be unavailable/i)
    ).toBeInTheDocument();
  });
});
