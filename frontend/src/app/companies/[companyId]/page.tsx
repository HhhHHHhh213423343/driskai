import { Layout } from "../../../components/layout/Layout";

type SearchParams = Record<string, string | string[] | undefined>;

type CompanyDetailRouteProps = {
  params: Promise<{
    companyId: string;
  }>;
  searchParams?: Promise<SearchParams>;
};

export default async function CompanyDetailRoute({
  params,
  searchParams,
}: CompanyDetailRouteProps) {
  const { companyId } = await params;
  const query = searchParams ? await searchParams : {};
  const companyParam = query.company;
  const company = typeof companyParam === "string" ? companyParam : "";

  return (
    <Layout
      key={`${companyId}-${company}-company-detail`}
      pageMode="company-detail"
      initialCompanyId={companyId}
      initialCompanyName={company}
    />
  );
}
