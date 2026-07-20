"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  BarChart3,
  FileStack,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";

import {
  fetchIngestionDashboardSummary,
  type IngestionDashboardSummary,
} from "../../lib/ingestionDashboardApi";
import { ThemeConfig } from "../../theme/ThemeConfig";

const fallbackSystemSummary = {
  totalCases: "20713",
  latestScan: "2026-03-23 09:10:15 至 2026-03-23 09:28:42",
  latestChange: "2026-03-22 / overseas_compliance / byd",
};

const fallbackTrendSeries = [
  { label: "03-17", value: 34 },
  { label: "03-18", value: 41 },
  { label: "03-19", value: 38 },
  { label: "03-20", value: 56 },
  { label: "03-21", value: 49 },
  { label: "03-22", value: 58 },
  { label: "03-23", value: 63 },
];

const fallbackDimensionDistribution = [
  { label: "宏观环境", value: 16, color: "#86BC25" },
  { label: "业务运营", value: 13, color: "#A6C85C" },
  { label: "财务健康", value: 12, color: "#C7D98A" },
  { label: "法律诉讼", value: 9, color: "#D79B64" },
  { label: "品牌舆情", value: 13, color: "#B5443A" },
];

const fallbackReportOutput = [
  { label: "维度报告", value: 9 },
  { label: "综合报告", value: 3 },
  { label: "已生成维度", value: 5 },
  { label: "高优先结论", value: 7 },
];

const categoryColors: Record<string, string> = {
  宏观环境: "#86BC25",
  业务运营: "#A6C85C",
  财务健康: "#C7D98A",
  法律诉讼: "#D79B64",
  品牌舆情: "#B5443A",
};

function buildSystemSummary(summary: IngestionDashboardSummary | null) {
  if (!summary) {
    return fallbackSystemSummary;
  }

  return {
    totalCases: new Intl.NumberFormat("zh-CN").format(summary.total_events),
    latestScan: summary.latest_scan_label,
    latestChange: summary.latest_change_label,
  };
}

function buildDimensionDistribution(summary: IngestionDashboardSummary | null) {
  if (!summary || Object.keys(summary.category_distribution).length === 0) {
    return fallbackDimensionDistribution;
  }

  return Object.entries(summary.category_distribution).map(([label, value]) => ({
    label,
    value,
    color: categoryColors[label] ?? "#86BC25",
  }));
}

function buildReportOutput(summary: IngestionDashboardSummary | null) {
  if (!summary || Object.keys(summary.report_output).length === 0) {
    return fallbackReportOutput;
  }

  const entries = Object.entries(summary.report_output).slice(0, 4);
  return entries.map(([label, value]) => ({ label, value }));
}

function buildOverviewStats(summary: IngestionDashboardSummary | null) {
  if (!summary) {
    return ThemeConfig.overviewStats;
  }

  return [
    {
      label: "风险事件总数",
      value: new Intl.NumberFormat("zh-CN").format(summary.total_events),
      hint: "来自已接入公开数据源与批处理入库记录",
    },
    {
      label: "近 7 日新增",
      value: new Intl.NumberFormat("zh-CN").format(summary.last_7_days_events),
      hint: "按事件发生日期优先统计，缺失时回退到入库时间",
    },
    {
      label: "高优先级事件",
      value: new Intl.NumberFormat("zh-CN").format(summary.high_priority_events),
      hint: "由公告、处罚、诉讼、亏损等关键词自动归类",
    },
    {
      label: "深度报告快照",
      value: new Intl.NumberFormat("zh-CN").format(summary.report_count),
      hint: "统计已生成的维度报告与综合分析报告",
    },
  ];
}

