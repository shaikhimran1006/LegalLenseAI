import type { AttentionSummary } from "@/types";
import { cn } from "@/lib/utils";

export function AttentionRadar({
  summary,
  compact,
}: {
  summary: AttentionSummary;
  compact?: boolean;
}) {
  const total = Math.max(1, summary.high + summary.medium + summary.low);
  const segments = [
    { key: "high", value: summary.high, color: "#b42318", label: "HIGH ATTENTION" },
    { key: "medium", value: summary.medium, color: "#b54708", label: "MEDIUM" },
    { key: "low", value: summary.low, color: "#067647", label: "LOW" },
  ];
  const summaryLabel = `${total} clause${total === 1 ? "" : "s"}: ${summary.high} high attention, ${summary.medium} medium, ${summary.low} low.`;

  const segs = segments
    .filter((s) => s.value > 0)
    .sort((a, b) => a.value - b.value);
  let cumulative = 0;
  const pieces = segs.map((s) => {
    const start = cumulative / total;
    cumulative += s.value;
    const end = cumulative / total;
    return { ...s, start, end };
  });
  const angle = (fraction: number) => fraction * 360 - 90;
  const arcPath = (start: number, end: number) => {
    const large = end - start > 0.5 ? 1 : 0;
    const cx = 50;
    const cy = 50;
    const r = 42;
    const startAngle = (angle(start) * Math.PI) / 180;
    const endAngle = (angle(end) * Math.PI) / 180;
    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };

  return (
    <div className={cn("flex items-center gap-5", compact && "gap-4")}>
      <span className="sr-only" role="img" aria-label={summaryLabel} />
      <div className={cn("relative", compact ? "h-24 w-24" : "h-32 w-32")}>
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-0" aria-hidden="true" focusable="false">
          {pieces.map((p) => (
            <path key={p.key} d={arcPath(p.start, p.end)} fill="none" stroke={p.color} strokeWidth={14} strokeLinecap="butt" />
          ))}
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <div className="text-center">
            <p className="text-lg font-bold text-slate-900">{total}</p>
            <p className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">clauses</p>
          </div>
        </div>
      </div>
      <div className="space-y-2">
        {segments.map((s) => (
          <div key={s.key} className="flex items-center gap-2 text-xs">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
            <span className="w-24 font-medium text-slate-600">{s.label}</span>
            <span className="font-bold tabular-nums text-slate-900">{s.value}</span>
            <span className="text-slate-400">
              {total > 0 && !(s.value === 0)
                ? `${Math.round((s.value / total) * 100)}%`
                : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}