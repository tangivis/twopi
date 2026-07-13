# Tau — Architecture Research Notes

Repo: `/home/keiten_ubuntu/workspace/code/tau` — "Tau" by alejandro-ao, v0.1.5, PyPI package `tau-ai`, docs at twotimespi.dev ("two times pi = tau" — the name is a math joke about the circle constant τ = 2π; see `website/content/why-tau.md`). Git history: first commit 2026-06-11, ~539 commits, last commit 2026-07-09. Self-description from `pyproject.toml:8`: *"A Python implementation of a minimalist Pi-style coding-agent harness."*

## 1. Project Layout & Stats

### Package structure (confirmed names)

```text
src/tau_ai       — provider/model streaming layer          (~3,404 LOC, 13 files)
src/tau_agent    — portable agent brain                    (~1,351 LOC, 13 files)
src/tau_coding   — the coding application (CLI/TUI/tools)  (~19,832 LOC, 40 files)
tests/           — flat pytest suite                       (~19,156 LOC, 34 files, ~725 test functions)
```

The dependency direction is strictly one-way: `tau_coding → tau_agent → tau_ai` (stated in `README.md:35`, `website/content/internals/architecture.md:12-46`). Note one deliberate quirk: `tau_ai` *imports message/tool types from* `tau_agent` (`src/tau_ai/provider.py:8-9` imports `tau_agent.messages.AgentMessage` and `tau_agent.tools.AgentTool`), so the neutral data model lives in `tau_agent` and `tau_ai` adapts providers **to** it.

Key file sizes (largest first): `tau_coding/tui/app.py` 4,384; `session.py` 2,274; `provider_config.py` 2,201; `tui/widgets.py` 1,541; `tools.py` 1,057; `session_export.py` 1,023; `openai_compatible.py` 925; `commands.py` 815; `openai_codex.py` 743. Core-layer files are tiny: `loop.py` 276, `harness.py` 298, `messages.py` 47, `types.py` 8.

### Python version, dependencies, tooling

