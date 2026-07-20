"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowUpRight, FileWarning, Search } from "lucide-react";

import type { RegulatoryDashboardPayload } from "../../lib/regulatoryTypes";
import { ThemeConfig } from "../../theme/ThemeConfig";

export function RegulatoryMeasuresBoard() {
  const [data, setData] = useState<RegulatoryDashboardPayload | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    fetch("/api/regulatory/dashboard", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`监管数据接口返回 ${response.status}`);
        }
        return (await response.json()) as RegulatoryDashboardPayload;
      })
      .then((payload) => {
        if (!ignore) setData(payload);
      })
      .catch((reason: unknown) => {
        if (!ignore) setError(reason instanceof Error ? reason.message : "监管数据加载失败");
      });
    return () => {
      ignore = true;
    };
  }, []);

  const cases = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const records = data?.caseRecords ?? [];
    if (!normalized) return records.slice(0, 20);
    return records
      .filter((item) =>
        [item.title, item.publisher, item.regionName, item.summary]
          .join(" ")
          .toLowerCase()
          .includes(normalized),
      )
      .slice(0, 20);
  }, [data, query]);

  if (error) {
    return (
      <div className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <div className="flex gap-3 rounded-2xl border border-[#F0C9BE] bg-[#FFF4F0] p-5 text-[#9E3D32]">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <p className="text-sm font-medium text-[#5D7F17]">D.Data / 监管动态</p>
        <h2 className="font-brand-title mt-2 text-3xl font-semibold text-[#2D2D2D]">
          证监会行政处罚与监管措施
        </h2>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["今日新增", data?.todayCount ?? "—"],
            ["本周新增", data?.weekCount ?? "—"],
            ["近 30 日", data?.monthCount ?? "—"],
            ["累计案件", data?.totalCases ?? "—"],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-[#E5E1D8] bg-[#FFFCF8] p-4">
              <p className="text-xs text-[#6F6A61]">{label}</p>
              <p className="mt-2 text-2xl font-semibold text-[#2D2D2D]">{value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <label className="flex items-center gap-3 rounded-2xl border border-[#E5E1D8] bg-white px-4 py-3">
          <Search className="h-4 w-4 text-[#86BC25]" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="检索案件、发布机构或地区"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none"
          />
        </label>
        <div className="mt-5 space-y-3">
          {cases.map((item) => (
            <a
              key={item.id}
              href={item.sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="block rounded-2xl border border-[#E5E1D8] bg-[#FFFCF8] p-5 transition hover:border-[#86BC25]"
            >
              <div className="flex flex-wrap items-center gap-2 text-xs text-[#6F6A61]">
                <span className="rounded-full bg-[#F4F8EA] px-3 py-1 text-[#5D7F17]">
                  {item.typeDisplay}
                </span>
                <span>{item.regionName}</span>
                <span>{item.publishDateIso || item.publishDateRaw}</span>
              </div>
              <div className="mt-3 flex items-start justify-between gap-4">
                <div>
                  <p className="font-semibold text-[#2D2D2D]">{item.title}</p>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-[#6F6A61]">
                    {item.summary}
                  </p>
                </div>
                <ArrowUpRight className="h-4 w-4 shrink-0 text-[#9E3D32]" />
              </div>
            </a>
          ))}
          {data && !cases.length ? (
            <div className="flex items-center gap-3 rounded-2xl bg-[#F7F5F0] p-5 text-sm text-[#6F6A61]">
              <FileWarning className="h-5 w-5" />
              没有匹配的监管案件。
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
