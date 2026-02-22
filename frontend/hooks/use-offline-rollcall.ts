"use client";

import { useState, useEffect, useCallback } from "react";
import { useNetworkStatus } from "./use-network-status";
import {
  queueRollCall,
  syncPendingRollCalls,
  getRollCallQueueSize,
} from "@/lib/offline/sync";
import type { QueuedRollCall } from "@/lib/offline/db";

interface UseOfflineRollCallOptions {
  postRollCall: (
    houseId: string,
    date: string,
    timeOfDay: string,
    records: QueuedRollCall["records"]
  ) => Promise<boolean>;
}

export function useOfflineRollCall({ postRollCall }: UseOfflineRollCallOptions) {
  const { isOnline } = useNetworkStatus();
  const [pendingCount, setPendingCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);

  // Update pending count
  useEffect(() => {
    const updateCount = async () => {
      try {
        const count = await getRollCallQueueSize();
        setPendingCount(count);
      } catch {
        // Ignore
      }
    };
    updateCount();
    const interval = setInterval(updateCount, 5000);
    return () => clearInterval(interval);
  }, []);

  // Submit roll call: online -> API, offline -> IndexedDB queue
  const saveRollCall = useCallback(
    async (
      houseId: string,
      date: string,
      timeOfDay: string,
      records: QueuedRollCall["records"],
      tenantId: string
    ): Promise<{ saved: boolean; offline: boolean }> => {
      if (isOnline) {
        try {
          const success = await postRollCall(houseId, date, timeOfDay, records);
          return { saved: success, offline: false };
        } catch {
          // Network failed despite being "online", save offline
          await queueRollCall(houseId, date, timeOfDay, records, tenantId);
          setPendingCount((c) => c + 1);
          return { saved: true, offline: true };
        }
      } else {
        await queueRollCall(houseId, date, timeOfDay, records, tenantId);
        setPendingCount((c) => c + 1);
        return { saved: true, offline: true };
      }
    },
    [isOnline, postRollCall]
  );

  // Sync pending items
  const syncNow = useCallback(async () => {
    if (!isOnline || isSyncing) return;
    setIsSyncing(true);
    try {
      const result = await syncPendingRollCalls(postRollCall);
      const count = await getRollCallQueueSize();
      setPendingCount(count);
      return result;
    } finally {
      setIsSyncing(false);
    }
  }, [isOnline, isSyncing, postRollCall]);

  // Auto-sync when coming back online
  useEffect(() => {
    if (isOnline && pendingCount > 0) {
      syncNow();
    }
  }, [isOnline]); // eslint-disable-line react-hooks/exhaustive-deps

  // Register for background sync
  useEffect(() => {
    if ("serviceWorker" in navigator && "SyncManager" in window) {
      navigator.serviceWorker.ready.then((registration) => {
        if (pendingCount > 0) {
          (registration as unknown as { sync?: { register: (tag: string) => Promise<void> } }).sync
            ?.register("sync-rollcall")
            .catch(() => {
              // Background sync not available
            });
        }
      });
    }
  }, [pendingCount]);

  return {
    isOnline,
    pendingCount,
    isSyncing,
    saveRollCall,
    syncNow,
  };
}
