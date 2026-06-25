const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type Source = {
  document_id: string;
  title: string;
  source_url: string;
  organization: string | null;
  authority_score: number;
  chunk_index: number;
  similarity: number;
};

export type SearchResult = Source & {
  content: string;
};

export type ChatResponse = {
  answer: string;
  sources: Source[];
  session_id: string | null;
};

export async function sendChat(query: string, sessionId: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId })
  });
  return parseResponse(response);
}

export async function searchDocuments(query: string): Promise<SearchResult[]> {
  const response = await fetch(`${API_BASE_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: 8, min_similarity: 0, min_authority_score: 0 })
  });
  const data = await parseResponse<{ results: SearchResult[] }>(response);
  return data.results;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string" ? detail : detail?.message ?? "APIエラーが発生しました。しばらく後にお試しください。";
    throw new Error(message);
  }
  return data as T;
}

