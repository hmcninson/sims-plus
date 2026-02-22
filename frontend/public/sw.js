// SIMS Plus Service Worker
importScripts('https://storage.googleapis.com/workbox-cdn/releases/7.3.0/workbox-sw.js');

if (workbox) {
  // Static assets: StaleWhileRevalidate
  workbox.routing.registerRoute(
    ({request}) => request.destination === 'script' || request.destination === 'style' || request.destination === 'font',
    new workbox.strategies.StaleWhileRevalidate({ cacheName: 'static-assets' })
  );

  // Images: CacheFirst with 30-day expiry
  workbox.routing.registerRoute(
    ({request}) => request.destination === 'image',
    new workbox.strategies.CacheFirst({
      cacheName: 'images',
      plugins: [
        new workbox.expiration.ExpirationPlugin({ maxEntries: 100, maxAgeSeconds: 30 * 24 * 60 * 60 })
      ]
    })
  );

  // HTML/navigation: NetworkFirst with offline fallback
  workbox.routing.registerRoute(
    ({request}) => request.mode === 'navigate',
    new workbox.strategies.NetworkFirst({
      cacheName: 'pages',
      plugins: [
        new workbox.expiration.ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 24 * 60 * 60 })
      ]
    })
  );

  // API calls: NetworkOnly (no caching)
  workbox.routing.registerRoute(
    ({url}) => url.pathname.startsWith('/api/'),
    new workbox.strategies.NetworkOnly()
  );
  // Offline fallback for navigation requests
  workbox.routing.setCatchHandler(({ event }) => {
    if (event.request.mode === 'navigate') {
      return caches.match('/offline') || Response.error();
    }
    return Response.error();
  });
} else {
  console.warn('Workbox failed to load');

  // Fallback offline handler when Workbox is unavailable
  self.addEventListener('fetch', (event) => {
    if (event.request.mode === 'navigate') {
      event.respondWith(
        fetch(event.request).catch(() => caches.match('/offline'))
      );
    }
  });
}

// Push notification handler
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'SIMS Plus';
  const options = {
    body: data.body || 'You have a new notification',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    tag: data.tag || 'default',
    data: { url: data.url || '/dashboard' }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/dashboard';
  event.waitUntil(clients.openWindow(url));
});

// Background sync handler (for offline attendance)
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-attendance') {
    event.waitUntil(syncAttendanceFromSW());
  }
  if (event.tag === 'sync-rollcall') {
    event.waitUntil(syncRollcallFromSW());
  }
});

// =========================
// IndexedDB helper for service worker (cannot use npm `idb` package)
// =========================

const DB_NAME = 'sims_plus_offline';
const DB_VERSION = 1;

function idbOpen() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    // If the DB doesn't exist yet, create stores (mirrors lib/offline/db.ts)
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('attendance_queue')) {
        const attStore = db.createObjectStore('attendance_queue', { keyPath: 'id', autoIncrement: true });
        attStore.createIndex('by-tenant', 'tenant_id');
      }
      if (!db.objectStoreNames.contains('rollcall_queue')) {
        const rcStore = db.createObjectStore('rollcall_queue', { keyPath: 'id', autoIncrement: true });
        rcStore.createIndex('by-tenant', 'tenant_id');
      }
      if (!db.objectStoreNames.contains('students')) {
        const stStore = db.createObjectStore('students', { keyPath: 'section_id' });
        stStore.createIndex('by-tenant', 'tenant_id');
      }
      if (!db.objectStoreNames.contains('sync_meta')) {
        db.createObjectStore('sync_meta', { keyPath: 'key' });
      }
    };
  });
}

function idbGetAll(db, storeName) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const store = tx.objectStore(storeName);
    const request = store.getAll();
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

function idbDelete(db, storeName, key) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    const request = store.delete(key);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

function idbPut(db, storeName, value) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    const request = store.put(value);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

// =========================
// Background sync implementations
// =========================

async function syncAttendanceFromSW() {
  console.log('[SW] Background sync: attendance');
  try {
    const db = await idbOpen();
    const items = await idbGetAll(db, 'attendance_queue');

    for (const item of items) {
      if (item.retry_count >= 5) continue; // Skip items that have exceeded max retries

      try {
        const response = await fetch('/api/v1/attendance/students/bulk', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            section_id: item.section_id,
            date: item.date,
            records: item.records,
          }),
        });

        if (response.ok) {
          await idbDelete(db, 'attendance_queue', item.id);
          console.log('[SW] Synced attendance record:', item.id);
        } else {
          // Increment retry count
          await idbPut(db, 'attendance_queue', {
            ...item,
            retry_count: (item.retry_count || 0) + 1,
          });
          console.log('[SW] Attendance sync failed (HTTP', response.status, '), will retry');
        }
      } catch (err) {
        // Network error for this item, increment retry and continue
        await idbPut(db, 'attendance_queue', {
          ...item,
          retry_count: (item.retry_count || 0) + 1,
        });
        console.log('[SW] Attendance sync error for item', item.id, ':', err.message);
      }
    }
  } catch (err) {
    console.log('[SW] Attendance sync failed:', err.message);
  }
}

async function syncRollcallFromSW() {
  console.log('[SW] Background sync: rollcall');
  try {
    const db = await idbOpen();
    const items = await idbGetAll(db, 'rollcall_queue');

    for (const item of items) {
      if (item.retry_count >= 5) continue; // Skip items that have exceeded max retries

      try {
        const response = await fetch('/api/v1/boarding/roll-calls', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            house_id: item.house_id,
            date: item.date,
            roll_call_type: item.time_of_day,
            entries: item.records.map((r) => ({
              student_id: r.student_id,
              status: r.status,
            })),
          }),
        });

        if (response.ok) {
          await idbDelete(db, 'rollcall_queue', item.id);
          console.log('[SW] Synced roll call record:', item.id);
        } else {
          await idbPut(db, 'rollcall_queue', {
            ...item,
            retry_count: (item.retry_count || 0) + 1,
          });
          console.log('[SW] Roll call sync failed (HTTP', response.status, '), will retry');
        }
      } catch (err) {
        await idbPut(db, 'rollcall_queue', {
          ...item,
          retry_count: (item.retry_count || 0) + 1,
        });
        console.log('[SW] Roll call sync error for item', item.id, ':', err.message);
      }
    }
  } catch (err) {
    console.log('[SW] Roll call sync failed:', err.message);
  }
}
