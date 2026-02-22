"use client";

export default function OfflinePage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-background p-4">
      <div className="mx-auto max-w-md text-center">
        <div className="mb-6 flex justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground text-2xl font-bold">
            S+
          </div>
        </div>
        <h1 className="mb-2 text-2xl font-bold tracking-tight">
          You are offline
        </h1>
        <p className="mb-6 text-muted-foreground">
          It looks like you&apos;ve lost your internet connection. Some features
          may be unavailable until you&apos;re back online.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
        >
          Try again
        </button>
        <p className="mt-4 text-xs text-muted-foreground">
          Attendance and roll call data saved offline will sync automatically
          when you reconnect.
        </p>
      </div>
    </div>
  );
}
