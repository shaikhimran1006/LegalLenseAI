import { useEffect, useRef, useState } from "react";
import { Send, ShieldCheck, Loader2 } from "lucide-react";
import type { AskResponse, ContextRankingResponse } from "@/types";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { Badge } from "@/components/ui/Badge";

interface Message {
  role: "user";
  text: string;
  ts: number;
}

interface AssistantMessage {
  role: "assistant";
  data: AskResponse;
  ranked: ContextRankingResponse["ranked_clauses"];
  ts: number;
}

type ChatMessage = Message | AssistantMessage;

const SEED_QUESTIONS = [
  "What happens if I resign after 8 months?",
  "What is the notice period?",
  "Are there any repayment obligations?",
  "What happens during probation?",
  "What are my confidentiality obligations?",
];

export function ChatPanel({
  documentId,
  pendingQuestion,
  onConsumed,
}: {
  documentId: string;
  pendingQuestion?: string | null;
  onConsumed?: () => void;
}) {
  const { push } = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const listEnd = useRef<HTMLDivElement>(null);
  const consumedRef = useRef(false);

  const askRef = useRef(ask);
  askRef.current = ask;

  useEffect(() => {
    if (!pendingQuestion) {
      consumedRef.current = false;
      return;
    }
    if (consumedRef.current) return;
    consumedRef.current = true;
    onConsumed?.();
    askRef.current(pendingQuestion);
  }, [pendingQuestion, onConsumed]);

  async function ask(question: string) {
    if (!question.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text: question, ts: Date.now() }]);
    setInput("");
    setLoading(true);
    listEnd.current?.scrollIntoView({ behavior: "smooth" });
    try {
      const [answer, ranking] = await Promise.all([
        api.ask(documentId, question),
        api.contextRanking(documentId, question).catch(() => null),
      ]);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", data: answer, ranked: ranking?.ranked_clauses ?? [], ts: Date.now() },
      ]);
      listEnd.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      push(e instanceof ApiError ? e.detail : "Ask failed", "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-card">
      <div className="flex-1 overflow-y-auto px-4 py-4" role="log" aria-live="polite">
        {messages.length === 0 && (
          <div className="grid h-full place-items-center text-center text-slate-400">
            <div>
              <ShieldCheck className="mx-auto mb-3 h-8 w-8 text-brand-200" />
              <p className="text-sm font-medium">Ask a question grounded in this document</p>
              <p className="mt-1 text-xs text-slate-400">All answers cite source text</p>
              <div className="mt-4 grid grid-cols-1 gap-2 text-left sm:grid-cols-2">
                {SEED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => ask(q)}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-left text-xs text-slate-600 transition-colors hover:border-brand-300 hover:bg-brand-50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
        <div className="space-y-4">
          {messages.map((m, i) => {
            if (m.role === "user") {
              return (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[85%] rounded-xl bg-brand-600 px-4 py-3 text-sm text-white">
                    {m.text}
                  </div>
                </div>
              );
            }
            const d = m.data;
            return (
              <div key={i} className="flex justify-start">
                <div className="max-w-[85%] rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-800">
                  <p className="mb-2 text-sm leading-relaxed">{d.answer.answer}</p>

                  {d.answer.insufficient && (
                    <Badge tone="amber">Insufficient information in document</Badge>
                  )}

                  {d.answer.evidence.length > 0 && (
                    <div className="mt-2 space-y-2 rounded-md border border-dashed border-amber-300 bg-amber-50/60 px-3 py-2">
                      <p className="text-[10px] font-bold uppercase tracking-wide text-amber-800">Cited source</p>
                      {d.answer.evidence.map((ev, j) => (
                        <div key={j} className="text-xs text-amber-700">
                          <p className="italic">“{ev.quote}”</p>
                          <p className="mt-0.5 text-[10px] text-amber-500">
                            Page {ev.page}{ev.section ? `, section ${ev.section}` : ""}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}

                  {m.ranked.length > 0 && (
                    <div className="mt-3 space-y-1 border-t border-slate-100 pt-3">
                      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">
                        Related clauses
                      </p>
                      {m.ranked.slice(0, 3).map((r, ri) => (
                        <div key={ri} className="flex items-start gap-2 text-xs text-slate-600">
                          <span className="font-bold text-slate-300">#{ri + 1}</span>
                          <span className="font-medium text-slate-700">{r.clause.title}</span>
                          <span className="text-slate-400">p.{r.clause.source_page}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          {loading && (
            <div className="flex justify-start" role="status" aria-label="Generating answer">
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              </div>
            </div>
          )}
          <div ref={listEnd} />
        </div>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
        className="flex gap-2 border-t border-slate-200 px-4 py-3"
      >
        <label htmlFor="chat-input" className="sr-only">
          Ask a question about this document
        </label>
        <input
          id="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask any question about this document"
          className="input flex-1"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="rounded-lg bg-brand-600 px-3 py-2 text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
          aria-label="Ask"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}