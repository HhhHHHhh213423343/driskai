import {
  BookOpenText,
  Building2,
  Globe2,
  History,
  LayoutDashboard,
  Search,
  type LucideIcon,
  Scale,
  UserCircle2,
  WalletCards,
  Waypoints,
} from "lucide-react";

export type WorkspaceKey =
  | "analysis-search"
  | "analysis-topic-macro"
  | "analysis-topic-operations-finance"
  | "analysis-topic-legal-compliance"
  | "analysis-topic-brand"
  | "dashboard"
  | "knowledge-base"
  | "report-assembly"
  | "regulatory-actions";
export type AnalysisTabKey =
  | "macro"
  | "operations"
  | "finance"
  | "legal"
  | "brand";

type SidebarItem = {
  key: WorkspaceKey;
  label: string;
  icon: LucideIcon;
  hint: string;
};

type SidebarGroup = {
  label: "D.Analysis" | "D.Data" | "D.Ask";
  items: readonly SidebarItem[];
};

type FooterItem = {
  key: "history" | "profile";
  label: string;
  icon: LucideIcon;
};

type AnalysisTab = {
  key: AnalysisTabKey;
  label: string;
  icon: LucideIcon;
  accent: string;
};

type OverviewStat = {
  label: string;
  value: string;
  hint: string;
};

export type AnalysisTopicKey =
  | "macro"
  | "operations-finance"
  | "legal-compliance"
  | "brand";

type AnalysisTopic = {
  key: AnalysisTopicKey;
  workspaceKey: WorkspaceKey;
  title: string;
  eyebrow: string;
  description: string;
  sections: readonly {
    title: string;
    description: string;
    items: readonly string[];
  }[];
};

