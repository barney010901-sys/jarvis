import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * Backend connection settings, persisted locally. No AI logic lives here —
 * this is purely "where is the backend and how do I authenticate to it",
 * editable from the Settings screen.
 */
export type JarvisSettings = {
  backendHttpUrl: string;
  backendWsUrl: string;
  apiToken: string;
};

const STORAGE_KEY = 'jarvis.settings.v1';

// Sensible defaults for a backend running on a developer machine reachable
// from an Android emulator (10.0.2.2 is the emulator's alias for the host).
export const DEFAULT_SETTINGS: JarvisSettings = {
  backendHttpUrl: 'http://10.0.2.2:8000',
  backendWsUrl: 'ws://10.0.2.2:8000/ws',
  apiToken: '',
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
