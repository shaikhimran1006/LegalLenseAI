export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function importanceTone(importance: string): {
  label: string;
  text: string;
  bg: string;
  border: string;
  dot: string;
} {
  switch (importance) {
    case "HIGH":
      return {
        label: "HIGH ATTENTION",
        text: "text-red-700",
        bg: "bg-red-50",
        border: "border-red-200",
        dot: "bg-red-500",
      };
    case "MEDIUM":
      return {
        label: "MEDIUM",
        text: "text-amber-700",
        bg: "bg-amber-50",
        border: "border-amber-200",
        dot: "bg-amber-500",
      };
    default:
      return {
        label: "LOW",
        text: "text-emerald-700",
        bg: "bg-emerald-50",
        border: "border-emerald-200",
        dot: "bg-emerald-500",
      };
  }
}

export function confidenceTone(confidence: string): string {
  switch (confidence) {
    case "HIGH":
      return "text-emerald-700 bg-emerald-50 border-emerald-200";
    case "MEDIUM":
      return "text-amber-700 bg-amber-50 border-amber-200";
    default:
      return "text-slate-600 bg-slate-100 border-slate-200";
  }
}

export const categoryLabels: Record<string, string> = {
  financial: "Financial obligations",
  termination: "Termination",
  notice: "Notice period",
  confidentiality: "Confidentiality",
  non_compete: "Non-compete",
  liability: "Liability",
  ip: "Intellectual property",
  renewal: "Renewal & duration",
  data: "Data & privacy",
  other: "Other",
};