export const ThemeConfig: {
  brand: string;
  heroTitle: string;
  heroSubtitle: string;
  eyebrow: string;
  palette: {
    primary: string;
    accent: string;
    background: string;
    text: string;
    textMuted: string;
    border: string;
  };
  surfaces: {
    canvas: string;
    glassCard: string;
    glassCardMuted: string;
    tabIdle: string;
    tabActive: string;
    pill: string;
  };
  sidebarItems: readonly SidebarItem[];
  sidebarGroups: readonly SidebarGroup[];
  footerItems: readonly FooterItem[];
  analysisTabs: readonly AnalysisTab[];
  analysisTopics: readonly AnalysisTopic[];
  quickPrompts: readonly string[];
  overviewStats: readonly OverviewStat[];
} = {
  brand: "D.Risk AI",
  heroTitle: "可信、深度的商业风险感知与分析平台",
  heroSubtitle:
    "面向宏观、业务、财务、法律与品牌舆情的企业级检索分析平台，强调证据链、可追溯来源与快速研判。",
  eyebrow: "开始分析",
  palette: {
    primary: "#86BC25",
    accent: "#0E0E0E",
    background: "#F5F6F4",
    text: "#171717",
    textMuted: "#5F6360",
    border: "#D8DECF",
  },
  surfaces: {
    canvas:
      "bg-[linear-gradient(180deg,_#F7F8F6_0%,_#ECEFED_100%)]",
    glassCard:
      "rounded-lg border border-[#D8DECF] bg-white shadow-sm",
    glassCardMuted:
      "rounded-lg border border-[#D8DECF] bg-[#FAFBF8] shadow-sm",
    tabIdle:
      "rounded-lg border border-[#D8DECF] bg-white text-[#5F6360] shadow-sm transition hover:border-[#86BC25] hover:bg-[#F7FAF1] hover:text-[#171717]",
    tabActive:
      "rounded-lg border border-[#86BC25] bg-[#EEF7E0] text-[#171717] shadow-sm",
    pill: "rounded-md border border-[#B7DB82] bg-[#EEF7E0] px-3 py-1 text-xs font-medium text-[#2B5010]",
  },
  sidebarItems: [
    {
      key: "analysis-search",
      label: "搜索",
      icon: Search,
      hint: "企业检索 / 总览",
    },
    {
      key: "dashboard",
      label: "数据看板",
      icon: LayoutDashboard,
      hint: "趋势总览 / 图表",
    },
    {
      key: "knowledge-base",
      label: "知识库问答",
      icon: BookOpenText,
      hint: "FastAsk RAG",
    },
    {
      key: "report-assembly",
      label: "生成报告",
      icon: Waypoints,
      hint: "综合报告生成",
    },
  ],
  sidebarGroups: [
    {
      label: "D.Analysis",
      items: [
        {
          key: "analysis-search",
          label: "搜索",
          icon: Search,
          hint: "企业检索 / 总览",
        },
        {
          key: "analysis-topic-macro",
          label: "宏观环境及行业分析",
          icon: Globe2,
          hint: "政策 / 经济 / 行业",
        },
        {
          key: "analysis-topic-operations-finance",
          label: "企业业务运营分析以及财务状况分析",
          icon: WalletCards,
          hint: "运营 / 财务 / 模拟",
        },
        {
          key: "analysis-topic-legal-compliance",
          label: "法律及合规风险分析",
          icon: Scale,
          hint: "诉讼 / 合规 / 处置",
        },
        {
          key: "analysis-topic-brand",
          label: "品牌舆情分析",
          icon: Building2,
          hint: "动态监测 / 议题热度",
        },
      ],
    },
    {
      label: "D.Data",
      items: [
        {
          key: "dashboard",
          label: "数据看板",
          icon: LayoutDashboard,
          hint: "风险检索数据总览",
        },
      ],
    },
    {
      label: "D.Ask",
      items: [
        {
          key: "knowledge-base",
          label: "Knowledge Base Q&A",
          icon: BookOpenText,
          hint: "公司知识库问答",
        },
      ],
    },
  ],
  footerItems: [
    {
      key: "history",
      label: "历史记录",
      icon: History,
    },
    {
      key: "profile",
      label: "个人中心",
      icon: UserCircle2,
    },
  ],
  analysisTabs: [
    {
      key: "macro",
      label: "宏观环境及行业分析",
      icon: Globe2,
      accent: "from-[#EAF4D8] via-[#F8FBF1] to-transparent",
    },
    {
      key: "operations",
      label: "企业业务运营分析",
      icon: Waypoints,
      accent: "from-[#EDF5DF] via-[#FBFCF6] to-transparent",
    },
    {
      key: "finance",
      label: "企业财务状况分析",
      icon: WalletCards,
      accent: "from-[#F0F6E3] via-[#FBFCF7] to-transparent",
    },
    {
      key: "legal",
      label: "法律诉讼风险分析",
      icon: Scale,
      accent: "from-[#EEF5E0] via-[#FAFCF4] to-transparent",
    },
    {
      key: "brand",
      label: "品牌舆情分析",
      icon: Building2,
      accent: "from-[#EDF4E2] via-[#FBFCF7] to-transparent",
    },
  ],
  analysisTopics: [
    {
      key: "macro",
      workspaceKey: "analysis-topic-macro",
      eyebrow: "D.Analysis / Topic",
      title: "宏观环境及行业分析",
      description:
        "分别分析宏观环境和行业走势，覆盖政策、经济、环境、竞争格局、商业模式与技术演进。",
      sections: [
        {
          title: "宏观环境",
          description: "包括政策、经济、环境不同维度分析。",
          items: [
            "国际最新政策与 reference 摘要",
            "全球经济趋势图",
            "不同环境变量趋势图",
            "基于宏观环境的行动建议",
          ],
        },
        {
          title: "行业分析",
          description: "支持搜索和筛选区间，输出行业结构化判断。",
          items: [
            "市场规模",
            "竞争等级：直接、间接、潜在",
            "商业模式与技术趋势",
            "根据行业分析给出的建议",
          ],
        },
      ],
    },
    {
      key: "operations-finance",
      workspaceKey: "analysis-topic-operations-finance",
      eyebrow: "D.Analysis / Topic",
      title: "企业业务运营分析以及财务状况分析",
      description:
        "把运营效率、组织配置、同业对比、财务表现与场景模拟放在同一个专题视角下评估。",
      sections: [
        {
          title: "业务运营",
          description: "分析企业运营状况以及待优化建议。",
          items: [
            "企业核心理念与同业对比",
            "组织架构以及人才配置对比",
            "各家运营长短板对比",
            "建议深度分析方向",
          ],
        },
        {
          title: "财务状况",
          description: "根据年度或季度财务报表分析薄弱点。",
          items: [
            "财务状况分析",
            "场景模拟：关键假设、现金流、利润、增长率",
            "财务分析建议",
          ],
        },
      ],
    },
    {
      key: "legal-compliance",
      workspaceKey: "analysis-topic-legal-compliance",
      eyebrow: "D.Analysis / Topic",
      title: "法律及合规风险分析",
      description:
        "围绕法律诉讼、合规处罚、风险传导与处置方案，形成从识别到管控的分析链路。",
      sections: [
        {
          title: "法律诉讼",
          description: "公司法律风险趋势以及重点分析。",
          items: [
            "核心风险领域与相似案例",
            "风险传导路径与后果",
            "风险管控策略矩阵",
            "风险发生后建议的后续处理方案",
            "建议深度分析方向",
          ],
        },
        {
          title: "合规",
          description: "支持自定义文本输入与合规风险检索。",
          items: ["外规处罚", "合规事件归因", "预防性整改建议"],
        },
      ],
    },
    {
      key: "brand",
      workspaceKey: "analysis-topic-brand",
      eyebrow: "D.Analysis / Topic",
      title: "品牌舆情分析",
      description:
        "实时监测公司业务、产品与关键议题舆情，评估影响力权重与潜在风险热度。",
      sections: [
        {
          title: "舆情搜索",
          description: "支持自定义文本输入，定位公司或产品相关议题。",
          items: [
            "动态监测：实时监测公司各业务或产品舆情",
            "影响力权重：媒体、KOL 等",
            "实时议题热度：时兴议题与潜在风险",
            "建议深度分析方向",
          ],
        },
      ],
    },
  ],
  quickPrompts: [
    "比亚迪股份有限公司",
    "比亚迪汽车工业有限公司",
    "比亚迪电子（国际）有限公司",
    "宁德时代新能源科技股份有限公司",
    "特斯拉（上海）有限公司",
  ],
  overviewStats: [
    {
      label: "今日风险事件总数",
      value: "18",
      hint: "当前 BYD Demo 重点来自海外合规与价格战舆情",
    },
    {
      label: "近 7 日新增",
      value: "63",
      hint: "包含宏观、财务、法律与品牌舆情四条主线",
    },
    {
      label: "高优先级事件",
      value: "7",
      hint: "集中在欧盟反补贴、海外工厂与知识产权风险",
    },
    {
      label: "深度报告快照",
      value: "9",
      hint: "支持维度报告与综合风险报告双层输出",
    },
  ],
} as const;
