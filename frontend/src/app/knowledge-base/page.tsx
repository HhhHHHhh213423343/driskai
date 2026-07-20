import { Layout } from "../../components/layout/Layout";
import { ThemeConfig, type AnalysisTabKey } from "../../theme/ThemeConfig";

type SearchParams = Record<string, string | string[] | undefined>;

type KnowledgeBasePageProps = {
  searchParams?: Promise<SearchParams>;
};

const validTabs = new Set<AnalysisTabKey>(
  ThemeConfig.analysisTabs.map((item) => item.key),
);

export default async function KnowledgeBasePage({
  searchParams,
}: KnowledgeBasePageProps) {
  const params = searchParams ? await searchParams : {};
  const companyIdParam = params.companyId;
  const companyParam = params.company;
  const tabParam = params.tab;

  const companyId =
    typeof companyIdParam === "string" && companyIdParam.trim()
      ? companyIdParam
      : undefined;
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
      key={`${companyId ?? "no-company"}-${company}-${tab}-knowledge-base`}
      pageMode="knowledge-base"
      initialCompanyId={companyId}
      initialCompanyName={company}
      initialTab={tab}
    />
  );
}
