import { useApp } from "@/context/AppContext";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { ResponsibleAiNotice } from "@/components/ResponsibleAiNotice";
import { Logo } from "@/components/Logo";

export default function Settings() {
  const { workspaceId, setWorkspaceId } = useApp();

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="mb-6 text-xl font-bold text-slate-900">Settings</h1>

      <div className="space-y-6">
        <Card>
          <CardHeader title="Preferences" subtitle="Workspace settings" />
          <CardBody className="space-y-4">
            <div>
              <label className="label" htmlFor="settings-workspace-id">Workspace ID</label>
              <input
                id="settings-workspace-id"
                value={workspaceId}
                onChange={(e) => setWorkspaceId(e.target.value.trim() || "public")}
                className="input w-full sm:w-64"
                placeholder="public"
              />
              <p className="mt-1 text-[11px] text-slate-400">
                Stored locally. Sample documents are always accessible regardless of workspace.
              </p>
            </div>
          </CardBody>
        </Card>

        <ResponsibleAiNotice />

        <Card>
          <CardHeader title="About LegalLens AI" />
          <CardBody>
            <Logo />
            <p className="mt-3 text-sm text-slate-600">
              LegalLens AI is a document-intelligence platform that uses structured AI outputs
              to highlight high-attention clauses, answer grounded questions, and produce
              plain-language explanations — all backed by the original source text.
            </p>
            <div className="mt-4 grid gap-3 text-sm text-slate-500 sm:grid-cols-2">
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="font-semibold text-slate-700">Evidence Grounding</p>
                <p className="mt-1 text-xs">
                  Every clause, answer, and action cites the exact page and quoted source text.
                </p>
              </div>
              <div className="rounded-lg bg-slate-50 p-3">
                <p className="font-semibold text-slate-700">Prompt-injection defense</p>
                <p className="mt-1 text-xs">
                  Uploaded document text is wrapped and scanned before LLM processing.
                </p>
              </div>
            </div>
            <p className="mt-4 text-[11px] text-slate-400">
              v1.0.0 · API: {import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}