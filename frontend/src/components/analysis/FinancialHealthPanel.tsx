import { BanknoteArrowUp, Landmark, ShieldCheck } from "lucide-react";

import type { AnalysisPanelProps } from "./AnalysisTypes";
import { ThemeConfig } from "../../theme/ThemeConfig";

const revenueSeries = [42, 48, 55, 60, 58, 67, 74];
const cashflowSeries = [18, 24, 22, 31, 29, 34, 39];
const metrics = [
  {
    title: "营收增速",
    value: "+16.2%",
    detail: "主营业务修复明显",
    icon: BanknoteArrowUp,
  },
  {
    title: "现金流弹性",
    value: "稳健",
    detail: "经营现金净流入持续为正",
    icon: Landmark,
  },
  {
    title: "偿债安全边际",
    value: "2.4x",
    detail: "短期偿债能力良好",
    icon: ShieldCheck,
  },
];

function buildLinePath(points: number[]) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const height = 120;
  const width = 340;

  return points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * width;
      const ratio = max === min ? 0.5 : (point - min) / (max - min);
      const y = height - ratio * 90 - 12;
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
}

export function FinancialHealthPanel({
  companyName,
}: AnalysisPanelProps) {
  return (
    <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <div className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-7`}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-[#5D7F17]">财务趋势</p>
            <h3 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
              {companyName} 的营收与现金流同步改善
            </h3>
          </div>
          <span className={ThemeConfig.surfaces.pill}>JSON 报告快照可落库</span>
        </div>

        <div className="mt-8 rounded-[28px] border border-[#E5E1D8] bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-sm text-[#6F6A61]">
            <span>近 7 期营收趋势</span>
            <span>单位: 亿元</span>
          </div>
          <svg
            viewBox="0 0 340 140"
            className="mt-4 h-44 w-full"
            fill="none"
            aria-label="财务营收趋势图"
          >
            <defs>
              <linearGradient
                id="revenueGradient"
                x1="0"
                y1="0"
                x2="340"
                y2="140"
              >
                <stop offset="0%" stopColor="#9E3D32" stopOpacity="0.95" />
                <stop offset="100%" stopColor="#86BC25" stopOpacity="0.85" />
              </linearGradient>
            </defs>
            <path
              d={buildLinePath(revenueSeries)}
              stroke="url(#revenueGradient)"
              strokeWidth="4"
              strokeLinecap="round"
            />
            <path
              d={buildLinePath(cashflowSeries)}
              stroke="#A89F93"
              strokeWidth="3"
              strokeDasharray="7 7"
              strokeLinecap="round"
            />
          </svg>
          <div className="mt-2 flex items-center gap-4 text-xs text-[#6F6A61]">
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-[#9E3D32]" />
              营收
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-[#A89F93]" />
              经营现金流
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <div className="grid gap-4">
          {metrics.map((item) => {
            const Icon = item.icon;
            return (
              <article
                key={item.title}
                className={`${ThemeConfig.surfaces.glassCardMuted} p-5`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#F4F8EA] text-[#5D7F17]">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm text-[#6F6A61]">{item.title}</p>
                    <p className="text-xl font-semibold text-[#2D2D2D]">
                      {item.value}
                    </p>
                  </div>
                </div>
                <p className="mt-3 text-sm leading-6 text-[#6F6A61]">
                  {item.detail}
                </p>
              </article>
            );
          })}
        </div>
        <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
          <p className="text-sm font-medium text-[#6F6A61]">财务结论</p>
          <p className="mt-3 text-sm leading-7 text-[#6F6A61]">
            建议将毛利率、回款周期与资本开支同步纳入监控。若后续新增诉讼或执行事件，
            可直接在 `analysis_reports.snapshot` 中保留图表配置和结论摘要，方便复盘。
          </p>
        </div>
      </div>
    </section>
  );
}
