"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  ArrowUpRight,
  Search,
  Sparkles,
} from "lucide-react";

import { AgentWorkbench } from "../analysis/AgentWorkbench";
import { BrandSentimentPanel } from "../analysis/BrandSentimentPanel";
import { BusinessOperationsPanel } from "../analysis/BusinessOperationsPanel";
import { CompanyDetailPage } from "../company/CompanyDetailPage";
import { DataDashboard } from "../dashboard/DataDashboard";
import { FinancialHealthPanel } from "../analysis/FinancialHealthPanel";
import { LegalLitigationPanel } from "../analysis/LegalLitigationPanel";
import { MacroEnvironmentPanel } from "../analysis/MacroEnvironmentPanel";
import { KnowledgeBaseQA } from "../knowledge-base/KnowledgeBaseQA";
import { RegulatoryMeasuresBoard } from "../regulatory/RegulatoryMeasuresBoard";
import { ReportAssemblyBoard } from "../report-assembly/ReportAssemblyBoard";
import {
  fetchCompanyById,
  resolveCompanyByName,
  searchAndIngestCompany,
} from "../../lib/companyApi";
import {
  ThemeConfig,
  type AnalysisTopicKey,
  type AnalysisTabKey,
  type WorkspaceKey,
} from "../../theme/ThemeConfig";

type PageMode =
  | "home"
  | "company-detail"
  | "dashboard"
  | "analysis"
  | "topic-analysis"
  | "knowledge-base"
  | "assembly"
  | "regulatory-actions";

type LayoutProps = {
  pageMode?: PageMode;
  initialTab?: AnalysisTabKey;
  initialTopic?: AnalysisTopicKey;
  initialCompanyName?: string;
  initialCompanyId?: string;
};

function renderDashboardPanel(
  activeTab: AnalysisTabKey,
  companyName: string,
) {
  switch (activeTab) {
    case "macro":
      return <MacroEnvironmentPanel companyName={companyName} />;
    case "operations":
      return <BusinessOperationsPanel companyName={companyName} />;
    case "finance":
      return <FinancialHealthPanel companyName={companyName} />;
    case "legal":
      return <LegalLitigationPanel companyName={companyName} />;
    case "brand":
      return <BrandSentimentPanel companyName={companyName} />;
    default:
      return <MacroEnvironmentPanel companyName={companyName} />;
  }
}

const agentSupportCards = [
  {
    title: "单项报告预览",
    detail: "根据当前维度生成结构化预览，便于先审阅再汇总。",
  },
  {
    title: "生成报告",
    detail: "把已确认的维度结论加入自定义综合风险报告。",
  },
  {
    title: "数据来源",
    detail: "保留来源链接、采集时间与关键引用，支撑可追溯判断。",
  },
  {
    title: "建议深度分析方向",
    detail: "基于当前公司数据提出下一步深挖主题。",
  },
] as const;

