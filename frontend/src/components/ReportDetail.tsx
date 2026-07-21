"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, BarChart3, Building2, CheckCircle2, Download, FileJson, FileText, Loader2, Printer, ShieldAlert } from "lucide-react";

type Metric = { key: string; label: string; value: string; unit: string; description?: string; tone?: string };
type Source = { title: string; source_name: string; source_url?: string; source_tag?: string; published_at?: string | null; page_hint?: string };
type Analysis = { category?: string; summary?: string; key_points?: string[]; next_actions?: string[]; metrics?: Metric[]; sources?: Source[]; data_quality?: Quality; generated_at?: string };
type Quality = { status?: string; coverage_percent?: number; evidence_count?: number; warnings?: string[] };
type EmbeddedReport = { report_type: string; title: string; summary: string; generated_at?: string; snapshot?: { analysis?: Analysis; evidence?: Source[]; data_quality?: Quality } };
type AnalysisReport = { id: string; company_id: string; report_type: string; title: string; summary: string; snapshot: { assembled_reports?: EmbeddedReport[]; analysis?: Analysis; evidence?: Source[]; data_quality?: Quality }; model_name?: string; created_at: string };
type Company = { id: string; name: string; industry?: string | null; region?: string | null };

const CATEGORY_LABELS: Record<string, string> = { macro: "宏观与行业", operations: "业务运营", finance: "财务健康", legal: "法律合规", brand: "品牌舆情" };

