import { openDB, type DBSchema, type IDBPDatabase } from "idb";

interface AttendanceRecord {
  student_id: string;
  status: string;
  notes?: string;
}

interface QueuedAttendance {
  id?: number;
  section_id: string;
  date: string;
  records: AttendanceRecord[];
  tenant_id: string;
  queued_at: number;
  retry_count: number;
}

interface QueuedRollCall {
  id?: number;
  house_id: string;
  date: string;
  time_of_day: string;
  records: { student_id: string; status: string; notes?: string }[];
  tenant_id: string;
  queued_at: number;
  retry_count: number;
}

interface SyncMeta {
  key: string;
  value: string;
  updated_at: number;
}

interface CachedStudents {
  section_id: string;
  tenant_id: string;
  students: Array<{
    id: string;
    student_id: string;
    first_name: string;
    last_name: string;
    gender?: string;
  }>;
  cached_at: number;
}

interface SimsPlusDB extends DBSchema {
  attendance_queue: {
    key: number;
    value: QueuedAttendance;
    indexes: { "by-tenant": string };
  };
  rollcall_queue: {
    key: number;
    value: QueuedRollCall;
    indexes: { "by-tenant": string };
  };
  students: {
    key: string;
    value: CachedStudents;
    indexes: { "by-tenant": string };
  };
  sync_meta: {
    key: string;
    value: SyncMeta;
  };
}

const DB_NAME = "sims_plus_offline";
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase<SimsPlusDB>> | null = null;

export function getOfflineDB(): Promise<IDBPDatabase<SimsPlusDB>> {
  if (!dbPromise) {
    dbPromise = openDB<SimsPlusDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        // Attendance queue
        const attendanceStore = db.createObjectStore("attendance_queue", {
          keyPath: "id",
          autoIncrement: true,
        });
        attendanceStore.createIndex("by-tenant", "tenant_id");

        // Roll call queue
        const rollcallStore = db.createObjectStore("rollcall_queue", {
          keyPath: "id",
          autoIncrement: true,
        });
        rollcallStore.createIndex("by-tenant", "tenant_id");

        // Cached students (keyed by section_id)
        const studentsStore = db.createObjectStore("students", {
          keyPath: "section_id",
        });
        studentsStore.createIndex("by-tenant", "tenant_id");

        // Sync metadata
        db.createObjectStore("sync_meta", { keyPath: "key" });
      },
    });
  }
  return dbPromise;
}

export async function clearOfflineData(): Promise<void> {
  const db = await getOfflineDB();
  const tx = db.transaction(
    ["attendance_queue", "rollcall_queue", "students", "sync_meta"],
    "readwrite"
  );
  await Promise.all([
    tx.objectStore("attendance_queue").clear(),
    tx.objectStore("rollcall_queue").clear(),
    tx.objectStore("students").clear(),
    tx.objectStore("sync_meta").clear(),
    tx.done,
  ]);
}

export async function clearTenantData(tenantId: string): Promise<void> {
  const db = await getOfflineDB();

  // Clear attendance queue for this tenant
  const attTx = db.transaction("attendance_queue", "readwrite");
  const attIndex = attTx.store.index("by-tenant");
  let attCursor = await attIndex.openCursor(tenantId);
  while (attCursor) {
    await attCursor.delete();
    attCursor = await attCursor.continue();
  }
  await attTx.done;

  // Clear rollcall queue for this tenant
  const rcTx = db.transaction("rollcall_queue", "readwrite");
  const rcIndex = rcTx.store.index("by-tenant");
  let rcCursor = await rcIndex.openCursor(tenantId);
  while (rcCursor) {
    await rcCursor.delete();
    rcCursor = await rcCursor.continue();
  }
  await rcTx.done;

  // Clear cached students for this tenant
  const stTx = db.transaction("students", "readwrite");
  const stIndex = stTx.store.index("by-tenant");
  let stCursor = await stIndex.openCursor(tenantId);
  while (stCursor) {
    await stCursor.delete();
    stCursor = await stCursor.continue();
  }
  await stTx.done;
}

export type {
  QueuedAttendance,
  QueuedRollCall,
  CachedStudents,
  AttendanceRecord,
  SimsPlusDB,
};
