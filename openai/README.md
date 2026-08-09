# OpenAI API Guide

https://developers.openai.com/cookbook

This folder now serves two purposes:

- runnable, text-only learning scripts
- a compact guide to the main OpenAI API surfaces and the most important parameters

The examples in this repo are intentionally text-only. They use the modern `Responses` API, which is the recommended starting point for new projects that need text generation, structured outputs, streaming, and tool use.

## Quick Start

Set your API key in the environment:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

Optional model override:

```bash
export OPENAI_MODEL="gpt-5.4-mini"
```

The scripts default to `gpt-5.4-mini` if `OPENAI_MODEL` is not set.

## Current Model Catalog

The table below is a practical snapshot of the current text-capable OpenAI model family. It is not the full non-text catalog. The complete catalog also includes image, realtime, transcription, speech, embedding, and moderation-focused models, which are outside the scope of this text-only guide.

| Model | Best fit | Notable capabilities | Input $/1M | Output $/1M |
| --- | --- | --- | ---: | ---: |
| `gpt-5.6-sol` | Flagship reasoning and coding | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 5.00 | 30.00 |
| `gpt-5.6-terra` | Balanced quality and cost | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 2.50 | 15.00 |
| `gpt-5.6-luna` | Cost-sensitive high volume | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 1.00 | 6.00 |
| `gpt-5.5` | Complex professional work | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 5.00 | 30.00 |
| `gpt-5.5-pro` | Tough, higher-precision work | Text and image input, Responses, Chat Completions, Batch, function calling, structured outputs, no streaming | 30.00 | 180.00 |
| `gpt-5.4` | Older frontier coding/professional work | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 2.50 | 15.00 |
| `gpt-5.4-pro` | More precise GPT-5.4 work | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, no structured outputs | 30.00 | 180.00 |
| `gpt-5.4-mini` | Fast, efficient high-volume work | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 0.75 | 4.50 |
| `gpt-5.4-nano` | Cheapest GPT-5.4-class tasks | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 0.20 | 1.25 |
| `gpt-5` | Previous GPT-5 reasoning baseline | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 1.25 | 10.00 |
| `gpt-5-pro` | Advanced reasoning | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 15.00 | 120.00 |
| `gpt-5-mini` | Low-latency, cost-sensitive work | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 0.25 | 2.00 |
| `gpt-5-nano` | Fastest, cheapest GPT-5 | Text and image input, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 0.05 | 0.40 |
| `o3` | General reasoning | Text input/output, Responses, Chat Completions, Batch, streaming, function calling, structured outputs | 2.00 | 8.00 |
| `o3-pro` | Heavier reasoning | Text input/output, Responses, Chat Completions, Batch, function calling, structured outputs | 20.00 | 80.00 |

Notes:

- Input and output prices are in USD per 1M tokens.
- Availability and features can change, so verify a specific model page before building something cost-sensitive.
- The `gpt-5.4-mini` default keeps these examples aligned with a fast, inexpensive, text-capable model.

## SDK Pattern

Most Python SDK calls follow the same shape:

```python
from openai import OpenAI
client = OpenAI()
```

Then call a resource method such as `client.responses.create(...)` or `client.files.create(...)`.

Common parameter groups you will see across the API:

- `model`: which model to run
- `input` or `messages`: the prompt content
- `stream`: whether to stream partial output
- `metadata`: custom key/value tags for later filtering
- `store`: whether the object should be stored for retrieval
- `tools`: built-in tools or your own functions
- `response_format` or `text.format`: structured output control
- `previous_response_id`: continue a prior conversation

## Recommended Text API: Responses

Use `Responses` for new text workflows.

### Main method

- `client.responses.create(...)`: create a response in one shot
- `client.responses.stream(...)`: stream events while the model generates output

### Important parameters

