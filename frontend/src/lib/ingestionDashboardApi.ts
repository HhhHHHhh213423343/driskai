"use client";

export type IngestionTrendPoint = {
  label: string;
  value: number;
};

export type IngestionRunSummary = {
  id: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  requested_company_count: number;
  scanned_company_count: number;
  total_raw_count: number;
  inserted_count: number;
  skipped_count: number;
  source_breakdown: Record<string, number>;
  failures: unknown[];
  summary: Record<string, unknown>;
};

export type IngestionDashboardSummary = {
  total_events: number;
  last_7_days_events: number;
  high_priority_events: number;
  report_count: number;
  latest_scan_label: string;
  latest_change_label: string;
  trend_series: IngestionTrendPoint[];
  category_distribution: Record<string, number>;
  report_output: Record<string, number>;
  source_breakdown: Record<string, number>;
  latest_run?: IngestionRunSummary | null;
};

export async function fetchIngestionDashboardSummary(): Promise<IngestionDashboardSummary | null> {
  try {
    const response = await fetch("/api/v1/ingestion/dashboard-summary", {
      method: "GET",
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as IngestionDashboardSummary;
  } catch {
    return null;
  }
}
