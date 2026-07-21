import ReportHistory from "@/components/ReportHistory";

export default async function ReportsPage({ searchParams }: { searchParams: Promise<{ companyId?: string }> }) {
  const { companyId } = await searchParams;
  return <ReportHistory companyId={companyId ?? ""} />;
}
