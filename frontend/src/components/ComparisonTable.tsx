import { useState } from "react";
import { ArrowLeftRight, ExternalLink, Info } from "lucide-react";
import type { ComparisonResult } from "@/types";
import { EmptyState } from "@/components/ui/Feedback";

function changeBadge(change: string) {
  const tones: Record<string, string> = {
    Added: "bg-emerald-50 text-emerald-700 border-emerald-200",
    Removed: "bg-red-50 text-red-700 border-red-200",
    Modified: "bg-amber-50 text-amber-700 border-amber-200",
    Significant: "bg-red-50 text-red-700 border-red-200",
    Review: "bg-amber-50 text-amber-700 border-amber-200",
    Minor: "bg-slate-100 text-slate-600 border-slate-200",
  };
  return tones[change] ?? tones.Minor;
}

export function ComparisonUI({
  result,
}: {
  result: ComparisonResult;
}) {
  const [filter, setFilter] = useState<string>("all");

  const rows = result.comparison_rows;
  const filtered = filter === "all" ? rows : rows.filter((r) => r.change.toLowerCase() === filter.toLowerCase());
  const changeCounts = rows.reduce(
    (acc, r) => { acc[r.change] = (acc[r.change] ?? 0) + 1; return acc; },
    {} as Record<string, number>,
  );

  return (
    <div className="space-y-5">
      {result.important_changes && result.important_changes.length > 0 && (
        <div className="rounded-xl border border-brand-100 bg-brand-50/60 p-4">
          <p className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-brand-700">
            <Info className="h-3.5 w-3.5" /> Key differences
          </p>
          <ul className="space-y-1 text-sm text-brand-800">
            {result.important_changes.map((c, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-brand-500" />
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {[
            ["all", rows.length, "All"],
            ...Object.entries(changeCounts)
              .sort(([, a], [, b]) => b - a)
              .map(([k, v]) => [k, v, k] as [string, number, string]),
          ].map(([key, count, label]) => (
            <button
              key={key}
              onClick={() => setFilter(key as string)}
              className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors ${
                filter === key ? "border-brand-300 bg-brand-50 text-brand-700" : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
              }`}
            >
              {label} ({count as number})
            </button>
          ))}
        </div>
      </div>

      {rows.length === 0 && (
        <EmptyState
          icon={<ArrowLeftRight className="h-6 w-6" />}
          title="No differences found"
          description="The two documents appear to have equivalent terms."
        />
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-bold uppercase tracking-wide text-slate-500">
              <th className="px-4 py-2.5">Area</th>
              <th className="px-4 py-2.5">A</th>
              <th className="px-4 py-2.5">B</th>
              <th className="px-4 py-2.5">Change</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.map((r, i) => (
              <tr key={i} className="transition-colors hover:bg-slate-50/50">
                <td className="px-4 py-3 font-medium text-slate-700">{r.area}</td>
                <td className="max-w-[200px] px-4 py-3 text-xs text-slate-600">
                  {r.contract_a_value || "—"}
                  {r.a_source_page ? (
                    <span className="ml-1 inline-flex items-center gap-0.5 text-slate-400">
                      <ExternalLink className="h-3 w-3" /> p.{r.a_source_page}
                      {r.a_source_section ? `§${r.a_source_section}` : ""}
                    </span>
                  ) : null}
                </td>
                <td className="max-w-[200px] px-4 py-3 text-xs text-slate-600">
                  {r.contract_b_value || "—"}
                  {r.b_source_page ? (
                    <span className="ml-1 inline-flex items-center gap-0.5 text-slate-400">
                      <ExternalLink className="h-3 w-3" /> p.{r.b_source_page}
                      {r.b_source_section ? `§${r.b_source_section}` : ""}
                    </span>
                  ) : null}
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${changeBadge(r.change)}`}>
                    {r.change}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

    </div>
  );
}