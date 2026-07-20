import {
  Factory,
  Landmark,
  Orbit,
  TrendingUp,
} from "lucide-react";

import type { AnalysisPanelProps } from "./AnalysisTypes";
import { ThemeConfig } from "../../theme/ThemeConfig";

const macroDrivers = [
  {
    label: "政策支持强度",
    value: 82,
    icon: Landmark,
    note: "产业升级政策与地方专项资金维持正向拉动。",
  },
  {
    label: "行业景气度",
    value: 74,
    icon: TrendingUp,
    note: "需求端回暖，但价格战仍在压缩行业平均利润。",
  },
  {
    label: "供应链稳定性",
    value: 68,
    icon: Factory,
    note: "关键原材料供应稳定，海外运输成本边际回落。",
  },
];

const signalCards = [
  {
    title: "行业窗口",
    value: "Q2 增长 +11.8%",
    detail: "上游设备投资恢复快于下游终端消费修复。",
  },
  {
    title: "资金环境",
    value: "融资成本下行",
    detail: "利率中枢平稳，优质企业再融资环境改善。",
  },
  {
    title: "区域政策",
    value: "东部更强",
    detail: "长三角与珠三角的专项补贴密集释放。",
  },
];

export function MacroEnvironmentPanel({
  companyName,
}: AnalysisPanelProps) {
  return (
    <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <div className={`${ThemeConfig.surfaces.glassCard} p-6 md:p-7`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-[#9E3D32]">宏观信号雷达</p>
            <h3 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
              {companyName} 所处赛道处于温和扩张区间
            </h3>
          </div>
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#F4F8EA] text-[#5D7F17]">
            <Orbit className="h-6 w-6" />
          </div>
        </div>
        <div className="mt-7 space-y-5">
          {macroDrivers.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.label}
                className="rounded-2xl border border-[#E5E1D8] bg-white p-4 shadow-sm"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#F4F8EA] text-[#5D7F17]">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="font-medium text-[#2D2D2D]">{item.label}</p>
                      <p className="text-sm text-[#6F6A61]">{item.note}</p>
                    </div>
                  </div>
                  <span className="text-lg font-semibold text-[#2D2D2D]">
                    {item.value}
                  </span>
                </div>
                <div className="mt-4 h-2 rounded-full bg-[#F0EBE2]">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-[#9E3D32] to-[#86BC25]"
                    style={{ width: `${item.value}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="space-y-6">
        <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
          <p className="text-sm font-medium text-[#6F6A61]">行业脉冲</p>
          <div className="mt-4 grid gap-4">
            {signalCards.map((item) => (
              <article
                key={item.title}
                className="rounded-2xl border border-[#E5E1D8] bg-white p-4 shadow-sm"
              >
                <p className="text-sm text-[#6F6A61]">{item.title}</p>
                <p className="mt-2 text-xl font-semibold text-[#2D2D2D]">
                  {item.value}
                </p>
                <p className="mt-2 text-sm leading-6 text-[#6F6A61]">
                  {item.detail}
                </p>
              </article>
            ))}
          </div>
        </div>
        <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
          <p className="text-sm font-medium text-[#6F6A61]">结论摘要</p>
          <p className="mt-4 text-sm leading-7 text-[#6F6A61]">
            当前阶段更适合对 {companyName} 做中期跟踪，而不是单一事件驱动判断。
            推荐将政策节奏、产能释放与主要竞争对手资本开支并联观察。
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <span className={ThemeConfig.surfaces.pill}>政策利好偏强</span>
            <span className={ThemeConfig.surfaces.pill}>行业价格承压</span>
            <span className={ThemeConfig.surfaces.pill}>供给侧修复中</span>
          </div>
        </div>
      </div>
    </section>
  );
}
