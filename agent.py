#!/usr/bin/env python3
"""
k8s-triage-agent — AI-powered Kubernetes troubleshooting CLI.

Usage:
    python agent.py diagnose --namespace triage-demo
    python agent.py diagnose --pod crash-demo --namespace default --llm-provider claude
    python agent.py diagnose --namespace triage-demo --json
"""
import argparse
import os
import sys

# Load .env if present (before any imports that read env vars)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional — env vars can be set externally


def cmd_diagnose(args: argparse.Namespace) -> int:
    from core.orchestrator import run_investigation
    from output.console import stream_callback, print_diagnosis, print_error
    from output.json_out import print_json

    provider = args.llm_provider or os.environ.get("LLM_PROVIDER", "gemini")

    cb = None if args.json else stream_callback

    result = run_investigation(
        namespace=args.namespace,
        pod=args.pod,
        provider_name=provider,
        context=args.context,
        stream_cb=cb,
        max_iterations=args.max_iter,
        extra_context=args.context_hint or "",
    )

    if args.json:
        print_json(result)
        return 1 if result.is_error() else 0

    if result.is_error():
        print_error(result)
        return 1

    print_diagnosis(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="k8s-agent",
        description="AI-powered Kubernetes triage — point at a broken namespace and get a diagnosis.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    diag = sub.add_parser(
        "diagnose",
        help="Diagnose issues in a namespace or specific pod",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
Investigate a Kubernetes namespace or pod and return a root-cause diagnosis.

Examples:
  python agent.py diagnose --namespace triage-demo
  python agent.py diagnose --pod crash-demo --namespace default
  python agent.py diagnose --namespace triage-demo --llm-provider claude
  python agent.py diagnose --namespace triage-demo --json
        """,
    )

    diag.add_argument(
        "--namespace", "-n",
        required=True,
        help="Kubernetes namespace to investigate.",
    )
    diag.add_argument(
        "--pod", "-p",
        default=None,
        help="Specific pod to investigate. If omitted, agent discovers unhealthy pods.",
    )
    diag.add_argument(
        "--llm-provider",
        choices=["gemini", "claude"],
        default=None,
        help="LLM provider to use. Defaults to $LLM_PROVIDER env var or 'gemini'.",
    )
    diag.add_argument(
        "--context",
        default=None,
        help="kubeconfig context to use (e.g. minikube, kind-k8s-agent).",
    )
    diag.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output structured JSON instead of ANSI-colored display.",
    )
    diag.add_argument(
        "--max-iter",
        type=int,
        default=10,
        metavar="N",
        help="Maximum agent iterations (default: 10).",
    )
    diag.add_argument(
        "--context-hint",
        default=None,
        metavar="TEXT",
        help="Optional free-text hint for the agent (e.g. 'this broke after a deploy at 14:00').",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "diagnose":
        sys.exit(cmd_diagnose(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
