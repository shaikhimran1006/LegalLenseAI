import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, FileText, Clock, FolderOpen, ExternalLink } from "lucide-react";
import type { DocumentSummary } from "@/types";
import { api, SAMPLE_DOCUMENT_ID } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { DocumentUpload } from "@/components/DocumentUpload";
import { EmptyState, Spinner } from "@/components/ui/Feedback";
import { Badge } from "@/components/ui/Badge";
import { formatDate, formatBytes, cn } from "@/lib/utils";

export default function Documents() {
  const navigate = useNavigate();
  const { push } = useToast();
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);

  async function loadDocs() {
    setLoading(true);
    try {
      const [userDocs, samples] = await Promise.all([api.documents(), api.sampleDocuments()]);
      const seen = new Map<string, DocumentSummary>();
      for (const d of userDocs) {
        const id = d.id as string;
        if (!seen.has(id)) seen.set(id, { ...d, is_sample: d.mode === "demo" });
      }
      for (const s of samples.items) {
        const id = s.id as string;
        if (!seen.has(id)) seen.set(id, { ...s, is_sample: true });
      }
      setDocs([...seen.values()]);
    } catch (e) {
      push("Failed to load documents", "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadDocs(); }, []);

  function handleUploaded(d: DocumentSummary) {
    setDocs((prev) => [d, ...prev]);
    setShowUpload(false);
  }

  const sorted = [...docs].sort((a, b) => (b.is_sample ? 1 : 0) - (a.is_sample ? 1 : 0));

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Documents</h1>
          <p className="text-sm text-slate-500">Upload your own document or start with the sample</p>
        </div>
        <Button onClick={() => setShowUpload(true)}>
          <Upload className="h-4 w-4" /> Upload document
        </Button>
      </div>

      {showUpload && (
        <div className="mb-6 card p-5 animate-fade-up">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-800">Upload a document</h2>
            <button onClick={() => setShowUpload(false)} className="text-xs text-slate-400 hover:text-slate-600">✕ close</button>
          </div>
          <DocumentUpload onUploaded={handleUploaded} />
        </div>
      )}

      {loading && (
        <div className="grid h-64 place-items-center">
          <Spinner />
        </div>
      )}

      {!loading && sorted.length === 0 && (
        <EmptyState
          icon={<FolderOpen className="h-7 w-7" />}
          title="No documents yet"
          description="Upload a PDF, DOCX, or TXT file to get started, or explore the sample employment agreement."
          action={
            <div className="flex gap-2">
              <Button onClick={() => setShowUpload(true)}>Upload first</Button>
              <Button variant="secondary" onClick={() => navigate(`/analyze?id=${SAMPLE_DOCUMENT_ID}`)}>Try with Sample Document</Button>
            </div>
          }
        />
      )}

      {!loading && sorted.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((d) => (
            <button
              key={d.id}
              type="button"
              className={cn(
                "card group w-full cursor-pointer p-5 text-left transition-all hover:shadow-lift focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                d.is_sample && "ring-1 ring-brand-100 bg-brand-50/30",
              )}
              onClick={() => navigate(`/analyze?id=${d.id}`)}
            >
              <div className="flex items-start gap-3">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-100 text-brand-500">
                  <FileText className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-800" title={d.filename}>{d.filename}</p>
                  <p className="text-[11px] text-slate-400">
                    {d.page_count} pages · {formatBytes(d.size)}
                    {d.context ? ` · ${d.context}` : ""}
                  </p>
                </div>
                {d.is_sample && (
                  <Badge tone="brand" className="shrink-0">Sample</Badge>
                )}
              </div>
              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                  <Clock className="h-3 w-3" />
                  {d.is_sample ? "Sample document" : formatDate(d.created_at ?? "")}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-brand-600 opacity-0 transition-opacity group-hover:opacity-100">
                    Analyze <ExternalLink className="ml-1 inline h-3 w-3" />
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}