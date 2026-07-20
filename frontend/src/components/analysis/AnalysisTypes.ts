export interface AnalysisPanelProps {
  companyName: string;
}

export type AgentSource = {
  title: string;
  source_name: string;
  source_url: string;
  source_tag: string;
  page_hint: string;
  published_at: string | null;
  severity: string;
  sentiment: string;
};

export type AgentMetric = {
  key: string;
  label: string;
  value: string;
  unit: string;
  delta: string;
  tone: "positive" | "warning" | "neutral" | string;
  description: string;
  source_ids: string[];
};

export type AgentSeries = {
  key: string;
  label: string;
  unit: string;
  points: Array<{ period: string; value: number }>;
  source_ids: string[];
};

export type AgentSection = {
  key: string;
  title: string;
  kind:
    | "timeline"
    | "distribution"
    | "table"
    | "scenario"
    | "funnel"
    | "comparison"
    | "insight"
    | "recommendation"
    | string;
  summary: string;
  items: Array<Record<string, unknown>>;
  source_ids: string[];
};

export type AgentDataQuality = {
  status: "complete" | "partial" | "insufficient" | string;
  coverage_percent: number;
  evidence_count: number;
  warnings: string[];
  updated_at: string | null;
};

export type AgentAnalysisPreview = {
  company_name: string;
  category: string;
  report_type: string;
  retrieval_stage: string;
  summary: string;
  key_points: string[];
  next_actions: string[];
  sources: AgentSource[];
  metrics: AgentMetric[];
  series: AgentSeries[];
  sections: AgentSection[];
  data_quality: AgentDataQuality;
  generated_at: string;
};
