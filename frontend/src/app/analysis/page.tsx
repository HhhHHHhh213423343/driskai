import { redirect } from "next/navigation";

import { Layout } from "../../components/layout/Layout";
import { ThemeConfig, type AnalysisTabKey } from "../../theme/ThemeConfig";

type SearchParams = Record<string, string | string[] | undefined>;

type AnalysisPageProps = {
  searchParams?: Promise<SearchParams>;
};

const validTabs = new Set<AnalysisTabKey>(
  ThemeConfig.analysisTabs.map((item) => item.key),
);

export default async function LegacyAnalysisPage({
  searchParams,
}: AnalysisPageProps) {
  const params = searchParams ? await searchParams : {};
  const companyIdParam =
    typeof params.companyId === "string"
      ? params.companyId
      : typeof params.company_id === "string"
        ? params.company_id
        : "";
  const companyParam =
    typeof params.company === "string"
      ? params.company
      : typeof params.companyName === "string"
        ? params.companyName
        : "";
  const tabParam = typeof params.tab === "string" ? params.tab : "";
  const tab = validTabs.has(tabParam as AnalysisTabKey)
    ? (tabParam as AnalysisTabKey)
    : "macro";

  if (companyIdParam) {
    const companyQuery = companyParam
      ? `&company=${encodeURIComponent(companyParam)}`
      : "";
    redirect(`/analysis/${companyIdParam}?tab=${tab}${companyQuery}`);
  }

  if (companyParam.trim()) {
    return (
      <Layout
        key={`${companyParam}-${tab}-free-analysis`}
        pageMode="analysis"
        initialCompanyName={companyParam}
        initialTab={tab}
      />
    );
  }

  redirect("/");
}
