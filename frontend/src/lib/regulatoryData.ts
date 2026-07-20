import { promises as fs } from "fs";
import path from "path";

import type {
  RegulatoryCaseRecord,
  RegulatoryCaseType,
  RegulatoryChangeLogEntry,
  RegulatoryDashboardPayload,
  RegulatoryWeeklyDigest,
} from "./regulatoryTypes";

const DEMO_REGULATORY_CASES: RegulatoryCaseRecord[] = [
  {
    id: "demo-administrative-1",
    caseType: "administrative_penalty",
    typeDisplay: "行政处罚",
    regionCode: "fujian",
    regionName: "福建",
    publisher: "中国证券监督管理委员会福建监管局",
    publishDateRaw: "2026-03-13",
    publishDateIso: "2026-03-13",
    decisionDateRaw: "2026-03-13",
    decisionDateIso: "2026-03-13",
    title: "中国证券监督管理委员会福建监管局 行政处罚决定书〔2026〕3号（王琳晶）",
    docNo: "中国证券监督管理委员会福建监管局 行政处罚决定书〔2026〕3号",
    summary:
      "当事人：王琳晶，男，1975年2月出生，任天风证券股份有限公司总裁，住址：北京市海淀区。依据《中华人民共和国证券法》的有关规定，我局对天风证券未及时披露福建省永安林业（集团）股份有限公司持股变动信息行为进行了立案调查。",
    sourceUrl: "https://www.csrc.gov.cn/fujian/c104064/c7619933/content.shtml",
  },
  {
    id: "demo-administrative-2",
    caseType: "administrative_penalty",
    typeDisplay: "行政处罚",
    regionCode: "fujian",
    regionName: "福建",
    publisher: "中国证券监督管理委员会福建监管局",
    publishDateRaw: "2026-03-12",
    publishDateIso: "2026-03-12",
    decisionDateRaw: "2026-03-12",
    decisionDateIso: "2026-03-12",
    title: "中国证券监督管理委员会福建监管局 行政处罚决定书〔2026〕2号（天风证券）",
    docNo: "中国证券监督管理委员会福建监管局 行政处罚决定书〔2026〕2号",
    summary:
      "当事人：天风证券股份有限公司，住所：湖北省武汉市武昌区。依据《中华人民共和国证券法》的有关规定，我局对天风证券未及时披露福建省永安林业（集团）股份有限公司持股变动信息行为进行了立案调查。",
    sourceUrl: "https://www.csrc.gov.cn/fujian/c104064/c7619931/content.shtml",
  },
  {
    id: "demo-administrative-3",
    caseType: "administrative_penalty",
    typeDisplay: "行政处罚",
    regionCode: "hubei",
    regionName: "湖北",
    publisher: "湖北证监局",
    publishDateRaw: "2026-03-12",
    publishDateIso: "2026-03-12",
    decisionDateRaw: "2026-03-12",
    decisionDateIso: "2026-03-12",
    title: "湖北证监局行政处罚决定书〔2026〕5号",
    docNo: "湖北证监局行政处罚决定书〔2026〕5号",
    summary:
      "当事人包含天风证券股份有限公司及相关责任人员。经查，在信息披露、内部控制与人员履职方面存在违规情形，湖北证监局依法作出行政处罚决定。",
    sourceUrl: "https://www.csrc.gov.cn/hubei/c104406/c7619973/content.shtml",
  },
  {
    id: "demo-administrative-4",
    caseType: "administrative_penalty",
    typeDisplay: "行政处罚",
    regionCode: "jiangsu",
    regionName: "江苏",
    publisher: "中国证券监督管理委员会江苏监管局",
    publishDateRaw: "2026-03-11",
    publishDateIso: "2026-03-11",
    decisionDateRaw: "2026-03-11",
    decisionDateIso: "2026-03-11",
    title: "中国证券监督管理委员会江苏监管局行政处罚决定书〔2026〕3号",
    docNo: "中国证券监督管理委员会江苏监管局行政处罚决定书〔2026〕3号",
    summary:
      "当事人存在内幕交易“登云股份”等行为。依据《中华人民共和国证券法》的有关规定，江苏证监局依法向当事人告知作出行政处罚的事实、理由、依据及其依法享有的权利。",
    sourceUrl: "https://www.csrc.gov.cn/jiangsu/c103902/c7619896/content.shtml",
  },
  {
    id: "demo-regulatory-1",
    caseType: "regulatory_measures",
    typeDisplay: "监管措施",
    regionCode: "shenzhen",
    regionName: "深圳",
    publisher: "深圳证监局",
    publishDateRaw: "2026-03-10",
    publishDateIso: "2026-03-10",
    decisionDateRaw: "2026-03-10",
    decisionDateIso: "2026-03-10",
    title: "深圳证监局关于对深圳市建艺装饰集团股份有限公司采取责令改正并对唐亮等人采取出具警示函措施的决定",
    docNo: "深圳证监局监管措施决定",
    summary:
      "因公司治理、信息披露与内部控制方面存在问题，深圳证监局依法采取责令改正并对相关责任人出具警示函的监管措施。",
    sourceUrl: "https://www.csrc.gov.cn/shenzhen/c104320/c7617118/content.shtml",
  },
  {
    id: "demo-regulatory-2",
    caseType: "regulatory_measures",
    typeDisplay: "监管措施",
    regionCode: "hubei",
    regionName: "湖北",
    publisher: "湖北证监局",
    publishDateRaw: "2026-03-09",
    publishDateIso: "2026-03-09",
    decisionDateRaw: "2026-03-09",
    decisionDateIso: "2026-03-09",
    title: "湖北证监局关于对孙凯采取出具警示函措施的决定",
    docNo: "湖北证监局警示函决定",
    summary:
      "围绕私募基金管理、适当性义务与信息披露要求，湖北证监局对相关责任主体采取出具警示函的监管措施。",
    sourceUrl: "https://www.csrc.gov.cn/hubei/c104408/c7616912/content.shtml",
  },
];

