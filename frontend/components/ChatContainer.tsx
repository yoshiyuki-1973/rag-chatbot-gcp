"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { sendChat } from "@/lib/api";
import { InputArea } from "./InputArea";
import { type ChatMessage, MessageList } from "./MessageList";

export function ChatContainer() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const sessionId = useMemo(() => crypto.randomUUID(), []);

  useEffect(() => {
    const list = messageListRef.current;
    if (!list) {
      return;
    }
    list.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

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
    <main className="relative mx-auto flex min-h-screen max-w-5xl flex-col border-x border-white/10 bg-[#120914]/80 text-[#f8f5ff] shadow-2xl shadow-black/40 backdrop-blur">
      <header className="flex items-center justify-between border-b border-white/10 bg-[#1b0d24]/90 px-4 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#1de9ff]">Sports Rule Stage</p>
          <h1 className="mt-1 text-lg font-semibold">スポーツルールRAGチャットボット</h1>
        </div>
        <a
          className="rounded border border-[#1de9ff]/60 px-3 py-2 text-sm font-semibold text-[#1de9ff] shadow-[0_0_18px_rgba(29,233,255,0.24)] transition hover:border-[#ceff42] hover:text-[#ceff42]"
          href="/search"
        >
          検索
        </a>
      </header>
      {error ? (
        <div className="border-b border-[#ff2d92]/40 bg-[#351225] px-4 py-3 text-sm text-[#ffb7d8]" role="alert">
          {error}
        </div>
      ) : null}
      <MessageList ref={messageListRef} messages={messages} loading={loading} />
      <InputArea value={query} disabled={loading} onChange={setQuery} onSubmit={submit} />
    </main>
  );
}
