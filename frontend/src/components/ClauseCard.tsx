import { FileText, Zap } from "lucide-react";
import type { Clause } from "@/types";
import { AttentionBadge, ConfidencePill } from "@/components/AttentionBadge";
import { categoryLabels } from "@/lib/utils";
import { cn } from "@/lib/utils";

export function ClauseCard({
  clause,
  onOpen,
  active,
  rank,
}: {
  clause: Clause;
  onOpen: (c: Clause) => void;
  active?: boolean;
  rank?: number;
}) {
  return (
    <button
      onClick={() => onOpen(clause)}
      className={cn(
        "group w-full rounded-xl border bg-white p-4 text-left transition-all hover:shadow-lift",
        active ? "border-brand-300 ring-2 ring-brand-100" : "border-slate-200",
        clause.importance === "HIGH"
          ? "border-l-4 border-l-red-500"
          : clause.importance === "MEDIUM"
            ? "border-l-4 border-l-amber-400"
            : "border-l-4 border-l-emerald-400",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {rank !== undefined && (
              <span className="text-lg font-bold text-slate-300">#{rank}</span>
            )}
            <h4 className="text-sm font-semibold text-slate-900">{clause.title}</h4>
          </div>
          <p className="mt-0.5 text-xs text-slate-500">
            {categoryLabels[clause.category] ?? clause.category} · Page {clause.source_page}
            {clause.source_section ? ` · §${clause.source_section}` : ""}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <AttentionBadge importance={clause.importance} />
          <ConfidencePill confidence={clause.confidence} />
        </div>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{clause.plain_language}</p>
      <div className="mt-3 flex items-center gap-3 text-[11px] font-medium text-brand-600">
        <span className="inline-flex items-center gap-1">
          <FileText className="h-3.5 w-3.5" /> Evidence
        </span>
        <span className="inline-flex items-center gap-1">
          <Zap className="h-3.5 w-3.5" /> Explain
        </span>
        <span className="ml-auto text-slate-300 transition-colors group-hover:text-brand-400">View details →</span>
      </div>
    </button>
  );
}