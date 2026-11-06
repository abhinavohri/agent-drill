# Connect Agent Drill to Telegram through Switch

Switch starts an agent provider in this repository. Switch then sends Telegram room messages to the agent and sends the replies back to Telegram. Agent Drill does not need a Switch SDK or a Telegram dependency.

Official references:

- [Switch quickstart](https://docs.switchagents.ai/switch-rooms/getting-started)
- [Set up agent providers](https://docs.switchagents.ai/switch-rooms/getting-started/set-up-agent-providers)
- [Onboard agents](https://docs.switchagents.ai/switch-rooms/getting-started/onboard-your-agents)
- [Connect Telegram](https://docs.switchagents.ai/switch-rooms/deploy/messaging-apps/telegram)

## Requirements

- Install Switch Console.
- Install Codex, Claude Code, or another supported provider and sign in to it on the same computer.
- Add a username to your Telegram account.
- Create a Telegram group that can include the Switch bot.

## Add the project agent

1. Open Switch Console.
2. Start a Switch server on this computer.
3. Open **Settings**, then **Agent providers**.
4. Confirm that Codex shows **Signed in**.
5. Open **Your Agents** and add an agent.
6. Use these values:

   - Name: `agent-drill.dev`
   - Description: `Builds and explains Agent Drill.`
   - Run location: **This computer**
   - Directory: select the root of this repository.
   - Agent provider: select the provider installed on this computer.
   - Auto mode: on
   - Bypass permissions: off

7. Add these agent instructions:

```text
Work on Agent Drill from the repository root.
Read and follow AGENTS.md before you act.
Keep Telegram replies short.
Use lists instead of tables in Telegram.
Do not commit or push unless the user asks.
```

The repository rules stay in `AGENTS.md`. Do not copy those rules into the Switch instructions.

## Use different agent providers

The Telegram connection is shared. Each Switch agent uses one provider. Team members can create separate agents that use the same repository rules.

For example:

- `agent-drill.dev` can use Codex.
- `agent-drill.<member>` can use Claude Code.

Set the repository root as the directory for each agent. Invite each agent to the same Telegram room. Do not add provider-specific rules to `AGENTS.md`.

## Connect Telegram

1. Open `@BotFather` in Telegram.
2. Send `/newbot` and create a bot.
3. Store the bot token in a password manager.
4. Send `/mybots` to BotFather.
5. Select the new bot.
6. Open **Bot Settings**, then **Group Privacy**.
7. Turn off group privacy before you add the bot to a group.
8. Open the Switch server Home page.
9. Under **Messaging apps**, select **Connect**.
10. Select **Telegram**.
11. Enter a connection name, the bot token, and the bot username.
12. Select **Connect**.
13. Add the bot to the Telegram group.
14. Send one message in the group.
15. In Switch Console, select **Link my account** for the Telegram connection.
16. Select your Telegram username.

Do not add the bot token to this repository. Switch stores the connection data outside this project.

## Add the agent to the room

Send this command in the Telegram group:

```text
/invite_agent @agent-drill.dev
```

Then send a test request:

```text
agent-drill.dev summarize the current repository status.
```

The agent must reply with its name at the start of the Telegram message.

## Verify the connection

Confirm all of these results:

- The Telegram connection has no error in Switch Console.
- The Telegram group appears under **Your Rooms**.
- `/list_agents` shows `agent-drill.dev`.
- The test request gets a reply.
- Switch Console is open while the local agent works.

## Repair group privacy

If the bot sees only direct mentions, remove it from the group. Turn off group privacy in BotFather. Then add the bot to the group again.

Use a different bot token for each Switch deployment. Two processes that use one token can split incoming messages.
