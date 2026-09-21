import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

interface Toast {
  id: number;
  message: string;
  tone: "success" | "error" | "info";
}

interface ToastContextValue {
  push: (message: string, tone?: Toast["tone"]) => void;
}

const ToastContext = createContext<ToastContextValue>({ push: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);

  const push = useCallback((message: string, tone: Toast["tone"] = "info") => {
    const id = ++counter.current;
    setToasts((prev) => [...prev, { id, message, tone }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4200);
  }, []);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`animate-fade-up pointer-events-auto rounded-lg border px-4 py-3 text-sm shadow-lift ${
              t.tone === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : t.tone === "error"
                  ? "border-red-200 bg-red-50 text-red-900"
                  : "border-slate-200 bg-white text-slate-800"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}