const DEMO_CHANGE_LOGS: RegulatoryChangeLogEntry[] = [
  {
    id: "demo-change-central-20260317",
    date: "2026-03-17",
    caseType: "administrative_penalty",
    typeDisplay: "行政处罚",
    regionCode: "",
    regionName: "中央",
    addedCount: 4,
    removedCount: 0,
    addedTitles: [
      "中国证券监督管理委员会行政处罚决定书",
      "中国证券监督管理委员会行政处罚决定书",
      "中国证券监督管理委员会行政处罚决定书",
      "中国证券监督管理委员会行政处罚决定书",
    ],
    removedTitles: [],
    addedUrls: [
      "https://www.csrc.gov.cn/csrc/c101928/c7619967/content.shtml",
      "https://www.csrc.gov.cn/csrc/c101928/c7619972/content.shtml",
      "https://www.csrc.gov.cn/csrc/c101928/c7619943/content.shtml",
      "https://www.csrc.gov.cn/csrc/c101928/c7619963/content.shtml",
    ],
    removedUrls: [],
  },
  {
    id: "demo-change-fujian-20260317",
    date: "2026-03-17",
    caseType: "administrative_penalty",
    typeDisplay: "行政处罚",
    regionCode: "fujian",
    regionName: "福建",
    addedCount: 2,
    removedCount: 0,
    addedTitles: [
      "中国证券监督管理委员会福建监管局 行政处罚决定书〔2026〕2号（天风证券）",
      "中国证券监督管理委员会福建监管局 行政处罚决定书〔2026〕3号（王琳晶）",
    ],
    removedTitles: [],
    addedUrls: [
      "https://www.csrc.gov.cn/fujian/c104064/c7619931/content.shtml",
      "https://www.csrc.gov.cn/fujian/c104064/c7619933/content.shtml",
    ],
    removedUrls: [],
  },
  {
    id: "demo-change-hubei-20260317",
    date: "2026-03-17",
    caseType: "administrative_penalty",
    typeDisplay: "行政处罚",
    regionCode: "hubei",
    regionName: "湖北",
    addedCount: 1,
    removedCount: 0,
    addedTitles: ["湖北证监局行政处罚决定书〔2026〕5号"],
    removedTitles: [],
    addedUrls: [
      "https://www.csrc.gov.cn/hubei/c104406/c7619973/content.shtml",
    ],
    removedUrls: [],
  },
  {
    id: "demo-change-jiangsu-20260317",
    date: "2026-03-17",
    caseType: "administrative_penalty",
    typeDisplay: "行政处罚",
    regionCode: "jiangsu",
    regionName: "江苏",
    addedCount: 2,
    removedCount: 0,
    addedTitles: [
      "中国证券监督管理委员会江苏监管局行政处罚决定书",
      "中国证券监督管理委员会江苏监管局行政处罚决定书",
    ],
    removedTitles: [],
    addedUrls: [
      "https://www.csrc.gov.cn/jiangsu/c103902/c7618534/content.shtml",
      "https://www.csrc.gov.cn/jiangsu/c103902/c7619896/content.shtml",
    ],
    removedUrls: [],
  },
];

