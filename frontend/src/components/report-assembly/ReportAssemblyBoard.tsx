"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  CheckCircle2,
  Download,
  FileOutput,
  Layers3,
  Plus,
  Trash2,
} from "lucide-react";

import { getAgentScenario } from "../analysis/agentWorkspaceData";
import {
  useReportAssembly,
  type AssemblyItem,
} from "../../lib/reportAssembly";
import {
  ThemeConfig,
  type AnalysisTabKey,
} from "../../theme/ThemeConfig";

type PersistedAnalysisReport = {
  id: string;
  report_type: string;
  title: string;
  summary: string;
  generated_at: string;
  snapshot: {
    depth?: "scan" | "deep";
    tab_key?: AnalysisTabKey;
    assembled_reports?: Array<{
      report_type: string;
      title: string;
      summary: string;
    }>;
  };
};

type ReportAssemblyBoardProps = {
  companyId?: string;
  companyName: string;
};

const orderedTabs = ThemeConfig.analysisTabs.map((item) => item.key);

function sortAssemblyItems(items: AssemblyItem[]) {
  return [...items].sort(
    (left, right) =>
      orderedTabs.indexOf(left.tabKey) - orderedTabs.indexOf(right.tabKey),
  );
}

function formatTimestamp(value: string) {
  return value.replace("T", " ").slice(0, 16);
}

function buildFallbackMarkdown(
  companyName: string,
  items: AssemblyItem[],
) {
  const createdAt = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());

  const sections = items
    .map((item) => `## ${item.title}\n\n${item.summary}`)
    .join("\n\n");

  return `# ${companyName} 综合风险报告

生成时间：${createdAt}

本次综合风险报告由 ${items.length} 个已生成维度自动汇总而成，用于统一导出和内部汇总。

${sections}
`;
}

function buildPersistedMarkdown(
  report: PersistedAnalysisReport,
  companyName: string,
) {
  const sections = Array.isArray(report.snapshot?.assembled_reports)
    ? report.snapshot.assembled_reports
        .map((item) => `## ${item.title}\n\n${item.summary}`)
        .join("\n\n")
    : "";

  return `# ${report.title || `${companyName} 综合风险报告`}

生成时间：${formatTimestamp(report.generated_at)}

${report.summary}

${sections}
`;
}

function triggerDownload(filename: string, content: string) {
  const blob = new Blob([content], {
    type: "text/markdown;charset=utf-8",
  });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.URL.revokeObjectURL(url);
}

function toAssemblyItem(
  tabKey: AnalysisTabKey,
  report: PersistedAnalysisReport,
): AssemblyItem {
  return {
    tabKey,
    reportType: report.report_type,
    title: report.title,
    summary: report.summary,
    depth: report.snapshot?.depth === "deep" ? "deep" : "scan",
    status: "generated",
    generatedAt: formatTimestamp(report.generated_at),
    includedAt: new Date().toISOString(),
  };
}

