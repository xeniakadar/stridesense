"use client";

import { createContext, useContext, useEffect, useState } from "react";

import { api } from "@/lib/api";

// false until /config confirms demo mode — a public demo briefly showing
// edit buttons that 403 is harmless; the reverse (hiding features from a
// normal install while /config loads) would not be.
const DemoContext = createContext(false);

export function DemoProvider({ children }: { children: React.ReactNode }) {
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    api
      .getConfig()
      .then((config) => setDemoMode(config.demo_mode))
      .catch(() => setDemoMode(false));
  }, []);

  return <DemoContext.Provider value={demoMode}>{children}</DemoContext.Provider>;
}

export function useDemoMode(): boolean {
  return useContext(DemoContext);
}