const DEMO_WEEKLY_DIGEST: RegulatoryWeeklyDigest = {
  title: "第 12 周监管发文周报",
  dateRangeLabel: "2026-03-11 至 2026-03-17",
  summary:
    "本周演示数据重点体现中央、福建、湖北与江苏四个区域的行政处罚发文集中更新，同时保留深圳、湖北监管措施样本，用于完整演示证监会统计页面的看板、案件筛选与变更日志联动。",
  highlights: [
    "中央层面新增 4 条行政处罚决定书，适合作为总览页“最近变更记录”的来源。",
    "福建局新增 2 条行政处罚决定书，标题与文号与案件列表、变更日志保持一致。",
    "监管措施样本保留深圳和湖北两条典型案例，便于类型分布与筛选功能演示。",
  ],
  metrics: [
    {
      label: "本周新增",
      value: "4",
    },
    {
      label: "近 30 日新增",
      value: "23",
    },
    {
      label: "行政处罚占比",
      value: "4715",
    },
    {
      label: "监管措施占比",
      value: "15998",
    },
  ],
};

const CASE_TYPES: Record<RegulatoryCaseType, string> = {
  administrative_penalty: "行政处罚",
  regulatory_measures: "监管措施",
};

const REGION_NAMES: Record<string, string> = {
  "": "中央",
  anhui: "安徽",
  beijing: "北京",
  chongqing: "重庆",
  dalian: "大连",
  fujian: "福建",
  gansu: "甘肃",
  guangdong: "广东",
  guangxi: "广西",
  guizhou: "贵州",
  hainan: "海南",
  hebei: "河北",
  heilongjiang: "黑龙江",
  henan: "河南",
  hubei: "湖北",
  hunan: "湖南",
  jiangsu: "江苏",
  jiangxi: "江西",
  jilin: "吉林",
  liaoning: "辽宁",
  neimenggu: "内蒙古",
  ningbo: "宁波",
  ningxia: "宁夏",
  qingdao: "青岛",
  qinghai: "青海",
  shaanxi: "陕西",
  shandong: "山东",
  shanghai: "上海",
  shanxi: "山西",
  shenzhen: "深圳",
  sichuan: "四川",
  tianjin: "天津",
  tibet: "西藏",
  xiamen: "厦门",
  xinjiang: "新疆",
  yunnan: "云南",
  zhejiang: "浙江",
};

const YEAR_DIGITS: Record<string, string> = {
  "零": "0",
  "〇": "0",
  "○": "0",
  "O": "0",
  "一": "1",
  "二": "2",
  "三": "3",
  "四": "4",
  "五": "5",
  "六": "6",
  "七": "7",
  "八": "8",
  "九": "9",
};

const CN_NUMBERS: Record<string, number> = {
  "零": 0,
  "〇": 0,
  "一": 1,
  "二": 2,
  "三": 3,
  "四": 4,
  "五": 5,
  "六": 6,
  "七": 7,
  "八": 8,
  "九": 9,
};

const CANDIDATE_ROOTS = Array.from(
  new Set(
    [
      process.env.CSRC_MONITOR_ROOT,
      "/data/csrc-monitor",
      path.resolve(process.cwd(), "data/csrc-monitor"),
      path.resolve(process.cwd(), "../data/csrc-monitor"),
      path.resolve(process.cwd(), "../../data/csrc-monitor"),
      path.resolve(process.cwd(), "../csrc_monitor_deployment_package"),
      path.resolve(process.cwd(), "../../csrc_monitor_deployment_package"),
    ].filter(Boolean),
  ),
) as string[];

