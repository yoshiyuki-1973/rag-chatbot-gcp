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

export function MessageList({ messages, loading }: Props) {
  return (
    <div className="flex-1 space-y-4 overflow-y-auto p-4">
      {messages.length === 0 ? (
        <div className="rounded border border-line bg-white p-4">
          <p className="text-lg font-semibold">スポーツルールRAGチャットボット</p>
          <p className="mt-2 text-sm text-ink/70">
            質問を送ると、回答と参照した出典が表示されます。
          </p>
        </div>
      ) : null}
      {messages.map((message, index) => (
        <article
          key={message.id}
          className={`max-w-3xl rounded border p-4 ${
            message.role === "user"
              ? "ml-auto border-ink bg-ink text-white"
              : "mr-auto border-line bg-white"
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
        <div className="mr-auto rounded border border-line bg-white p-4 text-sm" aria-live="polite">
          回答を生成しています...
        </div>
      ) : null}
    </div>
  );
}
