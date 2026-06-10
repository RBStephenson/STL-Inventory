import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { api, AppSettings } from "../api/client";

// Mirrors the backend DEFAULTS in routers/settings.py — used until the
// server responds, so gated UI stays hidden during the initial fetch.
const DEFAULTS: AppSettings = {
  painting_guides_enabled: false,
};

interface AppSettingsContextValue {
  settings: AppSettings;
  update: (patch: Partial<AppSettings>) => Promise<void>;
}

const AppSettingsContext = createContext<AppSettingsContextValue>({
  settings: DEFAULTS,
  update: async () => {},
});

export function AppSettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(DEFAULTS);

  useEffect(() => {
    api.settings.get().then(setSettings).catch(() => {});
  }, []);

  const update = async (patch: Partial<AppSettings>) => {
    setSettings(await api.settings.update(patch));
  };

  return (
    <AppSettingsContext.Provider value={{ settings, update }}>
      {children}
    </AppSettingsContext.Provider>
  );
}

export const useAppSettings = () => useContext(AppSettingsContext);