- `model`: the model to call, such as `gpt-5.4-mini`, `gpt-5.6-terra`, or another text-capable model
- `input`: the user or multi-turn input
- `instructions`: developer/system-style instructions for the response
- `previous_response_id`: continue a previous response in the same conversation
- `conversation`: explicit conversation state when you manage conversation objects directly
- `prompt`: reference a saved prompt template and variables
- `stream`: enable server-sent events
- `max_output_tokens`: cap the response length
- `temperature`: control randomness in sampling
- `top_p`: nucleus sampling alternative to temperature
- `reasoning`: configure reasoning effort for reasoning-capable models
- `text`: output formatting controls
- `text.format`: use `{"type": "text"}` for plain text or `{"type": "json_schema"}` for structured outputs
- `text.verbosity`: hint for output detail level, where supported
- `tools`: attach built-in tools or custom function tools
- `tool_choice`: control whether the model may use tools or must choose a specific one
- `parallel_tool_calls`: allow more than one tool call when the model can do so safely
- `max_tool_calls`: cap tool calls across a response
- `include`: request extra fields in the output
- `store`: store the response for later retrieval
- `metadata`: attach search/filter tags
- `background`: run the response in background mode
- `truncation`: choose how the request behaves when the input is too long
- `service_tier`: select a service tier when available
- `moderation`: control moderation behavior for the request
- `prompt_cache_key`: improve cache hit rate for repeated prompts
- `prompt_cache_retention`: choose prompt cache retention, including `24h` where supported
- `safety_identifier`: stable identifier for abuse detection and safety handling
- `user`: legacy field that is being replaced by `safety_identifier` and `prompt_cache_key`

### Output shape

A normal text response is easiest to consume through:

```python
response.output_text
```

That is the SDK convenience property used in the scripts in this folder.

### Text-only examples in this repo

- `ex1_params.py`: basic text generation
- `ex2_num_responses.py`: streamed text output
- `ex3_chat_completion.py`: structured JSON output with `text.format`
- `ex4_multi_turn_text_response.py`: follow-up conversation with `previous_response_id`

## Chat Completions

Use Chat Completions when you are maintaining older code or need compatibility with an existing chat-based implementation. For new work, OpenAI recommends Responses.

### Legacy code node

- Old pattern: `client.chat.completions.create(...)`
- Modern replacement: `client.responses.create(...)` with `input`, `instructions`, `text.format`, and `previous_response_id`
- Migration tip: replace `messages` with a single `input` flow unless you need to preserve a chat-specific contract

### Main method

- `client.chat.completions.create(...)`

### Important parameters

- `model`: the model to run
- `messages`: ordered chat messages, usually with `system`, `developer`, `user`, and `assistant` roles
- `stream`: stream partial output
- `temperature`: sampling randomness
- `top_p`: nucleus sampling
- `n`: number of alternative choices to generate
- `max_tokens` or `max_completion_tokens`: output cap, depending on model and SDK version
- `stop`: stop sequences
- `presence_penalty`: discourage the model from introducing new repeated topics
- `frequency_penalty`: discourage repeated wording
- `tools`: attach tools or function definitions
- `tool_choice`: control whether and how the model uses tools
- `response_format`: request a structured or JSON-formatted response when supported
- `logprobs` and `top_logprobs`: request token-level log probability information when supported
- `store`: store the completion so it can be retrieved later
- `metadata`: custom tags
- `seed`: request repeatability when supported
- `user`: legacy user identifier in older chat patterns

### When to use it

- you have a legacy chat app
- you already depend on `messages`
- you need to preserve an existing Chat Completions contract during migration

## Embeddings

Use embeddings when you need vector representations of text for search, clustering, retrieval, similarity, or classification.

### Legacy code node

- Old pattern: using embeddings only as a standalone side step in a text pipeline
- Modern recommendation: keep embeddings as a separate step, but pair them with retrieval or semantic search instead of treating them as the final user-facing output
- Migration tip: if your old code used embeddings to power a chat assistant, move the generation step to `Responses` and keep embeddings only for retrieval/scoring

### Main method

- `client.embeddings.create(...)`

### Important parameters

- `model`: embedding model name
- `input`: text string, array of strings, or token arrays depending on the SDK and model
- `encoding_format`: vector serialization format when supported
- `dimensions`: requested vector size for models that support it
- `user`: stable end-user identifier when supported

### Output shape

The response contains one embedding vector per input item, usually under `data[].embedding`.

## Moderations

Use Moderations to classify text for safety or policy violations.

### Legacy code node

