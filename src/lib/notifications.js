/**
 * In-App Sound Alerts and Browser Push Notification Utilities
 * Bytelytic OS - Clinic Dashboard
 */

/**
 * Play a high-quality dual-tone chime using the Web Audio API.
 * Uses synthesis so it requires no external assets and works in all browsers.
 */
export const playNotificationChime = () => {
  try {
    const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtxClass) {
      console.warn("[Notifications] Web Audio API is not supported in this browser.");
      return false;
    }

    const ctx = new AudioCtxClass();
    if (ctx.state === "suspended") {
      ctx.resume();
    }

    const now = ctx.currentTime;

    // Tone 1: D5 (587.33 Hz) — Warm initial note
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(587.33, now);
    
    // Envelope for tone 1
    gain1.gain.setValueAtTime(0.0001, now);
    gain1.gain.exponentialRampToValueAtTime(0.22, now + 0.04);
    gain1.gain.exponentialRampToValueAtTime(0.0001, now + 0.28);

    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.3);

    // Tone 2: A5 (880.00 Hz) — Clear harmonic accent
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = "sine";
    osc2.frequency.setValueAtTime(880.0, now + 0.12);

    // Envelope for tone 2
    gain2.gain.setValueAtTime(0.0001, now + 0.12);
    gain2.gain.exponentialRampToValueAtTime(0.28, now + 0.16);
    gain2.gain.exponentialRampToValueAtTime(0.0001, now + 0.48);

    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.5);

    return true;
  } catch (err) {
    console.warn("[Notifications] Audio playback error:", err);
    return false;
  }
};

/**
 * Returns current browser notification permission status.
 * Values: 'granted', 'denied', 'default', 'unsupported'
 */
export const getBrowserNotificationStatus = () => {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return "unsupported";
  }
  return Notification.permission;
};

/**
 * Requests permission from the user for desktop browser notifications.
 */
export const requestBrowserNotificationPermission = async () => {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return { supported: false, permission: "unsupported" };
  }

  try {
    const permission = await Notification.requestPermission();
    return { supported: true, permission };
  } catch (err) {
    console.error("[Notifications] Permission request error:", err);
    return { supported: true, permission: Notification.permission || "default" };
  }
};

/**
 * Displays a desktop browser notification if permission is granted.
 */
export const showBrowserNotification = (title, options = {}) => {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return null;
  }

  if (Notification.permission !== "granted") {
    return null;
  }

  try {
    const defaultOptions = {
      icon: "/favicon.ico",
      badge: "/favicon.ico",
      silent: false,
      tag: "bytelytic-alert",
      ...options,
    };

    const notification = new Notification(title, defaultOptions);
    notification.onclick = () => {
      window.focus();
      if (options.onClickUrl) {
        window.location.href = options.onClickUrl;
      }
      notification.close();
    };

    return notification;
  } catch (err) {
    console.warn("[Notifications] Could not display browser notification:", err);
    return null;
  }
};
