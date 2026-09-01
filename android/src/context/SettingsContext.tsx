import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { DEFAULT_SETTINGS, JarvisSettings, loadSettings, saveSettings } from '../config/settings';

type SettingsContextValue = {
  settings: JarvisSettings;
  loaded: boolean;
  update: (next: JarvisSettings) => Promise<void>;
};

const SettingsContext = createContext<SettingsContextValue | undefined>(undefined);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<JarvisSettings>(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    loadSettings().then((s) => {
      setSettings(s);
      setLoaded(true);
    });
  }, []);

  const update = useCallback(async (next: JarvisSettings) => {
    setSettings(next);
    await saveSettings(next);
  }, []);

  return (
    <SettingsContext.Provider value={{ settings, loaded, update }}>{children}</SettingsContext.Provider>
  );
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within a SettingsProvider');
  return ctx;
}
