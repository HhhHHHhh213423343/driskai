"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Building2, CheckCircle2, Clock3, Search, ShieldCheck } from "lucide-react";

type Company = {
  id: string;
  name: string;
  industry?: string | null;
  region?: string | null;
  description?: string;
  company_profile?: { akshare_profile?: { stock_code?: string; stock_name?: string; status?: string } };
};

function stockCode(company: Company) {
  return company.company_profile?.akshare_profile?.stock_code ?? "";
}

export default function HomeSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [companies, setCompanies] = useState<Company[]>([]);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/v1/companies", { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail ?? "无法读取企业列表");
        return payload;
      })
      .then(setCompanies)
      .catch(() => setCompanies([]));
  }, []);

  useEffect(() => {
    if (!busy) { setElapsed(0); return; }
    const startedAt = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  const candidates = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return companies.slice(0, 6);
    return companies.filter((company) =>
      company.name.toLowerCase().includes(normalized) || stockCode(company).includes(normalized),
    ).slice(0, 6);
  }, [companies, query]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = query.trim();
    if (!input) { setError("请输入公司名称、股票简称或 6 位股票代码"); return; }
    setBusy(true);
    setError("");
    try {
      const isStockCode = /^\d{6}$/.test(input);
      const response = await fetch("/api/v1/companies/search-and-ingest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          name: input,
          stock_code: isStockCode ? input : "",
          trigger_ingestion: true,
          max_results_per_source: 5,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "企业检索失败");
      const company = payload.company ?? payload;
      const id = company.id ?? payload.company_id;
      if (!id) throw new Error("后端未返回企业 ID");
      router.push(`/analysis/${id}?tab=macro`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "企业检索失败");
    } finally {
      setBusy(false);
    }
  }

  const progressText = elapsed < 8
    ? "正在识别企业与证券代码"
    : elapsed < 25
      ? "正在获取公开财务数据与公告"
      : "外部数据源响应较慢，检索仍在继续";

  return (
    <main className="min-h-[100dvh] bg-[#07110b] text-white">
      <div className="mx-auto flex min-h-[100dvh] max-w-7xl flex-col px-6 py-8 lg:px-12">
        <header className="flex items-center justify-between border-b border-white/10 pb-6">
          <div className="flex items-center gap-4">
            <div className="grid h-12 w-12 place-items-center rounded-xl bg-white text-2xl font-black text-[#172019]">D.</div>
            <div><p className="text-xs font-semibold tracking-[.28em] text-[#85c82b]">RISK INTELLIGENCE</p><h1 className="text-xl font-semibold">D.Risk AI</h1></div>
          </div>
          <div className="hidden items-center gap-2 text-sm text-white/60 sm:flex"><ShieldCheck size={18} className="text-[#85c82b]" />公开数据　证据可追溯　缺失不臆测</div>
        </header>

        <section className="grid flex-1 items-center gap-14 py-14 lg:grid-cols-[1.08fr_.92fr]">
          <div>
            <p className="mb-5 text-sm font-semibold tracking-[.3em] text-[#85c82b]">ENTERPRISE RISK WORKSPACE</p>
            <h2 className="max-w-3xl text-5xl font-semibold leading-[1.08] tracking-tight lg:text-7xl">从一家企业开始，<br /><span className="text-[#9bdb45]">让风险有据可查。</span></h2>
            <p className="mt-7 max-w-2xl text-lg leading-8 text-white/60">输入公司名称或股票代码，联动五个分析 Agent，并保留每条结论的数据来源与覆盖质量。</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-white/[.06] p-7 shadow-2xl backdrop-blur">
            <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#85c82b] text-[#07110b]"><Building2 /></div>
            <h3 className="text-2xl font-semibold">智能检索企业</h3>
            <p className="mt-2 text-sm leading-6 text-white/55">支持公司全称、股票简称或 6 位股票代码。A 股上市公司优先匹配 AkShare 财务数据。</p>
            <form onSubmit={submit} className="mt-7">
              <label className="mb-2 block text-sm font-medium text-white/80" htmlFor="company-search">公司名称或股票代码</label>
              <div className="flex rounded-2xl bg-white p-2 text-[#172019] focus-within:ring-2 focus-within:ring-[#85c82b]">
                <Search className="ml-3 mt-3 shrink-0 text-black/40" size={20} />
                <input id="company-search" value={query} onChange={(event) => setQuery(event.target.value)} disabled={busy} className="min-w-0 flex-1 bg-transparent px-3 py-3 outline-none placeholder:text-black/45" placeholder="例如：工商银行 / 601398" />
                <button disabled={busy} className="flex shrink-0 items-center gap-2 rounded-xl bg-[#78be20] px-5 font-semibold text-[#102006] active:scale-[.98] disabled:opacity-60">{busy ? "检索中" : "开始分析"}<ArrowRight size={17} /></button>
              </div>
              <p className="mt-2 text-xs text-white/45">精确股票代码可以减少同名公司或简称匹配误差。</p>
            </form>

            {busy && <div className="mt-5 rounded-2xl border border-[#85c82b]/25 bg-[#85c82b]/10 p-4" aria-live="polite">
              <div className="flex items-center justify-between gap-3"><span className="flex items-center gap-2 text-sm font-medium text-[#b8e47c]"><Clock3 size={16} />{progressText}</span><span className="text-xs text-white/45">{elapsed} 秒</span></div>
              <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10"><div className="loading-bar h-full w-2/3 rounded-full bg-[#85c82b]" /></div>
            </div>}
            {error && <p className="mt-4 rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p>}

            <div className="mt-7 border-t border-white/10 pt-5">
              <div className="flex items-center justify-between"><h4 className="text-sm font-semibold">{query ? "匹配的已分析企业" : "最近分析企业"}</h4><span className="text-xs text-white/40">{candidates.length} 家</span></div>
              {candidates.length > 0 ? <div className="mt-3 grid gap-2 sm:grid-cols-2">{candidates.map((company) => <button key={company.id} onClick={() => router.push(`/analysis/${company.id}?tab=macro`)} className="group flex items-center justify-between rounded-xl border border-white/10 bg-white/[.04] px-3 py-3 text-left transition hover:border-[#85c82b]/50 hover:bg-white/[.07] active:scale-[.99]"><span className="min-w-0"><span className="block truncate text-sm font-medium">{company.name}</span><span className="mt-1 block text-xs text-white/40">{stockCode(company) || company.industry || "基础档案已入库"}</span></span><CheckCircle2 size={16} className="ml-2 shrink-0 text-[#85c82b]" /></button>)}</div> : <p className="mt-3 rounded-xl border border-dashed border-white/15 px-4 py-4 text-sm text-white/45">没有本地候选，提交后将执行智能检索。</p>}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
