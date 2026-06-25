import { forwardRef } from "react";
import type { Source } from "@/lib/api";
import { SourceBadge } from "./SourceBadge";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

type Props = {
  messages: ChatMessage[];
  loading: boolean;
};

export const MessageList = forwardRef<HTMLDivElement, Props>(function MessageList(
  { messages, loading },
  ref,
) {
  return (
    <div ref={ref} className="flex-1 space-y-4 overflow-y-auto p-4">
      {messages.length === 0 ? (
        <div className="rounded border border-white/15 bg-white/10 p-4 shadow-xl shadow-black/20 backdrop-blur">
          <p className="text-lg font-semibold text-white">スポーツルールRAGチャットボット</p>
          <p className="mt-2 text-sm text-white/70">
            質問を送ると、回答と参照した出典が表示されます。
          </p>
        </div>
      ) : null}
      {messages.map((message) => (
        <article
          key={message.id}
          className={`max-w-3xl rounded border p-4 shadow-lg ${
            message.role === "user"
              ? "ml-auto border-[#ff2d92]/70 bg-[#ff2d92] text-white shadow-[#ff2d92]/20"
              : "mr-auto border-white/15 bg-white/95 text-[#1a1020] shadow-black/20"
          }`}
        >
          <p className="whitespace-pre-wrap leading-7">{message.content}</p>
          {message.sources?.length ? (
            <div className="mt-4 grid gap-2">
              {message.sources.map((source) => (
                <SourceBadge
                  key={`${source.document_id}-${source.chunk_index}`}
                  source={source}
                />
              ))}
            </div>
          ) : null}
        </article>
      ))}
      {loading ? (
        <div className="mr-auto rounded border border-[#1de9ff]/40 bg-[#102434]/90 p-4 text-sm text-[#b9f8ff] shadow-[0_0_22px_rgba(29,233,255,0.18)]" aria-live="polite">
          回答を生成しています...
        </div>
      ) : null}
    </div>
  );
});
