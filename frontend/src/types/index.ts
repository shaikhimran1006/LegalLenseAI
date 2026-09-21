export type Importance = "HIGH" | "MEDIUM" | "LOW";
export type Confidence = "HIGH" | "MEDIUM" | "LOW";
export type Mode = "real_ai" | "demo";

export interface AttentionSummary {
  high: number;
  medium: number;
  low: number;
}

export interface Clause {
  id?: string;
  title: string;
  category: string;
  importance: Importance;
  plain_language: string;
  why_it_matters: string;
  evidence: string;
  source_page: number;
  source_section?: string;
  confidence: Confidence;
  highlight_keywords?: string[];
  verdict?: string | null;
}

export interface DocumentAnalysis {
  document_id: string;
  mode: Mode;
  attention_summary: AttentionSummary;
  clauses: Clause[];
  clauses_discarded?: number;
  warnings?: string[];
  analysis_round?: number;
  generated_at: string;
}

export interface AnalyzeResponse {
  document_id: string;
  analysis: {
    document_type?: string;
    document_title?: string;
    parties?: string[];
    effective_date?: string;
    expiration_date?: string;
    jurisdiction?: string;
    important_dates?: string[];
    financial_amounts?: string[];
    important_clauses: Clause[];
    clauses_discarded?: number;
    attention_summary: AttentionSummary;
  };
  mode: Mode;
  duration_ms?: number;
}

export interface ClausesResponse {
  document_id: string;
  clauses: Clause[];
  attention_summary: AttentionSummary;
}

export interface AskResponse {
  document_id: string;
  answer: Answer;
  mode: Mode;
}

export interface ActionPackResponse {
  document_id: string;
  action_pack: ActionPack;
  mode: Mode;
}

export interface CompareResponse {
  comparison_id: string;
  document_a: string;
  document_b: string;
  result: ComparisonResult;
  mode: Mode;
}

export interface RankedClauseItem {
  clause: Clause;
  relevance: number;
  reasons: string[];
}

export interface ContextRankingResponse {
  context: string;
  profile?: { label: string };
  ranked_clauses: RankedClauseItem[];
}

export interface ExplainResult {
  clause: Clause;
  mode: Mode;
}

export interface DocumentSummary {
  id: string;
  filename: string;
  extension?: string;
  status: string;
  page_count: number;
  size?: number;
  context?: string;
  mode?: Mode;
  status_detail?: string;
  created_at?: string;
  is_sample?: boolean;
}

export interface SampleDocumentsResponse {
  items: DocumentSummary[];
  fictional_notice: string;
}

export interface Answer {
  answer: string;
  evidence: EvidenceRef[];
  insufficient?: boolean;
}

export interface EvidenceRef {
  page: number;
  section: string;
  quote: string;
}

export interface RankedClauseItem {
  clause: Clause;
  relevance: number;
  reasons: string[];
}

export interface ContextRankingResponse {
  context: string;
  profile?: { label: string };
  ranked_clauses: RankedClauseItem[];
}

export interface QuestionItem {
  question: string;
}

export interface ActionPack {
  important_clauses: string[];
  questions_to_ask: string[];
  info_to_collect: string[];
  things_to_clarify: string[];
  preparation_checklist: string[];
  questions_for_legal_professional: QuestionItem[];
}

export interface ComparisonRow {
  area: string;
  contract_a_value?: string;
  contract_b_value?: string;
  change: "Significant" | "Review" | "Minor" | "Added" | "Removed" | "Modified";
  a_source_page?: number;
  a_source_section?: string;
  b_source_page?: number;
  b_source_section?: string;
}

export interface ComparisonResult {
  comparison_rows: ComparisonRow[];
  important_changes?: string[];
  clauses_added?: string[];
  clauses_removed?: string[];
  clauses_modified?: string[];
}

export interface HealthStatus {
  status: string;
  version: string;
  demo_mode: boolean;
  ai_configured: boolean;
}