- Old pattern: checking moderation only after user-visible generation
- Modern recommendation: moderate user input before generation and use the result to decide whether to continue, refuse, or route to a safer path
- Migration tip: keep moderation as a preflight or guardrail step, not as a post-processing afterthought

### Main method

- `client.moderations.create(...)`

### Important parameters

- `input`: text to classify, or an array of inputs when supported
- `model`: moderation model name, usually a latest alias

### Output shape

The response includes category scores and flags so you can gate downstream actions.

## Files

Use Files to upload documents for other endpoints.

### Legacy code node

- Old pattern: treating files as an application-specific storage layer
- Modern recommendation: upload only what an OpenAI endpoint actually needs, then read back the result from the endpoint that consumes the file
- Migration tip: keep raw documents in your own storage and use OpenAI file uploads as the handoff format for `batch`, `fine-tuning`, `assistants`, or retrieval workflows

### Main methods

- `client.files.create(...)`
- `client.files.list(...)`
- `client.files.retrieve(...)`
- `client.files.delete(...)`
- `client.files.content(...)`

### Important parameters

- `file`: the file object or upload stream
- `purpose`: why the file exists

### Common purposes

- `batch`
- `fine-tune`
- `assistants`
- `assistants_output`
- `user_data`
- `vision`

### Output shape

A file object includes fields such as `id`, `filename`, `bytes`, `created_at`, `expires_at`, and `purpose`.

## Batches

Use Batches for asynchronous, high-volume request processing.

### Legacy code node

- Old pattern: looping over many single requests one at a time
- Modern recommendation: batch independent work into a JSONL file and submit it to `/v1/batches`
- Migration tip: if you have retry-heavy bulk jobs or offline classification tasks, batch them instead of serializing synchronous calls

### Main methods

- `client.batches.create(...)`
- `client.batches.retrieve(...)`
- `client.batches.list(...)`
- `client.batches.cancel(...)`

### Important parameters

- `completion_window`: current batch processing window, commonly `24h`
- `endpoint`: the API endpoint to batch, such as `/v1/responses`, `/v1/chat/completions`, `/v1/embeddings`, `/v1/completions`, or `/v1/moderations`
- `input_file_id`: uploaded JSONL file containing batch requests
- `metadata`: optional tags when supported by the SDK

### Batch input line fields

- `custom_id`: developer-defined request ID
- `method`: currently `POST`
- `url`: relative endpoint path
- `body`: the request body for the chosen endpoint

### When to use it

- you can tolerate asynchronous completion
- you need throughput over immediate latency
- you want cheaper bulk processing

## Fine-Tuning

Use fine-tuning to adapt supported base models to your domain or output style.

### Legacy code node

- Old pattern: trying to solve style or domain adaptation with a long prompt alone
- Modern recommendation: use fine-tuning when the task is stable, repetitive, and benefits from a trained format or tone
- Migration tip: start with prompt + evals first; fine-tune only when repeated prompt engineering is no longer enough

### Main methods

- `client.fine_tuning.jobs.create(...)`
- `client.fine_tuning.jobs.retrieve(...)`
- `client.fine_tuning.jobs.list(...)`
- `client.fine_tuning.jobs.cancel(...)`
- `client.fine_tuning.jobs.pause(...)`
- `client.fine_tuning.jobs.resume(...)`
- `client.fine_tuning.jobs.list_events(...)`
- `client.fine_tuning.jobs.list_checkpoints(...)`

### Important parameters

- `model`: base model to fine-tune
- `training_file`: uploaded JSONL training file ID
- `validation_file`: optional validation file ID
- `method`: tuning method, such as supervised for supported models
- `suffix`: optional custom suffix for the resulting model name
- `integrations`: optional integrations such as W&B when supported
- `metadata`: optional tags
- `seed`: optional repeatability control when supported

### File requirements

- training data must be uploaded with `purpose="fine-tune"`
- the file format depends on whether the model expects chat, completions, or preference data

## Models

Use Models to inspect what is available or to delete fine-tuned models.

### Legacy code node

- Old pattern: hard-coding a single model everywhere and never checking what the account can actually use
- Modern recommendation: list or retrieve models when you need runtime discovery, and keep the model name configurable through environment variables
- Migration tip: for new text work, prefer the GPT-5.4 family and make the model configurable rather than baking it into code

### Main methods