export function Layout({
  pageMode = "home",
  initialTab = "macro",
  initialTopic = "macro",
  initialCompanyName = "比亚迪股份有限公司",
  initialCompanyId,
}: LayoutProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<AnalysisTabKey>(initialTab);
  const [companyName, setCompanyName] = useState(initialCompanyName);
  const [companyId, setCompanyId] = useState<string | null>(
    initialCompanyId ?? null,
  );
  const [isScanning, setIsScanning] = useState(false);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    setCompanyName(initialCompanyName);
  }, [initialCompanyName]);

  useEffect(() => {
    setCompanyId(initialCompanyId ?? null);
  }, [initialCompanyId]);

  useEffect(() => {
    const stableCompanyId = initialCompanyId;

    if (stableCompanyId) {
      if (initialCompanyName.trim()) {
        return;
      }

      const companyIdToLoad: string = stableCompanyId;
      let ignore = false;

      async function loadCompanyById() {
        const company = await fetchCompanyById(companyIdToLoad);
        if (!ignore && company?.name) {
          setCompanyName(company.name);
        }
      }

      void loadCompanyById();

      return () => {
        ignore = true;
      };
    }

    if (pageMode === "home" || !initialCompanyName.trim()) {
      return;
    }

    let ignore = false;

    async function resolveCompanyContext() {
      const company = await resolveCompanyByName(initialCompanyName);
      if (!ignore && company) {
        setCompanyId(company.id);
        setCompanyName(company.name);
      }
    }

    void resolveCompanyContext();

    return () => {
      ignore = true;
    };
  }, [initialCompanyId, initialCompanyName, pageMode]);

  const activeWorkspace: WorkspaceKey =
    pageMode === "knowledge-base"
      ? "knowledge-base"
      : pageMode === "topic-analysis"
        ? (ThemeConfig.analysisTopics.find((topic) => topic.key === initialTopic)
            ?.workspaceKey ?? "analysis-topic-macro")
      : pageMode === "assembly"
        ? "report-assembly"
        : pageMode === "regulatory-actions"
          ? "regulatory-actions"
          : pageMode === "dashboard"
            ? "dashboard"
            : "analysis-search";

  function buildWorkspaceHref(key: WorkspaceKey) {
    const encodedCompany = encodeURIComponent(companyName.trim());

    switch (key) {
      case "analysis-search":
        return "/";
      case "analysis-topic-macro":
        return "/analysis/topics/macro";
      case "analysis-topic-operations-finance":
        return "/analysis/topics/operations-finance";
      case "analysis-topic-legal-compliance":
        return "/analysis/topics/legal-compliance";
      case "analysis-topic-brand":
        return "/analysis/topics/brand";
      case "dashboard":
        return "/dashboard";
      case "knowledge-base":
        if (companyId) {
          return `/knowledge-base?companyId=${companyId}&company=${encodedCompany}&tab=${activeTab}`;
        }
        return companyName.trim()
          ? `/knowledge-base?company=${encodedCompany}&tab=${activeTab}`
          : "/knowledge-base";
      case "report-assembly":
        if (companyId) {
          return `/assembly?companyId=${companyId}&company=${encodedCompany}&tab=${activeTab}`;
        }
        return companyName.trim()
          ? `/assembly?company=${encodedCompany}&tab=${activeTab}`
          : "/assembly";
      case "regulatory-actions":
        return "/regulatory-actions";
      default:
        return "/";
    }
  }

  const activeTopic =
    ThemeConfig.analysisTopics.find((topic) => topic.key === initialTopic) ??
    ThemeConfig.analysisTopics[0];

  async function handleScan() {
    const trimmedName = companyName.trim();
    if (!trimmedName || isScanning) {
      return;
    }

    setIsScanning(true);
    const result = await searchAndIngestCompany({
      companyName: trimmedName,
      triggerIngestion: true,
    });
    setIsScanning(false);

    if (!result?.company) {
      router.push(`/companies/search?company=${encodeURIComponent(trimmedName)}`);
      return;
    }

    const company = result.company;
    setCompanyId(company.id);
    setCompanyName(company.name);
    router.push(
      `/companies/${company.id}?company=${encodeURIComponent(company.name)}`,
    );
  }

  function renderSearchBox() {
    return (
      <>
        <div className="relative">
          <div className="pointer-events-none absolute inset-x-12 -top-6 h-20 rounded-full bg-[#D5EAB5] opacity-70 blur-3xl" />
          <div className="relative rounded-lg border border-[#D8DECF] bg-white p-3 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row">
              <div className="flex flex-1 items-center gap-4 rounded-lg bg-[#F7F8F6] px-5 py-5">
                <Search className="h-6 w-6 text-[#5F6360]" />
                <input
                  value={companyName}
                  onChange={(event) => setCompanyName(event.target.value)}
                  placeholder="输入公司名称，立即开始检索"
                  className="w-full border-0 bg-transparent text-base text-[#171717] outline-none placeholder:text-[#7B807B] md:text-lg"
                />
              </div>
              <button
                type="button"
                onClick={handleScan}
                disabled={isScanning}
                className="relative inline-flex h-[68px] items-center justify-center gap-2 overflow-hidden rounded-lg bg-[#86BC25] px-7 text-base font-semibold text-[#0E0E0E] transition hover:bg-[#78A922] disabled:cursor-not-allowed disabled:bg-[#BFD98A]"
              >
                {isScanning ? <span className="scan-sheen" /> : null}
                <Sparkles className="relative z-10 h-5 w-5" />
                <span className="relative z-10">
                  {isScanning ? "检索中" : "开始检索"}
                </span>
              </button>
            </div>
          </div>
        </div>
      </>
    );
  }

  function renderHomePage() {
    return (
      <>
        <section
          className={`${ThemeConfig.surfaces.glassCard} mx-auto max-w-[1380px] p-6 md:p-8 lg:p-10`}
        >
          <div className="mx-auto max-w-[980px] text-center">
            <div className="flex justify-center">
              <div className="inline-flex items-center gap-2 rounded-md border border-[#B7DB82] bg-[#EEF7E0] px-4 py-2 text-sm font-medium text-[#2B5010]">
                <Sparkles className="h-4 w-4" />
                D.Analysis / 搜索
              </div>
            </div>
            <h2 className="font-brand-title mt-6 text-4xl font-semibold tracking-tight text-[#171717] md:text-6xl">
              {ThemeConfig.brand}
            </h2>
            <p className="mt-5 text-xl font-semibold text-[#171717] md:text-3xl">
              {ThemeConfig.heroTitle}
            </p>
            <p className="mx-auto mt-5 max-w-4xl text-base leading-8 text-[#5F6360] md:text-lg">
              {ThemeConfig.heroSubtitle}
            </p>

            <div className="mt-10">{renderSearchBox()}</div>
          </div>
        </section>
      </>
    );
  }

  function renderDashboardPage() {
    return <DataDashboard />;
  }

  function renderAnalysisPage() {
    return (
      <section className="mx-auto max-w-[1380px]">
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => router.push("/")}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#C9D1C4] bg-white px-4 py-3 text-sm font-medium text-[#171717] transition hover:border-[#86BC25]"
          >
            返回开始分析
          </button>
        </div>

        <section className="mt-6">
          <AgentWorkbench
            activeTab={activeTab}
            companyName={companyName}
            companyId={companyId ?? undefined}
          >
            {renderDashboardPanel(activeTab, companyName)}
          </AgentWorkbench>
        </section>

        <section className="mt-8 grid gap-4 lg:grid-cols-4">
          {agentSupportCards.map((item) => (
            <article
              key={item.title}
              className={`${ThemeConfig.surfaces.glassCardMuted} p-5`}
            >
              <p className="text-sm font-semibold text-[#2B5010]">
                {item.title}
              </p>
              <p className="mt-3 text-sm leading-6 text-[#5F6360]">
                {item.detail}
              </p>
            </article>
          ))}
        </section>
      </section>
    );
  }

  function renderTopicAnalysisPage() {
    return (
      <section className="mx-auto max-w-[1380px] space-y-8">
        <section className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-8`}>
          <p className="text-sm font-semibold text-[#2B5010]">
            {activeTopic.eyebrow}
          </p>
          <h2 className="font-brand-title mt-3 text-4xl font-semibold text-[#171717] md:text-5xl">
            {activeTopic.title}
          </h2>
          <p className="mt-4 max-w-4xl text-sm leading-7 text-[#5F6360]">
            {activeTopic.description}
          </p>
        </section>

        <section className="grid gap-5 lg:grid-cols-2">
          {activeTopic.sections.map((section) => (
            <article
              key={section.title}
              className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}
            >
              <p className="text-sm font-semibold text-[#2B5010]">
                {section.title}
              </p>
              <p className="mt-3 text-sm leading-7 text-[#5F6360]">
                {section.description}
              </p>
              <div className="mt-5 grid gap-3">
                {section.items.map((item) => (
                  <div
                    key={item}
                    className="rounded-lg border border-[#D8DECF] bg-white px-4 py-3 text-sm text-[#171717]"
                  >
                    {item}
                  </div>
                ))}
              </div>
            </article>
          ))}
        </section>

        <section className={`${ThemeConfig.surfaces.glassCard} p-6`}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm font-semibold text-[#2B5010]">
                建议深度分析方向
              </p>
              <p className="mt-2 text-sm leading-7 text-[#5F6360]">
                专题入口用于行业和风险主题研究；如需生成某家公司的五维 Agent 报告，请先从搜索进入企业总览。
              </p>
            </div>
            <button
              type="button"
              onClick={() => router.push("/")}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#86BC25] px-5 py-3 text-sm font-semibold text-[#0E0E0E] transition hover:bg-[#78A922]"
            >
              进入企业搜索
              <ArrowUpRight className="h-4 w-4" />
            </button>
          </div>
        </section>
      </section>
    );
  }

  function renderCompanyDetailPage() {
    return (
      <CompanyDetailPage
        companyId={companyId ?? undefined}
        initialCompanyName={companyName}
      />
    );
  }

  function renderKnowledgeBasePage() {
    return (
      <section className="mx-auto max-w-[1380px]">
        <div className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-8`}>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-medium text-[#2B5010]">
                Knowledge Base Q&amp;A
              </p>
              <h2 className="font-brand-title mt-3 text-4xl font-semibold text-[#171717] md:text-5xl">
                面向 {companyName} 的知识库问答
              </h2>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-[#5F6360]">
                问答优先读取 PostgreSQL 中的结构化 `risk_events`，命中不足时再回退到 FastAsk 知识库补充非结构化文档。
              </p>
            </div>
            <div className="inline-flex items-center gap-2 rounded-md border border-[#D8DECF] bg-white px-4 py-2 text-sm text-[#5F6360]">
              PostgreSQL + FastAsk
              <ArrowUpRight className="h-4 w-4 text-[#2B5010]" />
            </div>
          </div>
        </div>

        <section className="mt-8">
          <KnowledgeBaseQA companyName={companyName} />
        </section>
      </section>
    );
  }

  function renderAssemblyPage() {
    return (
      <section className="mx-auto max-w-[1380px]">
        <div className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-8`}>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-medium text-[#2B5010]">生成报告</p>
              <h2 className="font-brand-title mt-3 text-4xl font-semibold text-[#171717] md:text-5xl">
                {companyName} 综合风险报告生成
              </h2>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-[#5F6360]">
                在各个 Agent 面板点击“加入综合报告”后，维度状态会同步到这里。你可以统一查看已生成的维度、移除不需要的部分，并最终生成和导出综合风险报告。
              </p>
            </div>
            <button
              type="button"
              onClick={() =>
                companyId
                  ? router.push(
                      `/analysis/${companyId}?tab=${activeTab}&company=${encodeURIComponent(companyName.trim())}`,
                    )
                  : router.push("/")
              }
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#C9D1C4] bg-white px-4 py-3 text-sm font-medium text-[#171717] transition hover:border-[#86BC25]"
            >
              {companyId ? "返回分析详情页" : "返回开始分析"}
            </button>
          </div>
        </div>

        <section className="mt-8">
          <ReportAssemblyBoard
            companyId={companyId ?? undefined}
            companyName={companyName}
          />
        </section>
      </section>
    );
  }

  function renderRegulatoryActionsPage() {
    return (
      <section className="mx-auto max-w-[1480px]">
        <RegulatoryMeasuresBoard />
      </section>
    );
  }

  return (
    <div
      className={`min-h-screen overflow-hidden text-[#2D2D2D] ${ThemeConfig.surfaces.canvas}`}
    >
      <div className="relative flex min-h-screen flex-col lg:flex-row">
        <aside className="w-full border-b border-[#20231F] bg-[#0B0F0C] text-white lg:w-[304px] lg:border-b-0 lg:border-r">
          <div className="flex h-full flex-col px-5 py-6">
            <div>
              <div className="flex items-center gap-3">
                <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-white">
                  <Image
                    src="/deloitte-logo.svg"
                    alt="Deloitte"
                    width={44}
                    height={44}
                    priority
                  />
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#86BC25]">
                    Risk Intelligence
                  </p>
                  <h1 className="font-brand-title mt-1 text-2xl font-semibold text-white">
                    {ThemeConfig.brand}
                  </h1>
                </div>
              </div>
              <p className="mt-4 border-l-2 border-[#86BC25] pl-3 text-xs leading-5 text-[#BFC7BD]">
                Deloitte-inspired enterprise risk analysis workspace.
              </p>
            </div>

            <div className="mt-9 grid gap-7">
              {ThemeConfig.sidebarGroups.map((group) => (
                <div key={group.label}>
                  <p className="px-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#86BC25]">
                    {group.label}
                  </p>
                  <div className="mt-3 grid gap-2">
                    {group.items.map((item) => {
                      const Icon = item.icon;
                      const isActive = activeWorkspace === item.key;
                      return (
                        <button
                          key={item.key}
                          type="button"
                          onClick={() => router.push(buildWorkspaceHref(item.key))}
                          className={`flex items-start gap-3 rounded-lg px-3 py-3 text-left transition ${
                            isActive
                              ? "border border-[#86BC25] bg-[#17220F] text-white shadow-sm"
                              : "border border-transparent text-[#C9D1C4] hover:border-[#2C332B] hover:bg-[#151A16] hover:text-white"
                          }`}
                        >
                          <div
                            className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${
                              isActive
                                ? "bg-[#86BC25] text-[#0B0F0C]"
                                : "bg-[#1C221D] text-[#86BC25]"
                            }`}
                          >
                            <Icon className="h-4 w-4" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold">{item.label}</p>
                            <p className="mt-1 text-xs leading-5 opacity-75">
                              {item.hint}
                            </p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-auto grid gap-2 pt-10">
              {ThemeConfig.footerItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.key}
                    type="button"
                    className="flex items-center gap-3 rounded-lg border border-transparent px-3 py-3 text-left text-[#C9D1C4] transition hover:border-[#2C332B] hover:bg-[#151A16] hover:text-white"
                  >
                    <div className="flex h-9 w-9 items-center justify-center rounded-md bg-[#1C221D] text-[#86BC25]">
                      <Icon className="h-4 w-4" />
                    </div>
                    <span className="text-sm font-medium">{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[1480px] px-5 py-8 md:px-8 lg:px-10 lg:py-10">
            {pageMode === "home"
              ? renderHomePage()
              : pageMode === "company-detail"
                ? renderCompanyDetailPage()
              : pageMode === "dashboard"
                ? renderDashboardPage()
                : pageMode === "analysis"
                  ? renderAnalysisPage()
                  : pageMode === "topic-analysis"
                    ? renderTopicAnalysisPage()
                    : pageMode === "knowledge-base"
                      ? renderKnowledgeBasePage()
                      : pageMode === "assembly"
                        ? renderAssemblyPage()
                        : renderRegulatoryActionsPage()}
          </div>
        </main>
      </div>
    </div>
  );
}
