import type { AnalysisTabKey } from "../../theme/ThemeConfig";
import type { AgentAnalysisPreview } from "./AnalysisTypes";

export type ReportDepth = "scan" | "deep";

export type TraceableSource = {
  id: string;
  kind: "结构化风险" | "新闻" | "财报PDF" | "研报PDF" | "数据库";
  sourceName: string;
  title: string;
  url: string;
  publishedAt: string;
  note: string;
  pageHint?: string;
};

type SectionTemplate = {
  title: string;
  body: string;
  sourceIds: string[];
};

type AgentScenarioTemplate = {
  agentName: string;
  reportType: string;
  objective: string;
  retrievalFlow: string[];
  headline: string;
  scanSummary: string;
  deepSummary: string;
  keyPoints: string[];
  deepDivePrompts: string[];
  sources: TraceableSource[];
  scanSections: SectionTemplate[];
  deepSections: SectionTemplate[];
};

export type GeneratedReport = {
  key: AnalysisTabKey;
  reportType: string;
  title: string;
  summary: string;
  createdAt: string;
  depth: ReportDepth;
  sections: SectionTemplate[];
  sources: TraceableSource[];
  analysis?: AgentAnalysisPreview;
};

export type ComprehensiveReport = {
  title: string;
  summary: string;
  createdAt: string;
  includedReportTypes: string[];
  sections: Array<{
    title: string;
    summary: string;
    reportType: string;
  }>;
};

