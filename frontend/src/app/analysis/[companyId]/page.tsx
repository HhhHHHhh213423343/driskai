import { Layout } from "../../../components/layout/Layout";
import { ThemeConfig, type AnalysisTabKey } from "../../../theme/ThemeConfig";

type SearchParams = Record<string, string | string[] | undefined>;

type AnalysisDetailPageProps = {
  params: Promise<{
    companyId: string;
  }>;
  searchParams?: Promise<SearchParams>;
};

const validTabs = new Set<AnalysisTabKey>(
  ThemeConfig.analysisTabs.map((item) => item.key),
);

export default async function AnalysisDetailPage({
  params,
  searchParams,
}: AnalysisDetailPageProps) {
  const { companyId } = await params;
  const query = searchParams ? await searchParams : {};
  const companyParam = query.company;
  const tabParam = query.tab;

  const company =
    typeof companyParam === "string" && companyParam.trim()
      ? companyParam
      : "比亚迪股份有限公司";
  const tabValue = typeof tabParam === "string" ? tabParam : "";
  const tab = validTabs.has(tabValue as AnalysisTabKey)
    ? (tabValue as AnalysisTabKey)
    : "macro";

  return (
    <Layout
      key={`${companyId}-${company}-${tab}-analysis`}
      pageMode="analysis"
      initialCompanyId={companyId}
      initialCompanyName={company}
      initialTab={tab}
    />
  );
}
