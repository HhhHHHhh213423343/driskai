"use client";

import { startTransition, useState } from "react";
import { DatabaseZap, Send, ShieldEllipsis } from "lucide-react";

import { ThemeConfig } from "../../theme/ThemeConfig";

type ChatMessage = {
  role: "assistant" | "user";
  content: string;
};

type KnowledgeBaseQAProps = {
  companyName: string;
  chatEndpoint?: string;
};

export function KnowledgeBaseQA({
  companyName,
  chatEndpoint = "/api/v1/knowledge-base/chat",
}: KnowledgeBaseQAProps) {
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "你可以直接提问企业风险、财务表现或法律事件。我会先检索 PostgreSQL 的 risk_events 结构化风险，再由服务端向 FastAsk 发起补充问答。",
    },
  ]);

  async function handleAsk() {
    const normalizedQuestion = question.trim();
    if (!normalizedQuestion || isLoading) {
      return;
    }

    setQuestion("");
    setMessages((current) => [
      ...current,
      { role: "user", content: normalizedQuestion },
    ]);
    setIsLoading(true);

    try {
      const response = await fetch(chatEndpoint, {
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          company_name: companyName,
          question: normalizedQuestion,
          max_events: 8,
        }),
      });

      let payload: Record<string, unknown> | null = null;
      try {
        payload = (await response.json()) as Record<string, unknown>;
      } catch {
        payload = null;
      }

      if (!response.ok) {
        const detail =
          typeof payload?.detail === "string"
            ? payload.detail
            : `知识库请求失败: ${response.status}`;
        throw new Error(detail);
      }

      const reply =
        typeof payload?.answer === "string" && payload.answer.trim()
          ? payload.answer
          : "知识库没有返回可用内容。";

      startTransition(() => {
        setMessages((current) => [
          ...current,
          { role: "assistant", content: reply },
        ]);
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "未知错误";

      startTransition(() => {
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: `知识库问答暂未连通：${message}。当前部署已改为后端代理 FastAsk，避免在浏览器暴露密钥。`,
          },
        ]);
      });
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[0.7fr_1.3fr]">
      <div className={`${ThemeConfig.surfaces.glassCard} p-6`}>
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#F4F8EA] text-[#5D7F17]">
            <DatabaseZap className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-[#5D7F17]">FastAsk RAG</p>
            <h3 className="font-brand-title text-xl font-semibold text-[#2D2D2D]">
              实时风险注入
            </h3>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-[#E5E1D8] bg-white p-5 shadow-sm">
          <p className="text-sm text-[#6F6A61]">当前企业</p>
          <p className="mt-2 text-lg font-semibold text-[#2D2D2D]">
            {companyName}
          </p>
          <p className="mt-4 text-sm leading-7 text-[#6F6A61]">
            问答由后端统一编排：先读取 PostgreSQL 中的 `risk_events`
            结构化事件，再把整理后的上下文传给 FastAsk 兼容接口，浏览器端不再直接持有 API Key。
          </p>
        </div>

        <div className="mt-6 rounded-2xl border border-dashed border-[#D7E6B3] bg-[#F4F8EA] p-5">
          <div className="flex items-start gap-3">
            <ShieldEllipsis className="mt-0.5 h-5 w-5 text-[#5D7F17]" />
            <p className="text-sm leading-6 text-[#5D7F17]">
              公网部署建议继续保持这种后端代理模式，把 FastAsk 令牌只放在服务端环境变量里。
            </p>
          </div>
        </div>
      </div>

      <div className={`${ThemeConfig.surfaces.glassCard} flex min-h-[520px] flex-col p-6`}>
        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-7 ${
                message.role === "user"
                  ? "ml-auto bg-[#9E3D32] text-white"
                  : "bg-white text-[#2D2D2D] shadow-sm"
              }`}
            >
              {message.content}
            </div>
          ))}
          {isLoading ? (
            <div className="max-w-[90%] rounded-2xl bg-white px-4 py-3 text-sm text-[#6F6A61] shadow-sm">
              正在整理实时风险上下文并请求服务端知识库...
            </div>
          ) : null}
        </div>

        <div className="mt-6 rounded-[28px] border border-[#E5E1D8] bg-white p-3 shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="输入你想追问的企业问题，例如：最近一个月法律风险是否在上升？"
              className="min-h-[96px] flex-1 resize-none rounded-2xl border-0 bg-transparent px-3 py-2 text-sm leading-7 text-[#2D2D2D] outline-none placeholder:text-[#8A847A]"
            />
            <button
              type="button"
              onClick={handleAsk}
              disabled={isLoading}
              className="relative inline-flex h-14 items-center justify-center gap-2 overflow-hidden rounded-2xl bg-[#86BC25] px-6 text-sm font-medium text-white transition hover:bg-[#769f21] disabled:cursor-not-allowed disabled:bg-[#BFD98A]"
            >
              {isLoading ? <span className="scan-sheen" /> : null}
              <Send className="relative z-10 h-4 w-4" />
              <span className="relative z-10">
                {isLoading ? "分析中" : "发送到知识库"}
              </span>
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
