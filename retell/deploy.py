"""Create or update Sara's Retell LLM and agent from retell/config.yaml and prompt/agent_prompt.md, then publish.

Usage (from the repo root):
    .venv/bin/python retell/deploy.py               # deploy and publish
    .venv/bin/python retell/deploy.py --dry-run     # print what would be sent, change nothing
    .venv/bin/python retell/deploy.py --no-publish  # update a draft only, e.g. to test it with tests/simulate.py --version

IDs of the LLM and agent are kept in retell/deployed.json so later runs update them in place.
RETELL_API_KEY and N8N_DOMAIN come from .env.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from retell import Retell

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "retell" / "config.yaml"
PROMPT_PATH = ROOT / "prompt" / "agent_prompt.md"
STATE_PATH = ROOT / "retell" / "deployed.json"


def fill_env(value):
    """Replace ${VAR} placeholders with values from the environment, failing loudly if one is missing."""
    if isinstance(value, dict):
        return {k: fill_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [fill_env(v) for v in value]
    if isinstance(value, str):
        def lookup(match):
            name = match.group(1)
            if not os.environ.get(name):
                sys.exit(f"Missing {name} in .env")
            return os.environ[name]
        return re.sub(r"\$\{(\w+)\}", lookup, value)
    return value


def load_state():
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the payloads without calling Retell")
    parser.add_argument("--no-publish", action="store_true", help="leave the change in an unpublished draft")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    config = fill_env(yaml.safe_load(CONFIG_PATH.read_text()))
    prompt = PROMPT_PATH.read_text().strip()
    if not prompt:
        sys.exit(f"{PROMPT_PATH} is empty")

    llm_payload = {**config["llm"], "general_prompt": prompt}
    agent_payload = dict(config["agent"])
    state = load_state()

    if args.dry_run:
        print(json.dumps({"llm": llm_payload, "agent": agent_payload, "state": state}, indent=2))
        return

    if not os.environ.get("RETELL_API_KEY"):
        sys.exit("Missing RETELL_API_KEY in .env")
    client = Retell(api_key=os.environ["RETELL_API_KEY"])

    if not state.get("agent_id"):
        llm = client.llm.create(**llm_payload)
        state["llm_id"] = llm.llm_id
        save_state(state)
        print(f"Created LLM {llm.llm_id}")
        agent_payload["response_engine"] = {"type": "retell-llm", "llm_id": llm.llm_id}
        agent = client.agent.create(**agent_payload)
        state["agent_id"] = agent.agent_id
        save_state(state)
        print(f"Created agent {agent.agent_id} (version {agent.version})")
    else:
        # A published version (and the LLM version it points to) is read-only in Retell,
        # so every change goes into a draft: reuse the latest one or branch a new one.
        latest = client.agent.retrieve(state["agent_id"])
        draft = latest if not latest.is_published else client.agent.create_version(
            state["agent_id"], base_version=latest.version)
        llm_version = int(draft.response_engine.version)
        client.llm.update(state["llm_id"], version=llm_version, **llm_payload)
        print(f"Updated LLM {state['llm_id']} (draft version {llm_version})")
        agent_payload["response_engine"] = {"type": "retell-llm", "llm_id": state["llm_id"], "version": llm_version}
        agent = client.agent.update(state["agent_id"], version=draft.version, **agent_payload)
        print(f"Updated agent {agent.agent_id} (draft version {agent.version})")

    if args.no_publish:
        print(f"Left as unpublished draft version {agent.version}")
        return
    client.agent.publish(state["agent_id"], version=agent.version, version_title="deploy.py")
    state["published_version"] = agent.version
    save_state(state)
    print(f"Published agent version {agent.version}")


if __name__ == "__main__":
    main()
