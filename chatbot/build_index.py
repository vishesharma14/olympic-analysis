"""
build_index.py
--------------
Embeds every knowledge chunk with Gemini and writes chatbot/index/knowledge_index.npz, so the
app can retrieve notes without re-embedding them at startup. The file holds only vectors, chunk
ids and hashes of the public notes, and is committed with the code.

    python -m chatbot.build_index            # skips the API calls if the index is already current
    python -m chatbot.build_index --force    # re-embeds everything

Run it after editing any note in chatbot/knowledge/ or changing the embedding model.
"""

import os
import sys
import tempfile
import time

import numpy as np

from chatbot import llm
from chatbot.knowledge import load_chunks
from chatbot.retrieval import INDEX_PATH, load_index, text_hash


def build_index() -> None:
    chunks = load_chunks()
    start = time.perf_counter()
    vectors = llm.embed_documents([chunk.text for chunk in chunks])
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(suffix=".npz", dir=INDEX_PATH.parent)
    with os.fdopen(handle, "wb") as file:
        np.savez_compressed(
            file,
            vectors=vectors,
            ids=np.array([chunk.id for chunk in chunks]),
            text_sha256=np.array([text_hash(chunk.text) for chunk in chunks]),
            model=np.array(llm.embed_model()),
            dimensions=np.array(vectors.shape[1]),
        )
    os.replace(temp_name, INDEX_PATH)
    print(f"Embedded {len(chunks)} chunks with {llm.embed_model()} ({vectors.shape[1]} dimensions) "
          f"in {time.perf_counter() - start:.1f}s using {sum(llm.usage.values())} API requests.")
    print(f"Wrote {INDEX_PATH.relative_to(llm.ROOT)} ({INDEX_PATH.stat().st_size:,} bytes)")


def main() -> None:
    if "--force" not in sys.argv[1:] and INDEX_PATH.exists() and load_index() is not None:
        print(f"{INDEX_PATH.relative_to(llm.ROOT)} is up to date; nothing to embed (use --force to rebuild).")
        return
    build_index()


if __name__ == "__main__":
    main()