export function ReportAssemblyBoard({
  companyId,
  companyName,
}: ReportAssemblyBoardProps) {
  const {
    draft,
    items,
    upsertItem,
    removeItem,
    markComposed,
    clear,
  } = useReportAssembly(companyId, companyName);
  const [latestReports, setLatestReports] = useState<
    Partial<Record<AnalysisTabKey, PersistedAnalysisReport>>
  >({});
  const [composedReport, setComposedReport] =
    useState<PersistedAnalysisReport | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  const reportTypeToTab = useMemo(() => {
    return Object.fromEntries(
      ThemeConfig.analysisTabs.map((tab) => [
        getAgentScenario(tab.key, companyName || "目标公司").reportType,
        tab.key,
      ]),
    ) as Record<string, AnalysisTabKey>;
  }, [companyName]);

  const orderedItems = sortAssemblyItems(items);

  useEffect(() => {
    if (!companyId) {
      setLatestReports({});
      setComposedReport(null);
      return;
    }

    let ignore = false;

    async function loadReports() {
      try {
        const response = await fetch(
          `/api/v1/companies/${companyId}/analysis-reports?limit=50`,
          {
            method: "GET",
            cache: "no-store",
          },
        );

        if (!response.ok) {
          if (!ignore) {
            setLatestReports({});
            setComposedReport(null);
          }
          return;
        }

        const payload = (await response.json()) as PersistedAnalysisReport[];
        if (ignore) {
          return;
        }

        const latestByTab: Partial<Record<AnalysisTabKey, PersistedAnalysisReport>> =
          {};
        let latestComposed: PersistedAnalysisReport | null = null;

        for (const report of payload) {
          if (report.report_type === "comprehensive_risk_report") {
            if (!latestComposed) {
              latestComposed = report;
            }
            continue;
          }

          const tabKey = reportTypeToTab[report.report_type];
          if (tabKey && !latestByTab[tabKey]) {
            latestByTab[tabKey] = report;
          }
        }

        setLatestReports(latestByTab);
        setComposedReport(latestComposed);
      } catch {
        if (!ignore) {
          setLatestReports({});
          setComposedReport(null);
        }
      }
    }

    void loadReports();

    return () => {
      ignore = true;
    };
  }, [companyId, reportTypeToTab]);

  function toggleTabSelection(tabKey: AnalysisTabKey) {
    const existingItem = orderedItems.find((item) => item.tabKey === tabKey);
    if (existingItem) {
      removeItem(tabKey);
      return;
    }

    const report = latestReports[tabKey];
    if (!report) {
      return;
    }

    upsertItem(toAssemblyItem(tabKey, report));
  }

  async function handleExport() {
    if (!companyId || !orderedItems.length || isExporting) {
      return;
    }

    setIsExporting(true);
    try {
      const response = await fetch("/api/v1/analysis-reports/compose", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          company_id: companyId,
          report_types: orderedItems.map((item) => item.reportType),
          title: `${companyName} 综合风险报告`,
        }),
      });

      if (!response.ok) {
        triggerDownload(
          `${companyName}-综合风险报告.md`,
          buildFallbackMarkdown(companyName, orderedItems),
        );
        return;
      }

      const report = (await response.json()) as PersistedAnalysisReport;
      setComposedReport(report);
      markComposed(report.title);
      triggerDownload(
        `${companyName}-综合风险报告.md`,
        buildPersistedMarkdown(report, companyName),
      );
    } catch {
      triggerDownload(
        `${companyName}-综合风险报告.md`,
        buildFallbackMarkdown(companyName, orderedItems),
      );
    } finally {
      setIsExporting(false);
    }
  }

  if (!companyId) {
    return (
      <div className={`${ThemeConfig.surfaces.glassCard} p-8`}>
        <p className="text-sm font-medium text-[#9E3D32]">等待生成对象</p>
        <h3 className="font-brand-title mt-3 text-3xl font-semibold text-[#2D2D2D]">
          先检索一个目标公司，再进入生成报告
        </h3>
        <p className="mt-4 max-w-2xl text-sm leading-7 text-[#6F6A61]">
          当前没有可用的 `company_id`。请先在首页输入公司名称执行“开始检索”，系统会创建或解析公司档案后跳转到独立分析详情页。
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-4xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#D7E6B3] bg-[#F4F8EA] px-3 py-1.5 text-xs font-medium text-[#5D7F17]">
              <Layers3 className="h-4 w-4" />
              综合报告生成状态
            </div>
            <h3 className="font-brand-title mt-4 text-3xl font-semibold text-[#2D2D2D]">
              {companyName} 生成报告
            </h3>
            <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
              已加入综合报告的维度会在这里统一汇总。导出动作会调用后端综合报告生成接口，并生成可下载的 Markdown 报告文件。
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:min-w-[420px]">
            <button
              type="button"
              onClick={handleExport}
              disabled={!orderedItems.length || isExporting}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#2D2D2D] px-4 py-3 text-sm font-medium text-white transition hover:bg-[#1F1F1F] disabled:cursor-not-allowed disabled:bg-[#8A847A]"
            >
              <Download className="h-4 w-4" />
              {isExporting ? "导出中" : "统一导出综合报告"}
            </button>
            <button
              type="button"
              onClick={clear}
              disabled={!orderedItems.length}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[#E5E1D8] bg-white px-4 py-3 text-sm font-medium text-[#2D2D2D] transition hover:border-[#CFC9BD] disabled:cursor-not-allowed disabled:text-[#8A847A]"
            >
              <Trash2 className="h-4 w-4" />
              清空报告列表
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-full border border-[#E5E1D8] bg-[#FFFCF8] px-4 py-3 text-sm text-[#6F6A61]">
          <span>点击下方卡片即可选择或取消该维度是否纳入综合报告。</span>
          <span className="text-[#C9C1B3]">/</span>
          <span>只有已生成的维度可被选中。</span>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {ThemeConfig.analysisTabs.map((tab) => {
            const included = orderedItems.some((item) => item.tabKey === tab.key);
            const generated = Boolean(latestReports[tab.key]);
            const report = latestReports[tab.key];
            const disabled = !generated && !included;

            return (
              <button
                key={tab.key}
                type="button"
                disabled={disabled}
                onClick={() => toggleTabSelection(tab.key)}
                className={`rounded-2xl border p-5 text-left shadow-sm transition ${
                  included
                    ? "border-[#D7E6B3] bg-[#F4F8EA] shadow-[0_10px_24px_rgba(134,188,37,0.14)]"
                    : generated
                      ? "border-[#E5E1D8] bg-[#FFFCF8] hover:border-[#D7E6B3] hover:bg-[#F9FBF2]"
                      : "border-[#ECE7DE] bg-[#FCFAF6] opacity-70"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[#2D2D2D]">
                      {tab.label}
                    </p>
                    <p className="mt-3 text-xs leading-6 text-[#6F6A61]">
                      {included
                        ? "已选中，将进入综合报告"
                        : generated
                          ? "已生成，点击纳入综合报告"
                          : "尚未生成，暂不可选"}
                    </p>
                  </div>
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${
                      included
                        ? "bg-white text-[#5D7F17]"
                        : generated
                          ? "bg-[#F4F8EA] text-[#5D7F17]"
                          : "bg-white text-[#B2AB9F]"
                    }`}
                  >
                    {included ? (
                      <CheckCircle2 className="h-5 w-5" />
                    ) : (
                      <Plus className="h-5 w-5" />
                    )}
                  </div>
                </div>
                <div className="mt-4 rounded-2xl border border-[#E5E1D8] bg-white/80 px-4 py-3 text-xs leading-6 text-[#6F6A61]">
                  {report
                    ? `最新生成：${formatTimestamp(report.generated_at)}`
                    : "请先在对应 Agent 中生成单项报告"}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      <section className="grid gap-6 2xl:grid-cols-[minmax(0,1.35fr)_360px]">
        <div className={`${ThemeConfig.surfaces.glassCard} p-6`}>
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-medium text-[#9E3D32]">已加入维度</p>
              <h4 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
                当前待导出的综合报告清单
              </h4>
            </div>
            <div className="rounded-full border border-[#E5E1D8] bg-[#FFFCF8] px-4 py-2 text-sm text-[#6F6A61]">
              共 {orderedItems.length} / {ThemeConfig.analysisTabs.length} 个维度
            </div>
          </div>

          {orderedItems.length ? (
            <div className="mt-6 space-y-4">
              {orderedItems.map((item) => {
                const tab = ThemeConfig.analysisTabs.find(
                  (entry) => entry.key === item.tabKey,
                );
                const route = `/analysis/${companyId}?tab=${item.tabKey}&company=${encodeURIComponent(companyName)}`;

                return (
                  <article
                    key={item.tabKey}
                    className="rounded-2xl border border-[#E5E1D8] bg-[#FFFCF8] p-5 shadow-sm"
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="max-w-3xl">
                        <div className="inline-flex items-center gap-2 rounded-full border border-[#D7E6B3] bg-[#F4F8EA] px-3 py-1 text-xs font-medium text-[#5D7F17]">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          已生成
                        </div>
                        <h5 className="mt-3 text-xl font-semibold text-[#2D2D2D]">
                          {tab?.label}
                        </h5>
                        <p className="mt-2 text-sm leading-7 text-[#6F6A61]">
                          {item.summary}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-3">
                        <a
                          href={route}
                          className="inline-flex items-center gap-2 rounded-2xl border border-[#E5E1D8] bg-white px-4 py-3 text-sm font-medium text-[#2D2D2D] transition hover:border-[#CFC9BD]"
                        >
                          返回该 Agent
                          <ArrowUpRight className="h-4 w-4" />
                        </a>
                        <button
                          type="button"
                          onClick={() => removeItem(item.tabKey)}
                          className="inline-flex items-center gap-2 rounded-2xl border border-[#E5E1D8] bg-white px-4 py-3 text-sm font-medium text-[#2D2D2D] transition hover:border-[#9E3D32] hover:text-[#9E3D32]"
                        >
                          <Trash2 className="h-4 w-4" />
                          移出报告列表
                        </button>
                      </div>
                    </div>
                    <div className="mt-4 rounded-2xl border border-[#E5E1D8] bg-white px-4 py-3 text-sm text-[#6F6A61]">
                      报告标题：{item.title} · 生成时间：{item.generatedAt}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="mt-6 rounded-2xl border border-dashed border-[#D9D2C6] bg-[#FFFCF8] p-8">
              <p className="text-lg font-semibold text-[#2D2D2D]">
                还没有加入任何维度
              </p>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-[#6F6A61]">
                请先回到分析详情页，在任一 Agent 面板中点击“加入综合报告”。一旦加入，这里会立即同步显示，并可统一导出。
              </p>
            </div>
          )}
        </div>

        <aside className="space-y-6">
          <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
            <p className="text-sm font-medium text-[#6F6A61]">生成摘要</p>
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl border border-[#E5E1D8] bg-white p-4 shadow-sm">
                <p className="text-sm text-[#6F6A61]">已加入维度</p>
                <p className="mt-2 text-3xl font-semibold text-[#2D2D2D]">
                  {orderedItems.length}
                </p>
              </div>
              <div className="rounded-2xl border border-[#E5E1D8] bg-white p-4 shadow-sm">
                <p className="text-sm text-[#6F6A61]">最近生成时间</p>
                <p className="mt-2 text-base font-medium text-[#2D2D2D]">
                  {draft?.lastComposedAt
                    ? formatTimestamp(draft.lastComposedAt)
                    : "尚未导出"}
                </p>
              </div>
              <div className="rounded-2xl border border-[#E5E1D8] bg-white p-4 shadow-sm">
                <p className="text-sm text-[#6F6A61]">最近生成标题</p>
                <p className="mt-2 text-base font-medium text-[#2D2D2D]">
                  {draft?.lastComposedTitle || "尚未生成综合报告"}
                </p>
              </div>
            </div>
          </div>

          <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
            <p className="text-sm font-medium text-[#6F6A61]">导出预览</p>
            {composedReport ? (
              <div className="mt-4 space-y-3">
                <div className="rounded-2xl border border-[#E5E1D8] bg-white p-4 shadow-sm">
                  <div className="flex items-center gap-2 text-[#2D2D2D]">
                    <FileOutput className="h-4 w-4 text-[#5D7F17]" />
                    <p className="text-sm font-medium">{composedReport.title}</p>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
                    {composedReport.summary}
                  </p>
                </div>
              </div>
            ) : (
              <div className="mt-4 rounded-2xl border border-dashed border-[#D9D2C6] bg-white p-4 text-sm leading-7 text-[#6F6A61]">
                完成导出后，这里会显示最新一版综合风险报告摘要。
              </div>
            )}
          </div>
        </aside>
      </section>
    </div>
  );
}
