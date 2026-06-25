"use client";

import { useState } from "react";
import { searchDocuments, type SearchResult } from "@/lib/api";
import { SourceBadge } from "@/components/SourceBadge";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const trimmed = query.trim();
    if (!trimmed || loading) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResults(await searchDocuments(trimmed));
    } catch (err) {
      setError(err instanceof Error ? err.message : "エラーが発生しました。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative mx-auto min-h-screen max-w-5xl border-x border-white/10 bg-[#120914]/80 text-[#f8f5ff] shadow-2xl shadow-black/40 backdrop-blur">
      <header className="flex items-center justify-between border-b border-white/10 bg-[#1b0d24]/90 px-4 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#ceff42]">Source Search</p>
          <h1 className="mt-1 text-lg font-semibold">ドキュメント検索</h1>
        </div>
        <a
          className="rounded border border-[#ff2d92]/60 px-3 py-2 text-sm font-semibold text-[#ff8fc4] shadow-[0_0_18px_rgba(255,45,146,0.24)] transition hover:border-[#1de9ff] hover:text-[#1de9ff]"
          href="/"
        >
          チャット
        </a>
      </header>
      <form
        className="flex gap-2 border-b border-white/10 bg-[#160b1f]/95 p-4"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label className="sr-only" htmlFor="search-query">
          検索クエリ
        </label>
        <input
          id="search-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-11 flex-1 rounded border border-white/15 bg-white/95 px-3 text-[#1a1020] outline-none transition placeholder:text-[#6e6075] focus:border-[#ceff42] focus:shadow-[0_0_0_3px_rgba(206,255,66,0.24)]"
          placeholder="検索キーワード"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="h-11 w-20 rounded bg-[#ceff42] px-4 text-sm font-semibold text-[#182100] shadow-[0_0_20px_rgba(206,255,66,0.28)] transition hover:bg-[#dcff69] disabled:bg-white/20 disabled:text-white/50 disabled:shadow-none"
        >
          検索
        </button>
      </form>
      {error ? (
        <div className="border-b border-[#ff2d92]/40 bg-[#351225] px-4 py-3 text-sm text-[#ffb7d8]" role="alert">
          {error}
        </div>
      ) : null}
      <section className="grid gap-3 p-4">
        {loading ? <p className="text-sm text-[#b9f8ff]" aria-live="polite">ドキュメントを検索しています...</p> : null}
        {results.map((result) => (
          <article key={`${result.document_id}-${result.chunk_index}`} className="rounded border border-white/15 bg-white/95 p-4 text-[#1a1020] shadow-lg shadow-black/20">
            <SourceBadge source={result} />
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#24162d]/80">{result.content}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
