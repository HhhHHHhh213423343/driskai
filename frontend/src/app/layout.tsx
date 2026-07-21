import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "D.Risk AI · 企业风险分析",
  description: "基于公开证据与结构化数据的企业风险分析工作台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
