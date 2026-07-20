import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  CircleDashed,
  Database,
} from "lucide-react";

import type {
  AgentAnalysisPreview,
  AgentSection,
  AgentSeries,
} from "./AnalysisTypes";
import { ThemeConfig } from "../../theme/ThemeConfig";

type AgentDataPanelProps = {
  preview: AgentAnalysisPreview | null;
  loading: boolean;
  error: string;
};

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString("zh-CN") : value.toFixed(2);
  }
  return String(value);
}

function toneClass(tone: string) {
  if (tone === "positive") {
    return "border-[#D7E6B3] bg-[#F4F8EA] text-[#5D7F17]";
  }
  if (tone === "warning") {
    return "border-[#F0C9BE] bg-[#FFF4F0] text-[#9E3D32]";
  }
  return "border-[#E5E1D8] bg-[#FFFCF8] text-[#2D2D2D]";
}

function TrendChart({ series }: { series: AgentSeries }) {
  if (!series.points.length) {
    return null;
  }
  const values = series.points.map((item) => item.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = maximum - minimum || 1;
  const width = 520;
  const height = 176;
  const left = 18;
  const right = 18;
  const top = 18;
  const bottom = 32;
  const step =
    series.points.length > 1
      ? (width - left - right) / (series.points.length - 1)
      : 0;
  const coordinates = series.points.map((item, index) => ({
    ...item,
    x: left + index * step,
    y: top + ((maximum - item.value) / range) * (height - top - bottom),
  }));
  const path = coordinates.map((item) => `${item.x},${item.y}`).join(" ");

  return (
    <article className="rounded-2xl border border-[#E5E1D8] bg-[#FFFCF8] p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#2D2D2D]">{series.label}</p>
          <p className="mt-1 text-xs text-[#6F6A61]">单位：{series.unit || "数值"}</p>
        </div>
        <BarChart3 className="h-5 w-5 text-[#86BC25]" />
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="mt-4 h-44 w-full overflow-visible"
        role="img"
        aria-label={`${series.label}趋势图`}
      >
        {[0, 1, 2].map((line) => (
          <line
            key={line}
            x1={left}
            x2={width - right}
            y1={top + (line * (height - top - bottom)) / 2}
            y2={top + (line * (height - top - bottom)) / 2}
            stroke="#E9E5DC"
            strokeDasharray="4 5"
          />
        ))}
        <polyline
          points={path}
          fill="none"
          stroke="#86BC25"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {coordinates.map((item) => (
          <g key={item.period}>
            <circle cx={item.x} cy={item.y} r="5" fill="#86BC25" />
            <text
              x={item.x}
              y={height - 8}
              textAnchor="middle"
              className="fill-[#6F6A61] text-[10px]"
            >
              {item.period}
            </text>
          </g>
        ))}
      </svg>
      <div className="mt-2 flex items-center justify-between text-xs text-[#6F6A61]">
        <span>最低 {minimum.toLocaleString("zh-CN")}</span>
        <span>最新 {values.at(-1)?.toLocaleString("zh-CN")}</span>
        <span>最高 {maximum.toLocaleString("zh-CN")}</span>
      </div>
    </article>
  );
}

function Distribution({ section }: { section: AgentSection }) {
  const numericValues = section.items.map((item) => Number(item.value) || 0);
  const maximum = Math.max(...numericValues, 1);
  return (
    <div className="mt-5 space-y-3">
      {section.items.map((item, index) => {
        const value = numericValues[index];
        return (
          <div key={`${displayValue(item.label)}-${index}`}>
            <div className="flex items-center justify-between gap-4 text-sm">
              <span className="text-[#2D2D2D]">{displayValue(item.label)}</span>
              <span className="font-medium text-[#5D7F17]">{displayValue(item.value)}</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#E9E5DC]">
              <div
                className="h-full rounded-full bg-[#86BC25]"
                style={{ width: `${Math.max(4, (value / maximum) * 100)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Timeline({ section }: { section: AgentSection }) {
  return (
    <div className="mt-5 space-y-4">
      {section.items.length ? (
        section.items.map((item, index) => (
          <div key={`${displayValue(item.title)}-${index}`} className="flex gap-4">
            <div className="flex w-20 shrink-0 flex-col items-center">
              <span className="text-xs text-[#6F6A61]">{displayValue(item.date)}</span>
              <div className="mt-2 h-3 w-3 rounded-full bg-[#86BC25] ring-4 ring-[#F4F8EA]" />
              {index < section.items.length - 1 ? (
                <div className="mt-1 min-h-10 w-px flex-1 bg-[#D7E6B3]" />
              ) : null}
            </div>
            <div className="pb-4">
              <p className="text-sm font-semibold text-[#2D2D2D]">
                {displayValue(item.title)}
              </p>
              <p className="mt-2 text-sm leading-6 text-[#6F6A61]">
                {displayValue(item.detail ?? item.impact ?? item.action)}
              </p>
            </div>
          </div>
        ))
      ) : (
        <p className="rounded-xl bg-[#F7F5F0] px-4 py-3 text-sm text-[#6F6A61]">
          暂无可展示的时间线证据。
        </p>
      )}
    </div>
  );
}

function StructuredItems({ section }: { section: AgentSection }) {
  if (!section.items.length) {
    return (
      <p className="mt-5 rounded-xl bg-[#F7F5F0] px-4 py-3 text-sm text-[#6F6A61]">
        当前数据不足，暂不填充估算值。
      </p>
    );
  }
  return (
    <div className="mt-5 grid gap-3 md:grid-cols-2">
      {section.items.map((item, index) => (
        <div
          key={`${displayValue(item.title ?? item.label ?? item.scenario)}-${index}`}
          className="rounded-xl border border-[#E5E1D8] bg-white p-4"
        >
          {Object.entries(item)
            .filter(([key]) => !key.endsWith("_id") && key !== "source_id")
            .map(([key, value]) => (
              <div key={key} className="flex items-start justify-between gap-4 py-1.5 text-sm">
                <span className="shrink-0 text-[#8A857C]">{key}</span>
                <span className="text-right font-medium text-[#2D2D2D]">
                  {displayValue(value)}
                </span>
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}

function SectionCard({ section }: { section: AgentSection }) {
  return (
    <article className={`${ThemeConfig.surfaces.glassCardMuted} p-5`}>
      <h4 className="text-lg font-semibold text-[#2D2D2D]">{section.title}</h4>
      <p className="mt-2 text-sm leading-6 text-[#6F6A61]">{section.summary}</p>
      {section.kind === "distribution" ? <Distribution section={section} /> : null}
      {section.kind === "timeline" ? <Timeline section={section} /> : null}
      {section.kind !== "distribution" && section.kind !== "timeline" ? (
        <StructuredItems section={section} />
      ) : null}
    </article>
  );
}

export function AgentDataPanel({ preview, loading, error }: AgentDataPanelProps) {
  if (loading) {
    return (
      <div className={`${ThemeConfig.surfaces.glassCard} flex min-h-64 items-center justify-center p-8`}>
        <div className="text-center text-[#6F6A61]">
          <CircleDashed className="mx-auto h-8 w-8 animate-spin text-[#86BC25]" />
          <p className="mt-4 text-sm">正在汇总结构化事件与财务指标…</p>
        </div>
      </div>
    );
  }

  if (error || !preview) {
    return (
      <div className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <div className="flex items-start gap-3 rounded-2xl border border-[#F0C9BE] bg-[#FFF4F0] p-5 text-[#9E3D32]">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <p className="font-semibold">分析数据暂不可用</p>
            <p className="mt-2 text-sm leading-6">{error || "后端没有返回有效分析数据。"}</p>
          </div>
        </div>
      </div>
    );
  }

  const qualityLabel =
    preview.data_quality.status === "complete"
      ? "数据较完整"
      : preview.data_quality.status === "partial"
        ? "部分数据可用"
        : "证据不足";
  const QualityIcon =
    preview.data_quality.status === "complete" ? CheckCircle2 : AlertTriangle;

  return (
    <div className="space-y-6">
      <section className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 text-sm font-medium text-[#5D7F17]">
              <Database className="h-4 w-4" />
              实时分析数据
            </div>
            <h3 className="font-brand-title mt-2 text-2xl font-semibold text-[#2D2D2D]">
              {preview.company_name} · 指标与证据
            </h3>
          </div>
          <div className="min-w-64 rounded-2xl border border-[#E5E1D8] bg-[#FFFCF8] px-4 py-3">
            <div className="flex items-center justify-between text-sm">
              <span className="inline-flex items-center gap-2 font-medium text-[#2D2D2D]">
                <QualityIcon className="h-4 w-4 text-[#86BC25]" />
                {qualityLabel}
              </span>
              <span className="text-[#6F6A61]">{preview.data_quality.coverage_percent}%</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#E9E5DC]">
              <div
                className="h-full rounded-full bg-[#86BC25]"
                style={{ width: `${preview.data_quality.coverage_percent}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-[#8A857C]">
              {preview.data_quality.evidence_count} 条来源证据
            </p>
          </div>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {preview.metrics.map((metric) => (
            <article key={metric.key} className={`rounded-2xl border p-4 ${toneClass(metric.tone)}`}>
              <p className="text-xs font-medium opacity-75">{metric.label}</p>
              <p className="mt-2 text-2xl font-semibold">
                {metric.value}
                {metric.unit ? <span className="ml-1 text-sm font-medium">{metric.unit}</span> : null}
              </p>
              {metric.description ? (
                <p className="mt-2 text-xs leading-5 opacity-70">{metric.description}</p>
              ) : null}
            </article>
          ))}
        </div>

        {preview.data_quality.warnings.length ? (
          <div className="mt-5 rounded-2xl border border-[#F0DEC2] bg-[#FFF8EA] p-4">
            <p className="text-sm font-semibold text-[#8A5A14]">数据边界</p>
            <ul className="mt-2 space-y-1.5 text-sm leading-6 text-[#7A6545]">
              {preview.data_quality.warnings.map((warning) => (
                <li key={warning}>· {warning}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      {preview.series.length ? (
        <section className="grid gap-5 xl:grid-cols-2">
          {preview.series.map((series) => (
            <TrendChart key={series.key} series={series} />
          ))}
        </section>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-2">
        {preview.sections.map((section) => (
          <SectionCard key={section.key} section={section} />
        ))}
      </section>
    </div>
  );
}
