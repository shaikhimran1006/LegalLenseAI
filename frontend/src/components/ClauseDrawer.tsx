import { useState } from "react";
import { ScrollText, HelpCircle, ArrowRight, FileText } from "lucide-react";
import type { Clause, ExplainResult } from "@/types";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { Drawer } from "@/components/ui/Overlay";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Feedback";
import { AttentionBadge, ConfidencePill } from "@/components/AttentionBadge";
import { categoryLabels } from "@/lib/utils";

export function ClauseDrawer({
  clause,
  onClose,
  documentId,
  onAsk,
  onLocate,
}: {
  clause: Clause | null;
  onClose: () => void;
  documentId: string;
  onAsk: (question: string) => void;
  onLocate: (page: number, evidence: string) => void;
}) {
  const { push } = useToast();
  const [explainRes, setExplainRes] = useState<ExplainResult | null>(null);
  const [loadingExplain, setLoadingExplain] = useState(false);
  const [throwaway, setThrowaway] = useState("");

  async function runExplain() {
    if (!clause) return;
    setLoadingExplain(true);
    try {
      const res = await api.explain(documentId, clause.title);
      setExplainRes(res);
    } catch (e) {
      push(e instanceof ApiError ? e.detail : "Explain failed", "error");
    } finally {
      setLoadingExplain(false);
    }
  }

  const explained = (explainRes?.clause ?? clause) as Clause;

  return (
    <Drawer
      open={!!clause}
      onClose={() => {
        setExplainRes(null);
        onClose();
      }}
      title={clause?.title ?? ""}
      subtitle={
        clause ? (
          <span className="text-slate-500">
            {categoryLabels[clause.category] ?? clause.category} · Page {clause.source_page}
            {clause.source_section ? ` · §${clause.source_section}` : ""}
          </span>
        ) : undefined
      }
      footer={
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={runExplain}
            loading={loadingExplain}
            className="flex-1"
          >
            <HelpCircle className="h-4 w-4" /> Explain in plain language
          </Button>
          <Button
            className="flex-1"
            onClick={() => clause && onLocate(clause.source_page, clause.evidence)}
          >
            <FileText className="h-4 w-4" /> View source
          </Button>
        </div>
      }
    >
      {clause ? (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <AttentionBadge importance={explained.importance} />
            <ConfidencePill confidence={explained.confidence} />
          </div>

          {explainRes && (
            <div className="rounded-xl border border-brand-100 bg-brand-50/60 p-4 animate-fade-up">
              <p className="mb-1 text-xs font-bold uppercase tracking-wide text-brand-700">
                Plain-language meaning
              </p>
              <p className="text-sm leading-relaxed text-slate-800">{explained.plain_language}</p>
            </div>
          )}

          {!explainRes && (
            <section>
              <h4 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Plain meaning</h4>
              <p className="text-sm leading-relaxed text-slate-800">{explained.plain_language}</p>
            </section>
          )}

          <section>
            <h4 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Why it matters</h4>
            <p className="text-sm leading-relaxed text-slate-800">{explained.why_it_matters}</p>
          </section>

          <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-slate-500">
              <ScrollText className="h-3.5 w-3.5" /> Source evidence
            </div>
            <blockquote className="text-sm italic leading-relaxed text-slate-700">
              “{explained.evidence}”
            </blockquote>
            <p className="mt-2 text-[11px] text-slate-400">
              Page {explained.source_page}
              {explained.source_section ? `, section ${explained.source_section}` : ""} · quoted from the document
            </p>
          </section>

          <section>
            <p className="mb-2 text-sm font-medium text-slate-700">Question not answered? Ask about this clause.</p>
            <label htmlFor="clause-ask-input" className="sr-only">
              Ask a question about this clause
            </label>
            <div className="flex gap-2">
              <input
                id="clause-ask-input"
                value={throwaway}
                onChange={(e) => setThrowaway(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && throwaway.trim()) {
                    onAsk(throwaway.trim());
                    setThrowaway("");
                  }
                }}
                placeholder="e.g. What happens if I resign early?"
                className="input"
              />
              <Button
                size="md"
                disabled={!throwaway.trim()}
                aria-label="Ask about this clause"
                onClick={() => {
                  onAsk(throwaway.trim());
                  setThrowaway("");
                }}
              >
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </section>

          <p className="rounded-lg bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-500">
            This explanation is generated by AI and grounded in the quoted source text. Some information
            appears in plain language and does not constitute legal advice.
          </p>
        </div>
      ) : (
        <div className="grid h-full place-items-center">
          <Spinner />
        </div>
      )}
    </Drawer>
  );
}