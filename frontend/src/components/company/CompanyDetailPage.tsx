"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUpRight,
  Building2,
  CalendarDays,
  DatabaseZap,
  Landmark,
  MapPin,
  UserRound,
} from "lucide-react";

import { fetchCompanyById, type CompanyRecord } from "../../lib/companyApi";
import { ThemeConfig } from "../../theme/ThemeConfig";

type QichachaPerson = {
  name?: string;
  position?: string;
};

type QichachaShareholder = {
  name?: string;
  ratio?: string;
  capital?: string;
};

type QichachaChangeRecord = {
  project?: string;
  before?: string;
  after?: string;
  changed_at?: string;
};

type QichachaProfile = {
  status?: string;
  source?: string;
  reason?: string;
  message?: string;
  updated_at?: string;
  company_name?: string;
  legal_representative?: string;
  registered_capital?: string;
  start_date?: string;
  approved_date?: string;
  register_status?: string;
  credit_code?: string;
  company_type?: string;
  registration_authority?: string;
  address?: string;
  business_scope?: string;
  industry?: string;
  major_personnel?: QichachaPerson[];
  shareholders?: QichachaShareholder[];
  change_records?: QichachaChangeRecord[];
};

type CompanyDetailPageProps = {
  companyId?: string;
  initialCompanyName?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getQichachaProfile(company: CompanyRecord | null): QichachaProfile | null {
  const profile = company?.company_profile;
  if (!isRecord(profile)) {
    return null;
  }
  const qichachaProfile = profile.qichacha_profile;
  return isRecord(qichachaProfile) ? (qichachaProfile as QichachaProfile) : null;
}

function getAkshareProfile(company: CompanyRecord | null): Record<string, unknown> | null {
  const profile = company?.company_profile;
  if (!isRecord(profile)) {
    return null;
  }
  const akshareProfile = profile.akshare_profile;
  return isRecord(akshareProfile) ? akshareProfile : null;
}

function fieldValue(value: string | null | undefined) {
  return value && value.trim() ? value : "暂未获取";
}

function profileText(source: Record<string, unknown> | null, key: string) {
  const value = source?.[key];
  return typeof value === "string" && value.trim() ? value : "";
}

function nestedProfileText(
  source: Record<string, unknown> | null,
  objectKey: string,
  valueKey: string,
) {
  const nested = source?.[objectKey];
  if (!isRecord(nested)) {
    return "";
  }
  const value = nested[valueKey];
  return typeof value === "string" && value.trim() ? value : "";
}

function formatFinancialAmount(value: string) {
  if (!value) {
    return "";
  }
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return value;
  }
  return `${(amount / 100_000_000).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 亿元`;
}

function buildSparkline(points: number[]) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  return points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * 110;
      const y = 34 - ((point - min) / Math.max(max - min, 1)) * 26;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

const overviewSignals = [
  {
    label: "宏观环境及行业",
    value: "政策利好偏强，行业价格竞争仍需跟踪。",
  },
  {
    label: "业务运营",
    value: "交付链路改善，区域渠道节奏存在分化。",
  },
  {
    label: "财务状况",
    value: "营收与现金流同步改善，需关注资本开支节奏。",
  },
  {
    label: "法律诉讼",
    value: "合同纠纷与执行信息建议保持高频预警。",
  },
  {
    label: "品牌舆情",
    value: "价格战与产品口碑是近期舆情核心议题。",
  },
];

