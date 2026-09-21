---
name: bbc-news-query
description: Query the local BBC News Summary Chroma collection for questions about the indexed news articles and summaries.
---

# BBC News Query

Use this skill when the user asks a question that should be answered from the
BBC News Summary data indexed in the local Chroma database.

Run the query from the repository root with:

```bash
.venv/bin/python chromadb/ex04_query_bbc_news.py "<user question>"
```

For example:

```bash
.venv/bin/python chromadb/ex04_query_bbc_news.py "How are technology companies performing?"
```

Preserve the user's question verbatim inside the quoted argument. Add
`--n-results`, `--source-type`, or `--category` only when the user requests a

If the collection does not exist, tell the user to index it first with:

```bash
.venv/bin/python chromadb/ex03_index_bbc_news.py
```

Summarize the returned matches and distinguish retrieved evidence from any
inference.
