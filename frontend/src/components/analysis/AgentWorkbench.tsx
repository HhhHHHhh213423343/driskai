"use client";

import { useEffect, useState, type ReactNode } from "react";
import {
  ArrowUpRight,
  Bot,
  CheckCircle2,
  DatabaseZap,
  FileOutput,
  Layers3,
  Link2,
  SearchCheck,
  Sparkles,
} from "lucide-react";

import { AgentDataPanel } from "./AgentDataPanel";
import type { AgentAnalysisPreview } from "./AnalysisTypes";

import {
  buildComprehensiveReport,
  buildGeneratedReport,
  getAgentScenario,
  type ComprehensiveReport,
  type GeneratedReport,
  type ReportDepth,
} from "./agentWorkspaceData";
import {
  ensureCompanyByName,
  fetchCompanyById,
  resolveCompanyByName,
  type CompanyRecord,
} from "../../lib/companyApi";
import { useReportAssembly } from "../../lib/reportAssembly";
import { ThemeConfig, type AnalysisTabKey } from "../../theme/ThemeConfig";

type AgentWorkbenchProps = {
  activeTab: AnalysisTabKey;
  companyName: string;
  companyId?: string;
  children: ReactNode;
};

type PersistedAnalysisReport = {
  id: string;
  company_id: string;
  report_type: string;
  title: string;
  summary: string;
  snapshot: {
    sections?: Array<{
      title: string;
      body?: string;
      summary?: string;
      sourceIds?: string[];
    }>;
    assembled_reports?: Array<{
      report_type: string;
      title: string;
      summary: string;
    }>;
  };
  generated_at: string;
};

const tabKeys = ThemeConfig.analysisTabs.map((item) => item.key);

