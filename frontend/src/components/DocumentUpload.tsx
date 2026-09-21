import { useCallback, useRef, useState } from "react";
import { Upload, FileText, X } from "lucide-react";
import type { DocumentSummary } from "@/types";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

export function DocumentUpload({ onUploaded }: { onUploaded: (d: DocumentSummary) => void }) {
  const { push } = useToast();
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = ".pdf,.docx,.doc,.txt";

  function onFile(f: File) {
    const ext = f.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "docx", "doc", "txt"].includes(ext ?? "")) {
      push("Only PDF, DOCX, and TXT files are accepted.", "error");
      return;
    }
    setFile(f);
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  }, []);

  async function upload() {
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api.upload(form);
      onUploaded(result);
      push("Document uploaded successfully", "success");
    } catch (e) {
      push(e instanceof ApiError ? e.detail : "Upload failed", "error");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-all",
          dragging ? "border-brand-400 bg-brand-50" : "border-slate-300 bg-white hover:border-brand-300 hover:bg-slate-50",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => onFile(e.target.files?.[0]!)}
        />
        {file ? (
          <div className="flex flex-col items-center gap-2">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-brand-50">
              <FileText className="h-5 w-5 text-brand-600" />
            </div>
            <p className="max-w-full break-words text-center text-sm font-medium text-slate-800">{file.name}</p>
            <p className="text-xs text-slate-500">
              {(file.size / 1024).toFixed(1)} KB
            </p>
            <button
              onClick={(e) => { e.stopPropagation(); setFile(null); }}
              className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-red-500 hover:bg-red-50"
            >
              <X className="h-3 w-3" /> Remove
            </button>
          </div>
        ) : (
          <>
            <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-slate-100">
              <Upload className="h-6 w-6 text-slate-400" />
            </div>
            <p className="text-sm font-medium text-slate-700">Drop a legal document or click to browse</p>
            <p className="mt-1 text-xs text-slate-400">PDF, DOCX, or TXT up to 20 MB</p>
          </>
        )}
      </div>
      <Button
        onClick={upload}
        disabled={!file}
        loading={uploading}
        className="w-full"
      >
        {uploading ? "Uploading…" : "Upload document"}
      </Button>
    </div>
  );
}