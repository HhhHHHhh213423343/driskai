import { AlertTriangle, ArrowUpRight, Scale } from "lucide-react";

import type { AnalysisPanelProps } from "./AnalysisTypes";
import { ThemeConfig } from "../../theme/ThemeConfig";

const litigationEvents = [
  {
    date: "2026-03-18",
    severity: "高",
    title: "买卖合同纠纷进入二审",
    content: "涉案金额约 860 万元，涉及核心供应商结算争议。",
    source: "中国裁判文书网",
  },
  {
    date: "2026-02-27",
    severity: "中",
    title: "新增被执行人信息",
    content: "执行标的 132 万元，需排查是否已完成履约。",
    source: "中国执行信息公开网",
  },
  {
    date: "2026-01-12",
    severity: "中",
    title: "劳动争议仲裁立案",
    content: "集中发生于区域销售团队，可能映射组织治理问题。",
    source: "地方仲裁公告",
  },
];

const severityClassName: Record<string, string> = {
  高: "bg-rose-100 text-rose-700",
  中: "bg-amber-100 text-amber-700",
  低: "bg-emerald-100 text-emerald-700",
};

export function LegalLitigationPanel({
  companyName,
}: AnalysisPanelProps) {
  return (
    <section className="grid gap-6 xl:grid-cols-[1fr_0.9fr]">
      <div className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-[#9E3D32]">诉讼风险时间轴</p>
            <h3 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
              {companyName} 近期法律事件呈现连续暴露
            </h3>
          </div>
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#F8E9E5] text-[#9E3D32]">
            <Scale className="h-6 w-6" />
          </div>
        </div>
        <div className="relative mt-8 space-y-5 pl-6">
          <div className="absolute bottom-4 left-[11px] top-2 w-px bg-gradient-to-b from-[#C97165] via-[#EADFD2] to-transparent" />
          {litigationEvents.map((event) => (
            <article key={event.title} className="relative">
              <span className="absolute left-[-19px] top-5 h-3 w-3 rounded-full border-2 border-white bg-[#9E3D32]" />
              <div className="rounded-2xl border border-[#E5E1D8] bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-sm font-medium text-[#2D2D2D]">
                    {event.date}
                  </p>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${severityClassName[event.severity]}`}
                  >
                    {event.severity}风险
                  </span>
                </div>
                <p className="mt-3 text-lg font-semibold text-[#2D2D2D]">
                  {event.title}
                </p>
                <p className="mt-2 text-sm leading-6 text-[#6F6A61]">
                  {event.content}
                </p>
                <div className="mt-4 flex items-center gap-2 text-sm text-[#9E3D32]">
                  <ArrowUpRight className="h-4 w-4" />
                  {event.source}
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>

      <div className="space-y-6">
        <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#F8E9E5] text-[#9E3D32]">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-[#6F6A61]">风险摘要</p>
              <p className="text-xl font-semibold text-[#2D2D2D]">
                二审与执行信息需要重点预警
              </p>
            </div>
          </div>
          <div className="mt-4 space-y-3 text-sm leading-7 text-[#6F6A61]">
            <p>建议将涉案金额、案件阶段、关联主体与最新公告链接作为结构化字段落库。</p>
            <p>当 `severity` 达到 `high` 或 `critical` 时，可以自动触发日报与内部通知。</p>
          </div>
        </div>
        <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
          <p className="text-sm font-medium text-[#6F6A61]">联动建议</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className={ThemeConfig.surfaces.pill}>诉讼阶段追踪</span>
            <span className={ThemeConfig.surfaces.pill}>执行标的金额预警</span>
            <span className={ThemeConfig.surfaces.pill}>法务资料归档</span>
          </div>
        </div>
      </div>
    </section>
  );
}
