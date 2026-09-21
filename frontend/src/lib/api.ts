const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

/** Backend ID of the bundled sample employment agreement. */
export const SAMPLE_DOCUMENT_ID = "sample_employment";

export class ApiError extends Error {
  detail: string;
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.detail = detail;
    this.status = status;
  }
}

function workspaceId(): string {
  try {
    return localStorage.getItem("legallens-workspace") || "public";
  } catch {
    return "public";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("X-Workspace-Id", workspaceId());
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const postForm = <T,>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form });

export const api = {
  base: API_BASE,
  health: () => get<import("@/types").HealthStatus>("/api/health"),
  documents: () => get<import("@/types").DocumentSummary[]>("/api/documents"),
  document: (id: string) => get<import("@/types").DocumentSummary>(`/api/documents/${id}`),
  upload: (form: FormData) =>
    postForm<import("@/types").DocumentSummary>("/api/documents/upload", form),
  analyze: (id: string) => post<import("@/types").AnalyzeResponse>(`/api/documents/${id}/analyze`),
  clauses: (id: string) => get<import("@/types").ClausesResponse>(`/api/documents/${id}/clauses`),
  ask: (id: string, question: string) =>
    post<import("@/types").AskResponse>(`/api/documents/${id}/ask`, { question }),
  contextRanking: (id: string, question: string) =>
    get<import("@/types").ContextRankingResponse>(
      `/api/documents/${id}/context-ranking?context=${encodeURIComponent(question)}`,
    ),
  actionPack: (id: string) =>
    post<import("@/types").ActionPackResponse>(`/api/documents/${id}/action-pack`, {}),
  explain: (id: string, title: string) =>
    post<import("@/types").ExplainResult>(`/api/documents/${id}/explain`, { title }),
  compare: (a: string, b: string) =>
    post<import("@/types").CompareResponse>("/api/compare", { document_a_id: a, document_b_id: b }),
  comparison: (id: string) => get<import("@/types").ComparisonResult>(`/api/comparisons/${id}`),
  sampleDocuments: () => get<import("@/types").SampleDocumentsResponse>("/api/demo/documents"),
  sampleDocument: (id: string) => get<import("@/types").DocumentSummary>(`/api/demo/documents/${id}`),
};