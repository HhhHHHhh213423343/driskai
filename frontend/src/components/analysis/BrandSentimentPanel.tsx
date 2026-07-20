import {
  MessagesSquare,
  Newspaper,
  Sparkles,
  Waves,
} from "lucide-react";

import type { AnalysisPanelProps } from "./AnalysisTypes";
import { ThemeConfig } from "../../theme/ThemeConfig";

const channelMix = [
  { label: "正向声量", value: 64, color: "bg-emerald-500" },
  { label: "中性讨论", value: 24, color: "bg-slate-300" },
  { label: "负向预警", value: 12, color: "bg-rose-500" },
];

const hotTopics = [
  "新品上市节奏",
  "交付速度",
  "质量投诉",
  "海外扩张",
  "客服响应",
  "高管发言",
];

const mediaFocus = [
  {
    source: "财经媒体",
    summary: "关注产能扩张与盈利兑现节奏。",
    icon: Newspaper,
  },
  {
    source: "社交平台",
    summary: "讨论集中在服务体验与品牌态度。",
    icon: MessagesSquare,
  },
  {
    source: "行业自媒体",
    summary: "偏向比较竞品技术路线与市场份额。",
    icon: Waves,
  },
];

export function BrandSentimentPanel({
  companyName,
}: AnalysisPanelProps) {
  return (
    <section className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
      <div className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-[#5D7F17]">品牌声量分布</p>
            <h3 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
              {companyName} 的舆情结构整体偏稳
            </h3>
          </div>
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#F4F8EA] text-[#5D7F17]">
            <Sparkles className="h-6 w-6" />
          </div>
        </div>
        <div className="mt-8 space-y-4">
          {channelMix.map((item) => (
            <div key={item.label}>
              <div className="flex items-center justify-between text-sm text-[#6F6A61]">
                <span>{item.label}</span>
                <span>{item.value}%</span>
              </div>
              <div className="mt-2 h-3 rounded-full bg-[#EFEAE0]">
                <div
                  className={`h-3 rounded-full ${item.color}`}
                  style={{ width: `${item.value}%` }}
                />
              </div>
            </div>
          ))}
        </div>
        <div className="mt-8 flex flex-wrap gap-2">
          {hotTopics.map((item) => (
            <span
              key={item}
              className="rounded-full border border-[#D7E6B3] bg-[#F4F8EA] px-3 py-1.5 text-sm text-[#5D7F17]"
            >
              {item}
            </span>
          ))}
        </div>
      </div>

      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-3">
          {mediaFocus.map((item) => {
            const Icon = item.icon;
            return (
              <article
                key={item.source}
                className={`${ThemeConfig.surfaces.glassCardMuted} p-5`}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#F4F8EA] text-[#5D7F17]">
                  <Icon className="h-5 w-5" />
                </div>
                <p className="mt-4 text-sm text-[#6F6A61]">{item.source}</p>
                <p className="mt-2 text-base font-semibold text-[#2D2D2D]">
                  {item.summary}
                </p>
              </article>
            );
          })}
        </div>
        <div className={`${ThemeConfig.surfaces.glassCardMuted} p-6`}>
          <p className="text-sm font-medium text-[#6F6A61]">舆情处置建议</p>
          <div className="mt-4 space-y-3 text-sm leading-7 text-[#6F6A61]">
            <p>负向舆情建议按“产品质量 / 服务体验 / 合规争议”三类自动归档。</p>
            <p>若未来 24 小时内负向占比上升超过 8%，可触发品牌预警卡和日报推送。</p>
          </div>
        </div>
      </div>
    </section>
  );
}
