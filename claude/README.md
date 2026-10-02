# Claude API Guide

This directory contains demonstration scripts for the Anthropic Claude API and SDK, mirroring the OpenAI examples in the `openai/` directory.

## Quick Start

### Setup

1. Install the Anthropic SDK (included in `requirements.txt`):
   ```bash
   pip install anthropic
   ```

2. Set your API key and model in the root `.env` file:
   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   export ANTHROPIC_MODEL="claude-3-5-sonnet-20241022"  # or your preferred model
   ```

3. Run any script from the repo root:
   ```bash
   python claude/ex01_params.py
   ```

## Claude Models

Current recommended models:
- **claude-3-5-sonnet-20241022** – Best for general use (balanced performance and cost)
- **claude-3-opus-20250219** – Most capable, best for complex reasoning
- **claude-3-haiku-20250307** – Fastest and cheapest

See [Anthropic documentation](https://docs.anthropic.com) for the latest models.

## Scripts in This Directory

| Script | Description |
|---|---|
| `ex01_params.py` | Basic text response with temperature and top_p parameters |
| `ex02_num_responses.py` | Streaming text response |
| `ex03_json_structured_response.py` | Structured JSON output using tool use |
| `ex04_multi_turn_text_response.py` | Two-turn conversation with client-side history |
| `ex05_multi_turn_conversation.py` | Multi-turn conversation demo (printer support) |
| `ex06_interactive_conversation.py` | Interactive CLI chat with history and options |
| `ex07_web_search_tool.py` | Using Claude with web search (requires extended thinking or other capabilities) |
| `ex08_few_shots_learning_v1.py` | Few-shot learning example (version 1) |
| `ex08_few_shots_learning_v2.py` | Few-shot learning example (version 2, alternative style) |
| `ex09_chain_of_thought_zero_shot.py` | Zero-shot chain of thought reasoning |
| `ex10_chain_of_thought_few_shots.py` | Few-shot chain of thought (refund fraud detection) |
| `ex11_auto_cot.py` | Automatic chain-of-thought generation |
| `ex12_self_consistency.py` | Self-consistency with multiple reasoning paths and majority voting |
| `ex15_general_knowledge.py` | Two-step prompting: generate knowledge, then answer |
| `ex16_json_output.py` | JSON output generation |

## Key Differences from OpenAI API

- **Conversation history is client-side**: Claude uses a stateless Messages API. History is maintained in the `messages` list and resent each turn (see `common.py` for the `Conversation` helper class).
- **No server-side conversations**: Unlike OpenAI's Conversations API, Claude doesn't store conversation state on the server.
- **Tool use for structured output**: Structured outputs use tool definitions with JSON schemas (see `ex03_json_structured_response.py`).
- **Streaming**: Use `client.messages.stream()` as a context manager for streaming responses.

## Skipped Examples

The following OpenAI examples are not included because they don't map cleanly to Claude:

- **ex13_transfer_learning.py** – Fine-tuning API (Claude uses prompt-tuning/in-context learning instead)
- **ex14_perplexity.py** – Logprobs for perplexity calculation (Claude doesn't expose log probabilities)
- **ex17_embedding.py** – Embeddings via OpenAI SDK (Claude does not provide native embeddings; use a dedicated embeddings provider like Voyage AI)

## Utilities

### `common.py`

Shared utilities used by the scripts:

- `build_client()` – Create an Anthropic client
- `resolve_model()` – Read the model from `ANTHROPIC_MODEL` environment variable (raises `ValueError` if not set)
- `print_title(title)` – Print a formatted section header
- `Conversation` – Pydantic model for managing messages (includes `add_message()` and `to_api_format()` methods)
- `MessageContent` – Pydantic model for individual messages

### Environment Variables

Set these in your `.env` file:

- `ANTHROPIC_API_KEY` – Your Anthropic API key (required)
- `ANTHROPIC_MODEL` – The Claude model to use (required for most scripts; can be overridden with `--model` in interactive scripts like `ex06`)

## Code Style

All scripts follow the project's guidelines from `AGENTS.md`:

- PEP8-compliant Python code
- Functions under 100 lines
- Pydantic models for structured data
- Avoiding nested function calls
- Clear error messages (e.g., when `ANTHROPIC_MODEL` is not set)

Run `flake8 claude/` to check code style.

## Running Scripts

### Basic example:
```bash
python claude/ex01_params.py
```

### Interactive conversation:
```bash
python claude/ex06_interactive_conversation.py --model claude-3-5-sonnet-20241022 --temperature 0.5
```

### Examples that stream:
```bash
python claude/ex02_num_responses.py
```

## API Costs

These scripts call the live API, so each run incurs a small cost. See [Anthropic pricing](https://www.anthropic.com/pricing) for current rates.

## Documentation

- [Anthropic API Documentation](https://docs.anthropic.com)
- [Claude SDK Reference](https://github.com/anthropics/anthropic-sdk-python)
- [Prompt Engineering Guide](https://docs.anthropic.com/en/docs/build-a-claude-agent)