export function CompanyDetailPage({
  companyId,
  initialCompanyName = "",
}: CompanyDetailPageProps) {
  const router = useRouter();
  const [company, setCompany] = useState<CompanyRecord | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(companyId));

  useEffect(() => {
    if (!companyId) {
      setIsLoading(false);
      return;
    }

    const companyIdToLoad = companyId;
    let ignore = false;
    async function loadCompany() {
      setIsLoading(true);
      const data = await fetchCompanyById(companyIdToLoad);
      if (!ignore) {
        setCompany(data);
        setIsLoading(false);
      }
    }

    void loadCompany();

    return () => {
      ignore = true;
    };
  }, [companyId]);

  const qichachaProfile = getQichachaProfile(company);
  const akshareProfile = getAkshareProfile(company);
  const isProfileAvailable = qichachaProfile?.status === "available";
  const isAkshareAvailable = akshareProfile?.status === "available";
  const displayName =
    qichachaProfile?.company_name || company?.name || initialCompanyName || "目标公司";
  const stockCode = profileText(akshareProfile, "stock_code");
  const stockName = profileText(akshareProfile, "stock_name");
  const akshareMessage = profileText(akshareProfile, "message");
  const revenue = formatFinancialAmount(
    nestedProfileText(akshareProfile, "financial_highlights", "revenue"),
  );
  const netProfit = formatFinancialAmount(
    nestedProfileText(akshareProfile, "financial_highlights", "net_profit"),
  );
  const marketValue = nestedProfileText(akshareProfile, "financial_highlights", "market_value");
  const industryFromAkshare = nestedProfileText(akshareProfile, "financial_highlights", "industry");

  const kpiCards = useMemo(
    () => [
      {
        label: "营收",
        value: revenue || "待获取",
        trend: revenue ? "AkShare 财务摘要" : "等待上市公司财务数据",
        tone: "positive",
        points: [18, 28, 24, 38, 44, 58],
      },
      {
        label: "净利润",
        value: netProfit || "待获取",
        trend: netProfit ? "最新财务摘要" : "等待利润数据",
        tone: "positive",
        points: [16, 20, 22, 30, 28, 36],
      },
      {
        label: "风险指数",
        value: isAkshareAvailable ? "62" : "待评估",
        trend: isAkshareAvailable ? "中等风险，需持续监测" : "缺少实时数据",
        tone: "warning",
        points: [34, 40, 38, 46, 44, 52],
      },
      {
        label: "总市值",
        value: marketValue || "待获取",
        trend: stockCode ? `${stockName || displayName} / ${stockCode}` : "未匹配上市代码",
        tone: "neutral",
        points: [44, 42, 50, 48, 54, 56],
      },
      {
        label: "行业",
        value: industryFromAkshare || company?.industry || "待识别",
        trend: isAkshareAvailable ? "来自 AkShare 个股信息" : "自由搜索档案",
        tone: "neutral",
        points: [22, 24, 27, 31, 35, 37],
      },
    ],
    [
      company?.industry,
      displayName,
      industryFromAkshare,
      isAkshareAvailable,
      marketValue,
      netProfit,
      revenue,
      stockCode,
      stockName,
    ],
  );

  const fields = useMemo(
    () => [
      {
        label: "法定代表人",
        value: fieldValue(qichachaProfile?.legal_representative),
        icon: UserRound,
      },
      {
        label: "成立日期",
        value: fieldValue(qichachaProfile?.start_date),
        icon: CalendarDays,
      },
      {
        label: "登记状态",
        value: fieldValue(qichachaProfile?.register_status),
        icon: DatabaseZap,
      },
      {
        label: "注册资本",
        value: fieldValue(qichachaProfile?.registered_capital),
        icon: Landmark,
      },
      {
        label: "统一社会信用代码",
        value: fieldValue(qichachaProfile?.credit_code || company?.credit_code),
        icon: Building2,
      },
      {
        label: "所属行业",
        value: fieldValue(qichachaProfile?.industry || company?.industry),
        icon: Building2,
      },
      {
        label: "企业类型",
        value: fieldValue(qichachaProfile?.company_type),
        icon: Building2,
      },
      {
        label: "登记机关",
        value: fieldValue(qichachaProfile?.registration_authority),
        icon: Landmark,
      },
      {
        label: "核准日期",
        value: fieldValue(qichachaProfile?.approved_date),
        icon: CalendarDays,
      },
    ],
    [company, qichachaProfile],
  );

  const changeRecords = qichachaProfile?.change_records ?? [];
  const majorPersonnel = qichachaProfile?.major_personnel ?? [];
  const shareholders = qichachaProfile?.shareholders ?? [];

  function openAnalysis(tabKey: string) {
    const encodedCompany = encodeURIComponent(displayName);
    router.push(
      companyId
        ? `/analysis/${companyId}?tab=${tabKey}&company=${encodedCompany}`
        : `/analysis?tab=${tabKey}&company=${encodedCompany}`,
    );
  }

  if (isLoading) {
    return (
      <section className="mx-auto max-w-[1380px]">
        <div className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-8`}>
          <p className="text-sm font-medium text-[#6F6A61]">正在读取企业档案...</p>
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-[1380px] space-y-8">
      <section className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-8`}>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-md border border-[#B7DB82] bg-[#EEF7E0] px-3 py-1.5 text-xs font-medium text-[#2B5010]">
              <Building2 className="h-4 w-4" />
              D.Analysis / 搜索总览
            </div>
            <h2 className="font-brand-title mt-4 text-4xl font-semibold text-[#2D2D2D] md:text-5xl">
              {displayName}
            </h2>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-[#6F6A61]">
              先确认企业主体、股东关联、图谱线索和关键风险数据，再进入宏观、业务、财务、法律和品牌舆情五个维度展开分析。
            </p>
          </div>
          <div className="grid gap-2 text-sm">
            <div
              className={`rounded-lg border px-4 py-3 ${
                isAkshareAvailable
                  ? "border-[#86BC25] bg-[#EEF7E0] text-[#2B5010]"
                  : "border-[#D8DECF] bg-[#FAFBF8] text-[#5F6360]"
              }`}
            >
              {isAkshareAvailable
                ? `AkShare 已匹配 ${stockName || displayName}${stockCode ? ` / ${stockCode}` : ""}`
                : akshareMessage || "AkShare 暂未匹配上市公司，可继续自由搜索总览"}
            </div>
            <div
              className={`rounded-lg border px-4 py-3 ${
                isProfileAvailable
                  ? "border-[#D7E6B3] bg-[#F4F8EA] text-[#5D7F17]"
                  : "border-[#EFE4D8] bg-[#FFF8F2] text-[#9E3D32]"
              }`}
            >
              {isProfileAvailable
                ? "企查查官方 API 已返回档案"
                : qichachaProfile?.message || "企查查未配置，先使用 AkShare / 自由搜索档案"}
            </div>
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {kpiCards.map((card) => (
            <article
              key={card.label}
              className="rounded-lg border border-[#D8DECF] bg-[#FAFBF8] p-5"
            >
              <p className="text-sm font-semibold text-[#5F6360]">{card.label}</p>
              <p className="mt-3 truncate text-2xl font-semibold text-[#171717]">
                {card.value}
              </p>
              <p className="mt-2 min-h-10 text-xs leading-5 text-[#5F6360]">
                {card.trend}
              </p>
              <svg
                viewBox="0 0 110 40"
                className="mt-3 h-10 w-full"
                fill="none"
                aria-label={`${card.label}趋势线`}
              >
                <path
                  d={buildSparkline(card.points)}
                  stroke={card.tone === "warning" ? "#B7791F" : "#86BC25"}
                  strokeWidth="3"
                  strokeLinecap="round"
                />
              </svg>
            </article>
          ))}
        </div>

        <div className="mt-8 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          <article className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
            <p className="text-sm font-semibold text-[#2B5010]">
              企业图谱与关联方
            </p>
            <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
              用节点和连线展示企业、股东、管理层与风险事件的关系。当前先基于已获取档案生成轻量图谱，后续可替换为可交互 Knowledge Graph 组件。
            </p>
            <div className="relative mt-6 min-h-[320px] rounded-lg border border-[#D8DECF] bg-white p-5">
              <div className="absolute left-1/2 top-1/2 z-10 flex h-28 w-28 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-[#86BC25] bg-[#EEF7E0] px-4 text-center text-sm font-semibold text-[#171717]">
                {displayName}
              </div>
              {[
                { label: "股东层", className: "left-6 top-8" },
                { label: "主要人员", className: "right-6 top-8" },
                { label: stockCode ? `股票 ${stockCode}` : "上市信息", className: "left-8 bottom-8" },
                { label: "风险事件", className: "right-8 bottom-8" },
              ].map((node) => (
                <div
                  key={node.label}
                  className={`absolute z-10 rounded-lg border border-[#D8DECF] bg-[#FAFBF8] px-4 py-3 text-sm font-semibold text-[#171717] ${node.className}`}
                >
                  {node.label}
                </div>
              ))}
              <svg
                viewBox="0 0 600 320"
                className="absolute inset-0 h-full w-full"
                fill="none"
                aria-hidden="true"
              >
                <path d="M300 160 L95 65" stroke="#86BC25" strokeWidth="2" strokeDasharray="6 6" />
                <path d="M300 160 L505 65" stroke="#86BC25" strokeWidth="2" strokeDasharray="6 6" />
                <path d="M300 160 L110 255" stroke="#86BC25" strokeWidth="2" strokeDasharray="6 6" />
                <path d="M300 160 L500 255" stroke="#86BC25" strokeWidth="2" strokeDasharray="6 6" />
              </svg>
            </div>
          </article>

          <article className={`${ThemeConfig.surfaces.glassCard} p-6`}>
            <p className="text-sm font-semibold text-[#2B5010]">AI 建议总结</p>
            <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
              按五大维度给出初步研判。接入 LLM 后，这里可以基于 AkShare、风险事件和知识库上下文实时生成。
            </p>
            <div className="mt-5 grid gap-3">
              {overviewSignals.map((signal) => (
                <div
                  key={signal.label}
                  className="rounded-lg border border-[#D8DECF] bg-[#FAFBF8] p-4"
                >
                  <p className="text-sm font-semibold text-[#171717]">
                    {signal.label}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-[#5F6360]">
                    {signal.value}
                  </p>
                </div>
              ))}
            </div>
          </article>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {fields.map((field) => {
            const Icon = field.icon;
            return (
              <article
                key={field.label}
                className="rounded-lg border border-[#D8DECF] bg-[#FAFBF8] p-5"
              >
                <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-white text-[#2B5010]">
                      <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm text-[#6F6A61]">{field.label}</p>
                    <p className="mt-1 break-words text-base font-semibold text-[#2D2D2D]">
                      {field.value}
                    </p>
                  </div>
                </div>
              </article>
            );
          })}
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <article className="rounded-lg border border-[#D8DECF] bg-white p-5">
            <div className="flex items-center gap-2 text-sm font-medium text-[#2B5010]">
              <MapPin className="h-4 w-4" />
              注册地址
            </div>
            <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
              {fieldValue(qichachaProfile?.address || company?.region)}
            </p>
          </article>
          <article className="rounded-lg border border-[#D8DECF] bg-white p-5">
            <div className="flex items-center gap-2 text-sm font-medium text-[#2B5010]">
              <Building2 className="h-4 w-4" />
              经营范围
            </div>
            <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
              {fieldValue(qichachaProfile?.business_scope || company?.description)}
            </p>
          </article>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-3">
        <article className={`${ThemeConfig.surfaces.glassCardMuted} p-6 xl:col-span-1`}>
          <p className="text-sm font-medium text-[#9E3D32]">法人 / 主要人员</p>
          <div className="mt-4 space-y-3">
            {majorPersonnel.length ? (
              majorPersonnel.slice(0, 6).map((person, index) => (
                <div
                  key={`${person.name}-${person.position}-${index}`}
                  className="rounded-2xl border border-[#E5E1D8] bg-white px-4 py-3"
                >
                  <p className="font-medium text-[#2D2D2D]">
                    {person.name || "未披露姓名"}
                  </p>
                  <p className="mt-1 text-sm text-[#6F6A61]">
                    {person.position || "未披露职务"}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm leading-7 text-[#6F6A61]">
                暂未获取主要人员信息。配置企查查官方 API 后，这里会展示法人和管理层摘要。
              </p>
            )}
          </div>
        </article>

        <article className={`${ThemeConfig.surfaces.glassCardMuted} p-6 xl:col-span-1`}>
          <p className="text-sm font-medium text-[#9E3D32]">股东信息</p>
          <div className="mt-4 space-y-3">
            {shareholders.length ? (
              shareholders.slice(0, 6).map((shareholder, index) => (
                <div
                  key={`${shareholder.name}-${index}`}
                  className="rounded-2xl border border-[#E5E1D8] bg-white px-4 py-3"
                >
                  <p className="font-medium text-[#2D2D2D]">
                    {shareholder.name || "未披露股东"}
                  </p>
                  <p className="mt-1 text-sm text-[#6F6A61]">
                    {shareholder.ratio || "持股比例待获取"}
                    {shareholder.capital ? ` · ${shareholder.capital}` : ""}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm leading-7 text-[#6F6A61]">
                暂未获取股东信息。后续 API 返回后会在这里展示核心出资人。
              </p>
            )}
          </div>
        </article>

        <article className={`${ThemeConfig.surfaces.glassCardMuted} p-6 xl:col-span-1`}>
          <p className="text-sm font-medium text-[#9E3D32]">最近变更</p>
          <div className="mt-4 space-y-3">
            {changeRecords.length ? (
              changeRecords.slice(0, 5).map((record, index) => (
                <div
                  key={`${record.project}-${record.changed_at}-${index}`}
                  className="rounded-2xl border border-[#E5E1D8] bg-white px-4 py-3"
                >
                  <p className="font-medium text-[#2D2D2D]">
                    {record.project || "工商变更"}
                  </p>
                  <p className="mt-1 text-xs text-[#8A847A]">
                    {record.changed_at || "日期待获取"}
                  </p>
                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-[#6F6A61]">
                    {record.before ? `变更前：${record.before}；` : ""}
                    {record.after ? `变更后：${record.after}` : ""}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm leading-7 text-[#6F6A61]">
                暂未获取法人变更或工商变更记录。五个 Agent 分析仍可继续进入。
              </p>
            )}
          </div>
        </article>
      </section>

      <section className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-8`}>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-[#5D7F17]">进入分析维度</p>
            <h3 className="font-brand-title mt-3 text-3xl font-semibold text-[#2D2D2D]">
              选择一个 Agent 开始深度分析
            </h3>
          </div>
          <p className="max-w-2xl text-sm leading-7 text-[#6F6A61]">
            二级页只负责确认企业主体与档案；每个维度的来源侧栏、分析过程和报告生成会在独立详情页完成。
          </p>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-5">
          {ThemeConfig.analysisTabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => openAnalysis(tab.key)}
                className="group rounded-2xl border border-[#E5E1D8] bg-[#FFFCF8] p-5 text-left transition hover:border-[#D7E6B3] hover:bg-[#F4F8EA]"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-[#5D7F17]">
                  <Icon className="h-5 w-5" />
                </div>
                <p className="mt-4 text-base font-semibold text-[#2D2D2D]">
                  {tab.label}
                </p>
                <div className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-[#5D7F17]">
                  进入分析
                  <ArrowUpRight className="h-4 w-4 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </div>
              </button>
            );
          })}
        </div>
      </section>
    </section>
  );
}
