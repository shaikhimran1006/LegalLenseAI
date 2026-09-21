import { useState } from "react";
import { ArrowLeftRight, ArrowRight } from "lucide-react";
import type { ComparisonResult } from "@/types";
import { ComparisonUI } from "@/components/ComparisonTable";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Feedback";
import { ResponsibleAiNotice } from "@/components/ResponsibleAiNotice";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast";

export default function Compare() {
  const { push } = useToast();
  const [docA, setDocA] = useState("sample_employment");
  const [docB, setDocB] = useState("sample_contract_b");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ result: ComparisonResult; mode: string } | null>(null);

  async function run() {
    if (!docA.trim() || !docB.trim()) return;
    setLoading(true);
    try {
      const res = await api.compare(docA.trim(), docB.trim());
      setResult({ result: res.result, mode: res.mode });
    } catch (e) {
      push(e instanceof ApiError ? e.detail : "Compare failed", "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-900">Compare documents</h1>
        <p className="text-sm text-slate-500">Side-by-side comparison with added, removed, and modified clauses highlighted.</p>
      </div>

      <div className="card mb-6 p-5">
        <div className="flex flex-col items-center gap-4 sm:flex-row">
          <div className="flex-1">
            <label className="label" htmlFor="compare-doc-a">Document A (baseline)</label>
            <input
              id="compare-doc-a"
              value={docA}
              onChange={(e) => { setDocA(e.target.value); setResult(null); }}
              className="input"
              placeholder="e.g. sample_employment"
            />
          </div>
          <div className="mt-6">
            <ArrowRight className="h-5 w-5 text-slate-400" />
          </div>
          <div className="flex-1">
            <label className="label" htmlFor="compare-doc-b">Document B (comparison)</label>
            <input
              id="compare-doc-b"
              value={docB}
              onChange={(e) => { setDocB(e.target.value); setResult(null); }}
              className="input"
              placeholder="e.g. sample_contract_b"
            />
          </div>
          <div className="mt-6">
            <Button onClick={run} disabled={!docA.trim() || !docB.trim() || loading} loading={loading}>
              <ArrowLeftRight className="h-4 w-4" /> Compare
            </Button>
          </div>
        </div>
        <p className="mt-3 text-[11px] text-slate-400">
          Enter document IDs, or compare the sample employment agreement with its revised version.
        </p>
      </div>

      {loading && (
        <div className="grid h-48 place-items-center" role="status" aria-label="Comparing documents"><Spinner /></div>
      )}

      {result && !loading && (
        <div className="animate-fade-up">
          <ComparisonUI result={result.result} />
        </div>
      )}

      {!result && !loading && (
        <div className="mt-8">
          <ResponsibleAiNotice />
        </div>
      )}
    </div>
  );
}