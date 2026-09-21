import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Badge({
  className,
  tone = "slate",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: "slate" | "red" | "amber" | "emerald" | "brand" }) {
  const tones = {
    slate: "bg-slate-100 text-slate-600 border-slate-200",
    red: "bg-red-50 text-red-700 border-red-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
    brand: "bg-brand-50 text-brand-700 border-brand-200",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}