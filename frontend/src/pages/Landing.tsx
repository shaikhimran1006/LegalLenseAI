import { Link, useNavigate } from "react-router-dom";
import {
  Sparkles,
  FileSearch,
  ShieldCheck,
  ArrowRight,
  Upload,
  FileText,
} from "lucide-react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/Button";
import { ResponsibleAiNotice } from "@/components/ResponsibleAiNotice";
import { SAMPLE_DOCUMENT_ID } from "@/lib/api";

const FEATURES = [
  {
    icon: FileSearch,
    title: "Attention-driven analysis",
    desc: "Legal documents parsed clause-by-clause. HIGH / MEDIUM / LOW attention ratings highlight what matters most.",
  },
  {
    icon: ShieldCheck,
    title: "Every answer is grounded",
    desc: "AI responses cite the exact page, section, and original source text. No hallucinated clauses.",
  },
  {
    icon: Sparkles,
    title: "Responsible by design",
    desc: "Prompt-injection defenses, evidence-grounded answers, and an unmissable responsible-AI notice.",
  },
];

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-[calc(100vh-56px)]">
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-b from-brand-950 via-brand-900 to-brand-800 px-5 pb-28 pt-20 text-white">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_rgba(99,128,199,0.15),_transparent_60%)]" />
        <div className="relative mx-auto max-w-4xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-wide">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Real AI · 100% Evidence-Backed
          </div>
          <h1 className="mx-auto max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
            Understand before you sign.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-white/80">
            LegalLens AI reads legal documents, flags high-attention clauses, and gives you
            plain-language answers grounded in the original source text. Every response
            cites the exact page and passage.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" onClick={() => navigate(`/analyze?id=${SAMPLE_DOCUMENT_ID}`)} className="!bg-white !text-brand-800 hover:!bg-slate-100">
              <Sparkles className="h-4 w-4" /> Try with Sample Document <ArrowRight className="h-4 w-4" />
            </Button>
            <Button
              variant="secondary"
              size="lg"
              onClick={() => navigate("/documents")}
              className="!border-white/30 !bg-transparent !text-white hover:!bg-white/10"
            >
              <FileSearch className="h-4 w-4" /> Browse documents
            </Button>
          </div>
          <p className="mt-6 text-xs text-white/50">
            No sign-up required. Upload your own document or explore the sample employment agreement.
          </p>
        </div>
      </section>

      {/* Upload / Sample section */}
      <section className="mx-auto -mt-14 max-w-3xl px-5 sm:px-6">
        <div className="card rounded-2xl p-8 text-center shadow-lg animate-fade-up">
          <h2 className="text-xl font-bold text-slate-900">Analyze your legal document</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
            Upload a document to understand clauses, obligations, and areas that may need
            attention — or explore a ready sample right away.
          </p>
          <div className="mx-auto mt-6 flex max-w-xs flex-col items-stretch gap-3">
            <Button size="lg" onClick={() => navigate("/documents")} className="w-full">
              <Upload className="h-4 w-4" /> Upload Your Document
            </Button>
            <div className="flex items-center gap-3 text-xs font-medium uppercase tracking-wider text-slate-400">
              <span className="h-px flex-1 bg-slate-200" />
              or
              <span className="h-px flex-1 bg-slate-200" />
            </div>
            <Button
              variant="secondary"
              size="lg"
              onClick={() => navigate(`/analyze?id=${SAMPLE_DOCUMENT_ID}`)}
              className="w-full"
            >
              <FileText className="h-4 w-4" /> Try with Sample Document
            </Button>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="card p-5 animate-fade-up">
              <div className="mb-3 grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600">
                <f.icon className="h-5 w-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">{f.title}</h3>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Trust */}
      <section className="mx-auto max-w-6xl px-5 pb-16">
        <ResponsibleAiNotice />
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-400">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5">
          <Logo mark="" className="opacity-60" />
          <p>
            Sample documents use fictional entities and data. Not legal advice.{" "}
            <Link to="/settings" className="text-brand-600 hover:underline">
              Settings
            </Link>
          </p>
        </div>
      </footer>
    </div>
  );
}