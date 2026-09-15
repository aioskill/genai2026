# MCP File System Demo

This is a small educational Model Context Protocol app built in Python.

It has:

- `server.py`: an MCP server that exposes safe file-system tools
- `client.py`: a stdio client that starts the server, calls the tools, and reads a file resource
- `client_llm.py`: a LangChain agent that loads the MCP tools and solves a multi-step support case

The server is intentionally constrained to a demo workspace directory so it can show the mechanics of MCP without exposing your whole machine.

## What it demonstrates

- listing files and directories
- reading text files
- writing text files
- creating directories
- exposing a file as an MCP resource
- a realistic multi-step investigation where the model must inspect several files before it can answer

## Multi-tool use case

The demo is set up around a simple support case:

- `overview.txt` says the customer has both a billing problem and a shipping delay
- `billing.txt` contains the invoice balance
- `shipping.txt` contains the delivery status
- `contacts.txt` contains the right team contacts

To answer the question, an LLM has to:

1. discover the case directory with `list_directory`
2. inspect the files inside that directory with more `list_directory` calls
3. read several files with `read_text_file`
4. combine the evidence into one final response

## Setup

This repo uses `uv` and the official Python MCP SDK.

```bash
uv sync
```

## Run the server

```bash
uv run server.py
```

By default the server uses `./demo_workspace` as its root.

You can override that with:

```bash
MCP_FS_ROOT=/path/to/sandbox uv run server.py
```

## Run the client

```bash
uv run client.py
```

The client will:

1. start the server over stdio
2. seed the workspace with a support case
3. discover the relevant files through multiple tool calls
4. print the final briefing only after all context has been gathered
5. read a synthesized briefing back as an MCP resource

## Run the LangChain agent

`client_llm.py` connects the same MCP server to a LangChain agent.

It expects:

- `OPENAI_API_KEY`
- optionally `OPENAI_MODEL` if you want to override the default `gpt-4.1`

```bash
uv run client_llm.py
```

The built-in problem asks the agent to:

1. locate the investigation folder under `cases`
2. inspect several supporting files
3. combine billing, shipping, and contact evidence
4. answer in a short customer-facing briefing

## Files are sandboxed

The server rejects absolute paths and paths that escape the configured workspace root.

That keeps the example educational and prevents it from becoming a general-purpose file editor.
