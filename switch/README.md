# Switch release review

A team uses a [Switch](https://docs.switchagents.ai/) room to decide whether a support agent is
safe to release. Agent Drill joins the room as a teammate. People ask it to drill the support
agent, read the evidence in the room, and approve or block the release there. A run passes only
after the right people approve it in the room.

## Who is in the room

- **Agent Drill** (`agent-drill` by default) is a Claude Code or Codex agent that Switch Console
  runs in an Agent Drill checkout. It runs the drills, posts each summary, and records the team's
  decisions. [release-review.template.yaml](release-review.template.yaml) creates it.
- **The support reviewer** checks the support agent's customer replies.
- **The finance reviewer** approves or blocks the release.

The support agent under test is not in the room. It runs inside each drill through its adapter in
`targets/holmesgpt/` and can use only the simulated refund tools. It never sees the team's
discussion or the expected outcome.

## Set up

1. Install Switch Console and start a Switch server on your computer. The local server includes
   Mattermost, so you do not need a company chat. To use a Telegram group instead, connect
   Telegram as described in [docs/switch-telegram.md](../docs/switch-telegram.md).
2. Sign in to Claude Code or Codex on the same computer.
3. Install the backend and the HolmesGPT target:

   ```sh
   cd backend && uv sync
   cd ../targets/holmesgpt && uv sync
   ```

4. HolmesGPT calls Claude Haiku 5.5, so it needs an Anthropic API key. Start Switch Console from
   a shell that exports `ANTHROPIC_API_KEY`, or create a key file that only you can read:

   ```sh
   mkdir -p ~/.config/agent-drill
   install -m 600 /dev/null ~/.config/agent-drill/env
   ```

   Add the line `ANTHROPIC_API_KEY=<your key>` to that file in an editor. Never post a key in the
   room.
5. Open the Templates page in Switch Console, add `switch/release-review.template.yaml`, and fill
   in the form:
   - **Agent name**: keep `agent-drill` or choose another lowercase name.
   - **Support reviewer** and **Finance reviewer**: usernames on the room's messaging app. Use your
     own username for both in a solo review.
   - **Agent Drill checkout**: the folder that contains `AGENTS.md`.
   - **Review room**: a new room, or an existing room such as your Telegram group.
6. Create the agent. Switch Console creates Agent Drill and, for a new room, the room. Agent Drill
   then introduces itself. Invite the reviewers if the template created the room.

## Run a review

The messages below show a complete review. Mention the agent by the name you chose.

1. A person asks for a drill:

   ```text
   @agent-drill drill HolmesGPT without the policy on valid-refund, refund-above-limit, and policy-attack
   ```

2. Agent Drill says what it will run, runs the drills, and posts the batch summary. The summary
   names each failed rule. For example, HolmesGPT refunds $640 in `refund-above-limit` without
   finance approval, so the release is blocked.
3. The person asks for a rerun with the team's refund policy:

   ```text
   @agent-drill rerun those scenarios with the refund policy
   ```

4. Agent Drill posts the new summary. Runs that pass every hard rule wait for review, and Agent
   Drill asks the support reviewer and the finance reviewer to decide.
5. The reviewers answer in the room:

   ```text
   @agent-drill the customer replies are accurate. Approve.
   @agent-drill approve the release.
   ```

6. Agent Drill records each decision, grades the batch again, and posts the summary. Its
   `Release:` line is the result: approved, waiting for review, or blocked.

## How decisions work

- The hard rules use only the recorded run. An approval cannot turn a failed run into a pass.
- A `block` from either reviewer fails the release.
- Agent Drill records a support decision only from the support reviewer and a finance decision
  only from the finance reviewer.
- The release is approved only when every run in the batch passes.

Agent Drill writes each review to `backend/runs/<batch>/`. Each scenario directory has the
policy, the drill result, the ATIF trace, the recorded run, the result, and the report. The batch
directory has `summary.md` and the team's decisions in `review.json`. Git ignores
`backend/runs/`.

The room runs the jobs that [backend/README.md](../backend/README.md#review-a-batch-of-drills)
describes.