- **Python ≥ 3.12** (`pyproject.toml:12`, `.python-version` = `3.12`). Uses PEP 695 `type` aliases heavily (e.g. `type AgentMessage = UserMessage | AssistantMessage | ToolResultMessage`, `src/tau_agent/messages.py:47`; recursive `type JSONValue`, `src/tau_agent/types.py:6-8`).
- **Runtime deps** (`pyproject.toml:13-22`): `anyio>=4.0`, `httpx[socks]>=0.27` (no provider SDKs — raw HTTP/SSE), `packaging>=24.0`, `pydantic>=2.0`, `pygments>=2.18`, `rich>=13.0`, `textual>=1.0`, `typer>=0.12`.
- **Dev tooling**: `uv` (uv.lock present, all workflows via `uv run …`), dev group = `mypy>=1.10` (**strict mode**, `pyproject.toml:55-58`), `pytest>=8.0`, `ruff>=0.5` (line length 100, rules `E,F,I,UP,B,SIM`, `pyproject.toml:43-53`). Build backend: hatchling; entry point `tau = "tau_coding.cli:app"` (`pyproject.toml:31`).
- **Tests**: flat `tests/` dir (`testpaths` in `pyproject.toml:64-66`), plain pytest + `@pytest.mark.anyio` (anyio's bundled pytest plugin) for async tests (`tests/test_agent_loop.py:38`). Deterministic style: `FakeProvider` scripts provider event streams (`src/tau_ai/fake.py:13-43`); `tests/conftest.py:6-11` has one helper `isolate_home()` that redirects `HOME`/`USERPROFILE` to tmp. Biggest suites: `test_tui_app.py` (224 tests, 5,940 lines, drives Textual via `run_test()` pilots), `test_coding_session.py` (88), `test_tau_ai.py` (41), `test_coding_tools.py` (15), `test_agent_loop.py` (12), `test_agent_harness.py` (14). Test LOC ≈ source LOC (19k vs 24k) — behavior-focused, no coverage tooling configured.

### Docs & website

- `docs/` contains only `assets/tau-header.svg`. Real docs are a **Hugo site** in `website/` (`website/hugo.toml`, baseURL `https://twotimespi.dev/`, params.description = *"An educational Python project for learning how coding agents are built."*).
- `website/content/` pages: `_index.md`, `what-is-tau.md`, `why-tau.md` (the τ-vs-π math rant), `quickstart.md`, `concepts.md`, `contributing.md`, `releases.md`, `roadmap.md`; `guides/` (tui, print-mode, sessions, providers-and-models, project-instructions, skills-and-prompts, context); `internals/` (architecture, agent-loop, design-principles, custom-frontend); `reference/` (cli, configuration, keybindings, slash-commands, tools).
- `dev-notes/` is the contributor build-log (not published): `design/` (00-roadmap … 05-core-types-and-events, agent-loop, harness), `architecture/` (~40 phase notes, phase-1 … phase-24 plus hardening notes), `adr/` (3 ADRs). See §6.
- Root also has `AGENTS.md` (instructions for agents working on tau itself), `CONTRIBUTING.md`, `landing.html`, and a sample `session-temp.jsonl` (a real captured session showing the JSONL format).

## 2. tau_ai — Provider-Neutral LLM Streaming

### Core abstraction

`ModelProvider` is a **Protocol** (structural typing, no base class) at `src/tau_ai/provider.py:21-34`:

```python
class ModelProvider(Protocol):
    def stream_response(self, *, model: str, system: str,
        messages: list[AgentMessage], tools: list[AgentTool],
        signal: CancellationToken | None = None,
    ) -> AsyncIterator[ProviderEvent]: ...
```

`CancellationToken` is likewise a Protocol with a single `is_cancelled() -> bool` (`provider.py:13-18`) — polled cooperatively, no asyncio cancellation magic.

### Provider events (`src/tau_ai/events.py`)

Seven pydantic models (all `ConfigDict(extra="forbid")`, discriminated by a `type` Literal), unioned as `type ProviderEvent` (`events.py:83-91`): `ProviderResponseStartEvent`, `ProviderRetryEvent`, `ProviderTextDeltaEvent`, `ProviderThinkingDeltaEvent`, `ProviderToolCallEvent` (carries a complete `ToolCall` — tool calls are *not* streamed incrementally to consumers), `ProviderResponseEndEvent` (carries the finished `AssistantMessage` + `finish_reason`), `ProviderErrorEvent`.

**Notable absence: no token-usage/cost events.** `ProviderResponseEndEvent` has no usage field. Adapters even request usage (`stream_options: {"include_usage": true}`, `openai_compatible.py:588-589`) but never surface it. Context accounting in the app layer is purely **estimated** (chars/4; see §4), and per-model `cost` tables exist in the catalog (`catalog.toml`, `provider_catalog.py:39`) but are metadata only — no dollar tracking is implemented.

### Providers (5 real + 1 fake)

All use `httpx.AsyncClient` + hand-rolled SSE parsing (`_parse_sse_line` strips `data:` prefixes); each provider owns/creates its client lazily and exposes `aclose()`.

1. **`OpenAICompatibleProvider`** (`openai_compatible.py`, 925 lines) — the workhorse. Serves `/chat/completions` by default, but transparently routes to `/v1/responses` for models that require it: `_use_responses_api()` at `openai_compatible.py:42-47` matches `"codex" in model` or prefixes `gpt-5.5`/`gpt-5.4`; config `api: "openai-responses"` forces it. Two parser classes implement a shared `_StreamParser` protocol (`:282-297`): `_ChatStreamParser` and `_ResponsesStreamParser`, plus `_ToolCallBuilder`s that accumulate streamed argument fragments. Payload building supports a **`compat` dict** driven by catalog data (`_build_chat_payload`, `:560-611`): `supportsStore`, `supportsUsageInStreaming`, `supportsReasoningEffort`, `maxTokensField`, `openrouterProvider`, `zaiToolStream`, and a `thinking_format` dispatcher (`_apply_chat_reasoning`, `:613-650`) handling `openai`, `zai`, `qwen`, `qwen-chat-template`, `deepseek`, `openrouter`, `together` reasoning syntaxes. This single adapter therefore serves OpenAI, OpenRouter, Groq, DeepSeek, xAI, Cerebras, NVIDIA, Hugging Face, Fireworks, Together, Vercel AI Gateway, Z.AI, Moonshot, Xiaomi, local endpoints, etc.
2. **`AnthropicProvider`** (`anthropic.py`, 356 lines) — Messages API, `anthropic-version: 2023-06-01`, `x-api-key` header (`:75-81`). Parses `content_block_start/delta` SSE incl. `thinking_delta` and `input_json_delta`; `_AnthropicToolBuilder` (`:249-264`) joins partial JSON. Thinking: `budget` mode (`thinking: {type: enabled, budget_tokens}`) or `adaptive` mode with `output_config.effort` (`:288-295`); `max_tokens` auto-raised to `thinking_budget + 1024` (`:279-280`). Tool results are sent as `role:"user"` content blocks with `is_error` (`_anthropic_message`, `:318-329`).
3. **`OpenAICodexProvider`** (`openai_codex.py`, 743 lines) — ChatGPT **subscription** auth against `https://chatgpt.com/backend-api` (`:35`). Takes an async `credential_resolver` returning `OpenAICodexCredentials(access_token, account_id)` (`:39-47`); detects terminal rate-limit bodies like `"monthly usage limit reached"` (`:731-737`).
4. **`GoogleGenerativeAIProvider`** (`google.py`, 402 lines) — Generative Language API `models/{model}:streamGenerateContent?alt=sse&key=…` (`:68-71`); reuses `OpenAICompatibleConfig`; maps thinking effort to per-model budgets/levels (`_google_budget`/`_google_level`, `:277-308`), sanitizes JSON schemas for Gemini (`_sanitize_google_schema`, `:361`), and round-trips Gemini's `thought_signature` via the `ToolCall.thought_signature` field (`src/tau_agent/tools.py:42-44`).
5. **`MistralConversationsProvider`** (`mistral.py`, 416 lines) — Mistral's `/v1/conversations` API.
6. **`FakeProvider`** (`fake.py:13-43`) — replays scripted `ProviderEvent` streams and records `calls`; the backbone of deterministic loop tests.

### Retries, errors, HTTP

- Shared retry helpers in `retry.py`: exponential backoff `min(max_delay, 0.25 * 2^attempt)` (`retry_delay_seconds`, `:15-20`), a uniform `ProviderRetryEvent` factory (`provider_retry_event`, `:23-43`), and `wait_for_retry()` that sleeps in 50 ms slices so cancellation can interrupt backoff (`:46-62`). Retry policy per adapter: retry on network errors *only if nothing was emitted yet*, and on HTTP `{408, 409, 429, 500, 502, 503, 504}` (`anthropic.py:243-246`), up to `max_retries` (default 2).
- `http_errors.provider_http_error_message()` formats user-facing HTTP failures; `http.py` centralizes client creation with **SOCKS proxy normalization** — generic `socks://` env values are rewritten to `socks5://` before httpx construction (`normalize_proxy_url`, `http.py:22-34`; documented in `reference/configuration.md:33-56`).

### Config & key resolution (layer-level)

`env.py` defines frozen dataclass configs: `OpenAICompatibleConfig` (`:18-35`, with `api`, `reasoning_effort`, `thinking_format`, `compat`, `provider_name`…) and `AnthropicConfig` (`:38-52`, with `thinking_budget_tokens/effort/mode`). `openai_compatible_config_from_env()` (`:55-83`) reads `OPENAI_API_KEY`/`OPENAI_BASE_URL`/timeout/retry env vars with validation. The richer resolution chain (credential store → env var) lives in `tau_coding`.

## 3. tau_agent — The Portable Brain

Public API re-exported from `src/tau_agent/__init__.py` (48-93): events, `AgentHarness`, `run_agent_loop`, messages, tools, session entry types.

### Data model

- **Messages** (`messages.py`): `UserMessage{role:"user", content:str}`, `AssistantMessage{content:str, tool_calls:list[ToolCall]}`, `ToolResultMessage{tool_call_id, name, content, ok:bool, data, details, error}` — pydantic, `extra="forbid"`. Content is a **plain string**, not content-block lists — a major simplification vs. production agents (no image blocks in the transcript; images come back as base64 inside tool-result `data`).
- **Tools** (`tools.py`): `AgentTool` is a **frozen dataclass** (`:61-78`) of `name`, `description`, `input_schema: Mapping[str, JSONValue]` (hand-written JSON Schema dict — *not* pydantic-derived), `executor` (async callable Protocol `ToolExecutor`, `:22-31`), plus prompt metadata `prompt_snippet` / `prompt_guidelines`. No decorators, no registration framework: *"Tools are ordinary typed functions"* (`README.md:153`). `AgentToolResult` (`:47-58`) is the structured result; `ToolCall` (`:34-44`) carries `id/name/arguments/thought_signature`.

### Agent events (`events.py`)

14 event types unioned as `type AgentEvent` (`events.py:119-134`): `AgentStartEvent`, `AgentEndEvent`, `TurnStartEvent{turn}`, `TurnEndEvent{turn}`, `RetryEvent`, `QueueUpdateEvent{steering:tuple[str,...], follow_up:tuple[str,...]}`, `MessageStartEvent{message_role}`, `MessageDeltaEvent{delta}`, `ThinkingDeltaEvent{delta}`, `MessageEndEvent{message: AgentMessage}`, `ToolExecutionStartEvent{tool_call}`, `ToolExecutionUpdateEvent` (defined but never emitted by the built-in loop — a hook for streaming tool progress), `ToolExecutionEndEvent{result}`, `ErrorEvent{message, recoverable, data}`.

### The loop — `run_agent_loop()` (`loop.py:37-166`)

The actual loop is a single **pure async generator function** (not a class), ~130 lines. It is stateless: the caller owns `messages` and the loop appends to it (docstring `:50-56`). Step by step:

1. `yield AgentStartEvent()`; validate `max_turns` (default `None` = unlimited, "Like Pi" per `dev-notes/architecture/phase-3-agent-loop.md:194`).
2. Per turn: check `signal.is_cancelled()` → recoverable `ErrorEvent("Agent run cancelled")`; `yield TurnStartEvent(turn)`.
3. Iterate `provider.stream_response(...)`, translating provider events 1:1 into agent events (`:76-107`): `ResponseStart→MessageStart`, `TextDelta→MessageDelta`, `ThinkingDelta→ThinkingDelta`, `Retry→Retry`, `ResponseEnd→` append `AssistantMessage` to transcript + `MessageEndEvent`, `Error→ErrorEvent(recoverable=False)`.
4. If no assistant message arrived: emit `TurnEnd`, then break (with `ErrorEvent("Provider stream ended without an assistant message")` unless a provider error was already surfaced) (`:109-118`).
5. **No tool calls** → `TurnEnd`, then drain **steering** queue; if empty drain **follow-up** queue; if either yielded messages, echo them as `MessageStart/MessageEnd` pairs + `QueueUpdateEvent` and `continue` into a new turn; otherwise break (`:120-142`).
6. **Tool calls** → `_execute_tool_calls()` (`:190-214`): strictly **sequential** (`for index, tool_call in enumerate(tool_calls)`) — no parallel execution. Each call yields `ToolExecutionStart`, then either an unknown-tool failure result or `await tool.execute(...)`; exceptions are caught at the tool boundary and converted to `ok=False` results (`_execute_tool`, `:217-235` — "tools are an isolation boundary"); mismatched `tool_call_id`s are repaired via `model_copy`. Result is appended to the transcript as `ToolResultMessage` (error text folded into content, `_tool_result_message`, `:260-276`) and `ToolExecutionEnd` is yielded. If cancelled mid-batch, remaining calls get synthetic `"Tool call cancelled"` results (`:197-203`) so the transcript stays provider-valid.
7. After the tool batch: `TurnEnd`, drain steering only (steering interrupts between tool batches; follow-ups only run when the agent would stop), `turn += 1`.
8. `while…else` clause emits `ErrorEvent(max_turns reached, recoverable=True)`; finally `yield AgentEndEvent()`.

### The harness — `AgentHarness` (`harness.py:62-298`)

A small stateful wrapper ("Reusable stateful agent brain", `:63`): owns the transcript (`_messages`), listener list, current `SimpleCancellationToken` (`:47-59`), `_running` flag, and **two `deque` queues** — `_steering_queue`, `_follow_up_queue`.

- Entry points: `prompt(content)` appends a `UserMessage` and returns the event iterator; `continue_()` re-runs from existing state (used for resume/overflow-retry) (`:183-197`). Both raise `RuntimeError` if already running — the UI must use queueing instead (`_ensure_not_running`, `:238-242`).
- `steer(content)` / `follow_up(content)` enqueue mid-run user messages and return a `QueueUpdateEvent` snapshot (`:139-155`); `queue_mode` config is `"one_at_a_time"` (default — drain one per boundary) or `"all"` (`:19`, `_drain_queue` `:250-257`). Also `clear_queues()`, `pop_latest_steering/follow_up()` (used by the TUI's "edit queued message" feature).
- **User-message echo**: `_run()` yields the prompt's own `MessageStartEvent(message_role="user")`/`MessageEndEvent` right after the first `turn_start` (`:218-224`) so frontends render the user message from the same event stream ("mirrors Pi's loop behavior", `dev-notes/architecture/phase-20-1-context-accounting.md:47`).
- `subscribe(listener)` supports sync or async listeners with an unsubscribe closure (`:124-132`, `_notify` `:232-236`).
- **Transcript repair**: `_append_interrupted_tool_results()` (`:268-298`) scans for assistant tool calls that have no matching tool result (e.g. after Escape-cancel killed the worker) and appends synthetic `"Tool call interrupted by user"` failures — because OpenAI-compatible providers reject dangling tool calls. Called before every `prompt()`/`continue_()` and after cancellation (`:225-230`).

### Session primitives (`src/tau_agent/session/`)

A **session is an append-only tree of typed entries**, replayed into state:

- `entries.py`: `BaseSessionEntry{id: uuid4-hex, parent_id, timestamp}` (`:25-32`) and 9 entry types discriminated on `type` (`SessionEntry` union, `:103-114`): `message`, `model_change`, `thinking_level_change`, `compaction{summary, replaces_entry_ids}`, `branch_summary{summary, branch_root_id}`, `label`, `leaf{entry_id}` (append-only active-branch pointer), `session_info{created_at, cwd, title}`, `custom{namespace, data}` (extension escape hatch).
- `jsonl.py`: one pydantic `TypeAdapter(SessionEntry)` serializes each entry as one JSONL line (`entry_to_json_line`, `:16-18`).
- `storage.py`: `SessionStorage` Protocol (`append`/`read_all`, `:12-21`) + `JsonlSessionStorage` (plain sync file I/O inside async methods, `:24-40`).
- `tree.py`: `path_to_entry(entries, leaf_id)` walks parent pointers root→leaf with duplicate/cycle/missing checks (`:22-40`).
- `memory.py`: `SessionState.from_entries(entries, leaf_id=…)` (`:36-103`) replays either the full linear order or only the active root→leaf path, folding entries via a `match entry.type` — **compaction replay** (`_apply_compaction`, `:106-125`) replaces the covered message rows with a single synthetic `UserMessage("Previous conversation summary:\n…")` at the position of the first replaced row; `branch_summary` entries render as a `UserMessage` wrapped in `<summary>` tags (`:132-136`). State carries `messages`, `model`, `thinking_level`, `label`, `active_leaf_id`, `context_entry_ids` (message-row ids — the compaction bookkeeping), etc.

## 4. tau_coding — The Real App

### CLI entry (`src/tau_coding/cli.py`)

`tau` runs `typer` app `tau_coding.cli:app` (`pyproject.toml:31`). A single callback `main()` (`cli.py:132-294`) does everything: `--version`; pseudo-subcommands parsed from positional args (`tau sessions`, `tau export <id|file> [--format html|jsonl]`, `tau providers`, `tau setup`) (`:225-261`); otherwise **positional args become an initial TUI prompt** (Pi-style `tau "prompt"`), `-p/--prompt` runs **print mode**, plus `--provider`, `-m/--model`, `--cwd`, `-o/--output text|json|transcript`, `--resume <id>`, `--new-session`, `--auto-compact-threshold`. At import time it force-reconfigures stdout/stderr to UTF-8 for Windows codepages (`_force_utf8_streams`, `:71-85`). Startup does a PyPI **update check** (cached daily in `~/.tau/cache/update-check.json`, disabled by `TAU_NO_UPDATE_CHECK`/`CI`; `update_check.py`, 373 lines) and shows release notes on version change. Print mode: `run_print_mode()` (`:514-569`) loads a `CodingSession`, handles `! cmd` terminal commands and slash commands, then streams `session.prompt()` events into a renderer; exit code 1 on non-recoverable errors.

**Rendering** (`rendering/`): `PrintOutputMode` enum text/json/transcript with an `EventRenderer` Protocol (`base.py:11-27`); `FinalTextRenderer` (Pi-style "print only final assistant text", `plain.py:10-38`), `json.py` (one JSON object per event line), `transcript.py` (human-readable streamed transcript).

### TUI

Textual throughout (ADR 0001). Structure under `tui/`: `app.py` (4,384 lines — `TauTuiApp(App[None])` at `:1640`, ~10 `ModalScreen` classes: `SessionPickerScreen`, `TreePickerScreen` (branch picker with S=summarize, C=custom-instructions summary, Ctrl+T toggle tool-call entries), `BranchSummaryInstructionsScreen`, `CommandOutputScreen`, `LoginProviderPickerScreen`, `LoginMethodPickerScreen`, `ThemePickerScreen`, `ModelPickerScreen` (search + Space toggles scoped models), `CustomProviderLoginScreen`, `LoginScreen`, `OAuthLoginScreen`); `widgets.py` (transcript widgets, sidebar, Rich-rendered markdown/code blocks); `state.py` (`TuiState`/`ChatItem` — plain display state); `adapter.py` (`TuiEventAdapter.apply(event)` — the 100-line event→display-state translation, `adapter.py:23-100`); `autocomplete.py` (slash-command/skill/prompt/session-id completion); `config.py` (`~/.tau/tui.json`: 3 themes `tau-dark`/`tau-light`/`high-contrast`, rebindable keys); `terminal_title.py` (OSC tab titles).

Concurrency model: prompts run in a Textual **worker** (`self._prompt_worker = self.run_worker(self._run_prompt(text, run_id), exclusive=True)`, `app.py:2403-2409`); a monotonically increasing `_prompt_run_id` discards late events after cancellation. **Enter while running = steer; Alt+Enter = follow-up** (`action_submit_prompt`/`action_submit_follow_up` → `_submit_prompt_from_editor(streaming_behavior=…)`, `app.py:2205-2212`; queued via `session.prompt(text, streaming_behavior=…)`, `:2520-2532`). Escape cancels: `_cancel_active_prompt()` calls `session.cancel()` + `worker.cancel()` (`:2657-2678`). There's a `LoginRequiredProvider` stub provider that errors with "/login" guidance when no credentials exist (`app.py:135-159`). Also: optimistic user-message rendering, large-paste placeholders, selection-copy, compaction worker separate from prompt worker.

### Built-in tools — exactly four (`tools.py`)

`create_coding_tools()` returns `read`, `write`, `edit`, `bash` (`tools.py:96-116`) — **no grep/find/ls tools** (the system prompt tells the model to use bash for those; `system_prompt.py:92-99` even has dormant logic for a future grep/find/ls set). Each is a `create_*_tool_definition()` factory returning a `ToolDefinition` (name/description/prompt metadata/JSON schema/async closure executor; `tools.py:65-90`), converted via `.to_agent_tool()`. Limits: `DEFAULT_MAX_OUTPUT_BYTES = 50KB`, `DEFAULT_MAX_OUTPUT_LINES = 2000` (`:28-29`).

- **`read`** (`:119-257`): UTF-8 text with 1-indexed `offset`/`limit`; **head-truncation** with continuation hints (`[Showing lines X–Y of N. Use offset=Z to continue.]`); a first line larger than 50KB yields a hint to use `sed`/`head -c` via bash (`:191-197`); jpg/png/gif/webp detected by MIME and returned as `image_base64` in `data` (`:155-169`).
- **`write`** (`:260-317`): overwrite/create with `mkdir(parents=True)`; serialized by a **per-resolved-path `asyncio.Lock`** (`_file_locks`/`_FileLockContext`, `:93`, `:1041-1057`) shared with `edit`.
- **`edit`** (`:320-430`): array of `{oldText, newText}`; each `oldText` must be non-empty, occur **exactly once** in the *original* file, spans must not overlap (`_validate_non_overlapping`, `:942-947`); all edits validate before any write (all-or-nothing); matching normalizes CRLF→LF then restores the file's dominant ending (`detect_line_ending`/`restore_line_endings`, `:744-757`) and preserves a UTF-8 BOM (`_strip_bom`, `:961-962`); replacements applied right-to-left by offset (`apply_edits_to_normalized_content`, `:760-790`); an identical-result edit is an error (`_no_change_error`). Result `data` includes an ndiff, a **unified patch**, and `first_changed_line` (`:365-379`) — the TUI renders the patch. Legacy top-level `oldText/newText` and JSON-string `edits` are normalized (`_prepare_edit_arguments`, `:899-918`).
- **`bash`** (`:433-583`): `asyncio.create_subprocess_shell`, stderr merged to stdout, optional `timeout` (seconds, **no default timeout**), POSIX `start_new_session=True` + `os.killpg(SIGKILL)` to kill the whole process group on timeout/cancel (`_kill_process_tree`, `:1016-1026`); cancellation is polled every 50 ms alongside `communicate()` via `asyncio.wait(FIRST_COMPLETED)` (`_communicate_with_cancellation`, `:606-646`). Output is **tail-truncated**; on truncation the full output is written to `tau-bash-*.log` in tmp and the path is reported (`_write_temp_output`, `:1029-1038`). Optional `shell_command_prefix` from `~/.tau/settings.json` (`shellCommandPrefix`) is prepended for user aliases (`shell_config.py`; docs `reference/configuration.md:164-195`).

**Permissions/safety: there is none.** No approval prompts, no allowlists, no sandbox — grep confirms no permission/approval machinery anywhere in `src/`. The model can run any bash command immediately. Safety posture is limited to: catalog overlays being user-level-only so a cloned repo can't redirect providers ("cloning a repository cannot silently redirect a provider's base_url", `reference/configuration.md:66-70`), never sourcing the user's rc files (`:167-169`), credentials file chmod 0600 (`credentials.py:119`), and `store: false` on OpenAI payloads (`openai_compatible.py:590-591`).

### CodingSession (`session.py`, 2,274 lines)

*"`AgentHarness` owns the in-memory agent brain. `CodingSession` owns the coding-session environment around it"* (`session.py:209-214`). Construction via `CodingSession.load(config)` (`:258-334`): read all entries; if empty, prepare pending `SessionInfoEntry` + `ModelChangeEntry` + `ThinkingLevelChangeEntry` **in memory only** (file is not created until the first real message persists — "empty sessions are deferred", `dev-notes/design/04-sessions.md:53`); pick the latest `leaf` entry and replay the active path; build tools + system prompt; construct the harness with restored messages; then persist repairs for dangling tool calls (`_persist_loaded_interrupted_tool_repairs`, `:1341-1376`).

- **Durable message boundary**: inside `prompt()` (`:1214-1301`), every `MessageEndEvent` triggers `_persist_messages_since()` (`:1378-1398`) which appends a `MessageEntry` *and a `LeafEntry`* per message — messages are durable the moment they complete, not at run end (mirrors Pi; `design/04-sessions.md:40-53`).
- **Compaction**: manual `/compact [instructions]` → `compact()` (`:1121-1132`); automatic before/after each prompt via `_maybe_auto_compact()` when the estimate exceeds threshold; **overflow recovery**: if a provider error matches context-overflow heuristics (`_is_context_overflow_error`, `:1744`), Tau runs a recent-preserving compaction and **one** `continue_()` retry (`:1270-1293`). Thresholds: `auto_compaction_threshold = context_window − 16,384` reserve; keep-recent budget 20,000 tokens (`context_window.py:14-16`, `auto_compaction_threshold_for_context_window` `:162-166`). Summaries are **model-generated** with a structured prompt (Goal/Constraints/Progress Done-InProgress-Blocked/Key Decisions/Next Steps/Critical Context — `SUMMARIZATION_PROMPT`, `context_window.py:27-53`; incremental `UPDATE_SUMMARIZATION_PROMPT` merges into a previous summary `:55-86`), with a deterministic fallback (`summarize_messages_for_compaction`, `:189-196`). Estimation is chars/4 + overhead constants (`CHARS_PER_TOKEN=4`, `MESSAGE_OVERHEAD_TOKENS=4`, `TOOL_OVERHEAD_TOKENS=16`, `:10-12`).
- **Tree branching**: `tree_choices()`/`branch_to_entry()` (`:412-491`) move the leaf pointer (append a new `LeafEntry`); optional model-generated **branch summary** of abandoned messages (`branch_summary.py`, prompt `BRANCH_SUMMARY_PROMPT` with 60KB source cap); selecting a user message branches to *before* it and pre-fills the input with its text (`:468-470`).
- **Auto session naming**: after the first user message persists, a one-off model call with `SESSION_NAME_SYSTEM_PROMPT` ("maximum four words", `:111-114`) names the session; never overwrites a manual `/name` (an explicitly documented divergence from Pi — `internals/design-principles.md:41-49`).
- **Terminal commands**: input starting `!` runs bash outside the agent, `!!` also appends output to context as a `UserMessage` (`parse_terminal_command`, `:2108-2121`; `run_terminal_command`, `:1172-1212`).
- **Diagnostics**: non-recoverable errors and exceptions are logged as JSONL to `~/.tau/logs/agent-calls.jsonl` (`diagnostics.py`, `paths.py:33-35`).
- Also: `resume(session_id)`, `new_session()`, `reload()` (re-discovers skills/prompts/context and rebuilds the system prompt), model/provider switching with per-model thinking-level sync, `export()`.

### Sessions on disk & resume

`~/.tau/sessions/<slugified-path>-<sha256[:6]>/<uuid>.jsonl` per project (`TauPaths.project_session_dir`, `paths.py:81-92`); per-project `index.jsonl` of `SessionRecordModel{id,path,cwd,model,provider_name,title,created_at,updated_at}` plus a legacy global index (`session_manager.py:71-248`). `tau --resume <id>` / `/resume` picker / `tau sessions`. Export to self-contained HTML (pygments-highlighted, includes the preserved tree) or raw JSONL (`session_export.py`, 1,023 lines).

### System prompt, instructions, skills, prompt templates

- **System prompt** (`system_prompt.py:37-68`): deterministic "Pi-style" assembly — identity line, `Available tools:` from `prompt_snippet`s, de-duplicated `Guidelines:` from tool `prompt_guidelines` (+ "Be concise…"), optional append text, `<project_context>` block wrapping each `AGENTS.md` as `<project_instructions path="…">` (`format_project_context`, `:119-136`), `<available_skills>` XML index with name/description/location (only when the `read` tool exists — the model reads skill files itself, `:139-164`; "mirrors Pi", `dev-notes/architecture/phase-10-system-prompt.md:108`), then current date + cwd.
- **Project instructions** (`context.py`): discovers `AGENTS.md` from `~/.tau/`, `~/.agents/`, project root (found via markers `.git`, `pyproject.toml`, `uv.lock`, `setup.py`, `package.json`, `:10`) down through every ancestor dir to cwd, plus `.tau/AGENTS.md` and `.agents/AGENTS.md` (`_context_file_candidates`, `:44-62`).
- **Skills** (`skills.py`): Agent Skills spec — a skill is a directory containing `SKILL.md`, discovered across four roots in increasing precedence: `~/.tau/skills`, `~/.agents/skills`, `./.tau/skills`, `./.agents/skills` (`resources.py:62-80`); bare `.md` files produce a migration diagnostic instead of loading (ADR 0003; `skills.py:170-203`). Frontmatter is parsed by a **dependency-free minimal `key: value` parser** (`parse_markdown_resource`, `resources.py:132-160`). Invocation `/skill:name [request]` expands into the prompt as a `<skill name=… location=…>` block (`expand_skill_command`/`format_skill_invocation`, `skills.py:88-121`) — deliberately *not* a slash command.
- **Prompt templates** (`prompt_templates.py`): markdown files in `prompts/` dirs; invoked as `/<filename-stem> args`; `{{ arguments }}`/`{{ args }}` placeholders; no placeholders → args appended (`expand_prompt_template_command`, `:94-120`).

### Slash commands (`commands.py`)

`CommandRegistry` with parse/register/execute (`:146-198`) and a Protocol-typed `CommandSession` so commands are testable against fakes (`:23-89`). Handlers return a **declarative `CommandResult`** (flags like `exit_requested`, `resume_picker_requested`, `login_picker_requested`, `compact_summary`, `export_requested`… `:92-117`) — the frontend applies effects. 17 built-ins (`create_default_command_registry`, `:201+`): `/quit`(alias `/exit`), `/new`, `/compact`, `/export`, `/session`, `/system`, `/skill`, `/hotkeys`, `/reload`, `/resume`, `/tree`, `/name`, `/model`, `/scoped-models`, `/theme`, `/login`, `/logout`.

### Providers/config/credentials

- **Catalog** (`src/tau_coding/data/catalog.toml`, header: *"generated from Pi API-provider metadata"*): ~24 built-in providers — openai, openai-codex, anthropic, google, deepseek, xai, groq, cerebras, nvidia, openrouter, zai, mistral (kind `mistral-conversations`), minimax(+cn), moonshotai(+cn), huggingface, fireworks, together, vercel-ai-gateway, xiaomi(+3 regional token-plan variants) — with per-model `context_windows`, `model_metadata` (display name, reasoning flag, input modalities, max_tokens, **cost** per 1M tokens), thinking config (`thinking_levels`, `thinking_default`, `thinking_parameter`). Users overlay `~/.tau/catalog.toml` (same schema, merge semantics documented at `reference/configuration.md:72-110`); strict validation "fails loudly" (`catalog_loader.py`, 550 lines).
- **Preferences** `~/.tau/providers.json` (default provider/model, per-provider headers/timeouts/retries/thinking defaults, `scoped_models` for the Ctrl+P quick cycle); atomic writes + `.bak` (`provider_config.py:900-921`); `DEFAULT_PROVIDER_NAME = "openai"`, `DEFAULT_MODEL = "gpt-5.4"` (`provider_config.py:44-45`).
- **Credentials** `~/.tau/credentials.json` (chmod 0600): API keys via `/login` or **OAuth** — full PKCE flow for OpenAI Codex on `localhost:1455` with auto token refresh (`oauth.py:25-33`, `login_openai_codex` `:181`, refresh in `provider_runtime.OpenAICodexCredentialResolver._refresh_if_needed`, `provider_runtime.py:163-172`). **Resolution order: stored credential first, then env var named by `api_key_env`** (`reference/configuration.md:143-145`; `cli.py:459-473`).
- **Runtime construction**: `create_model_provider()` (`provider_runtime.py:46-98`) maps config kind → `AnthropicProvider` | `OpenAICodexProvider` | `GoogleGenerativeAIProvider` | `MistralConversationsProvider` | `OpenAICompatibleProvider`, wiring the session's `ThinkingLevel` (`off/minimal/low/medium/high/xhigh`, `thinking.py:8-20`) into provider-specific parameters (`reasoning_effort`, `reasoning.effort`, or Anthropic budget tokens: minimal=1024 … xhigh=16384, `thinking.py:63-74`).

## 5. Relationship to Pi

Tau is explicitly a **Python re-implementation of the architecture of Pi** (Mario Zechner's `pi-mono` / pi.dev coding agent, TypeScript). Evidence and specifics:

- `AGENTS.md:3`: *"Tau is a Python implementation of Pi's minimalist coding-agent harness architecture."* `dev-notes/design/00-roadmap.md:5-6`: *"The goal is not a line-by-line port; the goal is to preserve the same boundaries while using Python-native tools."* The docs site domain itself is the joke: twotimespi.dev.
- The **guiding split is copied verbatim from Pi**: `AgentHarness = reusable brain / AgentSession(CodingSession) = coding-agent environment / TUI = one possible frontend` (`AGENTS.md:17-21`, `README.md:47-50`, `dev-notes/design/01-architecture.md:33-37`).

**Borrowed from Pi (each documented in dev-notes):**
- Provider-neutral event stream as the frontend contract; UI adapter boundary (`dev-notes/architecture/phase-12-textual-tui.md:41`).
- No default turn limit in the loop (`phase-3-agent-loop.md:194`).
- User prompt echoed through the event stream after `turn_start` (`phase-20-1-context-accounting.md:47-49`).
- `MessageEndEvent` as the durable-message boundary + append-only leaf pointers ("mirrors Pi's session model", `design/04-sessions.md:44-51`).
- System prompt not persisted in session JSONL; rebuilt at resume ("This matches Pi's current behavior", `design/04-sessions.md:79`).
- Pi-style system prompt: XML-ish `<project_context>`/`<available_skills>` blocks; skills section only when `read` exists (`phase-10-system-prompt.md:78-108`).
- Tool behavior: `ToolDefinition` with prompt snippet/guidelines is "Pi-like" (`phase-5-coding-tools.md:23`); edit's unique-match/no-overlap rules are "Pi-inspired" (`:73-75`); truncation metadata + continuation hints are "Pi-style" (`:53`).
- Queued **steering/follow-up** message queues (`queued-steering-follow-ups.md:5`: "adds Pi-style message queueing"), cancellation-token boundary (`phase-23-tui-polish.md:131-134`), scoped models (`phase-18-provider-config-foundation.md:153-156`), `tau "prompt"` CLI form (`:104-106`), tree branching as structural mutation not transcript edit (`phase-24-session-tree-branching.md:6-7`), structured compaction summaries and append-only compaction ("keeps Pi's append-only session property", `phase-22-compaction-foundation.md:39-41`, "Pi-style automatic compaction by default", `:71`), HTML session export (`phase-20-4-session-export.md:49-53`), slash-command registry aligned to Pi's command list (`phase-15-slash-command-registry.md:64-96` explicitly lists Pi's commands and classifies which Tau adopted vs deferred: `/settings`, `/fork`, `/clone`, `/share`, `/import`, `/copy`, `/changelog` deferred), Pi-style stacked transcript blocks in the TUI (`phase-23-tui-polish.md:27`), the provider catalog is literally "generated from Pi API-provider metadata" (`catalog.toml:1`).

**Deliberate divergences (documented):**
- **Skills discovery**: ADR 0003 — Pi keeps a `SkillDiscoveryMode = "pi" | "agents"` split (bare `.md` allowed in `.pi/skills/` for backward compat); Tau, being pre-1.0, adopts the strict Agent Skills `SKILL.md` spec everywhere and emits migration diagnostics for bare `.md` (`adr/0003:52-79`; comment in `skills.py:170-176`).
- **Auto session naming**: Tau adds model-generated session titles, which Pi's minimalist baseline doesn't do; kept in `tau_coding` because it's app workflow, not harness behavior (`internals/design-principles.md:41-49`; `dev-notes/architecture/auto-session-naming.md:17-21`).
- **`/system` command, `/theme`,** and other conveniences noted as "small intentional product divergences".

**What Tau simplifies/omits vs Pi (observed):** no extensions/plugin system yet (**Phase 21 "Extensions" intentionally deferred**, `design/00-roadmap.md:61`), no `/fork`,`/clone`,`/share`,`/import`, no token-usage/cost accounting (estimation only), no MCP support, no sub-agents, only 4 tools, no permission system, string-only message content (no multimodal transcript), sequential tool execution.

**Python-specific choices:** `Protocol`s instead of TS interfaces (`ModelProvider`, `CancellationToken`, `ToolExecutor`, `SessionStorage`, `CommandSession`, `EventRenderer`); pydantic v2 models with `Literal` discriminators + PEP 695 `type` unions instead of TS discriminated unions; frozen `dataclass(slots=True)` for configs/tools; the loop as an **async generator** with `AsyncIterator[AgentEvent]`; `anyio.run` at the CLI edge, `asyncio` primitives inside; cooperative polling cancellation tokens (50 ms) rather than task cancellation as the contract; Textual instead of Pi's own TUI layer; hand-rolled `httpx` SSE instead of vendor SDKs; mypy `strict` as the typing gate.

## 6. Teaching Value

Tau is *"meant to be read"* (`README.md:30-32`), *"both a usable terminal coding agent and a teaching codebase"* (`CONTRIBUTING.md:3`). What concretely supports that:

- **Tiny, single-purpose core modules**: the entire portable brain is 1,351 lines across 13 files; `loop.py` (276) and `harness.py` (298) are each readable in one sitting; `types.py` is 8 lines. Complexity concentrates in the app layer (TUI, provider config) where it's honest about being product code.
- **Docstring discipline**: every module has a purpose docstring; tool factories carry reference-grade docstrings (e.g. `create_edit_tool_definition`, `tools.py:321-337`), and ADR 0002 explicitly decides to keep user docs hand-written *and* keep docstrings as contributor API docs rather than generating docs (dev-notes/adr/0002).
- **Docs map to code 1:1**: `internals/agent-loop.md` describes exactly `run_agent_loop`'s seven steps and lists the real event class names; `internals/architecture.md` describes the three packages; `internals/custom-frontend.md` is a working guide to building a frontend on `CodingSession` + `AgentEvent` (with the steer/follow_up API and "what not to depend on" list); `reference/tools.md` documents the exact truncation limits (2,000 lines / 50 KB) found in `tools.py:28-29`.
- **`dev-notes/` build journal**: ~40 phase notes (phase-1 core types … phase-24 tree branching, index at `dev-notes/architecture/index.md`) each answering "what was added / why it exists / how it maps to Pi's design / how to test it" (required by `AGENTS.md:70-77`). Design docs `00-05` (`roadmap`, `architecture`, `agent-loop`, `tools`, `sessions`, `core-types-and-events`) plus `agent-loop.md`/`harness.md` reference notes. Three ADRs: **0001** use Textual behind an adapter boundary; **0002** keep tool docs hand-written (no mkdocstrings); **0003** unify skill discovery on the Agent Skills spec (the most detailed Pi-divergence analysis, quoting Pi's changelog and `packages/coding-agent/src/core/package-manager.ts`).
- **Website internals/tutorial pages** (one-liners): `what-is-tau.md` — dual identity pitch; `concepts.md` — 8 core concepts (loop, providers, tools, sessions, AGENTS.md, skills/templates, context/compaction, thinking, two interfaces); `internals/architecture.md` — the three-layer boundary and why it matters; `internals/agent-loop.md` — loop steps + event catalog; `internals/design-principles.md` — 7 principles ("Small layers beat magic", "Events are the contract", "The core stays portable", "Tools are ordinary typed functions", "Sessions are durable and inspectable", "Small product divergences are explicit", "Documentation follows implementation"); `internals/custom-frontend.md` — build-your-own-frontend contract; `why-tau.md` — the τ math essay; guides cover TUI, print mode, sessions, providers, project instructions, skills/prompts, context; reference covers CLI, slash commands, keybindings, config file formats, tools.
- **Deterministic testability as pedagogy**: `FakeProvider` + Protocol seams mean the loop/harness/session tests read like specifications (e.g. `test_agent_loop.py:38` `test_agent_loop_streams_text_and_appends_assistant_message`); `tests/conftest.py` is 11 lines.
- **Inspectable persistence**: the root `session-temp.jsonl` sample shows the exact entry format (`session_info → model_change → thinking_level_change → message → leaf → …`), reinforcing "history is plain enough to read by hand" (`internals/design-principles.md:38`).
- Contribution culture encodes the teaching goal: "When in doubt, favor the smallest step that preserves the architecture and teaches the design clearly" (`CONTRIBUTING.md:145`); catalog additions are data-only PRs (`CONTRIBUTING.md:79-90`).

Minor doc drift worth noting: `CONTRIBUTING.md:112` and `dev-notes/README.md:7-8` still reference an older `website/src/content/docs/` path and a GitHub Pages URL, while the actual site is Hugo under `website/content/` published at twotimespi.dev; `dev-notes/architecture/index.md:23` links a `custom-tui.md` that no longer exists (superseded by `website/content/internals/custom-frontend.md`).