function buildDemoRegulatoryPayload(): RegulatoryDashboardPayload {
  const administrativePenaltyCount = DEMO_REGULATORY_CASES.filter(
    (item) => item.caseType === "administrative_penalty",
  ).length;
  const regulatoryMeasuresCount = DEMO_REGULATORY_CASES.length - administrativePenaltyCount;

  return {
    available: true,
    sourceRoot: null,
    sourceRootLabel: "内置 Demo 数据（仿真监管样本）",
    todayCount: 0,
    weekCount: 4,
    monthCount: 23,
    totalCases: 20713,
    latestScanStart: "2026-03-18 13:53:03",
    latestScanEnd: "2026-03-18 14:27:10",
    latestChangeLabel: "2026-03-17 / administrative_penalty / jiangsu",
    latestCases: DEMO_REGULATORY_CASES.slice(0, 4),
    caseRecords: DEMO_REGULATORY_CASES,
    caseListTotal: 20713,
    caseListPage: 1,
    caseListPageSize: 20,
    caseListTotalPages: 1036,
    changeLogs: DEMO_CHANGE_LOGS,
    weeklyDigest: DEMO_WEEKLY_DIGEST,
    typeStats: [
      {
        caseType: "administrative_penalty",
        typeDisplay: CASE_TYPES.administrative_penalty,
        count: 4715,
        widthPercent: 29,
      },
      {
        caseType: "regulatory_measures",
        typeDisplay: CASE_TYPES.regulatory_measures,
        count: 15998,
        widthPercent: 100,
      },
    ],
  };
}

function toChangeLogEntries(changeLog: unknown[]): RegulatoryChangeLogEntry[] {
  return changeLog
    .flatMap((row, index) => {
      if (!Array.isArray(row) || row.length < 7) {
        return [];
      }

      const [dateRaw, caseTypeRaw, regionCodeRaw, addedUrlsRaw, removedUrlsRaw, addedTitlesRaw, removedTitlesRaw] =
        row;
      if (
        (caseTypeRaw !== "administrative_penalty" &&
          caseTypeRaw !== "regulatory_measures") ||
        typeof dateRaw !== "string"
      ) {
        return [];
      }

      const caseType = caseTypeRaw as RegulatoryCaseType;
      const regionCode = typeof regionCodeRaw === "string" ? regionCodeRaw : "";
      const addedTitles = Array.isArray(addedTitlesRaw)
        ? addedTitlesRaw.filter((item): item is string => typeof item === "string")
        : [];
      const removedTitles = Array.isArray(removedTitlesRaw)
        ? removedTitlesRaw.filter((item): item is string => typeof item === "string")
        : [];
      const addedUrls = Array.isArray(addedUrlsRaw)
        ? addedUrlsRaw.filter((item): item is string => typeof item === "string")
        : [];
      const removedUrls = Array.isArray(removedUrlsRaw)
        ? removedUrlsRaw.filter((item): item is string => typeof item === "string")
        : [];

      return [
        {
          id: `change-log-${dateRaw}-${caseType}-${regionCode || "central"}-${index}`,
          date: dateRaw,
          caseType,
          typeDisplay: CASE_TYPES[caseType],
          regionCode,
          regionName: REGION_NAMES[regionCode] || regionCode || "中央",
          addedCount: addedTitles.length,
          removedCount: removedTitles.length,
          addedTitles,
          removedTitles,
          addedUrls,
          removedUrls,
        } satisfies RegulatoryChangeLogEntry,
      ];
    })
    .sort((left, right) => right.date.localeCompare(left.date, "zh-CN"));
}

