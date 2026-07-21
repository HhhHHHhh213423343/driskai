import ReportDetail from "@/components/ReportDetail";

export default async function ReportPage({
  params,
  searchParams,
}: {
  params: Promise<{ reportId: string }>;
  searchParams: Promise<{ companyId?: string; fromTab?: string }>;
}) {
  const { reportId } = await params;
  const { companyId, fromTab } = await searchParams;
  return <ReportDetail reportId={reportId} companyId={companyId ?? ""} fromTab={fromTab ?? "macro"} />;
}
