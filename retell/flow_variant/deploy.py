"""Alternative build (not the submitted agent): Sara as a Retell Conversation Flow, from the files in
retell/flow_variant/ (config.yaml, flow.yaml, global_prompt.md). See README "Conversation Flow variant".

Usage (from the repo root):
    .venv/bin/python retell/flow_variant/deploy.py            # deploy and publish
    .venv/bin/python retell/flow_variant/deploy.py --dry-run  # print what would be sent, change nothing
    .venv/bin/python retell/flow_variant/deploy.py --no-publish  # update a draft only, e.g. to test it first

IDs are kept in retell/deployed.json so later runs update the same flow and agent.
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

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "retell" / "flow_variant"
CONFIG_PATH = HERE / "config.yaml"
FLOW_PATH = HERE / "flow.yaml"
PROMPT_PATH = HERE / "global_prompt.md"
STATE_PATH = HERE / "deployed.json"


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
    parser.add_argument("--no-publish", action="store_true", help="leave the change in an unpublished draft (for tests/simulate.py --version)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    config = fill_env(yaml.safe_load(CONFIG_PATH.read_text()))
    flow_nodes = yaml.safe_load(FLOW_PATH.read_text())
    prompt = PROMPT_PATH.read_text().strip()
    if not prompt:
        sys.exit(f"{PROMPT_PATH} is empty")

    flow_payload = {**config["flow"], "global_prompt": prompt,
                    "start_node_id": flow_nodes["start_node_id"], "nodes": flow_nodes["nodes"]}
    agent_payload = dict(config["agent"])
    state = load_state()

    if args.dry_run:
        print(json.dumps({"flow": flow_payload, "agent": agent_payload, "state": state}, indent=2))
        return

    if not os.environ.get("RETELL_API_KEY"):
        sys.exit("Missing RETELL_API_KEY in .env")
    client = Retell(api_key=os.environ["RETELL_API_KEY"])

    if not state.get("agent_id"):
        if state.get("conversation_flow_id"):
            client.conversation_flow.update(state["conversation_flow_id"], **flow_payload)
            print(f"Updated conversation flow {state['conversation_flow_id']}")
        else:
            state["conversation_flow_id"] = client.conversation_flow.create(**flow_payload).conversation_flow_id
            save_state(state)
            print(f"Created conversation flow {state['conversation_flow_id']}")
        agent_payload["response_engine"] = {"type": "conversation-flow", "conversation_flow_id": state["conversation_flow_id"]}
        agent = client.agent.create(**agent_payload)
        state["agent_id"] = agent.agent_id
        save_state(state)
        print(f"Created agent {agent.agent_id} (version {agent.version})")
    else:
        # A published version (and the flow version it points to) is read-only in Retell,
        # so every change goes into a draft: reuse the latest one or branch a new one.
        latest = client.agent.retrieve(state["agent_id"])
        draft = latest if not latest.is_published else client.agent.create_version(
            state["agent_id"], base_version=latest.version)
        engine = draft.response_engine
        flow_id, flow_version = engine.conversation_flow_id, int(engine.version)
        client.conversation_flow.update(flow_id, version=flow_version, **flow_payload)
        print(f"Updated conversation flow {flow_id} (draft version {flow_version})")
        state["conversation_flow_id"] = flow_id
        save_state(state)
        agent_payload["response_engine"] = {"type": "conversation-flow", "conversation_flow_id": flow_id, "version": flow_version}
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
