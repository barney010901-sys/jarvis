import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * App-local settings, persisted on-device. Backend connection fields are
 * Phase 1; the voice/privacy fields below are Phase 3 — see each field's
 * comment for what's genuinely implemented vs. a real, honest toggle for
 * a capability this build doesn't have yet (never faked — see
 * docs/PHASE_3.md's REAL/MOCKED/PARTIALLY_IMPLEMENTED/NOT_TESTED table).
 */
export type JarvisSettings = {
  backendHttpUrl: string;
  backendWsUrl: string;
  apiToken: string;

  // REAL: expo-speech text-to-speech for completed assistant replies.
  ttsEnabled: boolean;

  // NOT_IMPLEMENTED in this build — no wake-word engine is bundled (would
  // require a native module + a custom dev client, not the Expo Go/managed
  // runtime this app ships as). The toggle exists so the Settings screen
  // can say so explicitly rather than silently omitting it.
  wakeWordEnabled: boolean;

  // NOT_IMPLEMENTED in this build — see PrivacyCenterScreen. Real 24/7
  // background listening needs a foreground service + wake word, neither
  // of which exist yet.
  alwaysOnMode: boolean;

  // Local-only "kill switch" the microphone UI respects regardless of any
  // other setting — REAL (it's just a boolean the recording button reads).
  microphoneEnabled: boolean;
};

const STORAGE_KEY = 'jarvis.settings.v2';

// Sensible defaults for a backend running on a developer machine reachable
// from an Android emulator (10.0.2.2 is the emulator's alias for the host).
export const DEFAULT_SETTINGS: JarvisSettings = {
  backendHttpUrl: 'http://10.0.2.2:8000',
  backendWsUrl: 'ws://10.0.2.2:8000/ws',
  apiToken: '',
  ttsEnabled: true,
  wakeWordEnabled: false,
  alwaysOnMode: false,
  microphoneEnabled: true,
};

export async function loadSettings(): Promise<JarvisSettings> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_SETTINGS, ...parsed };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export async function saveSettings(settings: JarvisSettings): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}
