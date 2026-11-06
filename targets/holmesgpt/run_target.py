import argparse
import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from pydantic import ValidationError

from holmes_trace import HolmesResult, trajectory_from_holmes

DEFAULT_MODEL = "anthropic/claude-haiku-5-5"
HOST_TOOLSETS = (
    "bash",
    "connectivity_check",
    "docker/core",
    "internet",
    "kubernetes/kube-prometheus-stack",
    "skills",
)
TIMEOUT_EXIT_CODE = 124


def holmes_config(mcp_url: str) -> str:
    disabled = "".join(f"  {name}:\n    enabled: false\n" for name in HOST_TOOLSETS)
    return (
        "mcp_servers:\n"
        "  agent_drill:\n"
        '    description: "Support desk tools for the online store"\n'
        "    config:\n"
        f'      url: "{mcp_url}"\n'
        "      mode: streamable-http\n"
        f"toolsets:\n{disabled}"
    )


def agent_version(model: str, with_policy: bool, allow_repeated_calls: bool) -> str:
    variant = ("+policy" if with_policy else "") + ("+repeated-calls" if allow_repeated_calls else "")
    return f"{version('holmesgpt')}+{model.rsplit('/', 1)[-1]}{variant}"


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    workspace = args.trace.resolve().parent
    home = workspace / "holmes-home"
    home.mkdir(parents=True, exist_ok=True)
    config = workspace / "holmes-config.yaml"
    config.write_text(holmes_config(args.mcp_url))
    answer = workspace / "holmes.json"
    command = [
        str(Path(sys.executable).with_name("holmes")),
        "ask",
        args.prompt,
        "--model",
        args.model,
        "--config",
        str(config),
        "--no-interactive",
        "--max-steps",
        str(args.max_steps),
        "--json-output-file",
        str(answer),
    ]
    if args.policy_file is not None:
        command += ["--system-prompt-additions", args.policy_file.read_text()]
    environment = os.environ | {
        "HOME": str(home),
        "TEMPERATURE": "none",
        "ENABLED_BY_DEFAULT_TOOLSETS": "",
        "TOOL_CALL_SAFEGUARDS_ENABLED": "false" if args.allow_repeated_calls else "true",
    }
    try:
        holmes = subprocess.run(command, env=environment, timeout=args.timeout, check=False)
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"HolmesGPT exceeded {args.timeout:g} seconds\n")
        return TIMEOUT_EXIT_CODE
    if holmes.returncode != 0:
        return holmes.returncode
    try:
        result = HolmesResult.model_validate_json(answer.read_text())
    except (OSError, ValidationError) as exc:
        sys.stderr.write(f"Cannot read the HolmesGPT answer: {exc}\n")
        return 1
    identity = agent_version(args.model, args.policy_file is not None, args.allow_repeated_calls)
    trajectory = trajectory_from_holmes(result, identity, args.model)
    args.trace.write_text(trajectory.model_dump_json(indent=2, exclude_none=True) + "\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run HolmesGPT against a Drill MCP server and write its ATIF trace.",
    )
    parser.add_argument("--mcp-url", required=True, help="Drill MCP streamable HTTP URL")
    parser.add_argument("--prompt", required=True, help="task sent to HolmesGPT")
    parser.add_argument("--trace", type=Path, required=True, help="ATIF trajectory output path")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LiteLLM model name")
    parser.add_argument("--policy-file", type=Path, help="policy appended to the system prompt")
    parser.add_argument("--max-steps", type=int, default=25, help="HolmesGPT step limit")
    parser.add_argument("--timeout", type=float, default=540, help="HolmesGPT time limit in seconds")
    parser.add_argument(
        "--allow-repeated-calls",
        action="store_true",
        help="turn off HolmesGPT's safeguard against repeating an identical tool call",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
