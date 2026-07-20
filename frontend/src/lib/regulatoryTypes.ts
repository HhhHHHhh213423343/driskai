export type RegulatoryCaseType =
  | "administrative_penalty"
  | "regulatory_measures";

export type RegulatoryCaseRecord = {
  id: string;
  caseType: RegulatoryCaseType;
  typeDisplay: string;
  regionCode: string;
  regionName: string;
  publisher: string;
  publishDateRaw: string;
  publishDateIso: string | null;
  decisionDateRaw: string;
  decisionDateIso: string | null;
  title: string;
  docNo: string;
  summary: string;
  sourceUrl: string;
};

export type RegulatoryChangeLogEntry = {
  id: string;
  date: string;
  caseType: RegulatoryCaseType;
  typeDisplay: string;
  regionCode: string;
  regionName: string;
  addedCount: number;
  removedCount: number;
  addedTitles: string[];
  removedTitles: string[];
  addedUrls: string[];
  removedUrls: string[];
};

export type RegulatoryWeeklyDigest = {
  title: string;
  dateRangeLabel: string;
  summary: string;
  highlights: string[];
  metrics: Array<{
    label: string;
    value: string;
  }>;
};

export type RegulatoryDashboardPayload = {
  available: boolean;
  sourceRoot: string | null;
  sourceRootLabel: string | null;
  todayCount: number;
  weekCount: number;
  monthCount: number;
  totalCases: number;
  latestScanStart: string | null;
  latestScanEnd: string | null;
  latestChangeLabel: string | null;
  latestCases: RegulatoryCaseRecord[];
  caseRecords: RegulatoryCaseRecord[];
  caseListTotal: number;
  caseListPage: number;
  caseListPageSize: number;
  caseListTotalPages: number;
  changeLogs: RegulatoryChangeLogEntry[];
  weeklyDigest: RegulatoryWeeklyDigest;
  typeStats: Array<{
    caseType: RegulatoryCaseType;
    typeDisplay: string;
    count: number;
    widthPercent: number;
  }>;
};
