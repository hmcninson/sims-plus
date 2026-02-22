import { getOfflineDB, type QueuedAttendance, type QueuedRollCall } from "./db";

const MAX_RETRIES = 5;
const BASE_DELAY_MS = 1000;

function getBackoffDelay(retryCount: number): number {
  return Math.min(BASE_DELAY_MS * Math.pow(2, retryCount), 30000);
}

export async function queueAttendance(
  sectionId: string,
  date: string,
  records: QueuedAttendance["records"],
  tenantId: string
): Promise<void> {
  const db = await getOfflineDB();
  await db.add("attendance_queue", {
    section_id: sectionId,
    date,
    records,
    tenant_id: tenantId,
    queued_at: Date.now(),
    retry_count: 0,
  });
}

export async function queueRollCall(
  houseId: string,
  date: string,
  timeOfDay: string,
  records: QueuedRollCall["records"],
  tenantId: string
): Promise<void> {
  const db = await getOfflineDB();
  await db.add("rollcall_queue", {
    house_id: houseId,
    date,
    time_of_day: timeOfDay,
    records,
    tenant_id: tenantId,
    queued_at: Date.now(),
    retry_count: 0,
  });
}

export async function getAttendanceQueueSize(): Promise<number> {
  const db = await getOfflineDB();
  return db.count("attendance_queue");
}

export async function getRollCallQueueSize(): Promise<number> {
  const db = await getOfflineDB();
  return db.count("rollcall_queue");
}

export async function getTotalQueueSize(): Promise<number> {
  const [att, rc] = await Promise.all([
    getAttendanceQueueSize(),
    getRollCallQueueSize(),
  ]);
  return att + rc;
}

export async function syncPendingAttendance(
  postAttendance: (sectionId: string, date: string, records: QueuedAttendance["records"]) => Promise<boolean>
): Promise<{ synced: number; failed: number }> {
  const db = await getOfflineDB();
  const all = await db.getAll("attendance_queue");

  let synced = 0;
  let failed = 0;

  for (const item of all) {
    if (item.retry_count >= MAX_RETRIES) {
      failed++;
      continue;
    }

    try {
      const success = await postAttendance(item.section_id, item.date, item.records);
      if (success) {
        await db.delete("attendance_queue", item.id!);
        synced++;
      } else {
        await db.put("attendance_queue", {
          ...item,
          retry_count: item.retry_count + 1,
        });
        failed++;
      }
    } catch {
      await db.put("attendance_queue", {
        ...item,
        retry_count: item.retry_count + 1,
      });
      failed++;
      // Exponential backoff
      await new Promise((r) => setTimeout(r, getBackoffDelay(item.retry_count)));
    }
  }

  return { synced, failed };
}

export async function syncPendingRollCalls(
  postRollCall: (houseId: string, date: string, timeOfDay: string, records: QueuedRollCall["records"]) => Promise<boolean>
): Promise<{ synced: number; failed: number }> {
  const db = await getOfflineDB();
  const all = await db.getAll("rollcall_queue");

  let synced = 0;
  let failed = 0;

  for (const item of all) {
    if (item.retry_count >= MAX_RETRIES) {
      failed++;
      continue;
    }

    try {
      const success = await postRollCall(item.house_id, item.date, item.time_of_day, item.records);
      if (success) {
        await db.delete("rollcall_queue", item.id!);
        synced++;
      } else {
        await db.put("rollcall_queue", {
          ...item,
          retry_count: item.retry_count + 1,
        });
        failed++;
      }
    } catch {
      await db.put("rollcall_queue", {
        ...item,
        retry_count: item.retry_count + 1,
      });
      failed++;
      await new Promise((r) => setTimeout(r, getBackoffDelay(item.retry_count)));
    }
  }

  return { synced, failed };
}
