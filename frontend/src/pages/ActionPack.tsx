import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Target, FolderOpen } from "lucide-react";
import type { DocumentSummary } from "@/types";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { Spinner, EmptyState } from "@/components/ui/Feedback";
import { ResponsibleAiNotice } from "@/components/ResponsibleAiNotice";
import { ActionPackContent } from "@/components/ActionPackPanel";
import type { ActionPackResponse } from "@/types";

export default function ActionPack() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const paramId = params.get("id");
  const { push } = useToast();

  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [resp, setResp] = useState<ActionPackResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  // Load available documents (uploaded + sample, same as Documents page)
  useEffect(() => {
    let cancelled = false;
    setLoadingDocs(true);
    setLoadError(false);
    (async () => {
      try {
        const [userDocs, samples] = await Promise.all([api.documents(), api.sampleDocuments()]);
        if (cancelled) return;
        const seen = new Map<string, DocumentSummary>();
        for (const d of userDocs) {
          if (d.status !== "analyzed") continue;
          const id = d.id;
          if (!seen.has(id)) seen.set(id, { ...d, is_sample: d.mode === "demo" });
        }
        for (const s of samples.items) {
          const id = s.id;
          if (!seen.has(id)) seen.set(id, { ...s, is_sample: true });
        }
        setDocs([...seen.values()]);
      } catch {
        if (!cancelled) setLoadError(true);
      } finally {
        if (!cancelled) setLoadingDocs(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Auto-select: prefer URL ?id= param when navigating from another page,
  // fall back to first available document.
  useEffect(() => {
    if (loadingDocs || !docs.length) return;
    const preferred = paramId ?? docs[0].id;
    const available = docs.some((d) => d.id === preferred) ? preferred : docs[0].id;
    setSelectedId(available);
  }, [paramId, loadingDocs, docs]);

  const sorted = [...docs].sort((a, b) => (a.is_sample ? 1 : 0) - (b.is_sample ? 1 : 0));

  function handleSelect(id: string) {
    setSelectedId(id);
    setResp(null);
    setError(null);
  }

  async function generate() {
    if (!selectedId || generating) return;
    setGenerating(true);
    setError(null);
    setResp(null);
    try {
      const r = await api.actionPack(selectedId);
      setResp(r);
    } catch (e) {
      const msg = e instanceof ApiError
        ? (e.status === 404
          ? "Selected document could not be found. It may have been removed."
          : e.status === 409
            ? "This document has not been analyzed yet. Run the analysis first, then generate its Action Pack."
            : "Could not generate the Action Pack. Please try again.")
        : "Could not generate the Action Pack. Please try again.";
      setError(msg);
      push(msg, "error");
    } finally {
      setGenerating(false);
    }
  }

  // Loading documents state
  if (loadingDocs) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-slate-900">Action Pack</h1>
          <p className="text-sm text-slate-500">Required actions prioritized by urgency and impact.</p>
        </div>
        <div className="grid h-64 place-items-center text-sm text-slate-500">
          <div className="flex items-center gap-2"><Spinner /> Loading documents&hellip;</div>
        </div>
      </div>
    );
  }

  // Load error state
  if (loadError) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-slate-900">Action Pack</h1>
        </div>
        <EmptyState
          icon={<FolderOpen className="h-7 w-7 text-red-500" />}
          title="Could not load documents"
          description="Something went wrong while fetching your documents."
          action={
            <Button variant="secondary" onClick={() => window.location.reload()}>Retry</Button>
          }
        />
      </div>
    );
  }

  // Empty state
  if (!sorted.length) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-slate-900">Action Pack</h1>
        </div>
        <EmptyState
          icon={<FolderOpen className="h-7 w-7" />}
          title="No documents available"
          description="Upload and analyze a document first to generate an Action Pack."
          action={<Button onClick={() => navigate("/documents")}>Upload document</Button>}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-900">Action Pack</h1>
        <p className="text-sm text-slate-500">
          Required actions prioritized by urgency and impact.
        </p>
      </div>

      <div className="card mb-6 p-5">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="label">Document</label>
            <select
              className="input"
              value={selectedId ?? ""}
              onChange={(e) => handleSelect(e.target.value)}
            >
              {sorted.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename}{d.is_sample ? " (Sample)" : ""}
                </option>
              ))}
            </select>
          </div>
          <Button
            onClick={generate}
            loading={generating}
            disabled={!selectedId || generating}
          >
            <Target className="h-4 w-4" /> Generate Action Pack
          </Button>
        </div>
      </div>

      {generating && (
        <div className="grid h-64 place-items-center text-sm text-slate-500">
          <div className="flex items-center gap-2">
            <Spinner />
            Generating Action Pack&hellip;
          </div>
        </div>
      )}

      {!generating && error && (
        <div className="card border-red-200 bg-red-50 p-5 text-center">
          <p className="text-sm text-red-700">{error}</p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={generate}>
            Try again
          </Button>
        </div>
      )}

      {!generating && !error && resp && (
        <div className="animate-fade-up">
          <ActionPackContent resp={resp} />
        </div>
      )}

      {!generating && !error && !resp && (
        <div className="mt-8">
          <ResponsibleAiNotice />
        </div>
      )}
    </div>
  );
}