const agentScenarios: Record<AnalysisTabKey, AgentScenarioTemplate> = {
  macro: {
    agentName: "宏观环境及行业分析 Agent",
    reportType: "macro_environment_report",
    objective:
      "重点关注欧盟/美国贸易政策、全球新能源车市占率变化与政策传导路径。",
    retrievalFlow: [
      "优先检索 risk_events 中 `macro` 类结构化风险，直接提取政策、比例变化与原始来源。",
      "若结构化事件不足，再补充 FastAsk 知识库中的行业白皮书、财报附件与外部研报。",
      "同源新闻与同主题文章通过向量相似度去重，避免同一事件重复进入分析结论。",
    ],
    headline: "{company} 的跨境政策与行业景气判断",
    scanSummary:
      "{company} 当前最核心的外部变量是欧美贸易政策与全球新能源车竞争格局变化。短期内，关税和反补贴预期会抬升海外成本与合规复杂度，但全球新能源渗透率提升仍提供长期增量空间。",
    deepSummary:
      "{company} 的宏观环境风险并非单一政策冲击，而是贸易壁垒、区域制造本地化和新能源渗透提速共同叠加的结果。深度分析应把关税、产能布局与市占率变化拆成可验证的证据链，并以时间线方式持续跟踪。",
    keyPoints: [
      "欧盟反补贴与美国关税政策是当前跨境经营的首要宏观变量。",
      "全球新能源车销量增长仍在提供行业扩容空间，但区域本地化趋势加强。",
      "建议把政策变动与海外工厂爬坡、单车盈利能力联动观察。",
    ],
    deepDivePrompts: [
      "欧盟反补贴调查对单车毛利率影响拆解",
      "美国关税与墨西哥/巴西替代市场承接能力评估",
      "全球新能源车市占率变化对 BYD 出海节奏的约束",
    ],
    sources: [
      {
        id: "macro-1",
        kind: "结构化风险",
        sourceName: "risk_events.macro",
        title: "欧盟反补贴调查与附加税预期",
        url: "https://ec.europa.eu/commission/presscorner/home/en",
        publishedAt: "2026-03-22",
        note: "结构化入库事件，后续应直接映射到原始公告页与影响比例字段。",
      },
      {
        id: "macro-2",
        kind: "新闻",
        sourceName: "Reuters",
        title: "全球电动车价格战与区域关税环境变化",
        url: "https://www.reuters.com/markets/companies/002594.SZ/",
        publishedAt: "2026-03-21",
        note: "用于交叉验证国际媒体对 BYD 出海环境的判断。",
      },
      {
        id: "macro-3",
        kind: "数据库",
        sourceName: "IEA EV Outlook",
        title: "全球新能源车渗透率与销量趋势",
        url: "https://www.iea.org/reports/global-ev-outlook-2025",
        publishedAt: "2025-05-01",
        note: "作为全球新能源市场基准数据源。",
      },
    ],
    scanSections: [
      {
        title: "政策外部性",
        body:
          "欧美贸易政策正推动 {company} 调整出海节奏。短期内附加税与审查流程会压缩出口端效率，但并未改变新能源需求长期扩张的方向。",
        sourceIds: ["macro-1", "macro-2"],
      },
      {
        title: "行业窗口",
        body:
          "全球新能源车渗透率仍在提升，行业扩容为 {company} 提供中长期增量空间，但增长红利会更多流向具备本地化制造和渠道运营能力的玩家。",
        sourceIds: ["macro-3"],
      },
    ],
    deepSections: [
      {
        title: "贸易壁垒时间线",
        body:
          "建议将欧盟调查节点、税率变化与对应车型出口结构串成时间线，以便判断 {company} 不同海外区域的政策敞口差异。",
        sourceIds: ["macro-1", "macro-2"],
      },
      {
        title: "市占率与产能耦合",
        body:
          "宏观层面的核心不是单一市占率数字，而是市占率变化是否能够被海外产能、本地销售网络和品牌定价承接。",
        sourceIds: ["macro-2", "macro-3"],
      },
    ],
  },
  operations: {
    agentName: "企业业务运营分析 Agent",
    reportType: "operations_report",
    objective:
      "跟踪仰望品牌销量、巴西/匈牙利建厂进度以及海外渠道执行效率。",
    retrievalFlow: [
      "先读取 risk_events 中 `operations` 事件，提取工厂、销量、交付与渠道相关记录。",
      "再检索知识库中的官方公告、财报附注和研报段落，补充产能与订单背景。",
      "对同一工厂进度或同一销量口径的多篇报道做向量去重，只保留首发和可信更新。",
    ],
    headline: "{company} 的海外工厂进度与高端品牌表现",
    scanSummary:
      "{company} 当前运营侧的核心看点是高端品牌销量验证与海外工厂的建设兑现。巴西、匈牙利等海外基地如果推进顺利，将显著改善关税冲击与本地交付效率。",
    deepSummary:
      "运营分析不能只看建厂“开工”新闻，更要看设备进场、认证节点、供应链本地化比例和单厂爬坡速度。对 {company} 而言，仰望品牌的销量质量与海外产能落地节奏需要合并分析。",
    keyPoints: [
      "巴西/匈牙利工厂是规避贸易壁垒与缩短交付半径的重要支点。",
      "仰望品牌销量不仅是高端化验证，也是盈利结构优化的信号。",
      "运营风险更多来自工厂建设延误、认证周期和本地供应链成熟度。",
    ],
    deepDivePrompts: [
      "仰望品牌销量质量与高端市场渗透拆解",
      "匈牙利工厂认证周期对欧洲交付效率影响",
      "巴西本地化供应链成熟度与成本改善节奏",
    ],
    sources: [
      {
        id: "ops-1",
        kind: "结构化风险",
        sourceName: "risk_events.operations",
        title: "匈牙利工厂建设节点更新",
        url: "https://www.byd.com/en/news",
        publishedAt: "2026-03-20",
        note: "应映射工厂状态、国家、建设阶段和预计投产时间。",
      },
      {
        id: "ops-2",
        kind: "新闻",
        sourceName: "Reuters",
        title: "BYD Brazil factory expansion and regional manufacturing plan",
        url: "https://www.reuters.com/markets/companies/002594.SZ/",
        publishedAt: "2026-03-18",
        note: "用于验证海外产能布局与本地化策略。",
      },
      {
        id: "ops-3",
        kind: "数据库",
        sourceName: "乘联会 / 公司公告",
        title: "仰望品牌销量与交付节奏",
        url: "https://www.byd.com/cn/InvestorRelations",
        publishedAt: "2026-03-15",
        note: "后续可替换为月度销量数据源。",
      },
    ],
    scanSections: [
      {
        title: "海外工厂兑现度",
        body:
          "{company} 在巴西与匈牙利的工厂布局，本质上是从“出口型”向“本地制造+本地交付”切换，能否如期落地决定其海外经营弹性。",
        sourceIds: ["ops-1", "ops-2"],
      },
      {
        title: "高端品牌验证",
        body:
          "仰望品牌的销量与交付质量，将成为判断 {company} 高端化是否真正打开盈利空间的关键指标。",
        sourceIds: ["ops-3"],
      },
    ],
    deepSections: [
      {
        title: "工厂爬坡拆解",
        body:
          "深度分析需要把工厂建设拆到设备、认证、供应链和人力四个节点，否则容易把“开工”误判为“具备交付能力”。",
        sourceIds: ["ops-1", "ops-2"],
      },
      {
        title: "销量质量校验",
        body:
          "仰望品牌应重点看订单结构、均价区间、交付周期与售后反馈，而不是只看单月总销量。",
        sourceIds: ["ops-3"],
      },
    ],
  },
  finance: {
    agentName: "企业财务状况分析 Agent",
    reportType: "financial_health_report",
    objective:
      "重点覆盖季度营收、盈利质量、研发投入占比与财报可追溯证据。",
    retrievalFlow: [
      "先查 risk_events 中 `finance` 动态，提取营收、利润、研发投入和资本开支相关结构化字段。",
      "若信息不足，再从 FastAsk 知识库补充财报解读、研报 PDF 摘录与图表配置。",
      "财报摘录需携带 PDF 页码或原始附件锚点，便于报告追溯。",
    ],
    headline: "{company} 的营收、研发与现金流穿透分析",
    scanSummary:
      "{company} 当前财务端的判断重点不只是营收增速，而是盈利质量、研发投入与海外扩张资本开支的平衡。财务 Agent 应优先提供可回溯到财报页码或附件的证据。",
    deepSummary:
      "财务深度分析要把营收、毛利率、现金流与研发投入放在一个统一框架里看，并把财报原文、研报解读和结构化风险事件拼成完整证据链，才能支撑管理层或投资侧使用。",
    keyPoints: [
      "研发投入占比与技术路线推进强相关，需要持续跟踪。",
      "海外建厂与渠道扩张会推高中期资本开支，需和现金流联动观察。",
      "财务结论必须挂载原始财报或 PDF 页码，避免二手摘要失真。",
    ],
    deepDivePrompts: [
      "研发投入占比与智驾/电池技术路线对应关系",
      "海外资本开支对自由现金流压力测算",
      "季度营收结构与单车盈利质量对照",
    ],
    sources: [
      {
        id: "fin-1",
        kind: "结构化风险",
        sourceName: "risk_events.finance",
        title: "季度营收与研发投入快照",
        url: "https://www.byd.com/cn/InvestorRelations",
        publishedAt: "2026-03-23",
        note: "来自结构化财务风险条目，后续建议直接携带指标字段。",
        pageHint: "财报 PDF 页码待接真实 extra_payload.page_hint",
      },
      {
        id: "fin-2",
        kind: "财报PDF",
        sourceName: "BYD Investor Relations",
        title: "比亚迪财务报告与公告入口",
        url: "https://www.byd.com/cn/InvestorRelations",
        publishedAt: "2026-03-23",
        note: "接入真实 PDF 后应支持 `#page=` 锚点跳转。",
      },
      {
        id: "fin-3",
        kind: "研报PDF",
        sourceName: "东方财富 / 券商研报",
        title: "BYD 研报聚合入口",
        url: "https://data.eastmoney.com/report/stock.jshtml",
        publishedAt: "2026-03-22",
        note: "用于补充利润率、估值与资本开支解读。",
      },
    ],
    scanSections: [
      {
        title: "盈利质量",
        body:
          "{company} 的财务判断关键是营收增长是否同步带来现金流改善，以及研发与资本开支是否保持在可承受区间。",
        sourceIds: ["fin-1", "fin-2"],
      },
      {
        title: "研发投入",
        body:
          "研发投入占比不仅关系技术竞争力，也关系未来 2-3 年产品迭代和品牌溢价能力，是财务 Agent 的核心解释变量之一。",
        sourceIds: ["fin-1", "fin-3"],
      },
    ],
    deepSections: [
      {
        title: "财报证据链",
        body:
          "深度分析必须把财报原文页码、研报段落和结构化风险字段并列展示，这样报告里的每个结论才可追溯、可复核。",
        sourceIds: ["fin-1", "fin-2", "fin-3"],
      },
      {
        title: "现金流与扩张平衡",
        body:
          "海外产能、本地渠道和技术研发都会争抢现金流，因此要拆分短中期投入节奏，判断 {company} 是否存在阶段性财务承压。",
        sourceIds: ["fin-1", "fin-3"],
      },
    ],
  },
  legal: {
    agentName: "法律诉讼风险分析 Agent",
    reportType: "legal_risk_report",
    objective:
      "重点跟踪欧盟反补贴调查、海外知识产权争议与执行信息。",
    retrievalFlow: [
      "优先检索 `legal` 类 risk_events，直接返回案件标题、重要性、来源链接与执行金额。",
      "若结构化结果不足，再检索知识库中的公告、法规文件与海外纠纷解读。",
      "所有案件结论必须保留“来源”标签，且链接到公告或判决原文。",
    ],
    headline: "{company} 的跨境调查与知识产权争议主线",
    scanSummary:
      "{company} 法律风险的关键不是案件数量，而是欧盟反补贴调查、海外知识产权纠纷和执行信息是否会直接影响出口、品牌或现金流。法律 Agent 应聚焦案件阶段与金额敞口。",
    deepSummary:
      "法律深度分析应围绕案件阶段、涉案金额、影响区域和业务链路做拆解。对 {company} 来说，跨境监管调查与知识产权诉讼的风险外溢远高于普通纠纷，必须用高优先级单独标注。",
    keyPoints: [
      "欧盟反补贴调查属于跨境经营的核心合规风险。",
      "海外知识产权纠纷会同时影响产品交付、品牌与费用率。",
      "法律条目必须保留案件阶段、涉案金额和原始链接。",
    ],
    deepDivePrompts: [
      "欧盟反补贴调查的阶段性影响路径",
      "海外知识产权纠纷对产品交付的潜在阻断",
      "执行金额与现金流风险敞口联动预警",
    ],
    sources: [
      {
        id: "legal-1",
        kind: "结构化风险",
        sourceName: "risk_events.legal",
        title: "欧盟反补贴调查最新节点",
        url: "https://ec.europa.eu/commission/presscorner/home/en",
        publishedAt: "2026-03-22",
        note: "结构化法律风险应直接挂载案件阶段、监管机构与链接。",
      },
      {
        id: "legal-2",
        kind: "新闻",
        sourceName: "Reuters",
        title: "海外知识产权争议与调查报道",
        url: "https://www.reuters.com/markets/companies/002594.SZ/",
        publishedAt: "2026-03-20",
        note: "用于交叉验证事件是否被国际媒体放大。",
      },
      {
        id: "legal-3",
        kind: "数据库",
        sourceName: "中国裁判文书网 / 监管公告",
        title: "公开判决与监管公告入口",
        url: "https://wenshu.court.gov.cn/",
        publishedAt: "2026-03-19",
        note: "后续可替换为具体案件页。",
      },
    ],
    scanSections: [
      {
        title: "监管调查主线",
        body:
          "{company} 当前最值得持续追踪的是欧盟反补贴调查，因为它可能穿透到出口定价、区域制造和渠道扩张策略。",
        sourceIds: ["legal-1", "legal-2"],
      },
      {
        title: "案件证据化",
        body:
          "法律 Agent 不应只输出“存在诉讼风险”，而要把案件阶段、原始链接、金额与受影响业务链路并列展示。",
        sourceIds: ["legal-1", "legal-3"],
      },
    ],
    deepSections: [
      {
        title: "案件优先级划分",
        body:
          "建议将案件按‘监管调查 / 知识产权 / 执行信息 / 劳务纠纷’分类，并为每类建立独立的高优先级预警阈值。",
        sourceIds: ["legal-1", "legal-2", "legal-3"],
      },
      {
        title: "外溢风险评估",
        body:
          "深度分析要回答一个问题：案件会不会影响销量、交付或品牌。如果答案是会，就不能把它仅视作法务事件。",
        sourceIds: ["legal-1", "legal-2"],
      },
    ],
  },
  brand: {
    agentName: "品牌舆情分析 Agent",
    reportType: "brand_sentiment_report",
    objective:
      "重点抓取价格战、刀片电池与智驾水平等讨论的真实情绪和风险标签。",
    retrievalFlow: [
      "先检索 `brand` 类 risk_events，提取结构化舆情摘要、正负面和原始链接。",
      "若数据库样本不足，再补充 FastAsk 知识库中的媒体稿、社媒摘录与研报评论。",
      "同一舆情事件基于向量相似度做去重，避免重复媒体转载刷屏。",
    ],
    headline: "{company} 的价格战与智驾口碑判断",
    scanSummary:
      "{company} 当前品牌舆情集中在价格战、刀片电池安全性和智驾水平讨论。舆情 Agent 不应只给情绪分数，还要保留原始媒体和社媒来源，方便后续复核与人工判断。",
    deepSummary:
      "品牌深度分析要把负面情绪拆成产品、服务、技术和合规四条子线，结合传播速度与影响面进行分级。对 {company} 来说，价格战和智驾口碑讨论都可能直接影响转化效率与品牌溢价。",
    keyPoints: [
      "价格战讨论会快速外溢到盈利预期与品牌定位。",
      "刀片电池与智驾水平是高频、高传播度话题。",
      "品牌舆情必须可追溯到原始链接，不能只存二次摘要。",
    ],
    deepDivePrompts: [
      "价格战舆情对品牌溢价的侵蚀路径",
      "刀片电池安全叙事与竞品比较分析",
      "智驾口碑分层：媒体评价、用户反馈、技术对比",
    ],
    sources: [
      {
        id: "brand-1",
        kind: "结构化风险",
        sourceName: "risk_events.brand",
        title: "价格战相关舆情摘要",
        url: "https://www.weibo.com/",
        publishedAt: "2026-03-23",
        note: "结构化舆情条目应保留正负面、传播平台与原始链接。",
      },
      {
        id: "brand-2",
        kind: "新闻",
        sourceName: "Reuters",
        title: "Chinese EV price war coverage",
        url: "https://www.reuters.com/markets/companies/002594.SZ/",
        publishedAt: "2026-03-21",
        note: "用于外媒视角校验价格战舆情的外溢影响。",
      },
      {
        id: "brand-3",
        kind: "新闻",
        sourceName: "BYD Official News",
        title: "刀片电池与智能驾驶相关官方内容",
        url: "https://www.byd.com/en/news",
        publishedAt: "2026-03-20",
        note: "用于与媒体/社媒评论做反向对照。",
      },
    ],
    scanSections: [
      {
        title: "情绪主轴",
        body:
          "{company} 当前的品牌舆情主要围绕价格战与技术口碑展开。舆情并非天然负面，但在传播链路过长时会迅速影响品牌认知。",
        sourceIds: ["brand-1", "brand-2"],
      },
      {
        title: "官方叙事对照",
        body:
          "品牌 Agent 要把官方表述与媒体、用户真实评价并列展示，才能识别‘叙事落差’是否扩大。",
        sourceIds: ["brand-2", "brand-3"],
      },
    ],
    deepSections: [
      {
        title: "情绪颗粒度",
        body:
          "建议将品牌舆情按产品性能、价格、服务体验、技术路线与合规争议拆解，分别设定预警阈值与处置动作。",
        sourceIds: ["brand-1", "brand-2", "brand-3"],
      },
      {
        title: "传播外溢路径",
        body:
          "深度分析要看舆情从社媒到财经媒体再到券商观点的传播路径，判断它是否会从讨论层面演化成财务或销量层面的真实影响。",
        sourceIds: ["brand-1", "brand-2"],
      },
    ],
  },
};