export function AgentWorkbench({
  activeTab,
  companyName,
  companyId,
}: AgentWorkbenchProps) {
  const [depthModes, setDepthModes] = useState<Record<AnalysisTabKey, ReportDepth>>({
    macro: "scan",
    operations: "scan",
    finance: "scan",
    legal: "scan",
    brand: "scan",
  });
  const [generatedReports, setGeneratedReports] = useState<
    Partial<Record<AnalysisTabKey, GeneratedReport>>
  >({});
  const [includedReportKeys, setIncludedReportKeys] = useState<AnalysisTabKey[]>([]);
  const [comprehensiveReport, setComprehensiveReport] =
    useState<ComprehensiveReport | null>(null);
  const [remotePreview, setRemotePreview] = useState<AgentAnalysisPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [previewError, setPreviewError] = useState("");
  const [companyRecord, setCompanyRecord] = useState<CompanyRecord | null>(null);
  const [syncState, setSyncState] = useState<"idle" | "syncing" | "synced" | "demo">(
    "idle",
  );
  const assemblyCompanyId = companyRecord?.id ?? companyId;
  const assemblyCompanyName = companyRecord?.name ?? companyName;
  const {
    items: assemblyItems,
    upsertItem: upsertAssemblyItem,
    removeItem: removeAssemblyItem,
    markComposed,
  } = useReportAssembly(assemblyCompanyId, assemblyCompanyName);

  const depth = depthModes[activeTab];
  const scenario = getAgentScenario(activeTab, companyName);
  const currentReport = generatedReports[activeTab];
  const reportSources = currentReport?.sources ?? scenario.sources;
  const retrievalStage = remotePreview?.retrieval_stage ?? "knowledge_base_fallback";
  const effectiveSources =
    remotePreview?.sources.length
      ? remotePreview.sources.map((item, index) => ({
          id: `${activeTab}-remote-${index + 1}`,
          kind: "结构化风险" as const,
          sourceName: item.source_name,
          title: item.title,
          url: item.source_url,
          publishedAt: item.published_at || "",
          note:
            `${item.source_tag}${item.page_hint ? ` · ${item.page_hint}` : ""}` +
            `${item.severity ? ` · ${item.severity}` : ""}` +
            `${item.sentiment ? ` · ${item.sentiment}` : ""}`,
          pageHint: item.page_hint,
        }))
      : scenario.sources;
  const effectiveSummary =
    currentReport?.summary ??
    remotePreview?.summary ??
    (depth === "deep" ? scenario.deepSummary : scenario.scanSummary);
  const effectiveKeyPoints =
    remotePreview?.key_points.length ? remotePreview.key_points : scenario.keyPoints;
  const effectiveNextActions =
    remotePreview?.next_actions.length
      ? remotePreview.next_actions
      : scenario.deepDivePrompts;
  const effectiveSections =
    currentReport?.sections ??
    remotePreview?.sections.map((section) => ({
      title: section.title,
      body: section.summary,
      sourceIds: [] as string[],
    })) ??
    (depth === "deep" ? scenario.deepSections : scenario.scanSections);

  function makePreviewQuery(category: AnalysisTabKey) {
    const query = new URLSearchParams({ category, limit: "12" });
    if (companyId) {
      query.set("company_id", companyId);
    } else {
      query.set("company_name", companyName);
    }
    return query;
  }

  async function fetchAgentPreview(category: AnalysisTabKey) {
    const response = await fetch(
      `/api/v1/agent-analysis/preview?${makePreviewQuery(category)}`,
      { method: "GET", cache: "no-store" },
    );
    if (!response.ok) {
      let detail = `分析接口返回 ${response.status}`;
      try {
        const payload = (await response.json()) as { detail?: string };
        detail = payload.detail || detail;
      } catch {
        // Keep the HTTP status when the response is not JSON.
      }
      throw new Error(detail);
    }
    return (await response.json()) as AgentAnalysisPreview;
  }

  function reportFromPreview(
    key: AnalysisTabKey,
    reportDepth: ReportDepth,
    preview: AgentAnalysisPreview,
  ): GeneratedReport {
    const base = buildGeneratedReport(key, companyName, reportDepth);
    const sources = preview.sources.map((item, index) => ({
      id: `${key}-remote-${index + 1}`,
      kind: item.source_tag === "财务数据" ? ("数据库" as const) : ("结构化风险" as const),
      sourceName: item.source_name,
      title: item.title,
      url: item.source_url,
      publishedAt: item.published_at || "",
      note: [item.source_tag, item.severity, item.sentiment].filter(Boolean).join(" · "),
      pageHint: item.page_hint,
    }));
    return {
      ...base,
      reportType: preview.report_type,
      summary: preview.summary,
      sections: preview.sections.map((section) => ({
        title: section.title,
        body: section.summary,
        sourceIds: [],
      })),
      sources,
      analysis: preview,
    };
  }

  useEffect(() => {
    setIncludedReportKeys(assemblyItems.map((item) => item.tabKey));
  }, [assemblyItems]);

  useEffect(() => {
    let ignore = false;

    async function loadCompanyRecord() {
      const data = companyId
        ? await fetchCompanyById(companyId)
        : await resolveCompanyByName(companyName);
      if (!ignore) {
        setCompanyRecord(data);
      }
    }

    async function loadPreview() {
      if (!ignore) {
        setPreviewLoading(true);
        setPreviewError("");
        setRemotePreview(null);
      }
      try {
        const data = await fetchAgentPreview(activeTab);
        if (!ignore) {
          setRemotePreview(data);
        }
      } catch (error) {
        if (!ignore) {
          setRemotePreview(null);
          setPreviewError(
            error instanceof Error ? error.message : "无法加载 Agent 分析。",
          );
        }
      } finally {
        if (!ignore) {
          setPreviewLoading(false);
        }
      }
    }

    void loadCompanyRecord();
    void loadPreview();

    return () => {
      ignore = true;
    };
  }, [activeTab, companyId, companyName]);

  function upsertReport(report: GeneratedReport) {
    setGeneratedReports((current) => ({
      ...current,
      [report.key]: report,
    }));
  }

  async function ensureCompanyRecord() {
    if (companyRecord) {
      return companyRecord;
    }

    if (companyId) {
      const byId = await fetchCompanyById(companyId);
      if (byId) {
        setCompanyRecord(byId);
        return byId;
      }
    }

    const trimmedName = companyName.trim();
    if (!trimmedName) {
      return null;
    }

    const resolved = await ensureCompanyByName(trimmedName);
    if (resolved) {
      setCompanyRecord(resolved);
      return resolved;
    }

    return null;
  }

  async function persistReport(report: GeneratedReport) {
    const company = await ensureCompanyRecord();
    if (!company) {
      setSyncState("demo");
      return null;
    }

    setSyncState("syncing");
    try {
      const response = await fetch("/api/v1/analysis-reports", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          company_id: company.id,
          report_type: report.reportType,
          title: report.title,
          summary: report.summary,
          snapshot: {
            sections: report.sections,
            sources: report.sources,
            retrieval_stage: retrievalStage,
            tab_key: report.key,
            depth: report.depth,
            analysis: report.analysis,
          },
          model_name: "d-trust-agent",
        }),
      });
      if (!response.ok) {
        setSyncState("demo");
        return null;
      }
      setSyncState("synced");
      return (await response.json()) as PersistedAnalysisReport;
    } catch {
      setSyncState("demo");
      return null;
    }
  }

  function toComprehensiveReport(report: PersistedAnalysisReport): ComprehensiveReport {
    const sections = Array.isArray(report.snapshot?.assembled_reports)
      ? report.snapshot.assembled_reports.map((item) => ({
          title: item.title,
          summary: item.summary,
          reportType: item.report_type,
        }))
      : [];

    return {
      title: report.title,
      summary: report.summary,
      createdAt: report.generated_at.replace("T", " ").slice(0, 16),
      includedReportTypes: sections.map((item) => item.reportType),
      sections,
    };
  }

  function syncAssemblyItem(
    report: GeneratedReport,
    persistedReport?: PersistedAnalysisReport | null,
  ) {
    upsertAssemblyItem({
      tabKey: report.key,
      reportType: report.reportType,
      title: persistedReport?.title ?? report.title,
      summary: persistedReport?.summary ?? report.summary,
      depth: report.depth,
      status: "generated",
      generatedAt: persistedReport
        ? persistedReport.generated_at.replace("T", " ").slice(0, 16)
        : report.createdAt,
      includedAt: new Date().toISOString(),
    });
  }

  function restoreGeneratedReport(key: AnalysisTabKey) {
    const draftItem = assemblyItems.find((item) => item.tabKey === key);
    if (!draftItem) {
      return undefined;
    }

    const scenarioForTab = getAgentScenario(key, companyName);
    return {
      key,
      reportType: draftItem.reportType,
      title: draftItem.title,
      summary: draftItem.summary,
      createdAt: draftItem.generatedAt,
      depth: draftItem.depth,
      sections:
        draftItem.depth === "deep"
          ? scenarioForTab.deepSections
          : scenarioForTab.scanSections,
      sources: scenarioForTab.sources,
    } satisfies GeneratedReport;
  }

  async function handleGenerateCurrentReport() {
    const preview = remotePreview ?? (await fetchAgentPreview(activeTab));
    const report = reportFromPreview(activeTab, depth, preview);
    upsertReport(report);
    await persistReport(report);
  }

  async function handleDeepDive() {
    setDepthModes((current) => ({
      ...current,
      [activeTab]: "deep",
    }));
    const preview = remotePreview ?? (await fetchAgentPreview(activeTab));
    const report = reportFromPreview(activeTab, "deep", preview);
    upsertReport(report);
    await persistReport(report);
  }

  async function toggleIncludeReport(key: AnalysisTabKey) {
    const included = includedReportKeys.includes(key);
    if (included) {
      setIncludedReportKeys((current) => current.filter((item) => item !== key));
      removeAssemblyItem(key);
      return;
    }

    const preview = key === activeTab && remotePreview
      ? remotePreview
      : await fetchAgentPreview(key);
    const report = reportFromPreview(key, depthModes[key] ?? "scan", preview);
    upsertReport(report);
    setIncludedReportKeys((current) =>
      current.includes(key) ? current : [...current, key],
    );
    const persisted = await persistReport(report);
    syncAssemblyItem(report, persisted);
  }

  async function handleAddCurrentToComposer() {
    const preview = remotePreview ?? (await fetchAgentPreview(activeTab));
    const report = reportFromPreview(activeTab, depth, preview);
    upsertReport(report);
    setIncludedReportKeys((current) =>
      current.includes(activeTab) ? current : [...current, activeTab],
    );
    const persisted = await persistReport(report);
    syncAssemblyItem(report, persisted);
  }

  async function handleComposeReport() {
    const selectedKeys = includedReportKeys.length
      ? tabKeys.filter((key) => includedReportKeys.includes(key))
      : [activeTab];
    if (!includedReportKeys.length) {
      setIncludedReportKeys((current) =>
        current.includes(activeTab) ? current : [...current, activeTab],
      );
    }

    const selectedReports: GeneratedReport[] = [];
    for (const key of selectedKeys) {
      const preview = key === activeTab && remotePreview
        ? remotePreview
        : await fetchAgentPreview(key);
      const report = reportFromPreview(key, depthModes[key] ?? "scan", preview);
      selectedReports.push(report);
      upsertReport(report);
      const persisted = await persistReport(report);
      syncAssemblyItem(report, persisted);
    }

    const company = await ensureCompanyRecord();
    if (!company) {
      setComprehensiveReport(
        buildComprehensiveReport(companyName, selectedReports),
      );
      return;
    }

    try {
      setSyncState("syncing");
      const response = await fetch("/api/v1/analysis-reports/compose", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          company_id: company.id,
          report_types: selectedReports.map((item) => item.reportType),
          title: `${company.name} 综合风险报告`,
        }),
      });
      if (!response.ok) {
        setSyncState("demo");
        setComprehensiveReport(
          buildComprehensiveReport(companyName, selectedReports),
        );
        markComposed(`${companyName} 综合风险报告`);
        return;
      }
      const report = (await response.json()) as PersistedAnalysisReport;
      setSyncState("synced");
      setComprehensiveReport(toComprehensiveReport(report));
      markComposed(report.title);
    } catch {
      setSyncState("demo");
      setComprehensiveReport(
        buildComprehensiveReport(companyName, selectedReports),
      );
      markComposed(`${companyName} 综合风险报告`);
    }
  }

  return (
    <div className="space-y-6">
      <section className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-4xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#D7E6B3] bg-[#F4F8EA] px-3 py-1.5 text-xs font-medium text-[#5D7F17]">
              <Bot className="h-4 w-4" />
              {scenario.agentName}
            </div>
            <h3 className="font-brand-title mt-4 text-3xl font-semibold text-[#2D2D2D]">
              {scenario.headline}
            </h3>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-[#6F6A61]">
              {scenario.objective}
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className={ThemeConfig.surfaces.pill}>risk_events 优先</span>
              <span className={ThemeConfig.surfaces.pill}>FastAsk 回退</span>
              <span className={ThemeConfig.surfaces.pill}>向量去重</span>
              <span className={ThemeConfig.surfaces.pill}>来源可追溯</span>
              <span className={ThemeConfig.surfaces.pill}>
                {retrievalStage === "knowledge_base_fallback"
                  ? "当前需回退知识库"
                  : "当前命中结构化风险"}
              </span>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[360px]">
            <button
              type="button"
              onClick={handleGenerateCurrentReport}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#2D2D2D] px-4 py-3 text-sm font-medium text-white transition hover:bg-[#1F1F1F]"
            >
              <FileOutput className="h-4 w-4" />
              生成该维度报告
            </button>
            <button
              type="button"
              onClick={handleDeepDive}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[#D7E6B3] bg-[#F4F8EA] px-4 py-3 text-sm font-medium text-[#5D7F17] transition hover:bg-[#EEF6DF]"
            >
              <Sparkles className="h-4 w-4" />
              深度分析
            </button>
            <button
              type="button"
              onClick={handleAddCurrentToComposer}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[#E5E1D8] bg-white px-4 py-3 text-sm font-medium text-[#2D2D2D] transition hover:border-[#CFC9BD]"
            >
              <Layers3 className="h-4 w-4" />
              加入综合报告
            </button>
            <button
              type="button"
              onClick={handleComposeReport}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#86BC25] px-4 py-3 text-sm font-medium text-white transition hover:bg-[#769F21]"
            >
              <CheckCircle2 className="h-4 w-4" />
              组装综合风险报告
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-3">
          {scenario.retrievalFlow.map((item, index) => {
            const Icon =
              index === 0 ? DatabaseZap : index === 1 ? SearchCheck : Link2;
            return (
              <article
                key={item}
                className="rounded-2xl border border-[#E5E1D8] bg-[#FFFCF8] p-4 shadow-sm"
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#F4F8EA] text-[#5D7F17]">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[#2D2D2D]">
                      步骤 {index + 1}
                    </p>
                    <p className="mt-1 text-sm leading-6 text-[#6F6A61]">
                      {item}
                    </p>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="grid gap-6 2xl:grid-cols-[minmax(0,1.45fr)_360px]">
        <div className="space-y-6">
          <AgentDataPanel
            preview={remotePreview}
            loading={previewLoading}
            error={previewError}
          />

          <div className={`${ThemeConfig.surfaces.glassCard} p-6`}>
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm font-medium text-[#9E3D32]">单项报告预览</p>
                <h4 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
                  {currentReport?.title ?? `${scenario.agentName} 尚未生成正式报告`}
                </h4>
              </div>
              <div className="rounded-full border border-[#E5E1D8] bg-[#FFFCF8] px-4 py-2 text-sm text-[#6F6A61]">
                模式：{depth === "deep" ? "深度分析" : "快速检索"}
              </div>
            </div>

            <p className="mt-5 text-sm leading-7 text-[#6F6A61]">
              {effectiveSummary}
            </p>
            <div className="mt-4 inline-flex flex-wrap items-center gap-2 rounded-full border border-[#E5E1D8] bg-[#FFFCF8] px-4 py-2 text-xs text-[#6F6A61]">
              <span>
                {companyRecord
                  ? `公司档案已绑定：${companyRecord.name}`
                  : "当前未绑定 companies 记录"}
              </span>
              <span className="text-[#C9C1B3]">/</span>
              <span>
                {syncState === "syncing"
                  ? "报告同步中"
                  : syncState === "synced"
                    ? "报告已落库"
                    : syncState === "demo"
                      ? "当前使用本地 Demo 回退"
                      : "等待生成"}
              </span>
            </div>

            <div className="mt-6 grid gap-4 xl:grid-cols-2">
              {effectiveSections.map((section) => (
                <article
                  key={section.title}
                  className="rounded-2xl border border-[#E5E1D8] bg-[#FFFCF8] p-5 shadow-sm"
                >
                  <h5 className="text-lg font-semibold text-[#2D2D2D]">
                    {section.title}
                  </h5>
                  <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
                    {section.body}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {section.sourceIds.map((sourceId) => {
                      const source = reportSources.find((item) => item.id === sourceId);
                      if (!source) {
                        return null;
                      }

                      return (
                        <a
                          key={sourceId}
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-2 rounded-full border border-[#E5E1D8] bg-white px-3 py-1.5 text-xs font-medium text-[#2D2D2D] transition hover:border-[#9E3D32] hover:text-[#9E3D32]"
                        >
                          来源
                          <span className="text-[#6F6A61]">{source.sourceName}</span>
                        </a>
                      );
                    })}
                  </div>
                </article>
              ))}
            </div>
          </div>

          <div className={`${ThemeConfig.surfaces.glassCard} p-6`}>
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm font-medium text-[#9E3D32]">生成报告</p>
                <h4 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
                  自定义综合风险报告
                </h4>
              </div>
              <button
                type="button"
                onClick={handleComposeReport}
                className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#86BC25] px-4 py-3 text-sm font-medium text-white transition hover:bg-[#769F21]"
              >
                <Layers3 className="h-4 w-4" />
                重新生成
              </button>
            </div>

            <div className="mt-6 grid gap-4 xl:grid-cols-5">
              {ThemeConfig.analysisTabs.map((tab) => {
                const report =
                  generatedReports[tab.key] ?? restoreGeneratedReport(tab.key);
                const included = includedReportKeys.includes(tab.key);
                return (
                  <article
                    key={tab.key}
                    className={`rounded-2xl border p-4 shadow-sm ${
                      included
                        ? "border-[#D7E6B3] bg-[#F4F8EA]"
                        : "border-[#E5E1D8] bg-[#FFFCF8]"
                    }`}
                  >
                    <p className="text-sm font-medium text-[#2D2D2D]">
                      {tab.label}
                    </p>
                    <p className="mt-2 text-xs leading-6 text-[#6F6A61]">
                      {report
                        ? `${report.depth === "deep" ? "深度" : "快速"}报告已生成`
                        : "尚未生成该维度报告"}
                    </p>
                    <label className="mt-4 flex items-center gap-2 text-sm text-[#6F6A61]">
                      <input
                        type="checkbox"
                        checked={included}
                        onChange={() => {
                          void toggleIncludeReport(tab.key);
                        }}
                        className="h-4 w-4 rounded border-[#CFC9BD] text-[#86BC25]"
                      />
                      纳入综合报告
                    </label>
                  </article>
                );
              })}
            </div>

            {comprehensiveReport ? (
              <div className="mt-6 rounded-[28px] border border-[#E5E1D8] bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className="text-sm font-medium text-[#9E3D32]">综合报告</p>
                    <h5 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
                      {comprehensiveReport.title}
                    </h5>
                  </div>
                  <div className="rounded-full border border-[#E5E1D8] bg-[#FFFCF8] px-4 py-2 text-sm text-[#6F6A61]">
                    生成时间：{comprehensiveReport.createdAt}
                  </div>
                </div>

                <p className="mt-5 text-sm leading-7 text-[#6F6A61]">
                  {comprehensiveReport.summary}
                </p>

                <div className="mt-6 space-y-4">
                  {comprehensiveReport.sections.map((section) => (
                    <article
                      key={section.reportType}
                      className="rounded-2xl border border-[#E5E1D8] bg-[#FFFCF8] p-5"
                    >
                      <p className="text-lg font-semibold text-[#2D2D2D]">
                        {section.title}
                      </p>
                      <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
                        {section.summary}
                      </p>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <aside className="space-y-6">
          <div className={`${ThemeConfig.surfaces.glassCard} p-6`}>
            <p className="text-sm font-medium text-[#9E3D32]">数据来源</p>
            <h4 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
              可追溯来源侧栏
            </h4>
            <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
              当前 Demo 展示的是 `risk_events.source_url`、新闻链接和财报/PDF
              挂载位。正式接通后，每条风险数据都应直接显示“来源”标签，并跳转原始链接或 PDF 页码。
            </p>
            <div className="mt-5 space-y-3">
              {effectiveSources.map((source) => (
                <a
                  key={source.id}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block rounded-2xl border border-[#E5E1D8] bg-[#FFFCF8] p-4 shadow-sm transition hover:border-[#9E3D32]"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="rounded-full bg-[#F4F8EA] px-3 py-1 text-xs font-medium text-[#5D7F17]">
                      {source.kind}
                    </span>
                    <span className="text-xs text-[#6F6A61]">{source.publishedAt}</span>
                  </div>
                  <p className="mt-3 text-sm font-medium leading-6 text-[#2D2D2D]">
                    {source.title}
                  </p>
                  <p className="mt-2 text-xs leading-6 text-[#6F6A61]">
                    {source.sourceName}
                    {source.pageHint ? ` · ${source.pageHint}` : ""}
                  </p>
                  <p className="mt-2 text-xs leading-6 text-[#6F6A61]">
                    {source.note}
                  </p>
                  <div className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-[#9E3D32]">
                    来源
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </div>
                </a>
              ))}
            </div>
          </div>

          <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
            <p className="text-sm font-medium text-[#6F6A61]">建议深度分析方向</p>
            <div className="mt-4 space-y-3">
              {effectiveNextActions.map((item) => (
                <div
                  key={item}
                  className="rounded-2xl border border-[#E5E1D8] bg-white px-4 py-3 text-sm text-[#2D2D2D] shadow-sm"
                >
                  {item}
                </div>
              ))}
            </div>
          </div>

          <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
            <p className="text-sm font-medium text-[#6F6A61]">Agent 结论摘要</p>
            <div className="mt-4 space-y-3">
              {effectiveKeyPoints.map((item) => (
                <div
                  key={item}
                  className="flex gap-3 rounded-2xl border border-[#E5E1D8] bg-white p-4 shadow-sm"
                >
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#F8E9E5] text-[#9E3D32]">
                    <CheckCircle2 className="h-4 w-4" />
                  </div>
                  <p className="text-sm leading-6 text-[#6F6A61]">{item}</p>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </section>
    </div>
  );
}