function buildWeeklyDigest(
  weekCount: number,
  monthCount: number,
  typeStats: RegulatoryDashboardPayload["typeStats"],
  latestChangeLabel: string | null,
): RegulatoryWeeklyDigest {
  return {
    title: "监管发文周报",
    dateRangeLabel: "最近 7 日滚动视图",
    summary:
      "该周报用于给管理层快速浏览近期行政处罚与监管措施的数量变化、主要地域来源与最近一次增量扫描。",
    highlights: [
      `近 7 日新增 ${weekCount} 条监管发文，近 30 日累计新增 ${monthCount} 条。`,
      `最近一次变更记录：${latestChangeLabel ?? "暂无变更记录"}。`,
      "真实接入数据包后，这里可继续扩展为地区排行、机构排行和周报导出入口。",
    ],
    metrics: [
      {
        label: "近 7 日新增",
        value: String(weekCount),
      },
      {
        label: "近 30 日新增",
        value: String(monthCount),
      },
      {
        label: CASE_TYPES.administrative_penalty,
        value: String(
          typeStats.find((item) => item.caseType === "administrative_penalty")?.count ?? 0,
        ),
      },
      {
        label: CASE_TYPES.regulatory_measures,
        value: String(
          typeStats.find((item) => item.caseType === "regulatory_measures")?.count ?? 0,
        ),
      },
    ],
  };
}

function parseCaseTypeAndRegion(stem: string): {
  caseType: RegulatoryCaseType;
  regionCode: string;
} | null {
  const cleaned = stem
    .replace(/^contents_of_csrc_/, "")
    .replace(/^links_to_csrc_/, "");

  if (cleaned.startsWith("administrative_penalty_")) {
    return {
      caseType: "administrative_penalty",
      regionCode: cleaned.replace(/^administrative_penalty_/, ""),
    };
  }

  if (cleaned.startsWith("regulatory_measures_")) {
    return {
      caseType: "regulatory_measures",
      regionCode: cleaned.replace(/^regulatory_measures_/, ""),
    };
  }

  return null;
}

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function cnNumberToInt(text: string) {
  const cleaned = text.replaceAll("廿", "二十").replaceAll("卅", "三十");
  if (cleaned === "十") {
    return 10;
  }
  if (cleaned.includes("十")) {
    const [left, right] = cleaned.split("十", 2);
    const tens = left ? (CN_NUMBERS[left] ?? 0) : 1;
    const ones = right ? (CN_NUMBERS[right] ?? 0) : 0;
    return tens * 10 + ones;
  }

  let total = 0;
  for (const char of cleaned) {
    total = total * 10 + (CN_NUMBERS[char] ?? 0);
  }
  return total;
}