- `client.models.list(...)`
- `client.models.retrieve(...)`
- `client.models.delete(...)`

### Important notes

- `list` shows available models
- `retrieve` returns metadata for one model ID
- `delete` is only relevant for fine-tuned models and requires appropriate permissions

## Choosing a Model

For current general-purpose text work, the OpenAI docs highlight the GPT-5.4 family.

Practical defaults:

- `gpt-5.4-mini`: balanced default for this folder
- `gpt-5.4-pro`: strongest capability in the GPT-5.4 family
- `gpt-5.4-nano`: cheapest high-volume GPT-5.4-class option

If you are migrating from older GPT-5.5 or GPT-5.4 patterns, keep the same reasoning setting as a baseline, then compare one level lower for latency-sensitive cases.

## Text-Only Scope

The scripts in this folder intentionally skip image, audio, and video. If you need those, they belong in separate examples because the request shape, output handling, and model choices differ.

## Practical Advice

- Use `Responses` for new text generation work.
- Use `Chat Completions` only when you need to preserve older chat code.
- Use `Structured Outputs` when your downstream code needs a schema, not free-form prose.
- Use `stream` when latency matters and you want partial output.
- Use `previous_response_id` when you want the API to carry forward conversation state.
- Use `metadata` whenever you want to filter or trace API objects later.

## Conversation History

If you are using stored conversations, you can retrieve the items by `conversation_id`.

### Main method

- `client.conversations.items.list(conversation_id=...)`

### Important parameters

- `conversation_id`: the conversation to inspect
- `after`: pagination cursor for the next page
- `limit`: number of items to return per page
- `order`: `asc` or `desc` when supported
- `include`: request additional fields such as reasoning data when needed

### Example

```python
from openai import OpenAI

client = OpenAI()
conversation_id = "conv_123"

page = client.conversations.items.list(
    conversation_id=conversation_id,
    limit=100,
    order="asc",
)

for item in page.data:
    print(item)
```

### Notes

- The API returns conversation items, not a single transcript string.
- Reconstruct the conversation by ordering the items and reading the content of each turn.
- If the conversation has more than one page of items, continue with `after=page.last_id` until `has_more` is false.
- Use this when you need to review or replay a stored conversation by ID.

## Deprecated And Legacy Surfaces

The table below separates APIs that are explicitly deprecated from APIs that are still supported but considered legacy for new projects.

| Surface | Status | Modern alternative | Recommendation |
| --- | --- | --- | --- |
| `/v1/completions` | Deprecated / legacy | `client.responses.create(...)` | Move new text work to `Responses`; keep Completions only for old prompts you cannot rewrite yet. |
| `text-moderation` / `text-moderation-stable` | Deprecated model family | `omni-moderation-latest` via `client.moderations.create(...)` | Switch moderation checks to `omni-moderation-latest`; keep moderation as a preflight guardrail. |
| `client.chat.completions.create(...)` | Legacy, not recommended for new projects | `client.responses.create(...)` | Migrate new work to `Responses`; keep Chat Completions only when you need an older `messages` contract. |
| `client.assistants.*` | Legacy for new text workflows | `client.responses.create(...)` with tools | Prefer `Responses` for new agentic text workflows and tool use. |
| `client.completions.*` in older SDK examples | Legacy | `client.responses.create(...)` | Replace old completion-only snippets with `Responses` and structured text input. |

### Migration Notes

- If a workflow only needs plain text output, move it to `Responses` first.
- If the workflow uses `messages`, flatten it into `input` unless preserving a chat contract matters.
- If the workflow is moderation-only, keep the endpoint but upgrade the model to `omni-moderation-latest`.
- If the workflow is batch or offline, keep the batch layer but target `/v1/responses` instead of older generation endpoints.

## Scripts In This Folder

- `ex1_params.py`
- `ex2_num_responses.py`
- `ex3_chat_completion.py`
- `ex4_multi_turn_text_response.py`
- `ex5_multi_turn_conversation.py`
- `ex6_interactive_conversation.py` - interactive CLI conversation using `click`

## Source Of Truth

This README is a practical guide. The exact live request and response schema can evolve, so use the official OpenAI API reference when you need the definitive parameter list for a specific endpoint.
