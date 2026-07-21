"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Building2, ChevronRight, FileText, Loader2, Search, ShieldAlert } from "lucide-react";

type Report = { id: string; company_id: string; report_type: string; title: string; summary: string; created_at: string; model_name?: string };
type Company = { id: string; name: string; industry?: string | null; region?: string | null };

const REPORT_LABELS: Record<string, string> = {
  comprehensive_risk_report: "综合风险报告",
  macro_environment_report: "宏观与行业",
  business_operations_report: "业务运营",
  financial_health_report: "财务健康",
  legal_risk_report: "法律合规",
  brand_sentiment_report: "品牌舆情",
};

function timestamp(value: string) {
  return new Date(value).toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function ReportHistory({ companyId }: { companyId: string }) {
  const router = useRouter();
  const [company, setCompany] = useState<Company | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!companyId) { setError("缺少企业 ID，无法读取报告"); setLoading(false); return; }
    Promise.all([
      fetch(`/api/v1/companies/${companyId}`, { cache: "no-store" }).then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail ?? "企业档案加载失败"); return payload; }),
      fetch(`/api/v1/companies/${companyId}/analysis-reports?limit=100`, { cache: "no-store" }).then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail ?? "历史报告加载失败"); return payload; }),
    ]).then(([companyPayload, reportPayload]) => { setCompany(companyPayload); setReports(reportPayload); }).catch((reason) => setError(reason.message)).finally(() => setLoading(false));
  }, [companyId]);

  const visibleReports = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return reports;
    return reports.filter((report) => `${report.title} ${report.summary} ${REPORT_LABELS[report.report_type] ?? report.report_type}`.toLowerCase().includes(normalized));
  }, [query, reports]);

  return <main className="min-h-[100dvh] bg-[#f4f7f1] text-[#162018]">
    <header className="border-b border-[#dce3d7] bg-[#07110b] text-white"><div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 md:px-8"><button onClick={() => router.push(companyId ? `/analysis/${companyId}?tab=macro` : "/")} className="flex items-center gap-3 text-left"><div className="grid h-10 w-10 place-items-center rounded-xl bg-white text-lg font-black text-[#172019]">D.</div><div><p className="text-[10px] font-semibold tracking-[.22em] text-[#85c82b]">RISK INTELLIGENCE</p><p className="font-semibold">报告中心</p></div></button><button onClick={() => router.push(companyId ? `/analysis/${companyId}?tab=macro` : "/")} className="flex items-center gap-2 rounded-xl border border-white/15 px-4 py-2 text-sm text-white/75 hover:bg-white/5"><ArrowLeft size={16} />返回 Agent 分析</button></div></header>
    <div className="mx-auto max-w-6xl px-5 py-8 md:px-8">
      <section className="flex flex-col justify-between gap-5 md:flex-row md:items-end"><div><div className="flex items-center gap-2 text-sm font-semibold text-[#5e8f27]"><Building2 size={16} />{company?.name ?? "企业报告"}</div><h1 className="mt-2 text-3xl font-semibold tracking-tight">历史分析报告</h1><p className="mt-2 text-sm text-[#69716a]">查看各 Agent 报告及综合风险报告，历史快照不会随实时数据更新而改变。</p></div><label className="flex w-full max-w-sm items-center gap-2 rounded-xl border border-[#d8dfd3] bg-white px-4 py-3 text-sm focus-within:ring-2 focus-within:ring-[#78be20]"><Search size={17} className="text-[#738071]" /><span className="sr-only">搜索报告</span><input value={query} onChange={(event) => setQuery(event.target.value)} className="min-w-0 flex-1 outline-none placeholder:text-[#899187]" placeholder="搜索报告标题或摘要" /></label></section>
      {error && <div className="mt-6 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"><ShieldAlert size={17} />{error}</div>}
      {loading ? <div className="mt-12 flex items-center justify-center gap-2 text-sm text-[#6d766d]"><Loader2 size={18} className="animate-spin" />正在读取报告</div> : visibleReports.length > 0 ? <section className="mt-8 grid gap-4 md:grid-cols-2">{visibleReports.map((report) => <button key={report.id} onClick={() => router.push(`/reports/${report.id}?companyId=${companyId}`)} className={`group rounded-2xl border p-5 text-left transition active:scale-[.99] ${report.report_type === "comprehensive_risk_report" ? "border-[#a9c982] bg-[#f0f7e8]" : "border-[#dde4d8] bg-white hover:border-[#a7c77e]"}`}><div className="flex items-start justify-between gap-3"><span className="rounded-lg bg-white px-2.5 py-1 text-xs font-semibold text-[#598721] ring-1 ring-[#d9e8c7]">{REPORT_LABELS[report.report_type] ?? report.report_type}</span><ChevronRight size={18} className="text-[#8b9688] transition group-hover:translate-x-1" /></div><h2 className="mt-4 text-lg font-semibold">{report.title}</h2><p className="mt-2 line-clamp-3 text-sm leading-6 text-[#69716a]">{report.summary || "该报告未提供摘要。"}</p><div className="mt-5 flex items-center justify-between text-xs text-[#858d84]"><span>{timestamp(report.created_at)}</span><span>{report.model_name || "structured-agent-v1"}</span></div></button>)}</section> : <section className="mt-10 rounded-2xl border border-dashed border-[#cad4c3] bg-white px-6 py-12 text-center"><FileText className="mx-auto text-[#83a65b]" /><h2 className="mt-3 font-semibold">暂无匹配报告</h2><p className="mt-1 text-sm text-[#747d74]">返回 Agent 分析页生成一份新报告。</p></section>}
    </div>
  </main>;
}
