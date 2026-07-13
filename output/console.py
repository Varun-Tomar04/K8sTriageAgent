"""
Rich ANSI console output with live streaming of tool events.
"""
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text
from rich import box

from core.llm import ToolCall
from core.prompts import DiagnosisResult

console = Console()

# Confidence level → color mapping
_CONFIDENCE_COLORS = {
    "high": "bold green",
    "medium": "bold yellow",
    "low": "bold red",
}

_CONFIDENCE_ICONS = {
    "high": "●",
    "medium": "◑",
    "low": "○",
}


def print_header(namespace: str, pod: str | None, provider: str) -> None:
    provider_badge = f"[cyan]{provider.upper()}[/cyan]"
    target = f"[bold white]{pod}[/bold white]" if pod else f"namespace [bold white]{namespace}[/bold white]"
    console.print()
    console.print(
        f"[bold blue]🔍 k8s-triage-agent[/bold blue]  {provider_badge}",
        highlight=False,
    )
    console.print(f"   Investigating {target} in namespace [dim]{namespace}[/dim]")
    console.print(Rule(style="dim"))


def print_tool_call(tc: ToolCall) -> None:
    args_str = ", ".join(f"{k}={v!r}" for k, v in tc.args.items())
    console.print(
        f"  [dim]→[/dim] [yellow]{tc.name}[/yellow]([dim]{args_str}[/dim])",
        highlight=False,
    )


def print_tool_result(tool_name: str, result: str) -> None:
    # Show a truncated preview of results (first 3 lines)
    lines = result.strip().splitlines()
    preview = "\n".join(lines[:3])
    if len(lines) > 3:
        preview += f"\n    [dim]… ({len(lines) - 3} more lines)[/dim]"
    console.print(f"    [dim]{preview}[/dim]", highlight=False)


def print_diagnosis(result: DiagnosisResult) -> None:
    console.print()
    console.print(Rule("[bold]DIAGNOSIS[/bold]", style="blue"))

    # Symptom
    console.print(f"[bold]Symptom:[/bold]    {result.symptom}")
    console.print()

    # Root cause
    console.print(f"[bold]Root Cause:[/bold] {result.root_cause}")
    console.print()

    # Evidence
    if result.evidence:
        console.print("[bold]Evidence:[/bold]")
        for item in result.evidence:
            console.print(f"  [green]•[/green] {item}", highlight=False)
        console.print()

    # Suggested fix
    console.print(Rule("[bold]SUGGESTED FIX[/bold]", style="green"))
    fix = result.suggested_fix
    if fix.command:
        console.print(Syntax(fix.command, "bash", theme="monokai", word_wrap=True))
    if fix.yaml_patch:
        console.print(Syntax(fix.yaml_patch, "yaml", theme="monokai", word_wrap=True))
    if fix.is_empty():
        console.print("[dim]No automated fix available — manual investigation recommended.[/dim]")
    console.print()

    # Confidence
    console.print(Rule("[bold]CONFIDENCE[/bold]", style="dim"))
    conf = result.confidence.lower()
    color = _CONFIDENCE_COLORS.get(conf, "white")
    icon = _CONFIDENCE_ICONS.get(conf, "?")
    console.print(
        f"  [{color}]{icon} {conf.upper()}[/{color}]  {result.confidence_reasoning}",
        highlight=False,
    )
    console.print()

    # Meta
    console.print(
        f"  [dim]Provider: {result.provider}  "
        f"Iterations: {result.iterations_used}  "
        f"Tokens: {result.tokens_used}[/dim]"
    )
    console.print()


def print_error(result: DiagnosisResult) -> None:
    console.print()
    console.print(
        Panel(
            f"[bold red]Investigation failed[/bold red]\n\n{result.error}",
            border_style="red",
            box=box.ROUNDED,
        )
    )


def stream_callback(event_type: str, data: Any) -> None:
    """
    Unified streaming callback passed to orchestrator.
    Called by orchestrator as tools fire and final answer arrives.
    """
    if event_type == "start":
        print_header(
            namespace=data["namespace"],
            pod=data.get("pod"),
            provider=data["provider"],
        )
    elif event_type == "tool_call":
        print_tool_call(data)
    elif event_type == "tool_result":
        print_tool_result(data["tool"], data["result"])
    elif event_type in ("final_text", "complete"):
        pass  # Handled by caller after run_investigation returns
