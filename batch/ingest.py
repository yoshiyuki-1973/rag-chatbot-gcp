import os
from pathlib import Path

import yaml

from chunker import count_tokens, split_text
from db import IngestRepository, SourceConfig, run_async
from embedder import EmbeddingBatchClient
from extractors.markdown import extract_markdown
from extractors.pdf import extract_pdf


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    use_vertex_ai = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
    gcp_project_id = os.getenv("GCP_PROJECT_ID")
    gcp_location = os.getenv("GCP_LOCATION", "us-central1")
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    if not use_vertex_ai and not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required when USE_VERTEX_AI is false")
    if use_vertex_ai and not gcp_project_id:
        raise RuntimeError("GCP_PROJECT_ID is required when USE_VERTEX_AI is true")

    sources = load_sources(Path("sources.yaml"))
    embedder = EmbeddingBatchClient(
        api_key=gemini_api_key,
        vertexai=use_vertex_ai,
        project=gcp_project_id,
        location=gcp_location,
    )
    repository = IngestRepository(database_url)
    completed = 0
    failed = 0

    for source in sources:
        try:
            print(f"[INFO] Processing: {source.path}")
            text = extract_text(source)
            print(f"[INFO]   Extracted {len(text)} chars")
            chunks = split_text(text)
            token_counts = [count_tokens(chunk) for chunk in chunks]
            print(f"[INFO]   Created {len(chunks)} chunks")
            embeddings = embedder.embed_many(chunks)
            print("[INFO]   Generated embeddings")
            document_id = run_async(
                repository.upsert_document_with_chunks(source, chunks, embeddings, token_counts)
            )
            print(f"[INFO]   Upserted document: {source.source_url} (id: {document_id})")
            print(f"[INFO]   Inserted {len(chunks)} chunks")
            completed += 1
        except Exception as exc:
            failed += 1
            print(f"[ERROR] {source.path}: {exc}")
            continue

    print(f"[INFO] Completed: {completed}/{len(sources)} files processed, {failed} files failed")


def load_sources(path: Path) -> list[SourceConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [SourceConfig(**item) for item in data.get("sources", [])]


def extract_text(source: SourceConfig) -> str:
    path = Path(source.path)
    if source.file_type == "markdown":
        return extract_markdown(path)
    if source.file_type == "pdf":
        return extract_pdf(path)
    raise ValueError(f"Unsupported file_type: {source.file_type}")


if __name__ == "__main__":
    main()
