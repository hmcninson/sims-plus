import { renderHook, act } from "@testing-library/react";
import { useNetworkStatus } from "@/hooks/use-network-status";

describe("useNetworkStatus", () => {
  // Save and restore original navigator.onLine
  const originalOnLine = navigator.onLine;

  afterEach(() => {
    Object.defineProperty(navigator, "onLine", {
      value: originalOnLine,
      writable: true,
      configurable: true,
    });
  });

  it("returns isOnline: true when navigator.onLine is true", () => {
    Object.defineProperty(navigator, "onLine", {
      value: true,
      writable: true,
      configurable: true,
    });

    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(true);
  });

  it("returns isOnline: false when navigator.onLine is false", () => {
    Object.defineProperty(navigator, "onLine", {
      value: false,
      writable: true,
      configurable: true,
    });

    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(false);
  });

  it("updates to false when offline event fires", () => {
    Object.defineProperty(navigator, "onLine", {
      value: true,
      writable: true,
      configurable: true,
    });

    const { result } = renderHook(() => useNetworkStatus());
    expect(result.current.isOnline).toBe(true);

    act(() => {
      window.dispatchEvent(new Event("offline"));
    });

    expect(result.current.isOnline).toBe(false);
  });

  it("updates to true when online event fires", () => {
    Object.defineProperty(navigator, "onLine", {
      value: false,
      writable: true,
      configurable: true,
    });

    const { result } = renderHook(() => useNetworkStatus());
    expect(result.current.isOnline).toBe(false);

    act(() => {
      window.dispatchEvent(new Event("online"));
    });

    expect(result.current.isOnline).toBe(true);
  });

  it("provides a checkConnection function", () => {
    const { result } = renderHook(() => useNetworkStatus());

    expect(typeof result.current.checkConnection).toBe("function");
  });
});
