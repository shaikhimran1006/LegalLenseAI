import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { RefreshCw, FileText, MessageSquare, Target, Eye, AlertCircle } from "lucide-react";
import type { Clause, DocumentSummary } from "@/types";
import type { ClausesResponse } from "@/types";
import type { ViewerPage } from "@/components/DocumentViewer";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { Spinner, EmptyState } from "@/components/ui/Feedback";
import { Badge } from "@/components/ui/Badge";
import { AttentionRadar } from "@/components/AttentionRadar";
import { ClauseCard } from "@/components/ClauseCard";
import { ClauseDrawer } from "@/components/ClauseDrawer";
import { DocumentViewer } from "@/components/DocumentViewer";
import { ChatPanel } from "@/components/ChatPanel";
import { ActionPackPanel } from "@/components/ActionPackPanel";
import { cn } from "@/lib/utils";

export default function Analyze() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const id = params.get("id");
  const { push } = useToast();
  const [doc, setDoc] = useState<DocumentSummary | null>(null);
  const [clausesRes, setClausesRes] = useState<ClausesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);
  const [selectedClause, setSelectedClause] = useState<Clause | null>(null);
  const [viewerPage, setViewerPage] = useState<number | undefined>();
  const [viewerHighlight, setViewerHighlight] = useState<string | undefined>();
  const [viewerPages, setViewerPages] = useState<ViewerPage[]>([]);
  const [rightTab, setRightTab] = useState<"chat" | "source" | "actions">("chat");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    if (!id) { navigate("/documents"); return; }
    setLoading(true);
    let cancelled = false;

    (async () => {
      try {
        const d = await api.document(id).catch(() => null);
        if (cancelled) return;

        if (d && d.status === "created") {
          try {
            await api.analyze(id);
          } catch {
            // analysis may already be running or triggered elsewhere; ignore
          }
          if (cancelled) return;
        }

        const cr = await api.clauses(id);
        if (cancelled) return;
        setDoc(d);
        setClausesRes(cr);
      } catch (e) {
        push(e instanceof ApiError ? e.detail : "Failed to load analysis", "error");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [id]);

  // Build viewer pages from clause evidence
  useEffect(() => {
    if (!clausesRes) return;
    const seen = new Map<number, string[]>();
    clausesRes.clauses.forEach((c) => {
      const existing = seen.get(c.source_page) ?? [];
      existing.push(`[§${c.source_section ?? "?"}] ${c.evidence}`);
      seen.set(c.source_page, existing);
    });
    const pages: ViewerPage[] = [...seen.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([page, texts]) => ({ page, text: texts.join("\n\n") }));
    setViewerPages(pages);
  }, [clausesRes]);

  const clauses = clausesRes?.clauses ?? [];

  const filtered = (() => {
    if (filter === "all") return clauses;
    if (filter === "high") return clauses.filter((c) => c.importance === "HIGH");
    if (filter === "medium") return clauses.filter((c) => c.importance === "MEDIUM");
    return clauses.filter((c) => c.importance === "LOW");
  })();

  async function rerun() {
    if (!id) return;
    setRerunning(true);
    try {
      await api.analyze(id);
      const cr = await api.clauses(id);
      setClausesRes(cr);
      push("Analysis refreshed", "success");
    } catch (e) {
      push(e instanceof ApiError ? e.detail : "Analysis failed", "error");
    } finally {
      setRerunning(false);
    }
  }

  function openClause(clause: Clause) {
    setSelectedClause(clause);
    setRightTab("source");
    setViewerPage(clause.source_page);
    setViewerHighlight(clause.evidence.slice(0, 80));
  }

  function handleAsk(question: string) {
    setPendingQuestion(question);
    setRightTab("chat");
  }

  function handleLocate(page: number, evidence: string) {
    setRightTab("source");
    setViewerPage(page);
    setViewerHighlight(evidence.slice(0, 80));
  }

  if (loading) {
    return (
      <div className="grid h-[60vh] place-items-center">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (!clausesRes || !id) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <EmptyState
          icon={<AlertCircle className="h-7 w-7 text-amber-500" />}
          title="No document selected"
          description="Go to Documents to select a document, or try the sample employment agreement."
          action={<Button onClick={() => navigate("/documents")}>Browse documents</Button>}
        />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-56px)] flex-col lg:flex-row">
      {/* LEFT: Analysis + clauses */}
      <div className="flex w-full flex-col overflow-y-auto border-r border-slate-200 bg-slate-50 lg:w-[55%]">
        <div className="border-b border-slate-200 bg-white px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <h1 className="truncate text-base font-bold text-slate-900">
                {doc?.filename ?? id}
              </h1>
              <p className="text-xs text-slate-500">
                {clauses.length} clauses · attention {clausesRes.attention_summary.high}/{clausesRes.attention_summary.medium}/{clausesRes.attention_summary.low}
                {doc?.mode === "demo" && (
                  <Badge tone="brand" className="ml-2">Sample</Badge>
                )}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button variant="secondary" size="sm" onClick={rerun} loading={rerunning}>
                <RefreshCw className="h-3.5 w-3.5" /> Re-run
              </Button>
              <Button variant="secondary" size="sm" onClick={() => navigate(`/action-pack?id=${id}`)}>
                <Target className="h-3.5 w-3.5" /> Action Pack
              </Button>
              <Button variant="secondary" size="sm" onClick={() => navigate("/documents")}>
                Back
              </Button>
            </div>
          </div>
        </div>

        {/* Attention radar */}
        <div className="border-b border-slate-200 bg-white px-6 py-5">
          <h2 className="mb-3 text-xs font-bold uppercase tracking-wide text-slate-400">Attention Distribution</h2>
          <AttentionRadar summary={clausesRes.attention_summary} />
        </div>

        {/* Clause list */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-xs font-bold uppercase tracking-wide text-slate-400">
              Clauses ({clauses.length})
            </h2>
            <div className="flex gap-1">
              {[
                ["all", "All"],
                ["high", "High"],
                ["medium", "Medium"],
                ["low", "Low"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setFilter(key)}
                  aria-pressed={filter === key}
                  className={cn(
                    "rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors",
                    filter === key
                      ? "bg-brand-100 text-brand-700"
                      : "bg-white text-slate-500 hover:bg-slate-100",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-3">
            {filtered.map((c, i) => (
              <ClauseCard
                key={`${c.title}-${c.source_page}-${i}`}
                clause={c}
                rank={i + 1}
                onOpen={openClause}
                active={selectedClause?.title === c.title && selectedClause?.source_page === c.source_page}
              />
            ))}
            {filtered.length === 0 && (
              <EmptyState
                icon={<FileText className="h-6 w-6" />}
                title="No clauses match filter"
                description="Try selecting a different attention level."
              />
            )}
          </div>
        </div>
      </div>

      {/* RIGHT: Chat + Source viewer + Actions */}
      <div className="flex w-full flex-1 flex-col bg-white lg:w-[45%]">
        {/* Right tabs */}
        <div className="flex border-b border-slate-200" role="tablist" aria-label="Document views">
          {[
            { key: "chat" as const, icon: MessageSquare, label: "Chat" },
            { key: "source" as const, icon: Eye, label: "Source" },
            { key: "actions" as const, icon: Target, label: "Actions" },
          ].map((tab) => (
            <button
              key={tab.key}
              role="tab"
              aria-selected={rightTab === tab.key}
              aria-controls={`right-panel-${tab.key}`}
              id={`tab-${tab.key}`}
              onClick={() => setRightTab(tab.key)}
              className={cn(
                "flex flex-1 items-center justify-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors",
                rightTab === tab.key
                  ? "border-brand-500 text-brand-700 bg-brand-50/50"
                  : "border-transparent text-slate-500 hover:text-slate-700",
              )}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Right content */}
        <div className="flex-1 overflow-hidden">
          {rightTab === "chat" && (
            <div id="right-panel-chat" role="tabpanel" aria-labelledby="tab-chat" className="h-full">
              <ChatPanel
                documentId={id}
                pendingQuestion={pendingQuestion}
                onConsumed={() => setPendingQuestion(null)}
              />
            </div>
          )}
          {rightTab === "source" && (
            <div id="right-panel-source" role="tabpanel" aria-labelledby="tab-source" className="h-full overflow-y-auto">
              <DocumentViewer
                pages={viewerPages}
                highlightText={viewerHighlight}
                jumpPage={viewerPage}
                filename={doc?.filename}
              />
            </div>
          )}
          {rightTab === "actions" && (
            <div id="right-panel-actions" role="tabpanel" aria-labelledby="tab-actions" className="h-full overflow-y-auto px-4 py-4">
              <ActionPackPanel documentId={id} />
            </div>
          )}
        </div>
      </div>

      {/* Clause Drawer */}
      <ClauseDrawer
        clause={selectedClause}
        onClose={() => setSelectedClause(null)}
        documentId={id}
        onAsk={handleAsk}
        onLocate={handleLocate}
      />
    </div>
  );
}