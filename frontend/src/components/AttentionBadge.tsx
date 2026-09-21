import { importanceTone } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import type { Importance } from "@/types";

export function AttentionBadge({ importance }: { importance: Importance }) {
  const tone = importanceTone(importance);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-bold tracking-wide ${tone.bg} ${tone.text} ${tone.border}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${tone.dot} ${importance === "LOW" ? "" : "animate-pulse"}`} />
      {tone.label}
    </span>
  );
}

export function ConfidencePill({ confidence }: { confidence: string }) {
  const cls =
    confidence === "HIGH"
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : confidence === "MEDIUM"
        ? "text-amber-700 bg-amber-50 border-amber-200"
        : "text-slate-600 bg-slate-100 border-slate-200";
  return <Badge className={"normal-case tracking-normal " + cls}>grounded: {confidence.toLowerCase()}</Badge>;
}