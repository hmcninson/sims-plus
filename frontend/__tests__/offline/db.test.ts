/**
 * Offline IndexedDB Tests
 *
 * Uses fake-indexeddb to provide an in-memory IndexedDB implementation
 * for testing the offline database module.
 */

import "fake-indexeddb/auto";
import { getOfflineDB, clearOfflineData, clearTenantData } from "@/lib/offline/db";

// Reset the module-level singleton between tests so each test gets a fresh DB
beforeEach(async () => {
  // Clear the singleton by re-importing. Since getOfflineDB caches the
  // promise, we need to clear all databases between tests.
  const dbs = await indexedDB.databases?.();
  if (dbs) {
    for (const dbInfo of dbs) {
      if (dbInfo.name) {
        indexedDB.deleteDatabase(dbInfo.name);
      }
    }
  }
});

describe("getOfflineDB", () => {
  it("creates the database with all expected object stores", async () => {
    const db = await getOfflineDB();

    expect(db.objectStoreNames.contains("attendance_queue")).toBe(true);
    expect(db.objectStoreNames.contains("rollcall_queue")).toBe(true);
    expect(db.objectStoreNames.contains("students")).toBe(true);
    expect(db.objectStoreNames.contains("sync_meta")).toBe(true);
  });

  it("returns the same database instance on repeated calls", async () => {
    const db1 = await getOfflineDB();
    const db2 = await getOfflineDB();

    // Should be the exact same instance (cached promise)
    expect(db1).toBe(db2);
  });
});

describe("clearOfflineData", () => {
  it("clears all stores", async () => {
    const db = await getOfflineDB();

    // Add some test data
    await db.add("attendance_queue", {
      section_id: "sec-1",
      date: "2026-02-20",
      records: [{ student_id: "stu-1", status: "present" }],
      tenant_id: "tenant-1",
      queued_at: Date.now(),
      retry_count: 0,
    });

    await db.put("sync_meta", {
      key: "last_sync",
      value: "2026-02-20T10:00:00Z",
      updated_at: Date.now(),
    });

    // Verify data exists
    expect(await db.count("attendance_queue")).toBe(1);
    expect(await db.count("sync_meta")).toBe(1);

    // Clear everything
    await clearOfflineData();

    // Verify all stores are empty
    expect(await db.count("attendance_queue")).toBe(0);
    expect(await db.count("rollcall_queue")).toBe(0);
    expect(await db.count("students")).toBe(0);
    expect(await db.count("sync_meta")).toBe(0);
  });
});

describe("clearTenantData", () => {
  it("clears only data for the specified tenant", async () => {
    const db = await getOfflineDB();

    // Add data for tenant-1
    await db.add("attendance_queue", {
      section_id: "sec-1",
      date: "2026-02-20",
      records: [{ student_id: "stu-1", status: "present" }],
      tenant_id: "tenant-1",
      queued_at: Date.now(),
      retry_count: 0,
    });

    // Add data for tenant-2
    await db.add("attendance_queue", {
      section_id: "sec-2",
      date: "2026-02-20",
      records: [{ student_id: "stu-2", status: "absent" }],
      tenant_id: "tenant-2",
      queued_at: Date.now(),
      retry_count: 0,
    });

    // Clear only tenant-1
    await clearTenantData("tenant-1");

    // tenant-1 data should be gone, tenant-2 data should remain
    const remaining = await db.getAll("attendance_queue");
    expect(remaining).toHaveLength(1);
    expect(remaining[0].tenant_id).toBe("tenant-2");
  });
});
