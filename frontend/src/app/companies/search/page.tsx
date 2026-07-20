import { Layout } from "../../../components/layout/Layout";

type SearchParams = Record<string, string | string[] | undefined>;

type CompanySearchRouteProps = {
  searchParams?: Promise<SearchParams>;
};

export default async function CompanySearchRoute({
  searchParams,
}: CompanySearchRouteProps) {
  const query = searchParams ? await searchParams : {};
  const companyParam = query.company;
  const company = typeof companyParam === "string" ? companyParam : "";

  return (
    <Layout
      key={`${company || "free-search"}-company-search`}
      pageMode="company-detail"
      initialCompanyName={company}
    />
  );
}
