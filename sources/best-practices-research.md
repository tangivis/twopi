# Research Notes: Building LLM Agents & Agent Harnesses (2025–2026 Landscape)

*Compiled 2026-07-11 for a learning document comparing two minimal agent harnesses (pi — TypeScript; tau — Python). Primary sources preferred; publication dates given where findable.*

---

## 1. Canonical Agent Design Guidance

### Anthropic — "Building Effective Agents" (Dec 19, 2024; Erik Schluntz & Barry Zhang)
Source: https://www.anthropic.com/engineering/building-effective-agents

The single most-cited agent design document. Key content:

- **Workflows vs agents**: workflows are "LLMs and tools orchestrated through predefined code paths"; agents are systems where "LLMs dynamically direct their own processes and tool usage, maintaining control over how they accomplish tasks."
- **The augmented LLM** is the basic building block: an LLM + retrieval + tools + memory, where the model itself generates queries, selects tools, and decides what to keep. Interfaces can be standardized via MCP.
- **Five workflow patterns**: (1) *prompt chaining* — fixed sequential subtasks, trades latency for accuracy (e.g., copy → translate); (2) *routing* — classify input, dispatch to specialized handlers/model sizes; (3) *parallelization* — sectioning (independent subtasks) and voting (multiple attempts, e.g., vulnerability review); (4) *orchestrator-workers* — a central LLM dynamically decomposes and delegates when subtasks can't be predicted (multi-file code changes); (5) *evaluator-optimizer* — one LLM generates, another critiques in a loop (literary translation, iterative search).
- **The agent loop**: agents are "typically just LLMs using tools based on environmental feedback in a loop" — they plan independently but must obtain "ground truth from the environment at each step (such as tool call results)."
- **Three principles**: keep designs **simple**; make planning **transparent**; and invest in the **agent-computer interface (ACI)** as much as you would a human interface — thorough tool docs/testing, formats close to naturally occurring text, no formatting overhead (e.g., don't force line-count bookkeeping), "poka-yoke" tools so mistakes are structurally hard.
- **When not to build agents**: start with single LLM calls + retrieval; "agentic systems often trade latency and cost for better task performance." Frameworks are fine for prototyping but shouldn't hide the underlying prompts and responses.

### Anthropic — "How we built Claude Code" (via Pragmatic Engineer deep-dive, Sep 23, 2025)
Source: https://newsletter.pragmaticengineer.com/p/how-claude-code-is-built (and https://www.anthropic.com/features/making-of-claude-code)

- Started by Boris Cherny (Nov 2024) as a personal CLI experiment; 50% of Anthropic engineering used it within five days of internal dogfooding.
- Stack: **TypeScript, React + Ink (terminal UI), Yoga layout, Bun** — deliberately "on distribution" (technologies the model already knows well). **~90% of Claude Code is written by Claude Code itself.**
- Philosophy: minimal business logic — Cherny: *"We want people to feel the model as raw as possible"* and *"Every time there's a new model release, we delete a bunch of code."* This is the definitive first-party statement of the thin-harness thesis.
- Prototype velocity: 20+ prototypes in 2–3 days per feature; ~60–100 internal releases/day; one public release/day; PR throughput up 67% while the team doubled.
- Architecture: a lightweight shell over tool definitions + local filesystem/command access; no virtualization (runs locally), with a multi-tiered permission system (per-project/user/company; static analysis matches commands against allowlists before prompting).

### Anthropic — "Writing effective tools for agents" (Sep 11, 2025)
Source: https://www.anthropic.com/engineering/writing-tools-for-agents

- Build **evals from real tasks** (dozens of realistic, multi-step prompt/outcome pairs); run with simple agentic loops; track accuracy, runtime, tool-call counts, tokens, errors; read transcripts and CoT to find confusion.
- **Consolidate tools** rather than wrapping every API endpoint: `schedule_event` instead of `list_users`+`list_events`+`create_event`; `search_logs` instead of `read_logs`. Each tool needs "a clear, distinct purpose."
- **Namespace** related tools (`asana_search`, `jira_search`); prefix vs suffix placement has "non-trivial effects" — test both.
- **Return meaningful context**: semantic names over UUIDs/mime-types; a `response_format: concise|detailed` enum lets the agent choose token cost (their Slack example: 72 vs 206 tokens).
- **Token efficiency**: pagination, filtering, truncation with sensible defaults (Claude Code caps tool responses at 25,000 tokens); truncation messages should steer ("use many small searches instead of one broad search").
- **Errors are prompts**: return "specific and actionable improvements," not opaque codes. Prompt-engineer error strings.
- Tool descriptions = onboarding docs for a new hire; unambiguous param names (`user_id` not `user`). Precise description refinements alone took Claude Sonnet 3.5 to state-of-the-art on SWE-bench Verified. Let Claude optimize its own tools from eval transcripts.

### Anthropic — "Effective context engineering for AI agents" (Sep 29, 2025)
Source: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

- Context engineering = "curating and maintaining the optimal set of tokens during LLM inference" — the successor discipline to prompt engineering.
- **Context is finite**: "context rot" — recall accuracy declines as token count grows (all models); attention is an "attention budget" stretched by n² pairwise relationships and thinner training on long sequences.
- System prompts should sit at the **"right altitude"**: not brittle hardcoded logic, not vague platitudes — "specific enough to guide behavior effectively, yet flexible enough to provide strong heuristics."
- **Just-in-time retrieval**: keep lightweight identifiers (file paths, links) and let the agent load data with tools at runtime (Claude Code's glob/grep model), vs pre-retrieval (RAG); hybrid works too.
- **Three long-horizon techniques**: *compaction* (summarize near the limit, preserving decisions/bugs, discarding redundant tool output — tool-result clearing is the lightest form); *structured note-taking / agentic memory* (write notes to files outside context, re-read later); *sub-agents* (clean context windows per focused task, returning 1–2k-token summaries). Compaction for long back-and-forth; notes for milestone-based work; sub-agents for parallel exploration.
- Guiding rule: "the smallest set of high-signal tokens that maximize the likelihood of your desired outcome."

### OpenAI — "A Practical Guide to Building Agents" (PDF, ~April 2025)
Source: https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf

- Agent = model using tools iteratively with autonomy within defined boundaries. Build agents when workflows involve (1) complex decision-making, (2) brittle rule systems, (3) unstructured data.
- Foundations: **model + tools + instructions**, with tools in three categories (data, action, orchestration).
- Orchestration: single-agent run loop first; then **manager pattern** (coordinator delegating to specialists) or **decentralized handoffs**. Explicit advice: *start with a single agent* and only add multi-agent complexity when needed.
- **Guardrails**: relevance/safety classifiers, tool-level safeguards (risk-rate each tool), and human-in-the-loop for high-stakes actions.

### 12-Factor Agents — Dex Horthy / HumanLayer (2025)
Source: https://github.com/humanlayer/12-factor-agents

Thesis: production "agents" are mostly deterministic software with strategic LLM steps; frameworks get you to ~70–80% quality, then teams rip them out because reaching production needs control the abstraction hides. The factors:

1. Natural language → tool calls; 2. **Own your prompts** (no framework-hidden prompts); 3. **Own your context window** (context construction is the real engineering); 4. Tools are just structured outputs; 5. Unify execution state and business state; 6. Launch/pause/resume with simple APIs; 7. Contact humans with tool calls (HITL as a tool); 8. **Own your control flow**; 9. Compact errors into the context window (let the model see and recover from failures, within budget); 10. **Small, focused agents** over monoliths; 11. Trigger from anywhere (Slack, cron, email); 12. Make the agent a **stateless reducer** (pure function over state). Appendix factor 13: pre-fetch context you'll predictably need.

Factors 2, 3, 8, and 12 are effectively the design brief for a minimal harness like pi or tau.

---

## 2. The Minimal-Harness Philosophy ("the model is the agent")

### Thorsten Ball — "How to Build an Agent" (Amp/ampcode, Apr 15, 2025)
Source: https://ampcode.com/how-to-build-an-agent

- Core claim: "It's an LLM, a loop, and enough tokens." A working code-editing agent in **~300–400 lines of Go**, most of it boilerplate.
- Three tools (`read_file`, `list_files`, `edit_file`), each just name + description + JSON schema + function. The harness only maintains conversation history, detects tool-use requests, executes, and feeds results back; "Claude realizes that it can read the file to answer that and off it goes." The perceived magic of agents is model capability, not scaffolding.

### sketch.dev — "The Unreasonable Effectiveness of an LLM Agent Loop with Tool Use" (Philip Zeyliger, May 15, 2025)
Source: https://sketch.dev/blog/agent-loop

- The agent is a **~9-line loop**: call LLM → execute requested tools → append results → repeat until no tool calls. With just `bash`, it fixes type errors, does git surgery, installs missing dependencies, adapts to environment quirks — often one-shot.
- Honest caveats: it can be "frustratingly unreliable" (e.g., skipping failing tests); and the real engineering lives in the tools — text-editing tools are "surprisingly tricky," models fumble `sed` one-liners, so purpose-built (visual-style) editors matter more than the loop.

### Mario Zechner (badlogic) — pi (Nov 30, 2025)
Source: https://mariozechner.at/posts/2025-11-30-pi-coding-agent/ (repo: github.com/badlogic/pi-mono)

The most detailed minimal-harness manifesto, and directly relevant since pi is one of the two harnesses being compared:

- **Why he left Claude Code**: "Claude Code has turned into a spaceship with 80% of functionality I have no use for"; prompts/tools change unpredictably per release; hidden context injection you can't inspect; and "exactly controlling what goes into the model's context yields better outputs."
- **Architecture** (TypeScript monorepo): `pi-ai` (unified multi-provider LLM API — Anthropic, OpenAI, Google, xAI, Groq, Cerebras, OpenRouter, OpenAI-compatible; four wire APIs suffice), `pi-agent-core` (the loop: tool execution, TypeBox/AJV validation, event streaming), `pi-tui` (differential-rendering terminal UI), `pi-coding-agent` (CLI wiring). **Four tools: read, write, edit, bash.** System prompt + tool definitions **< 1,000 tokens** (vs Claude Code's 10k+).
- **What an agent needs**: full filesystem/command access with *no permission checks* ("YOLO by default"), multi-provider + mid-session model switching, session continue/resume/branching, cost/token tracking, image input.
- **What it doesn't need**: built-in todo lists and plan mode (files are better and observable); **MCP** ("too much context overhead" — MCP servers eat 7–9% of the window; use CLI tools + READMEs instead); background bash (use tmux); built-in sub-agents (spawn new pi sessions via bash for full visibility); **permission prompts** ("security theater when agents can write and execute code" — exfiltration can't be prompted away; if security matters, **run the agent in a container** and cut network access).
- Context stance: context is the most precious resource; quality degrades past ~100k tokens; no built-in compaction yet; file-based artifacts carry state across sessions; progressive disclosure over up-front tool dumps.
- Benchmarks: competitive with Codex/Cursor on **Terminal-Bench 2.0** despite minimalism — and a raw tmux agent (Terminus 2) performs similarly, reinforcing "less is more."
- Third-party validation: Armin Ronacher (Jan 31, 2026, https://lucumr.pocoo.org/2026/1/31/pi/) praises pi's "shortest system prompt of any agent," its TypeScript extension API, session branching, and its role as the foundation of OpenClaw; his theme is "software building software" — agents extending their own harness. Vercel's AI SDK now ships a `HarnessAgent` that can run "Claude Code, Codex, or Pi" as preconfigured harnesses (https://ai-sdk.dev/docs/agents/overview) — evidence pi is treated as an established harness category member.

### Synthesis of the minimal-harness argument
1. The loop is trivial; capability lives in the model (Ball, sketch.dev). 2. Every token the harness injects is a confounder — small prompts and few tools give the model cleaner signal and give the operator reproducibility (Zechner). 3. Even the richest harness team agrees directionally: Anthropic deletes harness code every model generation and keeps "the model as raw as possible" (Pragmatic Engineer). 4. The counterweight: production concerns (evals, safety, sessions, HITL, cost) still need engineering somewhere — 12-Factor says own it yourself in plain code rather than importing a framework.

---

## 3. Framework Landscape

| Framework | Language | Abstraction level | Choose when | Main criticism |
|---|---|---|---|---|
| **Claude Agent SDK** (https://code.claude.com/docs/en/agent-sdk/overview) | Python + TypeScript | High — the full Claude Code harness as a library: built-in tools (Read/Write/Edit/Bash/Glob/Grep/WebSearch/WebFetch/AskUserQuestion), agent loop, auto-compaction, subagents, hooks (PreToolUse/PostToolUse/Stop…), permission modes, sessions (resume/fork, JSONL on disk), MCP, skills/CLAUDE.md | You want a batteries-included agent that works on files/commands, on your own infra; prototype → production automation | Claude-only; heavyweight, opinionated harness — the exact opacity minimal-harness people avoid; Anthropic itself distinguishes it from thinner tiers (raw Messages API loop, SDK "tool runner", hosted Managed Agents — see https://platform.claude.com/docs) |
| **OpenAI Agents SDK** (https://openai.github.io/openai-agents-python/, launched Mar 2025) | Python (+ JS port) | Low-to-mid — deliberately few primitives: Agents, Handoffs, Guardrails, Sessions, function tools, built-in run loop + tracing; production evolution of Swarm | Multi-agent handoff patterns on OpenAI models; you want tracing out of the box | OpenAI-centric (other providers via LiteLLM shims); handoff model is one fixed opinion about multi-agent |
| **LangGraph** (https://docs.langchain.com/oss/python/langgraph/overview) | Python + JS | Low — graph/state-machine runtime: durable execution, checkpointing/persistence, human-in-the-loop interrupts, time travel; LangChain's `create_agent` sits above it | Long-running stateful workflows needing fault tolerance and fine-grained orchestration (used by Klarna, Uber, J.P. Morgan) | Steep learning curve; state-management overhead; carries LangChain-ecosystem baggage — the archetypal target of 12-factor "frameworks obscure prompts/control flow" critique (comparison: https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen) |
| **smolagents** (HuggingFace, Dec 31, 2024, https://huggingface.co/blog/smolagents) | Python | Minimal — core logic ~1,000 lines; signature idea is **CodeAgent**: actions written as executable Python instead of JSON tool calls (~30% fewer steps, better composability, closer to pretraining data); E2B sandboxing | Research/prototyping; code-as-action experiments; Hub tool sharing | Code-execution security surface; less production machinery (state, durability) |
| **Vercel AI SDK** (https://ai-sdk.dev/docs/agents/overview; AI SDK 7 current) | TypeScript | Layered — `generateText`/`streamText` + tools with `stopWhen`/`prepareStep` loop control; `ToolLoopAgent` class; `HarnessAgent` wraps external harnesses (Claude Code, Codex, **Pi**) | TS/web apps needing streaming UI (Next.js/Svelte/Vue/Expo) across many providers | It's an app toolkit first; agent features are younger; docs themselves steer you back to explicit control flow for reliability |
| **PydanticAI** (https://pydantic.dev/docs/ai/overview/) | Python | Mid — "FastAPI feeling for GenAI": typed agents, Pydantic-validated structured outputs, DI via `RunContext`, tool decorators; durable execution via Temporal/DBOS/Prefect; HITL tool approval; MCP/A2A/AG-UI; Logfire observability | Type-safe production Python where validated outputs matter; model-agnostic (20+ providers) | Younger ecosystem; strongest value accrues if you also adopt Logfire/Pydantic stack |
| **Google ADK** (https://adk.dev/) | Python, TS/JS, Go, Java, Kotlin | Mid-high — `LlmAgent`, workflow agents (Sequential/Loop/Parallel), multi-agent hierarchies, rich tool ecosystem, eval tooling, bidi streaming; deploys to Agent Engine/Cloud Run/GKE; A2A protocol | Enterprise multi-agent on Google Cloud; Gemini-first but model-flexible | Google-ecosystem gravity; heavy conceptual surface for simple agents |
| **CrewAI** | Python | High — role/goal/backstory "crews"; fastest time-to-value (~35 lines for a minimal multi-agent) | Quick role-based multi-agent prototypes | "May lack sophistication for complex enterprise scenarios"; abstraction hides control flow (https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen) |
| **AutoGen** (Microsoft) | Python (+ .NET) | Mid — conversation-centric multi-agent orchestration | Research-ish conversational multi-agent | "Flexibility at the cost of growing complexity"; setup complexity; superseded in places by MS Agent Framework (same source) |

**MCP (Model Context Protocol)** — https://modelcontextprotocol.io/
- Open standard ("USB-C port for AI applications") for connecting agents to external tools/data: host apps run MCP *clients* that talk to MCP *servers* exposing **tools, resources, prompts**; transports are stdio and streamable HTTP.
- Timeline (https://en.wikipedia.org/wiki/Model_Context_Protocol, https://www.pento.ai/blog/a-year-of-mcp-2025-review): Anthropic released it Nov 2024; **OpenAI adopted it across Agents SDK/ChatGPT in March 2025**; Google DeepMind confirmed Gemini support April 2025; **donated to the Agentic AI Foundation under the Linux Foundation Dec 9, 2025** (co-founded by Anthropic, Block, OpenAI). SDK downloads grew from ~100k (Nov 2024) to tens of millions monthly.
- Why it matters: it decouples tool ecosystems from harnesses — any MCP-speaking harness gets thousands of integrations free. Counterpoint for minimal harnesses: Zechner rejects built-in MCP for context cost; the pi ecosystem adds it externally (OpenClaw via mcporter), and Anthropic's own "code execution with MCP" direction similarly moves tool schemas out of the prompt.

---

## 4. Key Engineering Topics

### Tool design
Consolidated from Anthropic's tool post (§1) plus "Building Effective Agents" ACI principle: few, distinct, consolidated tools; prescriptive *when-to-use* descriptions (trigger conditions in the description measurably lift correct-call rates — also in Anthropic API docs guidance); namespacing; semantic identifiers over UUIDs; response-format enums; pagination/truncation with steering text; error messages written as prompts; evals on real tasks before shipping a tool. Anthropic's agent-design docs add a **bash-vs-dedicated-tools rule of thumb**: start with bash for breadth; promote an action to a dedicated tool when you need to *gate* (permissions), *render* (custom UI), *audit*, or *parallelize* it — a dedicated tool gives the harness typed, interceptable calls where bash gives an opaque string (https://platform.claude.com/docs, agent design guidance).

### Context management
- **Context rot is measured**: Chroma's technical report (Kelly Hong, Anton Troynikov, Jeff Huber, July 2025, https://www.trychroma.com/research/context-rot) tested 18 models (GPT-4.1, Claude 4, Gemini 2.5, Qwen): performance degrades **non-uniformly** with input length even on trivial tasks; lower needle-question similarity degrades faster; single distractors hurt; models oddly do better on shuffled than logically-structured haystacks; LongMemEval shows large gaps between 300-token focused prompts and 113k full prompts.
- **Compaction/summarization**: Claude Code auto-compacts near the limit and supports `/compact <instructions>` and partial summarization; CLAUDE.md can carry compaction instructions ("always preserve modified-file list") (https://code.claude.com/docs/en/best-practices). Anthropic's context post: tune compaction recall-first, then precision; clear old tool results as the lightest touch. The Claude API now offers **server-side compaction** and **context editing** (clear old tool results/thinking) as platform primitives (https://platform.claude.com/docs/en/build-with-claude/compaction).
- **KV-cache-friendly prompt design** (Manus, Yichao "Peak" Ji, July 18, 2025, https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus): *"KV-cache hit rate is the single most important metric for a production-stage AI agent"* — cached input on Claude Sonnet cost $0.30/MTok vs $3.00 uncached (10x). Practices: byte-stable prompt prefix (no timestamps), **append-only context**, deterministic JSON serialization, explicit cache breakpoints; **mask tools, don't remove them** (logit masking via a state machine, since editing the tool list invalidates the cache and orphans references); **file system as ultimate context** (unlimited, persistent, restorable compression — drop page content, keep URL); **recitation** (rewrite `todo.md` at the end of context to fight lost-in-the-middle); **keep errors in context** (models update priors from observed failures — hiding errors prevents adaptation); **avoid few-shot ruts** (inject small structured variation). Anthropic's prompt-caching docs state the same invariant: caching is a prefix match; tools → system → messages render order; timestamps/UUIDs/unsorted serialization are silent cache killers (https://platform.claude.com/docs/en/build-with-claude/prompt-caching).

### Sub-agents / multi-agent orchestration
- Anthropic's multi-agent research system (June 13, 2025, https://www.anthropic.com/engineering/multi-agent-research-system): orchestrator-worker with Opus lead + parallel Sonnet subagents + a citation agent; **token usage alone explains ~80% of performance variance**; multi-agent beat single-agent Opus by 90.2% on internal research evals; parallel subagents + parallel tool calls cut research time up to 90%. Costs: agents ≈ **4x** chat tokens; multi-agent ≈ **15x** — only worth it for high-value, parallelizable, breadth-first tasks. **Coding is called out as a poor fit** (less parallelizable, agents need shared context). Prompt lessons: teach the lead to write detailed subtask specs (else duplication), embed effort-scaling rules (simple query = 1 agent/3–10 calls), treat extended thinking as a controllable scratchpad. Production lessons: errors compound; agents must resume from checkpoints; full tracing; rainbow deploys so restarts don't kill running agents; "the last mile often becomes most of the journey."
- Counterpoint for harness design: pi deliberately has no subagent machinery — spawn another pi via bash for observability; Claude Code's subagents exist mainly as a *context-isolation* tool (investigate in a separate window, return a summary) per https://code.claude.com/docs/en/best-practices.

### Evaluation of agents
- **SWE-bench Verified** (500 human-validated real GitHub issues) is the de facto coding-agent benchmark; scores went from <10% to >70% within roughly a year, and frontier models now sit ~54–81% pass@1 — approaching saturation (https://www.demandsphere.com/research/demandsphere-radar/ai-frontier-model-tracker/benchmarks/swe-bench/, https://arxiv.org/pdf/2506.09289). **pass@1/pass@k** (fraction solved in 1/k attempts) is the standard metric; harder successors exist — **SWE-Bench Pro** keeps frontier models under 25% pass@1 (https://arxiv.org/html/2509.16941v1).
- **Terminal-Bench 2.0** (Stanford × Laude Institute, https://www.tbench.ai/): 89 hard, verifier-scored terminal tasks (kernel builds, git servers, SSL, ML training) run in containers via the **Harbor** framework; it evaluates *harness + model pairs*, which is why it's the benchmark pi quotes. Zechner's result — minimal pi ≈ big-harness agents — is the key empirical datum for the thin-harness thesis.
- Anthropic's research-system evals: start with ~20 queries, LLM-as-judge with a single rubric (accuracy, citations, completeness, source quality, tool efficiency), grade **end states not step sequences**, keep humans in the loop for hallucination/source-bias catches. Meta-benchmarking infrastructure critique: Holistic Agent Leaderboard (https://arxiv.org/pdf/2510.11977).

### Safety & permissions
- **Claude Code's spectrum** (all first-party): default deny-with-prompts + allowlists (`/permissions`, `--allowedTools`); `--dangerously-skip-permissions` (YOLO) with long-standing guidance to use it only in a **container without internet access**; **sandboxing** (Oct 20, 2025, https://www.anthropic.com/engineering/claude-code-sandboxing) — dual isolation (filesystem via bubblewrap/Seatbelt + network via allowlisting proxy), both required ("without network isolation, a compromised agent could exfiltrate SSH keys; without filesystem isolation it could escape"); cut permission prompts **84%** internally; prompt injection stays contained; runtime open-sourced (`sandbox-runtime`). Then **auto mode** (Mar 25, 2026, https://www.anthropic.com/engineering/claude-code-auto-mode): users approve 93% of prompts anyway (fatigue), so a stripped-transcript Sonnet classifier reviews each action (0.4% false positives on real traffic; 17% FNR on real overeager actions; 5.7% FNR on synthetic exfiltration) — a middle path between prompts and full sandboxing.
- **pi's stance** is the clean opposite pole: permission prompts are "security theater" once an agent can write and execute code; the honest boundary is the OS — run in a container, restrict network (https://mariozechner.at/posts/2025-11-30-pi-coding-agent/). Note convergence: Anthropic's sandboxing post effectively concedes the point (real boundaries beat prompts), while keeping prompts for un-sandboxed environments.
- Managed/hosted agents put approvals at the API level: e.g., Anthropic Managed Agents `permission_policy: always_ask` emits a tool-confirmation event the client must answer (https://platform.claude.com/docs/en/managed-agents/overview); OpenAI's guide frames the same as tool-risk ratings + HITL thresholds.

### Session persistence & resumability
- Claude Agent SDK: sessions persisted as JSONL, `resume=session_id`, session **forking** to explore alternatives; checkpointing in Claude Code (`/rewind` restores conversation and/or file state; every prompt is a checkpoint) (https://code.claude.com/docs/en/agent-sdk/overview, https://code.claude.com/docs/en/best-practices).
- LangGraph makes **durable execution + checkpoints** its core selling point (resume after failure, time travel) (https://docs.langchain.com/oss/python/langgraph/overview); PydanticAI outsources durability to Temporal/DBOS; 12-Factor factors 5–6 and 12 (state unification, pause/resume APIs, stateless reducer) are the framework-free formulation. Anthropic's research system found resumability essential because long-running agents can't afford restart-from-scratch on transient errors.

### Steering & interruptibility
- Claude Code: `Esc` interrupts mid-action with context preserved; double-Esc/`/rewind` for restore-or-summarize; "course-correct early and often"; queued messages; `/clear` between tasks (https://code.claude.com/docs/en/best-practices).
- Hosted APIs expose interruption as an event (`user.interrupt` jumps the queue, agent halts at a safe boundary) (https://platform.claude.com/docs/en/managed-agents/overview). Anthropic's research post flags synchronous subagent execution as a bottleneck precisely because it prevents mid-run steering. For a minimal harness, interruptibility (SIGINT-safe loop, resumable transcript) is one of the few "real" features the loop itself must support.

---

## 5. Application Scenarios Beyond Coding

State of adoption: 57.3% of surveyed teams have agents in production (LangChain State of Agent Engineering, https://www.langchain.com/state-of-agent-engineering); customer service is the top use case (26.5%) with research & data analysis second (24.4%). Anthropic's Agent SDK launch post explicitly lists non-coding targets: finance agents, personal assistants, customer support, deep research (https://claude.com/blog/building-agents-with-the-claude-agent-sdk, Sep 29, 2025).

- **Customer support** — *Examples*: Intercom **Fin** (7,000+ businesses, >1M conversations/week, ~71% average resolution rate, ~$0.99/resolution — https://fin.ai/learn/ai-agents-in-customer-service); **Sierra** (Bret Taylor's company; ISO 42001, in-conversation payments — https://sierra.ai/). *Harness stress*: guardrails/policy adherence, HITL escalation, per-resolution economics, session state across channels — routing + guardrail workflow patterns more than open-ended loops.
- **Deep research** — *Examples*: OpenAI **Deep Research** (launched Feb 2, 2025 — https://openai.com/index/introducing-deep-research/); Anthropic's Claude Research feature built on the multi-agent orchestrator-worker system (https://www.anthropic.com/engineering/multi-agent-research-system). *Harness stress*: parallel sub-agents, isolated context windows, citation post-processing, token budgeting (~15x chat), end-state evals.
- **Computer use** — *Examples*: Anthropic computer use API (public beta Oct 22, 2024, Claude 3.5 Sonnet — https://simonwillison.net/2024/Oct/22/computer-use/); OpenAI **Operator** (Jan 23, 2025 — https://techcrunch.com/2025/01/23/openai-launches-operator-an-ai-agent-that-performs-tasks-autonomously/). *Harness stress*: screenshot-in/action-out loops, latency, sandboxed VMs, human takeover for credentials/payments.
- **Data analysis** — *Examples*: code-execution-sandbox agents (Anthropic code execution tool + skills producing xlsx/docx artifacts — https://platform.claude.com/docs); Manus as a general autonomous task agent whose engineering lessons (file-system-as-memory) came from data-heavy tasks (https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus). *Harness stress*: sandboxed code execution, file I/O, artifact hand-back, container/state reuse.
- **DevOps / SRE automation** — *Examples*: **Azure SRE Agent** (correlates telemetry, tests hypotheses, explains root cause — https://azure.microsoft.com/en-us/products/sre-agent); Anthropic's SRE incident-responder cookbook on Managed Agents (https://platform.claude.com/cookbook/managed-agents-sre-incident-responder); incident.io / PagerDuty AI SRE agents (https://incident.io/blog/ai-sre-agent-definition). *Harness stress*: read-mostly tool permissions with hard gates on mutating actions, observability-tool integration (MCP fits well), escalation to humans, audit trails — the domain where permission systems earn their keep, in contrast to pi's trusted-workstation context.

---

### Cross-cutting takeaways for a pi-vs-tau learning doc
1. Everyone's loop is the same ~10 lines (Ball, sketch.dev, Anthropic); harnesses differ in what they add *around* it: context management, tools, permissions, sessions, evals.
2. The 2025 consensus moved from "orchestration frameworks" to "context engineering + thin harnesses you own" — 12-Factor, Manus, Anthropic's context post, and pi all argue variants of "own your context window."
3. The genuine open design axes for a minimal harness: (a) permissions vs containers (pi: containers; Claude Code: layered prompts→sandbox→classifier); (b) built-in vs file-based state (todo lists, plans, memory); (c) MCP in-core vs external; (d) sub-agents as feature vs "just spawn another process"; (e) KV-cache discipline as a first-class constraint.
4. Benchmarks (Terminal-Bench 2.0) currently support the claim that a <1,000-token harness is competitive with 10k+-token harnesses on frontier models — the strongest empirical argument the minimal side has.

*Sources fetched July 2026; all URLs verified live at fetch time. Anthropic engineering URLs (anthropic.com/engineering/*) now 308-redirect to claude.com/blog/* and code.claude.com/docs/* — both forms resolve.*
