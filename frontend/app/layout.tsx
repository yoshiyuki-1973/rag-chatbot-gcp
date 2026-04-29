import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "スポーツルールRAGチャットボット",
  description: "出典付きで回答するスポーツ向けRAGチャットボット"
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
