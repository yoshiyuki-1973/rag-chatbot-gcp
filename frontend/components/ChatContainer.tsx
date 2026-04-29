"use client";

import { useMemo, useState } from "react";
import { sendChat } from "@/lib/api";
import { InputArea } from "./InputArea";
import { type ChatMessage, MessageList } from "./MessageList";

export function ChatContainer() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionId = useMemo(() => crypto.randomUUID(), []);

  async function submit() {
    const trimmed = query.trim();
    if (!trimmed || loading) {
      return;
    }
    setQuery("");
    setError(null);
    setLoading(true);
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: trimmed }]);
    try {
      const response = await sendChat(trimmed, sessionId);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "assistant", content: response.answer, sources: response.sources }
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "エラーが発生しました。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col border-x border-line bg-field">
      <header className="flex items-center justify-between border-b border-line bg-white px-4 py-3">
        <h1 className="text-lg font-semibold">スポーツルールRAGチャットボット</h1>
        <a className="text-sm font-medium text-moss" href="/search">
          検索
        </a>
      </header>
      {error ? (
        <div className="border-b border-brick bg-white px-4 py-3 text-sm text-brick" role="alert">
          {error}
        </div>
      ) : null}
      <MessageList messages={messages} loading={loading} />
      <InputArea value={query} disabled={loading} onChange={setQuery} onSubmit={submit} />
    </main>
  );
}
