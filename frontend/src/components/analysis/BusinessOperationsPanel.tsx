import {
  Activity,
  Boxes,
  ScanLine,
  TimerReset,
} from "lucide-react";

import type { AnalysisPanelProps } from "./AnalysisTypes";
import { ThemeConfig } from "../../theme/ThemeConfig";

const funnelStages = [
  { label: "商机进入", value: 100, display: "1,248" },
  { label: "方案报价", value: 76, display: "948" },
  { label: "签约转化", value: 51, display: "636" },
  { label: "回款完成", value: 44, display: "551" },
];

const operationSignals = [
  {
    title: "订单履约效率",
    value: "92h",
    description: "较上月缩短 8h，交付链路改善明显。",
    icon: Activity,
  },
  {
    title: "库存健康度",
    value: "良好",
    description: "慢动库存占比下降至 11.4%。",
    icon: Boxes,
  },
  {
    title: "风险工单闭环",
    value: "83%",
    description: "异常工单平均闭环时间 1.7 天。",
    icon: TimerReset,
  },
];

const bottlenecks = [
  "区域渠道分销节奏不均，华南交付高峰挤压售后资源。",
  "重点客户定制需求较多，标准化交付模板复用率不足。",
  "法务与财务审核节点串行，导致大额合同签约周期偏长。",
];

export function BusinessOperationsPanel({
  companyName,
}: AnalysisPanelProps) {
  return (
    <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
      <div className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-[#5D7F17]">运营漏斗</p>
            <h3 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
              {companyName} 的销售到回款链路仍有优化空间
            </h3>
          </div>
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#F4F8EA] text-[#5D7F17]">
            <ScanLine className="h-6 w-6" />
          </div>
        </div>

        <div className="mt-8 space-y-4">
          {funnelStages.map((stage) => (
            <div key={stage.label} className="space-y-2">
              <div className="flex items-center justify-between text-sm text-[#6F6A61]">
                <span>{stage.label}</span>
                <span>{stage.display}</span>
              </div>
              <div className="h-3 rounded-full bg-[#EFEAE0]">
                <div
                  className="h-3 rounded-full bg-gradient-to-r from-[#86BC25] to-[#9E3D32]"
                  style={{ width: `${stage.value}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          {operationSignals.map((item) => {
            const Icon = item.icon;
            return (
              <article
                key={item.title}
                className={`${ThemeConfig.surfaces.glassCardMuted} p-5`}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#F4F8EA] text-[#5D7F17]">
                  <Icon className="h-5 w-5" />
                </div>
                <p className="mt-4 text-sm text-[#6F6A61]">{item.title}</p>
                <p className="mt-2 text-2xl font-semibold text-[#2D2D2D]">
                  {item.value}
                </p>
                <p className="mt-2 text-sm leading-6 text-[#6F6A61]">
                  {item.description}
                </p>
              </article>
            );
          })}
        </div>

        <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
          <p className="text-sm font-medium text-[#6F6A61]">当前运营瓶颈</p>
          <div className="mt-4 space-y-3">
            {bottlenecks.map((item, index) => (
              <div
                key={item}
                className="flex gap-3 rounded-2xl border border-[#E5E1D8] bg-white p-4 shadow-sm"
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#2D2D2D] text-xs font-semibold text-white">
                  {index + 1}
                </span>
                <p className="text-sm leading-6 text-[#6F6A61]">{item}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