function extractDateValue(text: string | null | undefined): Date | null {
  if (!text) {
    return null;
  }

  const cleaned = String(text)
    .replaceAll("：", ":")
    .replaceAll("/", "-")
    .replaceAll(".", "-")
    .replaceAll("\u3000", " ")
    .trim();

  const match = cleaned.match(/(20\d{2})[-年](\d{1,2})[-月](\d{1,2})日?/);
  if (match) {
    const [, year, month, day] = match;
    const parsed = new Date(
      Number(year),
      Number(month) - 1,
      Number(day),
      0,
      0,
      0,
      0,
    );
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  const chineseMatch = cleaned.match(
    /([零〇○O一二三四五六七八九]{4})年([一二三四五六七八九十廿卅]{1,3})月([一二三四五六七八九十廿卅]{1,3})日/,
  );
  if (!chineseMatch) {
    return null;
  }

  const [, yearText, monthText, dayText] = chineseMatch;
  const year = Number(
    yearText
      .split("")
      .map((char) => YEAR_DIGITS[char] ?? "")
      .join(""),
  );
  const month = cnNumberToInt(monthText);
  const day = cnNumberToInt(dayText);
  const parsed = new Date(year, month - 1, day, 0, 0, 0, 0);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function toIsoDate(dateValue: Date | null): string | null {
  if (!dateValue) {
    return null;
  }
  return `${dateValue.getFullYear()}-${pad(dateValue.getMonth() + 1)}-${pad(dateValue.getDate())}`;
}

function normalizeBodyText(text: string | null | undefined): string {
  if (!text) {
    return "";
  }

  return String(text)
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/^#TRS_AUTOADD_[\s\S]*?\/\*\*---JSON--[\s\S]*?--\*\*\//, "")
    .replace(/^#TRS_AUTOADD_[\s\S]*?(?=证监|中国证券监督管理委员会|〔20|证监罚字)/, "")
    .replaceAll("【打印】", "")
    .replaceAll("【关闭窗口】", "")
    .replace(/\n\s*\n\s*\n+/g, "\n\n")
    .trim();
}

function buildSummary(text: string | null | undefined): string {
  const normalized = normalizeBodyText(text).replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "暂无正文摘要。";
  }
  return normalized.length > 120 ? `${normalized.slice(0, 120)}...` : normalized;
}

function toDisplayRoot(root: string) {
  if (root.includes("csrc_monitor_deployment_package 2")) {
    return "csrc_monitor_deployment_package 2";
  }
  if (root.includes("csrc_monitor_deployment_package 3")) {
    return "csrc_monitor_deployment_package 3";
  }
  return path.basename(root);
}

async function pathExists(target: string) {
  try {
    await fs.access(target);
    return true;
  } catch {
    return false;
  }
}

async function findMonitorRoot() {
  for (const candidate of CANDIDATE_ROOTS) {
    const contentsDir = path.join(candidate, "contents");
    const apiFile = path.join(candidate, "api.py");
    if ((await pathExists(contentsDir)) && (await pathExists(apiFile))) {
      return candidate;
    }
  }
  return null;
}

async function readJson<T>(filePath: string, fallback: T): Promise<T> {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

async function loadCaseRecords(root: string): Promise<RegulatoryCaseRecord[]> {
  const contentsDir = path.join(root, "contents");
  const entries = await fs.readdir(contentsDir);
  const files = entries.filter(
    (item) => item.startsWith("contents_of_csrc_") && item.endsWith(".json"),
  );

  const allRecords = await Promise.all(
    files.map(async (fileName) => {
      const parsed = parseCaseTypeAndRegion(fileName.replace(/\.json$/, ""));
      if (!parsed) {
        return [];
      }

      const contentsPath = path.join(contentsDir, fileName);
      const rows = await readJson<unknown[]>(contentsPath, []);
      if (!Array.isArray(rows)) {
        return [];
      }

      const linksPath = path.join(
        root,
        "links",
        fileName.replace("contents_of", "links_to"),
      );
      const linksPayload = await readJson<unknown[]>(linksPath, [[], [], []]);
      const sourceUrls =
        Array.isArray(linksPayload) &&
        Array.isArray(linksPayload[0]) &&
        linksPayload[0].every((item) => typeof item === "string")
          ? (linksPayload[0] as string[])
          : [];

      return rows.flatMap((row, index) => {
        if (!Array.isArray(row) || row.length < 10) {
          return [];
        }

        const isHeaderStyle =
          String(row[0] || "").trim() === "索  引  号" &&
          String(row[2] || "").trim() === "发布机构";

        const title = String(isHeaderStyle ? row[7] : row[7] || "").trim();
        const publisher = String(isHeaderStyle ? row[3] : row[2] || "").trim();
        const publishDateRaw = String(isHeaderStyle ? row[9] : row[3] || "").trim();
        const decisionDateRaw = String(isHeaderStyle ? row[9] : row[9] || "").trim();
        const docNo = String(isHeaderStyle ? row[6] : row[5] || "").trim();
        const bodyText = String(row[8] || "");
        const publishDate = extractDateValue(publishDateRaw);
        const decisionDate = extractDateValue(decisionDateRaw);
        const sourceUrl = sourceUrls[index] || "";

        if (!title && !bodyText) {
          return [];
        }

        return [
          {
            id: `${parsed.caseType}__${parsed.regionCode || "central"}__${String(row[0] || title)}`,
            caseType: parsed.caseType,
            typeDisplay: CASE_TYPES[parsed.caseType],
            regionCode: parsed.regionCode,
            regionName: REGION_NAMES[parsed.regionCode] || parsed.regionCode || "中央",
            publisher,
            publishDateRaw,
            publishDateIso: toIsoDate(publishDate),
            decisionDateRaw,
            decisionDateIso: toIsoDate(decisionDate),
            title,
            docNo,
            summary: buildSummary(bodyText),
            sourceUrl,
          } satisfies RegulatoryCaseRecord,
        ];
      });
    }),
  );

  return allRecords
    .flat()
    .sort((left, right) => {
      const leftDate =
        left.publishDateIso || left.decisionDateIso || left.publishDateRaw || left.decisionDateRaw;
      const rightDate =
        right.publishDateIso ||
        right.decisionDateIso ||
        right.publishDateRaw ||
        right.decisionDateRaw;
      return String(rightDate).localeCompare(String(leftDate), "zh-CN");
    });
}

export async function loadRegulatoryDashboardData(): Promise<RegulatoryDashboardPayload> {
  const root = await findMonitorRoot();
  if (!root) {
    return buildDemoRegulatoryPayload();
  }

  const [scanRecord, changeLog, records] = await Promise.all([
    readJson<unknown[]>(path.join(root, "scan_record.json"), []),
    readJson<unknown[]>(path.join(root, "change_log.json"), []),
    loadCaseRecords(root),
  ]);

  const latestScanRow =
    Array.isArray(scanRecord) && Array.isArray(scanRecord[scanRecord.length - 1])
      ? (scanRecord[scanRecord.length - 1] as unknown[])
      : [];
  const latestScanStart =
    typeof latestScanRow[0] === "string" ? latestScanRow[0] : null;
  const latestScanEnd =
    typeof latestScanRow[1] === "string" ? latestScanRow[1] : null;

  const latestChangeRow =
    Array.isArray(changeLog) && Array.isArray(changeLog[changeLog.length - 1])
      ? (changeLog[changeLog.length - 1] as unknown[])
      : [];
  const latestChangeLabel =
    latestChangeRow.length >= 3
      ? `${String(latestChangeRow[0] || "")} / ${String(latestChangeRow[1] || "")} / ${String(latestChangeRow[2] || "central")}`
      : null;

  const now = new Date();
  const todayIso = toIsoDate(now);
  const weekAgo = new Date(now);
  weekAgo.setDate(now.getDate() - 7);
  const monthAgo = new Date(now);
  monthAgo.setDate(now.getDate() - 30);

  let todayCount = 0;
  let weekCount = 0;
  let monthCount = 0;
  let administrativePenaltyCount = 0;
  let regulatoryMeasuresCount = 0;

  for (const record of records) {
    const effectiveDate =
      record.publishDateIso || record.decisionDateIso || null;
    if (effectiveDate) {
      if (effectiveDate === todayIso) {
        todayCount += 1;
      }
      if (effectiveDate >= toIsoDate(weekAgo)!) {
        weekCount += 1;
      }
      if (effectiveDate >= toIsoDate(monthAgo)!) {
        monthCount += 1;
      }
    }

    if (record.caseType === "administrative_penalty") {
      administrativePenaltyCount += 1;
    } else {
      regulatoryMeasuresCount += 1;
    }
  }

  const totalCases = records.length;
  if (!totalCases) {
    return buildDemoRegulatoryPayload();
  }
  const maxTypeCount = Math.max(administrativePenaltyCount, regulatoryMeasuresCount, 1);
  const typeStats: RegulatoryDashboardPayload["typeStats"] = [
    {
      caseType: "administrative_penalty",
      typeDisplay: CASE_TYPES.administrative_penalty,
      count: administrativePenaltyCount,
      widthPercent: Math.max(
        18,
        Math.round((administrativePenaltyCount / maxTypeCount) * 100),
      ),
    },
    {
      caseType: "regulatory_measures",
      typeDisplay: CASE_TYPES.regulatory_measures,
      count: regulatoryMeasuresCount,
      widthPercent: Math.max(
        18,
        Math.round((regulatoryMeasuresCount / maxTypeCount) * 100),
      ),
    },
  ];
  const changeLogEntries = toChangeLogEntries(changeLog);

  return {
    available: true,
    sourceRoot: root,
    sourceRootLabel: toDisplayRoot(root),
    todayCount,
    weekCount,
    monthCount,
    totalCases,
    latestScanStart,
    latestScanEnd,
    latestChangeLabel,
    latestCases: records.slice(0, 8),
    caseRecords: records.slice(0, 20),
    caseListTotal: totalCases,
    caseListPage: 1,
    caseListPageSize: 20,
    caseListTotalPages: Math.max(1, Math.ceil(totalCases / 20)),
    changeLogs: changeLogEntries,
    weeklyDigest: buildWeeklyDigest(
      weekCount,
      monthCount,
      typeStats,
      latestChangeLabel,
    ),
    typeStats,
  };
}
