import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "燃点 · 创作工作台",
  description: "从想法到三平台发布包的本地创作控制台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