export type AgentScenario = AgentScenarioTemplate & {
  headline: string;
  objective: string;
  scanSummary: string;
  deepSummary: string;
  keyPoints: string[];
  deepDivePrompts: string[];
  sources: TraceableSource[];
  scanSections: SectionTemplate[];
  deepSections: SectionTemplate[];
};

function hydrateTemplate(text: string, companyName: string) {
  return text.replaceAll("{company}", companyName);
}

export function getAgentScenario(
  key: AnalysisTabKey,
  companyName: string,
): AgentScenario {
  const template = agentScenarios[key];

  return {
    ...template,
    headline: hydrateTemplate(template.headline, companyName),
    objective: hydrateTemplate(template.objective, companyName),
    scanSummary: hydrateTemplate(template.scanSummary, companyName),
    deepSummary: hydrateTemplate(template.deepSummary, companyName),
    keyPoints: template.keyPoints.map((item) => hydrateTemplate(item, companyName)),
    deepDivePrompts: template.deepDivePrompts.map((item) =>
      hydrateTemplate(item, companyName),
    ),
    sources: template.sources.map((item) => ({
      ...item,
      title: hydrateTemplate(item.title, companyName),
      note: hydrateTemplate(item.note, companyName),
    })),
    scanSections: template.scanSections.map((item) => ({
      ...item,
      title: hydrateTemplate(item.title, companyName),
      body: hydrateTemplate(item.body, companyName),
    })),
    deepSections: template.deepSections.map((item) => ({
      ...item,
      title: hydrateTemplate(item.title, companyName),
      body: hydrateTemplate(item.body, companyName),
    })),
  };
}

