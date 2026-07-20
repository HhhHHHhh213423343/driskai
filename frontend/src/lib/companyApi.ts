"use client";

export type CompanyRecord = {
  id: string;
  name: string;
  credit_code?: string | null;
  industry?: string | null;
  region?: string | null;
  description?: string | null;
  official_website?: string | null;
  company_profile?: Record<string, unknown>;
};

export type CompanySearchIngestResult = {
  company: CompanyRecord;
  created: boolean;
  ingestion_run?: {
    id: string;
    status: string;
    scanned_company_count: number;
    total_raw_count: number;
    inserted_count: number;
    skipped_count: number;
    source_breakdown: Record<string, number>;
    failures: unknown[];
  } | null;
};

export async function fetchCompanyById(
  companyId: string,
): Promise<CompanyRecord | null> {
  try {
    const response = await fetch(`/api/v1/companies/${companyId}`, {
      method: "GET",
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as CompanyRecord;
  } catch {
    return null;
  }
}

export async function resolveCompanyByName(
  companyName: string,
): Promise<CompanyRecord | null> {
  try {
    const query = new URLSearchParams({
      name: companyName,
    });
    const response = await fetch(`/api/v1/companies/resolve?${query}`, {
      method: "GET",
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as CompanyRecord;
  } catch {
    return null;
  }
}

export async function createCompanyByName(
  companyName: string,
): Promise<CompanyRecord | null> {
  try {
    const response = await fetch("/api/v1/companies", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: companyName,
      }),
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as CompanyRecord;
  } catch {
    return null;
  }
}

export async function ensureCompanyByName(
  companyName: string,
): Promise<CompanyRecord | null> {
  const trimmedName = companyName.trim();
  if (!trimmedName) {
    return null;
  }

  const resolved = await resolveCompanyByName(trimmedName);
  if (resolved) {
    return resolved;
  }

  const created = await createCompanyByName(trimmedName);
  if (created) {
    return created;
  }

  return resolveCompanyByName(trimmedName);
}

export async function searchAndIngestCompany({
  companyName,
  stockCode = "",
  triggerIngestion = true,
}: {
  companyName: string;
  stockCode?: string;
  triggerIngestion?: boolean;
}): Promise<CompanySearchIngestResult | null> {
  const trimmedName = companyName.trim();
  if (!trimmedName) {
    return null;
  }

  try {
    const response = await fetch("/api/v1/companies/search-and-ingest", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: trimmedName,
        stock_code: stockCode.trim(),
        trigger_ingestion: triggerIngestion,
      }),
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as CompanySearchIngestResult;
  } catch {
    return null;
  }
}
