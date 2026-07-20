"use client";

import { useCallback, useEffect, useState } from "react";

import type { ReportDepth } from "../components/analysis/agentWorkspaceData";
import type { AnalysisTabKey } from "../theme/ThemeConfig";

export type AssemblyItem = {
  tabKey: AnalysisTabKey;
  reportType: string;
  title: string;
  summary: string;
  depth: ReportDepth;
  status: "generated";
  generatedAt: string;
  includedAt: string;
};

export type AssemblyDraft = {
  companyId: string;
  companyName: string;
  items: AssemblyItem[];
  updatedAt: string;
  lastComposedAt?: string;
  lastComposedTitle?: string;
};

const STORAGE_PREFIX = "drisk-ai:assembly:";

function canUseStorage() {
  return typeof window !== "undefined" && !!window.localStorage;
}

function getStorageKey(companyId: string) {
  return `${STORAGE_PREFIX}${companyId}`;
}

function createEmptyDraft(companyId: string, companyName: string): AssemblyDraft {
  return {
    companyId,
    companyName,
    items: [],
    updatedAt: new Date().toISOString(),
  };
}

export function readAssemblyDraft(
  companyId: string,
  companyName = "",
): AssemblyDraft {
  if (!canUseStorage()) {
    return createEmptyDraft(companyId, companyName);
  }

  const raw = window.localStorage.getItem(getStorageKey(companyId));
  if (!raw) {
    return createEmptyDraft(companyId, companyName);
  }

  try {
    const parsed = JSON.parse(raw) as AssemblyDraft;
    return {
      ...parsed,
      companyId,
      companyName: parsed.companyName || companyName,
      items: Array.isArray(parsed.items) ? parsed.items : [],
    };
  } catch {
    return createEmptyDraft(companyId, companyName);
  }
}

function saveAssemblyDraft(draft: AssemblyDraft) {
  if (!canUseStorage()) {
    return;
  }

  window.localStorage.setItem(
    getStorageKey(draft.companyId),
    JSON.stringify(draft),
  );
}

export function useReportAssembly(
  companyId?: string,
  companyName?: string,
) {
  const [draft, setDraft] = useState<AssemblyDraft | null>(null);

  useEffect(() => {
    if (!companyId) {
      setDraft(null);
      return;
    }

    setDraft(readAssemblyDraft(companyId, companyName || ""));
  }, [companyId, companyName]);

  const persist = useCallback(
    (updater: (current: AssemblyDraft) => AssemblyDraft) => {
      if (!companyId) {
        return;
      }

      setDraft((current) => {
        const base = current ?? readAssemblyDraft(companyId, companyName || "");
        const next = updater({
          ...base,
          companyName: companyName || base.companyName,
        });
        saveAssemblyDraft(next);
        return next;
      });
    },
    [companyId, companyName],
  );

  const upsertItem = useCallback(
    (item: AssemblyItem) => {
      persist((current) => {
        const items = current.items.filter(
          (existing) => existing.tabKey !== item.tabKey,
        );
        return {
          ...current,
          items: [...items, item],
          updatedAt: new Date().toISOString(),
        };
      });
    },
    [persist],
  );

  const removeItem = useCallback(
    (tabKey: AnalysisTabKey) => {
      persist((current) => ({
        ...current,
        items: current.items.filter((item) => item.tabKey !== tabKey),
        updatedAt: new Date().toISOString(),
      }));
    },
    [persist],
  );

  const markComposed = useCallback(
    (title: string) => {
      persist((current) => ({
        ...current,
        updatedAt: new Date().toISOString(),
        lastComposedAt: new Date().toISOString(),
        lastComposedTitle: title,
      }));
    },
    [persist],
  );

  const clear = useCallback(() => {
    if (!companyId) {
      return;
    }

    const next = createEmptyDraft(companyId, companyName || "");
    setDraft(next);
    saveAssemblyDraft(next);
  }, [companyId, companyName]);

  return {
    draft,
    items: draft?.items ?? [],
    upsertItem,
    removeItem,
    markComposed,
    clear,
  };
}
