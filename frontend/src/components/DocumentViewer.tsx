import { useEffect, useMemo, useRef } from "react";
import { FileText } from "lucide-react";
import { EmptyState } from "@/components/ui/Feedback";

export interface ViewerPage {
  page: number;
  text: string;
}

function highlight(text: string, needle?: string): React.ReactNode[] {
  if (!needle) return [text];
  const lower = text.toLowerCase();
  const n = needle.toLowerCase();
  const parts: React.ReactNode[] = [];
  let i = 0;
  let key = 0;
  let idx = lower.indexOf(n, i);
  while (idx >= 0) {
    if (idx > i) parts.push(<span key={key++}>{text.slice(i, idx)}</span>);
    parts.push(
      <mark key={key++} className="rounded-sm bg-amber-200 px-0.5 text-slate-900">
        {text.slice(idx, idx + n.length)}
      </mark>,
    );
    i = idx + n.length;
    idx = lower.indexOf(n, i);
  }
  if (i < text.length) parts.push(<span key={key++}>{text.slice(i)}</span>);
  return parts;
}

export function DocumentViewer({
  pages,
  highlightText,
  jumpPage,
  filename,
}: {
  pages: ViewerPage[];
  highlightText?: string;
  jumpPage?: number;
  filename?: string;
}) {
  const targetRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (jumpPage && targetRef.current) {
      targetRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [jumpPage]);

  const visible = useMemo(() => [...pages].sort((a, b) => a.page - b.page), [pages]);

  if (visible.length === 0) {
    return (
      <div className="grid h-full place-items-center">
        <EmptyState
          icon={<FileText className="h-7 w-7" />}
          title="No source text"
          description="The document does not contain extractable page text."
        />
      </div>
    );
  }

  return (
    <div className="space-y-4 px-4 py-4">
      {filename && (
        <p className="truncate text-xs font-semibold uppercase tracking-wide text-slate-400">{filename}</p>
      )}
      {visible.map((p) => (
        <div
          key={p.page}
          ref={jumpPage === p.page ? targetRef : undefined}
          className="rounded-xl border border-slate-200 bg-white p-5 shadow-card"
        >
          <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-slate-400">
            <FileText className="h-3.5 w-3.5" />
            Page {p.page}
          </div>
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
            {highlight(p.text, highlightText)}
          </div>
        </div>
      ))}
    </div>
  );
}