function dateTime(value?: string) { return value ? new Date(value).toLocaleString("zh-CN") : "时间未提供"; }
function safeName(value: string) { return value.replace(/[\\/:*?"<>|]/g, "-").slice(0, 80); }
function reportParts(report: AnalysisReport): EmbeddedReport[] {
  if (report.snapshot.assembled_reports?.length) return report.snapshot.assembled_reports;
  return [{ report_type: report.report_type, title: report.title, summary: report.summary, generated_at: report.created_at, snapshot: { analysis: report.snapshot.analysis, evidence: report.snapshot.evidence, data_quality: report.snapshot.data_quality } }];
}
function markdown(report: AnalysisReport, company?: Company | null) {
  const lines = [`# ${report.title}`, "", `企业：${company?.name ?? "未提供"}`, `生成时间：${dateTime(report.created_at)}`, `报告类型：${report.report_type}`, "", "## 管理层摘要", "", report.summary || "未提供摘要。", ""];
  for (const part of reportParts(report)) {
    const analysis = part.snapshot?.analysis; const quality = part.snapshot?.data_quality ?? analysis?.data_quality; const sources = part.snapshot?.evidence ?? analysis?.sources ?? [];
    lines.push(`## ${part.title}`, "", part.summary || analysis?.summary || "未提供摘要。", "");
    if (analysis?.metrics?.length) { lines.push("### 核心指标", "", "| 指标 | 数值 | 说明 |", "| --- | ---: | --- |"); for (const metric of analysis.metrics) lines.push(`| ${metric.label} | ${metric.value}${metric.unit || ""} | ${metric.description || ""} |`); lines.push(""); }
    if (analysis?.key_points?.length) { lines.push("### 关键判断", "", ...analysis.key_points.map((item) => `- ${item}`), ""); }
    if (analysis?.next_actions?.length) { lines.push("### 建议动作", "", ...analysis.next_actions.map((item, index) => `${index + 1}. ${item}`), ""); }
    lines.push("### 数据质量", "", `覆盖率：${quality?.coverage_percent ?? 0}%`, `证据数量：${quality?.evidence_count ?? sources.length} 条`, "");
    if (quality?.warnings?.length) lines.push(...quality.warnings.map((item) => `- ${item}`), "");
    if (sources.length) { lines.push("### 证据来源", ""); for (const source of sources) lines.push(`- [${source.title}](${source.source_url || "#"})，${source.source_name}${source.page_hint ? `，${source.page_hint}` : ""}`); lines.push(""); }
  }
  lines.push("---", "本报告由 D.Risk AI 根据已入库的公开数据与证据快照生成，不构成投资、法律或审计意见。");
  return lines.join("\n");
}
function downloadText(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type }); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
}

export default function ReportDetail({ reportId, companyId, fromTab }: { reportId: string; companyId: string; fromTab: string }) {
  const router = useRouter();
  const [company, setCompany] = useState<Company | null>(null);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!companyId) { setError("缺少企业 ID，无法读取报告"); setLoading(false); return; }
    Promise.all([
      fetch(`/api/v1/companies/${companyId}`, { cache: "no-store" }).then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail ?? "企业档案加载失败"); return payload; }),
      fetch(`/api/v1/companies/${companyId}/analysis-reports?limit=100`, { cache: "no-store" }).then(async (response) => { const payload = await response.json(); if (!response.ok) throw new Error(payload.detail ?? "报告加载失败"); return payload; }),
    ]).then(([companyPayload, reports]: [Company, AnalysisReport[]]) => {
      const selected = reports.find((item) => item.id === reportId); if (!selected) throw new Error("未找到该报告，可能已被移除"); setCompany(companyPayload); setReport(selected);
    }).catch((reason) => setError(reason.message)).finally(() => setLoading(false));
  }, [companyId, reportId]);

  const parts = useMemo(() => report ? reportParts(report) : [], [report]);
  const evidenceTotal = parts.reduce((total, part) => total + (part.snapshot?.evidence?.length ?? part.snapshot?.analysis?.sources?.length ?? 0), 0);
  const coverageAverage = parts.length ? Math.round(parts.reduce((total, part) => total + (part.snapshot?.data_quality?.coverage_percent ?? part.snapshot?.analysis?.data_quality?.coverage_percent ?? 0), 0) / parts.length) : 0;
  const backUrl = companyId ? `/analysis/${companyId}?tab=${fromTab}` : "/";

  if (loading) return <main className="grid min-h-[100dvh] place-items-center bg-[#f4f7f1]"><div className="flex items-center gap-2 text-sm text-[#687168]"><Loader2 size={18} className="animate-spin" />正在整理报告页面</div></main>;
  if (error || !report) return <main className="grid min-h-[100dvh] place-items-center bg-[#f4f7f1] px-5"><div className="max-w-md rounded-2xl border border-red-200 bg-white p-6 text-center"><ShieldAlert className="mx-auto text-red-600" /><h1 className="mt-3 text-lg font-semibold">报告无法打开</h1><p className="mt-2 text-sm text-[#6d756d]">{error}</p><button onClick={() => router.push(backUrl)} className="mt-5 rounded-xl bg-[#78be20] px-4 py-2 text-sm font-semibold text-[#102006]">返回 Agent 分析</button></div></main>;

  return <main className="min-h-[100dvh] bg-[#f4f7f1] text-[#162018] print:bg-white">
    <header className="no-print sticky top-0 z-30 border-b border-[#dce3d7] bg-[#07110b] text-white"><div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-4 md:px-8"><button onClick={() => router.push(backUrl)} className="flex items-center gap-3 text-left"><div className="grid h-10 w-10 place-items-center rounded-xl bg-white text-lg font-black text-[#172019]">D.</div><div><p className="text-[10px] font-semibold tracking-[.22em] text-[#85c82b]">RISK INTELLIGENCE</p><p className="font-semibold">报告详情</p></div></button><div className="flex flex-wrap items-center gap-2"><button onClick={() => router.push(`/reports?companyId=${companyId}`)} className="rounded-xl border border-white/15 px-3 py-2 text-sm text-white/75 hover:bg-white/5">历史报告</button><button onClick={() => downloadText(markdown(report, company), `${safeName(report.title)}.md`, "text/markdown;charset=utf-8")} className="flex items-center gap-2 rounded-xl border border-white/15 px-3 py-2 text-sm text-white/75 hover:bg-white/5"><Download size={15} />Markdown</button><button onClick={() => downloadText(JSON.stringify(report, null, 2), `${safeName(report.title)}.json`, "application/json;charset=utf-8")} className="flex items-center gap-2 rounded-xl border border-white/15 px-3 py-2 text-sm text-white/75 hover:bg-white/5"><FileJson size={15} />JSON</button><button onClick={() => window.print()} className="flex items-center gap-2 rounded-xl bg-[#78be20] px-3 py-2 text-sm font-semibold text-[#102006]"><Printer size={15} />打印 / PDF</button></div></div></header>

    <article className="mx-auto max-w-6xl px-5 py-8 md:px-8 print:max-w-none print:px-0 print:py-0">
      <button onClick={() => router.push(backUrl)} className="no-print mb-6 flex items-center gap-2 text-sm font-medium text-[#567f2b]"><ArrowLeft size={16} />返回 Agent 分析</button>
      <section className="rounded-3xl border border-[#dbe3d6] bg-white p-7 md:p-10 print:border-0 print:p-0">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-start"><div className="max-w-3xl"><div className="flex items-center gap-2 text-sm font-semibold text-[#5c8d29]"><Building2 size={16} />{company?.name ?? "企业分析报告"}</div><h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight md:text-4xl">{report.title}</h1><p className="mt-5 text-base leading-8 text-[#59625a]">{report.summary}</p><p className="mt-5 text-xs text-[#858d85]">生成时间：{dateTime(report.created_at)}　模型：{report.model_name || "structured-agent-v1"}</p></div><div className="grid shrink-0 grid-cols-2 gap-3"><div className="rounded-2xl bg-[#eff6e7] p-4"><p className="text-xs text-[#6e796d]">平均覆盖率</p><p className="mt-1 text-2xl font-semibold text-[#56851f]">{coverageAverage}%</p></div><div className="rounded-2xl bg-[#eff6e7] p-4"><p className="text-xs text-[#6e796d]">证据数量</p><p className="mt-1 text-2xl font-semibold text-[#56851f]">{evidenceTotal}</p></div></div></div>
      </section>

      <div className="mt-6 space-y-6">{parts.map((part, partIndex) => { const analysis = part.snapshot?.analysis; const quality = part.snapshot?.data_quality ?? analysis?.data_quality; const sources = part.snapshot?.evidence ?? analysis?.sources ?? []; return <section key={`${part.report_type}-${partIndex}`} className="break-inside-avoid rounded-3xl border border-[#dbe3d6] bg-white p-6 md:p-8 print:rounded-none print:border-x-0 print:border-b-0 print:px-0">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start"><div className="max-w-3xl"><div className="flex items-center gap-2 text-sm font-semibold text-[#5c8d29]"><FileText size={16} />{CATEGORY_LABELS[analysis?.category ?? ""] ?? part.report_type}</div><h2 className="mt-2 text-2xl font-semibold">{part.title}</h2><p className="mt-3 text-sm leading-7 text-[#616a62]">{part.summary || analysis?.summary}</p></div><div className="rounded-xl border border-[#dce7d2] bg-[#f6f9f3] px-4 py-3 text-sm"><span className="block text-xs text-[#7d867c]">数据覆盖率</span><strong className="mt-1 block text-xl text-[#567f2b]">{quality?.coverage_percent ?? 0}%</strong></div></div>
        {analysis?.metrics?.length ? <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{analysis.metrics.map((metric) => <div key={metric.key} className="rounded-2xl border border-[#e1e7dd] bg-[#fafbf9] p-4"><p className="text-xs text-[#737c73]">{metric.label}</p><p className="mt-2 text-xl font-semibold">{metric.value}<span className="ml-1 text-sm text-[#697169]">{metric.unit}</span></p>{metric.description && <p className="mt-2 text-xs leading-5 text-[#788078]">{metric.description}</p>}</div>)}</div> : null}
        <div className="mt-6 grid gap-5 lg:grid-cols-2">{analysis?.key_points?.length ? <div><h3 className="flex items-center gap-2 font-semibold"><BarChart3 size={17} className="text-[#6da522]" />关键判断</h3><ul className="mt-3 space-y-2 text-sm leading-6 text-[#626a62]">{analysis.key_points.map((item, index) => <li key={index} className="rounded-xl bg-[#f7f9f5] px-4 py-3">{item}</li>)}</ul></div> : null}{analysis?.next_actions?.length ? <div><h3 className="flex items-center gap-2 font-semibold"><CheckCircle2 size={17} className="text-[#6da522]" />建议动作</h3><ol className="mt-3 space-y-2 text-sm leading-6 text-[#626a62]">{analysis.next_actions.map((item, index) => <li key={index} className="flex gap-3 rounded-xl bg-[#f7f9f5] px-4 py-3"><span className="font-semibold text-[#5f9028]">{index + 1}</span>{item}</li>)}</ol></div> : null}</div>
        {quality?.warnings?.length ? <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4"><h3 className="text-sm font-semibold text-amber-800">数据边界</h3><ul className="mt-2 space-y-1 text-sm leading-6 text-amber-800/85">{quality.warnings.map((item) => <li key={item}>- {item}</li>)}</ul></div> : null}
        {sources.length ? <div className="mt-6"><h3 className="font-semibold">证据来源</h3><div className="mt-3 grid gap-2 md:grid-cols-2">{sources.map((source, index) => <a key={`${source.title}-${index}`} href={source.source_url || undefined} target={source.source_url ? "_blank" : undefined} rel="noreferrer" className="rounded-xl border border-[#e0e6dc] px-4 py-3 text-sm hover:border-[#a7c77e]"><span className="block font-medium">{source.title}</span><span className="mt-1 block text-xs text-[#7b837b]">{source.source_name}{source.page_hint ? `，${source.page_hint}` : ""}</span></a>)}</div></div> : null}
      </section>; })}</div>
      <footer className="mt-6 border-t border-[#dce3d7] py-6 text-xs leading-5 text-[#7a827a]">本报告根据已入库的公开数据与证据快照生成，不构成投资、法律或审计意见。</footer>
    </article>
  </main>;
}
