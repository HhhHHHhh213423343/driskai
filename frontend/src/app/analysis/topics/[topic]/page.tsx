import { redirect } from "next/navigation";

import { Layout } from "../../../../components/layout/Layout";
import {
  ThemeConfig,
  type AnalysisTopicKey,
} from "../../../../theme/ThemeConfig";

type TopicAnalysisPageProps = {
  params: Promise<{
    topic: string;
  }>;
};

const validTopics = new Set<AnalysisTopicKey>(
  ThemeConfig.analysisTopics.map((item) => item.key),
);

export default async function TopicAnalysisPage({
  params,
}: TopicAnalysisPageProps) {
  const { topic } = await params;

  if (!validTopics.has(topic as AnalysisTopicKey)) {
    redirect("/analysis/topics/macro");
  }

  return (
    <Layout
      key={`${topic}-topic-analysis`}
      pageMode="topic-analysis"
      initialTopic={topic as AnalysisTopicKey}
      initialCompanyName=""
    />
  );
}
