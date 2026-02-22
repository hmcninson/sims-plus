/**
 * Offline Sync Tests
 *
 * Tests the attendance/roll-call queue and sync logic with mock API functions.
 * Uses fake-indexeddb for the IndexedDB backend.
 */

import "fake-indexeddb/auto";
import {
  queueAttendance,
  getAttendanceQueueSize,
  getRollCallQueueSize,
  getTotalQueueSize,
  syncPendingAttendance,
  queueRollCall,
} from "@/lib/offline/sync";

// fake-indexeddb/auto sets up the global but the module caches its db promise.
// We need to reset module state between tests.
// Since getOfflineDB is a singleton, we rely on clearOfflineData between tests.
import { clearOfflineData } from "@/lib/offline/db";

beforeEach(async () => {
  await clearOfflineData();
});

describe("queueAttendance", () => {
  it("adds an attendance record to the queue", async () => {
    await queueAttendance(
      "section-1",
      "2026-02-20",
      [{ student_id: "stu-1", status: "present" }],
      "tenant-1"
    );

    const size = await getAttendanceQueueSize();
    expect(size).toBe(1);
  });

  it("adds multiple records independently", async () => {
    await queueAttendance("sec-1", "2026-02-20", [], "tenant-1");
    await queueAttendance("sec-2", "2026-02-20", [], "tenant-1");
    await queueAttendance("sec-3", "2026-02-21", [], "tenant-2");

    const size = await getAttendanceQueueSize();
    expect(size).toBe(3);
  });
});

describe("queueRollCall", () => {
  it("adds a roll call record to the queue", async () => {
    await queueRollCall(
      "house-1",
      "2026-02-20",
      "morning",
      [{ student_id: "stu-1", status: "present" }],
      "tenant-1"
    );

    const size = await getRollCallQueueSize();
    expect(size).toBe(1);
  });
});

describe("getTotalQueueSize", () => {
  it("returns combined count of attendance and roll call queues", async () => {
    await queueAttendance("sec-1", "2026-02-20", [], "tenant-1");
    await queueAttendance("sec-2", "2026-02-20", [], "tenant-1");
    await queueRollCall("house-1", "2026-02-20", "morning", [], "tenant-1");

    const total = await getTotalQueueSize();
    expect(total).toBe(3);
  });

  it("returns 0 when both queues are empty", async () => {
    const total = await getTotalQueueSize();
    expect(total).toBe(0);
  });
});

describe("syncPendingAttendance", () => {
  it("syncs all queued items when postAttendance succeeds", async () => {
    await queueAttendance(
      "sec-1",
      "2026-02-20",
      [{ student_id: "stu-1", status: "present" }],
      "tenant-1"
    );
    await queueAttendance(
      "sec-2",
      "2026-02-20",
      [{ student_id: "stu-2", status: "absent" }],
      "tenant-1"
    );

    const mockPost = vi.fn().mockResolvedValue(true);

    const result = await syncPendingAttendance(mockPost);

    expect(result.synced).toBe(2);
    expect(result.failed).toBe(0);
    expect(mockPost).toHaveBeenCalledTimes(2);

    // Queue should be empty after successful sync
    const remaining = await getAttendanceQueueSize();
    expect(remaining).toBe(0);
  });

  it("increments retry_count when postAttendance returns false", async () => {
    await queueAttendance(
      "sec-1",
      "2026-02-20",
      [{ student_id: "stu-1", status: "present" }],
      "tenant-1"
    );

    const mockPost = vi.fn().mockResolvedValue(false);

    const result = await syncPendingAttendance(mockPost);

    expect(result.synced).toBe(0);
    expect(result.failed).toBe(1);

    // Item should still be in queue with incremented retry count
    const remaining = await getAttendanceQueueSize();
    expect(remaining).toBe(1);
  });

  it("skips items that have exceeded MAX_RETRIES (5)", async () => {
    // Manually insert an item with retry_count = 5 via queueing + repeated failures
    // Simpler: queue an item, fail it 5 times via successive syncs, then verify skip

    await queueAttendance("sec-1", "2026-02-20", [], "tenant-1");

    const failPost = vi.fn().mockResolvedValue(false);

    // Fail 5 times to hit MAX_RETRIES
    for (let i = 0; i < 5; i++) {
      await syncPendingAttendance(failPost);
    }

    // Now on the 6th sync, the item should be skipped (retry_count >= 5)
    const successPost = vi.fn().mockResolvedValue(true);
    const result = await syncPendingAttendance(successPost);

    expect(result.synced).toBe(0);
    expect(result.failed).toBe(1); // Counted as failed (max retries exceeded)
    expect(successPost).not.toHaveBeenCalled(); // Never even attempted
  });

  it("returns zero counts when queue is empty", async () => {
    const mockPost = vi.fn().mockResolvedValue(true);

    const result = await syncPendingAttendance(mockPost);

    expect(result.synced).toBe(0);
    expect(result.failed).toBe(0);
    expect(mockPost).not.toHaveBeenCalled();
  });
});
