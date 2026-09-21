import { cn } from "@/lib/utils";

export function Logo({ className, mark }: { className?: string; mark?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <svg viewBox="0 0 32 32" className="h-8 w-8 shrink-0" aria-hidden>
        <rect width="32" height="32" rx="7" fill="#22314f" />
        <path d="M10 9.5h7a4.5 4.5 0 0 1 4.5 4.5v2.2l2 1.6v-3.8A6.5 6.5 0 0 0 17 7.5h-7a1.5 1.5 0 1 0 0 3z" fill="#eef2fb" />
        <path d="M8 22.5A4.5 4.5 0 0 1 12.5 18h6.5a1 1 0 0 1 .62 1.78L16.1 22l3.52 2.72A1 1 0 0 1 19 26.5h-6.5A4.5 4.5 0 0 1 8 22z" fill="#b9c9ea" />
        <circle cx="21.5" cy="22.5" r="2.6" fill="#415da8" stroke="#b9c9ea" strokeWidth="1" />
        <path d="M23 22.5l1.2 1.2" stroke="#b9c9ea" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      <div className="leading-tight">
        <p className="text-[15px] font-700 font-bold tracking-tight text-slate-900">{mark ?? "LegalLens"}</p>
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-brand-500">AI</p>
      </div>
    </div>
  );
}