export function buildGeneratedReport(
  key: AnalysisTabKey,
  companyName: string,
  depth: ReportDepth,
): GeneratedReport {
  const scenario = getAgentScenario(key, companyName);
  const createdAt = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());

  return {
    key,
    reportType: scenario.reportType,
    title:
      depth === "deep"
        ? `${companyName}${scenario.agentName}深度报告`
        : `${companyName}${scenario.agentName}检索报告`,
    summary: depth === "deep" ? scenario.deepSummary : scenario.scanSummary,
    createdAt,
    depth,
    sections: depth === "deep" ? scenario.deepSections : scenario.scanSections,
    sources: scenario.sources,
  };
}

export function buildComprehensiveReport(
  companyName: string,
  reports: GeneratedReport[],
): ComprehensiveReport {
  const createdAt = new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());

  const sections = reports.map((item) => ({
    title: item.title,
    summary: item.summary,
    reportType: item.reportType,
  }));

  return {
    title: `${companyName} 综合风险报告`,
    summary:
      `${companyName} 综合风险报告由 ${reports.length} 个维度分析自动汇总而成，` +
      "已将单项报告按宏观、业务、财务、法律、品牌五类证据链汇总，适合用于内部周报或管理层汇报的首轮版本。",
    createdAt,
    includedReportTypes: reports.map((item) => item.reportType),
    sections,
  };
}
