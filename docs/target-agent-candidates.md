# Target agent candidates

Status: Shortlist for review  
Date: 6 November 2026

## Selection criteria

Each candidate must be a focused domain agent. It must run its real agent logic and real tool loop. It must provide a repeatable test environment, useful evaluation cases, and observable results. A local or free model path is preferred. A permissive license is required for a public demo.

## Current shortlist

### 1. HelpPilot

- Repository: <https://github.com/poysa213/HelpPilot>
- Domain: E-commerce customer support and refunds
- License: MIT
- Models: Groq `gpt-oss-20b` for triage and `gpt-oss-120b` for solving and review
- Local state: SQLite stores customers, orders, tickets, logs, approvals, and LangGraph checkpoints
- Agent flow: Triage, solve, wait for approval, review, and respond
- Important behavior: A refund pauses for human approval. The run can resume after a process restart. The reviewer can return work to the solver two times.
- Evaluation set: 30 support tickets
- Evaluation checks: Answer correctness, grounding, escalation correctness, and the rule that no refund occurs without approval
- Published result: 86.7% correctness, 100% grounding, 100% escalation correctness, and 100% approval-rule compliance
- Traces: Optional LangSmith traces. Local logs and approval state are in SQLite.
- Setup: Python, Groq API key, local SQLite, and a local Chroma index
- Strength: It gives Agent Drill a complete stateful simulation with a customer, an agent, an approver, and a final database result.
- Risk: The repository has only three commits. The evaluation set is small.

### 2. AgentForge Healthcare

- Repository: <https://github.com/Jojobeans1981/langchain-healthcare-tools>
- Domain: Healthcare information, medication safety, appointments, insurance, and FDA recalls
- License: MIT
- Models: Groq Llama 3.3 70B with Gemini Flash fallback
- Local state: SQLite stores medication watchlists. All external data tools have local mock fallbacks.
- Tools: Nine tools cover drug interactions, symptoms, providers, appointments, insurance, medication data, watchlists, and recalls.
- Agent flow: A LangGraph ReAct agent can call five to seven tools for one clinical decision report. Five verification stages check its response.
- Evaluation set: 100 cases
- Evaluation groups: 24 happy paths, 13 edge cases, 36 adversarial cases, 11 multi-step cases, 12 recall cases, and 4 grounding cases
- Evaluation checks: Expected tools, expected response terms, safety behavior, and latency
- Traces: Append-only JSONL traces contain the request lifecycle, tool use, latency, errors, tokens, cost, and feedback. LangSmith is optional.
- Setup: Python and a free Groq or Gemini key. Docker and an external database are not required.
- Strength: It has the largest ready evaluation set in this shortlist. It also has 165 offline tests.
- Risk: Most tools only read data. The repository does not commit the `eval_results.json` file that its documentation names.

### 3. Commerce Support Agent

- Repository: <https://github.com/Pragatheswar-72/support-agent>
- Domain: E-commerce orders, refunds, payments, and support questions
- License: MIT
- Models: Gemini 2.5 Flash with Groq Llama 3.3 70B fallback
- Local state: SQLite stores orders, payments, and refunds.
- Agent flow: A LangGraph router sends a request to an order, refund, payment, or FAQ specialist. The specialists call tools that read and change the SQLite state.
- Important behavior: Refund tools enforce eligibility in code. The system retries a failed run once and then creates a human escalation ticket. Conversation memory supports follow-up requests.
- Evaluation set: 21 routing scenarios
- Evaluation checks: Intent routing accuracy
- Published result: 100% routing accuracy on the included scenarios
- Tests: 38 tests cover tools, refund rules, routing, memory, retry, escalation, API behavior, and a previous tool-loop bug.
- Traces: The API returns the selected agent and tool trace. Requests use structured JSON logs.
- Setup: Python, local SQLite, and a free Gemini key. Groq is an optional fallback.
- Strength: It has real local refund and payment state changes with a permissive license.
- Risk: Its evaluation harness checks routing only. Agent Drill must add end-to-end state and policy checks.

### 4. OpenAI Customer Service Agents Demo

- Repository: <https://github.com/openai/openai-cs-agents-demo>
- Domain: Airline customer service
- License: MIT
- Models: OpenAI models through the OpenAI Agents SDK
- Local state: The demo includes mock itineraries and flight data.
- Agents: Triage, flight information, booking and cancellation, seats and special services, FAQ, and refunds and compensation
- Important behavior: The agents can book, rebook, cancel, assign seats, add special-service seats, open compensation cases, and issue hotel or meal support.
- Evaluation set: No public evaluation set
- Traces: The Agents SDK can expose agent handoffs and tool calls. This repository does not publish a trace corpus.
- Setup: Python backend, web interface, and an OpenAI API key
- Strength: OpenAI maintains the repository. It has a clear domain, several state-changing operations, and a mature agent SDK.
- Risk: Agent Drill must create the scenarios, expected final states, and baseline traces. The included mock world has only a small number of itineraries.

## Current recommendation

Use HelpPilot for the first Agent Drill demo. It provides the best balance of local state, real tool actions, human approval, published evaluations, free model access, and a permissive license.

Keep AgentForge as the second option when evaluation volume is more important than state changes. Keep the Commerce Support Agent as a simple Gemini-based fallback. Use the OpenAI demo only if the team can create its missing evaluation set.

## Required validation before selection

Before the team selects a target, run these checks:

1. Install the candidate from a clean checkout.
2. Run its offline tests.
3. Run three evaluation cases with the real model.
4. Confirm that each run exposes tool inputs, tool outputs, and final state.
5. Confirm that Agent Drill can reset the state between runs.
6. Record the exact commit, model, data version, and environment configuration.
