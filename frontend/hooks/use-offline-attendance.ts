"use client";

import { useState, useEffect, useCallback } from "react";
import { useNetworkStatus } from "./use-network-status";
import { getOfflineDB, type AttendanceRecord, type CachedStudents } from "@/lib/offline/db";
import {
  queueAttendance,
  syncPendingAttendance,
  getAttendanceQueueSize,
} from "@/lib/offline/sync";

interface OfflineStudent {
  id: string;
  student_id: string;
  first_name: string;
  last_name: string;
  gender?: string;
}

interface UseOfflineAttendanceOptions {
  sectionId: string;
  tenantId: string;
  fetchStudents: () => Promise<OfflineStudent[]>;
  postAttendance: (
    sectionId: string,
    date: string,
    records: AttendanceRecord[]
  ) => Promise<boolean>;
}

export function useOfflineAttendance({
  sectionId,
  tenantId,
  fetchStudents,
  postAttendance,
}: UseOfflineAttendanceOptions) {
  const { isOnline } = useNetworkStatus();
  const [students, setStudents] = useState<OfflineStudent[]>([]);
  const [isFromCache, setIsFromCache] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [pendingCount, setPendingCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);

  // Load students: try network first, fall back to IndexedDB cache
  const loadStudents = useCallback(async () => {
    setIsLoading(true);
    try {
      if (isOnline) {
        // Fetch from API
        const data = await fetchStudents();
        setStudents(data);
        setIsFromCache(false);

        // Cache in IndexedDB for offline use
        try {
          const db = await getOfflineDB();
          await db.put("students", {
            section_id: sectionId,
            tenant_id: tenantId,
            students: data.map((s) => ({
              id: s.id,
              student_id: s.student_id,
              first_name: s.first_name,
              last_name: s.last_name,
              gender: s.gender,
            })),
            cached_at: Date.now(),
          });
        } catch {
          // Cache failure is non-critical
        }
      } else {
        // Load from IndexedDB cache
        try {
          const db = await getOfflineDB();
          const cached = await db.get("students", sectionId);
          if (cached && cached.tenant_id === tenantId) {
            setStudents(cached.students);
            setIsFromCache(true);
          }
        } catch {
          // IndexedDB not available
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, [sectionId, tenantId, isOnline, fetchStudents]);

  // Load on mount and when section changes
  useEffect(() => {
    if (sectionId) {
      loadStudents();
    }
  }, [sectionId, loadStudents]);

  // Update pending count
  useEffect(() => {
    const updateCount = async () => {
      try {
        const count = await getAttendanceQueueSize();
        setPendingCount(count);
      } catch {
        // Ignore
      }
    };
    updateCount();
    const interval = setInterval(updateCount, 5000);
    return () => clearInterval(interval);
  }, []);

  // Save attendance: online -> API, offline -> IndexedDB queue
  const saveAttendance = useCallback(
    async (
      date: string,
      records: AttendanceRecord[]
    ): Promise<{ saved: boolean; offline: boolean }> => {
      if (isOnline) {
        try {
          const success = await postAttendance(sectionId, date, records);
          return { saved: success, offline: false };
        } catch {
          // Network failed despite being "online", save offline
          await queueAttendance(sectionId, date, records, tenantId);
          setPendingCount((c) => c + 1);
          return { saved: true, offline: true };
        }
      } else {
        await queueAttendance(sectionId, date, records, tenantId);
        setPendingCount((c) => c + 1);
        return { saved: true, offline: true };
      }
    },
    [isOnline, sectionId, tenantId, postAttendance]
  );

  // Sync pending items
  const syncNow = useCallback(async () => {
    if (!isOnline || isSyncing) return;
    setIsSyncing(true);
    try {
      const result = await syncPendingAttendance(postAttendance);
      const count = await getAttendanceQueueSize();
      setPendingCount(count);
      return result;
    } finally {
      setIsSyncing(false);
    }
  }, [isOnline, isSyncing, postAttendance]);

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
            ?.register("sync-attendance")
            .catch(() => {
              // Background sync not available
            });
        }
      });
    }
  }, [pendingCount]);

  return {
    students,
    isFromCache,
    isLoading,
    isOnline,
    pendingCount,
    isSyncing,
    saveAttendance,
    syncNow,
    loadStudents,
  };
}