function buildLinePath(values: number[], width: number, height: number) {
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = Math.max(max - min, 1);
  const stepX = width / Math.max(values.length - 1, 1);

  return values
    .map((value, index) => {
      const x = index * stepX;
      const y = height - ((value - min) / range) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function buildAreaPath(values: number[], width: number, height: number) {
  const line = buildLinePath(values, width, height);
  return `${line} L ${width} ${height} L 0 ${height} Z`;
}

export function DataDashboard() {
  const [summary, setSummary] = useState<IngestionDashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    fetchIngestionDashboardSummary().then((data) => {
      if (!isMounted) {
        return;
      }
      setSummary(data);
      setIsLoading(false);
    });
    return () => {
      isMounted = false;
    };
  }, []);

  const systemSummary = useMemo(() => buildSystemSummary(summary), [summary]);
  const trendSeries = summary?.trend_series?.length
    ? summary.trend_series
    : fallbackTrendSeries;
  const dimensionDistribution = useMemo(
    () => buildDimensionDistribution(summary),
    [summary],
  );
  const reportOutput = useMemo(() => buildReportOutput(summary), [summary]);
  const overviewStats = useMemo(() => buildOverviewStats(summary), [summary]);
  const sourceBreakdown = Object.entries(summary?.source_breakdown ?? {});
  const trendValues = trendSeries.map((item) => item.value);
  const linePath = buildLinePath(trendValues, 620, 220);
  const areaPath = buildAreaPath(trendValues, 620, 220);
  const maxDimensionValue = Math.max(
    ...dimensionDistribution.map((item) => item.value),
    1,
  );
  const maxReportValue = Math.max(...reportOutput.map((item) => item.value), 1);

  return (
    <div className="mx-auto max-w-[1380px] space-y-8">
      <section className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-8 lg:p-10`}>
        <div className="flex flex-col gap-8 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-5xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#EFE4D8] bg-[#FFF8F2] px-4 py-2 text-sm text-[#9E3D32]">
              <BarChart3 className="h-4 w-4" />
              数据看板
            </div>
            <h2 className="font-brand-title mt-6 text-4xl font-semibold tracking-tight text-[#2D2D2D] md:text-6xl">
              风险检索数据总览
            </h2>
            <p className="mt-4 max-w-4xl text-base leading-8 text-[#6F6A61] md:text-lg">
              公开公告、金融数据与白名单新闻源正在汇入同一套风险事件库。
            </p>
          </div>

          <div
            className={`${ThemeConfig.surfaces.glassCardMuted} min-w-full p-6 xl:min-w-[360px] xl:max-w-[420px]`}
          >
            <p className="text-sm font-medium text-[#6F6A61]">系统总览</p>
            <p className="mt-3 text-5xl font-semibold text-[#2D2D2D]">
              {systemSummary.totalCases}
            </p>
            <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
              最近检索：{isLoading ? "加载中" : systemSummary.latestScan}
            </p>
            <div className="mt-6 rounded-2xl border border-[#E5E1D8] bg-white p-4">
              <p className="text-sm text-[#6F6A61]">最近变更记录</p>
              <p className="mt-2 text-base font-medium text-[#2D2D2D]">
                {isLoading ? "加载中" : systemSummary.latestChange}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {overviewStats.map((item) => (
          <article
            key={item.label}
            className={`${ThemeConfig.surfaces.glassCardMuted} min-h-[192px] p-6`}
          >
            <p className="text-sm font-medium text-[#6F6A61]">{item.label}</p>
            <p className="mt-5 text-5xl font-semibold text-[#2D2D2D]">
              {item.value}
            </p>
            <p className="mt-4 text-sm leading-7 text-[#6F6A61]">{item.hint}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.45fr_0.95fr]">
        <article className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-8`}>
          <div className="flex items-start justify-between gap-5">
            <div>
              <p className="text-sm font-medium text-[#9E3D32]">趋势图</p>
              <h3 className="font-brand-title mt-3 text-3xl font-semibold text-[#2D2D2D]">
                近 7 日风险事件趋势
              </h3>
              <p className="mt-3 max-w-3xl text-sm leading-7 text-[#6F6A61]">
                每日批处理会按事件日期归档，缺失事件日期时回退到入库时间。
              </p>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[#DCE8C4] bg-[#F4F8EA] px-4 py-2 text-sm font-medium text-[#5D7F17]">
              <TrendingUp className="h-4 w-4" />
              每日批处理
            </div>
          </div>

          <div className="mt-8 overflow-hidden rounded-[28px] border border-[#E7E1D6] bg-[#FFFDF9] p-5 md:p-6">
            <svg viewBox="0 0 620 260" className="h-[260px] w-full">
              <defs>
                <linearGradient id="dashboard-area" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#86BC25" stopOpacity="0.24" />
                  <stop offset="100%" stopColor="#86BC25" stopOpacity="0.02" />
                </linearGradient>
              </defs>

              {[0, 1, 2, 3].map((tick) => {
                const y = 35 + tick * 60;
                return (
                  <line
                    key={tick}
                    x1="0"
                    y1={y}
                    x2="620"
                    y2={y}
                    stroke="#ECE7DE"
                    strokeDasharray="5 7"
                  />
                );
              })}

              <path d={areaPath} transform="translate(0 20)" fill="url(#dashboard-area)" />
              <path
                d={linePath}
                transform="translate(0 20)"
                fill="none"
                stroke="#86BC25"
                strokeWidth="4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {trendSeries.map((item, index) => {
                const x = (620 / Math.max(trendSeries.length - 1, 1)) * index;
                const y =
                  220 -
                  ((item.value - Math.min(...trendValues)) /
                    Math.max(Math.max(...trendValues) - Math.min(...trendValues), 1)) *
                    220;
                return (
                  <g key={item.label} transform={`translate(${x}, ${y + 20})`}>
                    <circle r="7" fill="#FFFDF9" stroke="#86BC25" strokeWidth="4" />
                  </g>
                );
              })}
            </svg>

            <div className="mt-2 grid grid-cols-7 gap-2 text-center">
              {trendSeries.map((item) => (
                <div key={item.label}>
                  <p className="text-sm font-medium text-[#2D2D2D]">{item.value}</p>
                  <p className="mt-1 text-xs text-[#8A847A]">{item.label}</p>
                </div>
              ))}
            </div>
          </div>
        </article>

        <div className="space-y-6">
          <article className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-8`}>
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-1 h-5 w-5 text-[#9E3D32]" />
              <div>
                <h3 className="font-brand-title text-2xl font-semibold text-[#2D2D2D]">
                  五维风险分布
                </h3>
                <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
                  事件按宏观、业务、财务、法律与品牌舆情五类归档。
                </p>
              </div>
            </div>

            <div className="mt-8 space-y-5">
              {dimensionDistribution.map((item) => (
                <div key={item.label}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-base font-medium text-[#2D2D2D]">{item.label}</p>
                    <p className="text-base font-semibold text-[#2D2D2D]">{item.value}</p>
                  </div>
                  <div className="mt-3 h-3 rounded-full bg-[#EFE9DE]">
                    <div
                      className="h-3 rounded-full"
                      style={{
                        width: `${Math.round((item.value / maxDimensionValue) * 100)}%`,
                        backgroundColor: item.color,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className={`${ThemeConfig.surfaces.glassCardMuted} p-6 md:p-8`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-[#9E3D32]">报告输出</p>
                <h3 className="font-brand-title mt-3 text-2xl font-semibold text-[#2D2D2D]">
                  报告产出结构
                </h3>
              </div>
              <ArrowUpRight className="mt-1 h-5 w-5 text-[#9E3D32]" />
            </div>

            <div className="mt-8 grid grid-cols-4 items-end gap-4">
              {reportOutput.map((item) => (
                <div key={item.label} className="text-center">
                  <div className="flex h-[180px] items-end justify-center rounded-[22px] bg-white px-3 py-4">
                    <div
                      className="w-full rounded-[18px] bg-gradient-to-t from-[#B5443A] via-[#D27C43] to-[#F2D6B6]"
                      style={{
                        height: `${Math.max(24, Math.round((item.value / maxReportValue) * 140))}px`,
                      }}
                    />
                  </div>
                  <p className="mt-3 text-xl font-semibold text-[#2D2D2D]">{item.value}</p>
                  <p className="mt-1 text-sm leading-6 text-[#6F6A61]">{item.label}</p>
                </div>
              ))}
            </div>

            <div className="mt-8 rounded-[24px] border border-[#E7E1D6] bg-white p-5">
              <div className="flex items-start gap-3">
                <FileStack className="mt-1 h-5 w-5 text-[#5D7F17]" />
                <div>
                  <p className="text-base font-semibold text-[#2D2D2D]">数据来源</p>
                  {sourceBreakdown.length > 0 ? (
                    <div className="mt-3 space-y-3">
                      {sourceBreakdown.map(([sourceName, value]) => (
                        <div
                          key={sourceName}
                          className="flex items-center justify-between gap-4 text-sm"
                        >
                          <span className="text-[#6F6A61]">{sourceName}</span>
                          <span className="font-semibold text-[#2D2D2D]">{value}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm leading-7 text-[#6F6A61]">
                      等待每日批处理写入第一批来源记录。
                    </p>
                  )}
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>
  );
}
