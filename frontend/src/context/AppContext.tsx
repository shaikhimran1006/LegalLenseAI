import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

interface AppContextValue {
  workspaceId: string;
  setWorkspaceId: (id: string) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [workspaceId, setWorkspaceIdState] = useState<string>(
    () => localStorage.getItem("legallens-workspace") || "public",
  );

  const value = useMemo<AppContextValue>(
    () => ({
      workspaceId,
      setWorkspaceId: (id) => {
        localStorage.setItem("legallens-workspace", id);
        setWorkspaceIdState(id);
      },
    }),
    [workspaceId],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}