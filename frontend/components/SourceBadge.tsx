import type { Source } from "@/lib/api";

type Props = {
  source: Source;
};

export function SourceBadge({ source }: Props) {
  const label = source.authority_score >= 0.8 ? "高信頼" : source.authority_score >= 0.5 ? "中信頼" : "要確認";
  const tone =
    source.authority_score >= 0.8
      ? "border-[#1de9ff]/55 bg-[#effdff] text-[#074a55]"
      : source.authority_score >= 0.5
        ? "border-[#ceff42]/60 bg-[#fbffed] text-[#3f5700]"
        : "border-[#ff2d92]/45 bg-[#fff2f8] text-[#781542]";
  // ブラックリスト方式で XSS を防止（より拡張性が高い）
  const isUnsafeUrl = source.source_url.toLowerCase().startsWith("javascript:");
  const safeUrl = isUnsafeUrl ? "#" : source.source_url;

  return (
    <a
      href={safeUrl}
      target="_blank"
      rel="noopener noreferrer"
      className={`block rounded border p-3 text-sm transition hover:-translate-y-0.5 hover:shadow-md ${tone}`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-semibold">{source.title}</span>
        <span className="shrink-0 rounded bg-white/70 px-2 py-1 text-xs font-semibold">{label}</span>
      </div>
      <div className="mt-1 text-xs text-[#24162d]/70">
        {source.organization ?? "不明"} / chunk {source.chunk_index} / similarity{" "}
        {source.similarity.toFixed(2)}
      </div>
    </a>
  );
}
