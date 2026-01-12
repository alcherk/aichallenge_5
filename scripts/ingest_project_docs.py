#!/usr/bin/env python3
"""Script to ingest project documentation into Chunkenizer."""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

import httpx


def get_project_docs() -> List[Dict[str, str]]:
    """Get list of project documentation files to ingest."""
    repo_root = Path(__file__).parent.parent
    
    docs = [
        {
            "path": repo_root / "README.md",
            "doc_type": "readme",
            "source": "project_docs",
        },
        {
            "path": repo_root / "CONTEXT.md",
            "doc_type": "architecture",
            "source": "project_docs",
        },
        {
            "path": repo_root / "DEPLOYMENT.md",
            "doc_type": "deployment",
            "source": "project_docs",
        },
        {
            "path": repo_root / "CLAUDE.md",
            "doc_type": "development",
            "source": "project_docs",
        },
        {
            "path": repo_root / "WEB_UI_ARCHITECTURE.md",
            "doc_type": "architecture",
            "source": "project_docs",
        },
        {
            "path": repo_root / "frontend" / "README.md",
            "doc_type": "frontend",
            "source": "project_docs",
        },
        {
            "path": repo_root / "app" / "app" / "schemas.py",
            "doc_type": "api",
            "source": "project_docs",
        },
    ]
    
    return docs


async def ingest_document(
    file_path: Path,
    doc_type: str,
    source: str,
    chunkenizer_url: str,
    force_reindex: bool = False,
) -> Dict[str, Any]:
    """Ingest a single document into Chunkenizer."""
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}
    
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"Failed to read file: {e}"}
    
    metadata = {
        "source": source,
        "doc_type": doc_type,
        "file_path": str(file_path.relative_to(Path(__file__).parent.parent)),
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{chunkenizer_url.rstrip('/')}/documents",
                files={"file": (file_path.name, content.encode("utf-8"), "text/plain")},
                data={
                    "metadata_json": json.dumps(metadata),
                    "force_reindex": str(force_reindex).lower(),
                },
            )
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "file": str(file_path),
                "document_id": result.get("document_id"),
                "chunk_count": result.get("chunk_count", 0),
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "file": str(file_path),
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
        except Exception as e:
            return {
                "success": False,
                "file": str(file_path),
                "error": str(e),
            }


async def main():
    parser = argparse.ArgumentParser(description="Ingest project documentation into Chunkenizer")
    parser.add_argument(
        "--chunkenizer-url",
        default="http://localhost:8000",
        help="Chunkenizer API URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--force-reindex",
        action="store_true",
        help="Force reindexing of existing documents",
    )
    args = parser.parse_args()
    
    docs = get_project_docs()
    print(f"Found {len(docs)} documentation files to ingest")
    print(f"Chunkenizer URL: {args.chunkenizer_url}")
    print()
    
    results = []
    for doc in docs:
        file_path = doc["path"]
        print(f"Ingesting: {file_path.name}...", end=" ", flush=True)
        
        result = await ingest_document(
            file_path=file_path,
            doc_type=doc["doc_type"],
            source=doc["source"],
            chunkenizer_url=args.chunkenizer_url,
            force_reindex=args.force_reindex,
        )
        
        results.append(result)
        
        if result["success"]:
            print(f"✓ ({result['chunk_count']} chunks)")
        else:
            print(f"✗ {result.get('error', 'Unknown error')}")
    
    print()
    print("Summary:")
    successful = sum(1 for r in results if r["success"])
    print(f"  Successfully ingested: {successful}/{len(results)}")
    
    if successful < len(results):
        print("\nFailed files:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['file']}: {r.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    
    asyncio.run(main())
