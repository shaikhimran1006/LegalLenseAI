import { ShieldCheck, AlertTriangle, BookOpen } from "lucide-react";

export function ResponsibleAiNotice({
  variant = "full",
}: {
  variant?: "full" | "compact" | "inline";
}) {
  if (variant === "compact") {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-brand-100 bg-brand-50/60 px-3 py-2 text-[11px] text-brand-700">
        <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
        <p className="leading-relaxed">
          <strong>Evidence-backed:</strong> All analysis cites original document text. AI explanations are not legal advice.
        </p>
      </div>
    );
  }

  if (variant === "inline") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
        <ShieldCheck className="h-3 w-3" />
        grounded · not legal advice
      </span>
    );
  }

  return (
    <div className="rounded-xl border border-brand-100 bg-white p-5 shadow-card">
      <div className="flex items-start gap-4">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div className="space-y-3 text-sm leading-relaxed text-slate-700">
          <h4 className="text-base font-bold text-slate-900">Responsible AI Notice</h4>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex items-start gap-2">
              <BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />
              <div>
                <p className="font-semibold text-slate-800">Evidence-backed answers</p>
                <p className="text-xs text-slate-500">
                  Every clause, ranking, and answer cites the exact page, section, and quoted text from the original document.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
              <div>
                <p className="font-semibold text-slate-800">Not legal advice</p>
                <p className="text-xs text-slate-500">
                  AI explanations are informational only and do not constitute legal advice. Always consult a qualified lawyer.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}