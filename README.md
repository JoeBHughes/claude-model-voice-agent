# A voice agent that says where its answers come from

Watch the 72-second demo:

https://github.com/user-attachments/assets/fdc168d9-3691-4ad5-b6e7-3ae867da13cd

## What this is

A voice agent is a program you talk to out loud. It turns your speech into text, sends the text to an AI model, and reads the model's answer back in a synthetic voice. Voice agents are fast and easy to use. They also have a weakness: a spoken answer can't show its sources, so you have no link to click and nothing to check.

This project is a small voice agent that answers one kind of question: is a given Claude model current, retiring or retired, and what should you switch to? Every answer comes from a table of Anthropic's published retirement dates, and the agent says where the answer came from out loud. Ask "Is Sonnet 4.5 still available?" and it tells you the model retires on November 30, 2026, names the replacement, and credits Anthropic's deprecations page.

It runs on [LiveKit Agents](https://github.com/livekit/agents), an open-source framework for voice AI, and it starts from LiveKit's [Python starter project](https://github.com/livekit-examples/agent-starter-python).

Independent project by Joe Hughes. Neither Anthropic nor LiveKit has reviewed or endorsed this project.

## Who this is for

- Managers and non-technical readers can read this section, "What I found on the first run," and "What this agent doesn't cover." Together they show what a voice agent can and can't promise about accuracy.
- Developers can follow the setup steps below. They take about 30 minutes on Windows and use a free LiveKit Cloud account.

## How a conversation works

The rest of this guide is hands-on. Here is what happens when you ask a question:

1. A speech-to-text model on LiveKit Cloud turns your words into text.
2. The language model reads the text and decides whether it's a question about a Claude model.
3. If it is, the language model calls one of two lookup tools in `src/agent.py`. `check_claude_model` looks up one model. `list_retiring_models` lists the models with an upcoming retirement date.
4. The lookup tool reads `deprecations.json`, a dated copy of [Anthropic's model deprecations page](https://platform.claude.com/docs/about-claude/model-deprecations), and returns the status, the dates, the replacement and a one-line source.
5. The language model turns that result into one to three spoken sentences, including the source.
6. A text-to-speech model reads the answer aloud.

The lookup tool understands model names however speech-to-text writes them. "Opus 4.8," "Opus four point eight" and "Opus 48" all find the same model. It also handles the older naming order, so "Haiku 3.5" finds `claude-3-5-haiku-20241022`.

## Set up and run it on Windows

You need Windows PowerShell, a microphone and about 30 minutes. Mac and Linux users can follow the same steps with their own terminal.

### 1. Install uv

uv is the Python package manager the starter project uses. It also installs a recent Python for you. In PowerShell, run:

```
winget install --id=astral-sh.uv -e
```

Close PowerShell, open it again, and run `uv --version` to confirm it worked.

### 2. Create a free LiveKit Cloud account

1. Go to cloud.livekit.io and sign up.
2. When asked what you're building, choose **AI agents**. On the **Build your first agent** screen, click **Skip for now**.
3. On your project's **Overview** page, click **Manage API keys**.
4. Copy three values: the project URL (it starts with `wss://`), the API key and the API secret. Use the copy icons, so nothing gets cut off.

LiveKit Cloud runs the speech and language models through LiveKit Inference, so you don't need accounts with any other AI provider.

### 3. Download this project

On this repository's page, click the green **Code** button, then **Download ZIP**. Extract the ZIP to a folder you can find, such as your Desktop.

### 4. Install the project

In PowerShell, go to the project folder and install its packages:

```
cd "C:\path\to\your\project-folder"
uv sync
```

Replace the path with your own. The folder you want contains `pyproject.toml` and a `src` folder.

### 5. Add your LiveKit keys

```
copy .env.example .env.local
notepad .env.local
```

Paste your three values after the `=` signs, with no spaces or quotation marks:

```
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-key
LIVEKIT_API_SECRET=your-secret
```

Save with Ctrl+S and close Notepad. Never commit `.env.local` to GitHub. This repository's `.gitignore` already excludes it.

### 6. Download the helper models

```
uv run -m livekit.agents download-files
```

### 7. Talk to the agent

```
uv run python src/agent.py console
```

The agent greets you and offers to check a Claude model. Try these questions:

| Question | What a correct answer says |
|---|---|
| "Is Claude Sonnet 4.5 still available?" | It still works, retires on November 30, 2026, and the replacement is Sonnet 5.5 |
| "What about Opus 4.8?" | It's released and available, with no retirement scheduled |
| "What's retiring soon?" | Sonnet 4.5, on November 30, 2026 |
| "Is Claude Opus 6 out?" | It can't confirm that model, and suggests checking the deprecations page |

Press Ctrl+C to stop the agent.

### 8. Run the tests

The lookup tests check the lookup logic without a microphone or a LiveKit account:

```
uv run pytest tests/test_lookup.py
```

The grounding test asks the agent real questions in text mode, so it needs your LiveKit keys. It makes about 30 calls to the language model:

```
uv run python tests/grounding_eval.py
```

## What I found on the first run

I built this on a Windows 11 laptop in one evening, starting from LiveKit's starter project. These are the problems I hit, in order, and how I got past each one.

1. **Windows blocked the LiveKit command-line tool.** LiveKit's quickstart uses a tool called `lk`. After I installed it, running it returned "An Application Control policy has blocked this file." The fix was to skip the tool: I downloaded the starter as a ZIP and copied my keys from the LiveKit dashboard by hand. Steps 2 through 5 above are that workaround.
2. **My keys didn't save the first time.** The agent stopped with "api_key is required." The settings file was 50 bytes, the same size as the empty example, so Notepad hadn't saved my changes. Checking the file size in PowerShell (`Get-ChildItem -Force .env*`) found the problem in seconds.
3. **A mistyped key fails later and less clearly.** On the next run, every connection failed with "401 Unauthorized." The key and secret didn't match. A fresh key, copied with the copy icons, fixed it.
4. **Two commands in the starter's README are out of date.** `python src/agent.py download-files` still works but prints a notice that it was replaced in version 1.5.10 by `uv run -m livekit.agents download-files`. `console` mode prints a notice that it will move to `lk agent console`, which is the tool Windows blocked. Step 6 above uses the current command.
5. **The agent contradicted its own lookup.** The lookup returned "Opus 4.8 is active," and the agent still said Opus 4.8 "isn't released yet." I made two changes: the lookup now says "released and available now," and the agent's instructions say its training data is out of date and the lookup results are the only facts it has. A later test couldn't reproduce the original error, so the cause is less clear than it first looked. See "Did the fix hold?" below.
6. **Speech-to-text heard "four point eight" as "48."** The first lookup searched for a model called "Opus 48" and found nothing. The lookup now treats a two-digit number as a version, so "48" also finds 4.8.

The base agent handled the hard voice problems well from the start. It began answering in about two seconds, and it stopped talking and listened when I interrupted it.

## Did the fix hold?

After the demo, I tested whether the agent answers from its lookup or from its own training data. `tests/grounding_eval.py` asks the agent 10 questions in text mode, 3 times each. Four of the questions ask about models the table lists as released, including Opus 4.8 and Fable 5.2. An automated script scores each answer with fixed rules:

- Did the agent call the lookup tool?
- Did it cite Anthropic's deprecations page?
- Did it give the right date or replacement?
- For a released model, did it avoid words like "unreleased" or "doesn't exist"?

I ran the test on the current agent and on the version from before the change in item 5 above.

| Result | Current agent | Before the change |
|---|---|---|
| Correct answers | 30 of 30 | 18 of 30 |
| Called the lookup tool | 30 of 30 | 30 of 30 |
| Cited the deprecations page | 30 of 30 | 30 of 30 |
| Doubted a released model | 0 of 12 | 0 of 12 |
| Called a released model "released" or "available" | 12 of 12 | 0 of 12 |

The older version lost its 12 points on wording. It called every released model "active," a status label from the table that means little to a listener. The change fixed that.

The original error never came back. I also replayed the demo conversation (Sonnet 4.5, then Opus 4.8, then Opus 6) against the older version 10 times. It doubted Opus 4.8 in 0 of 10 replays. Across both tests, that's 0 of 22 tries.

My best guess is that the error came from the voice pipeline, not the language model alone. In a later voice session, LiveKit logged that speech-to-text delivered part of my question ("Opus 4.8?") after it had already closed my turn ("Thank you. What about"). An agent that starts answering before it hears the model name has nothing to look up. I haven't confirmed this. Testing it needs live voice sessions, and LiveKit's own suggestion is to wait longer before deciding the user has finished speaking.

I read every failing answer before trusting these numbers. One rule in my first version of the script flagged correct answers about Opus 6 ("I can't confirm if Claude Opus six is out"). I fixed the rule, and the table above uses the corrected scoring.

## What this agent doesn't cover

- **The table is a dated copy.** `deprecations.json` shows its date in the `as_of` field, and the agent says that date out loud. When Anthropic announces a change, someone has to update the file. It won't update on its own.
- **It covers Anthropic's own platform.** Amazon Bedrock and Google Cloud Vertex AI set their own retirement schedules. The agent says so if you ask.
- **It doesn't answer general questions.** Its instructions keep it on Claude model status. You can change that in the `instructions` text in `src/agent.py`.
- **It runs on your own computer.** This guide doesn't cover deploying the agent for other people to call.

## Files

| File | What it does |
|---|---|
| `src/agent.py` | The agent: its instructions, the two lookup tools and the voice pipeline |
| `deprecations.json` | A dated copy of Anthropic's model retirement table, shared with [model-id-check](https://github.com/JoeBHughes/model-id-check) |
| `tests/test_lookup.py` | Tests for the lookup logic |
| `tests/grounding_eval.py` | Asks the agent real questions in text mode and scores whether its answers come from the lookup |
| `.env.example` | The three settings the agent needs, without values |
| `pyproject.toml`, `uv.lock` | The package list from LiveKit's starter project |

## Credits and license

This project builds on LiveKit's [agent-starter-python](https://github.com/livekit-examples/agent-starter-python), which is released under the MIT License. The LICENSE file keeps LiveKit's copyright notice. My changes are released under the same license.
