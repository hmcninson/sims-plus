/**
 * SIMS Plus - Push Notification Client Library
 *
 * Handles the browser-side push subscription lifecycle:
 * 1. Request notification permission
 * 2. Subscribe to push via the service worker
 * 3. Send subscription keys to the backend
 * 4. Unsubscribe and clean up
 */

import {
  getVapidPublicKey,
  registerPushSubscription,
  removePushSubscription,
} from "@/actions/push.action";

/**
 * Convert a URL-safe base64 VAPID key to a Uint8Array
 * for use with PushManager.subscribe().
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

/**
 * Subscribe the current browser to push notifications.
 *
 * Flow:
 * 1. Check browser support for service workers and PushManager
 * 2. Request notification permission from the user
 * 3. Fetch VAPID public key from the backend
 * 4. Subscribe via PushManager using the service worker registration
 * 5. Send the subscription keys to the backend for storage
 *
 * Returns true on success, false if any step fails or is unsupported.
 */
export async function subscribeToPush(): Promise<boolean> {
  try {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      return false;
    }

    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      return false;
    }

    // Fetch the VAPID public key from our backend
    const vapidResult = await getVapidPublicKey();
    if (!vapidResult.success || !vapidResult.data) {
      return false;
    }

    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidResult.data.public_key) as BufferSource,
    });

    const keys = subscription.toJSON().keys;
    if (!keys) return false;

    const result = await registerPushSubscription({
      endpoint: subscription.endpoint,
      p256dh_key: keys.p256dh || "",
      auth_key: keys.auth || "",
      user_agent: navigator.userAgent,
    });

    return result.success;
  } catch {
    return false;
  }
}

/**
 * Unsubscribe from push notifications.
 *
 * Removes the subscription from both the backend and the browser.
 * Returns true on success, false on error.
 */
export async function unsubscribeFromPush(): Promise<boolean> {
  try {
    if (!("serviceWorker" in navigator)) return false;

    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();

    if (subscription) {
      // Remove from backend first, then from browser
      await removePushSubscription(subscription.endpoint);
      await subscription.unsubscribe();
    }

    return true;
  } catch {
    return false;
  }
}
