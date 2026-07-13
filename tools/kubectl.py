"""
kubectl subprocess wrapper.
- shell=False for security (no injection)
- 30s timeout
- Read-only safety enforcement
- Respects KUBECONFIG env and --context/--kubeconfig flags
"""
import os
import subprocess
from typing import Optional


# Mutating kubectl subcommands — blocked at all times in v1
_BLOCKED_SUBCOMMANDS = {
    "apply", "delete", "patch", "edit", "exec", "cp",
    "create", "replace", "scale", "rollout", "label",
    "annotate", "taint", "cordon", "uncordon", "drain",
    "port-forward", "proxy", "attach", "run",
}

TOOL_TIMEOUT = 30  # seconds


class KubectlError(Exception):
    pass


class KubectlTimeoutError(KubectlError):
    pass


class KubectlSafetyError(KubectlError):
    pass


def _get_kubectl_base(context: Optional[str] = None, kubeconfig: Optional[str] = None) -> list[str]:
    cmd = ["kubectl"]
    kc = kubeconfig or os.environ.get("KUBECONFIG")
    if kc:
        cmd += ["--kubeconfig", kc]
    ctx = context or os.environ.get("KUBE_CONTEXT")
    if ctx:
        cmd += ["--context", ctx]
    return cmd


def run_kubectl(
    args: list[str],
    context: Optional[str] = None,
    kubeconfig: Optional[str] = None,
) -> dict:
    """
    Execute a kubectl command safely.

    Returns:
        {"success": bool, "output": str, "error": str}

    Raises:
        KubectlSafetyError: if a mutating subcommand is detected
        KubectlTimeoutError: if command exceeds TOOL_TIMEOUT
    """
    if not args:
        raise KubectlError("No arguments provided to kubectl")

    # Safety: block mutating subcommands
    subcommand = args[0].lower()
    if subcommand in _BLOCKED_SUBCOMMANDS:
        raise KubectlSafetyError(
            f"kubectl '{subcommand}' is blocked — agent uses read-only tools only"
        )

    cmd = _get_kubectl_base(context, kubeconfig) + args

    try:
        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT,
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        raise KubectlTimeoutError(
            f"kubectl command timed out after {TOOL_TIMEOUT}s: {' '.join(args)}"
        )
    except FileNotFoundError:
        raise KubectlError(
            "kubectl not found — ensure kubectl is installed and in PATH"
        )


def _fmt(result: dict) -> str:
    """Return output string, or error string if command failed."""
    if result["success"]:
        return result["output"] or "(no output)"
    err = result["error"] or result["output"] or "(no output)"
    return f"ERROR: {err}"


# ── Individual tool functions ──────────────────────────────────────────────

def describe_pod(name: str, namespace: str, context: Optional[str] = None) -> str:
    return _fmt(run_kubectl(["describe", "pod", name, "-n", namespace], context=context))


def get_pod_logs(
    name: str,
    namespace: str,
    previous: bool = False,
    tail: int = 100,
    context: Optional[str] = None,
) -> str:
    args = ["logs", name, "-n", namespace, f"--tail={tail}"]
    if previous:
        args.append("--previous")
    return _fmt(run_kubectl(args, context=context))


def get_events(namespace: str, since: str = "1h", context: Optional[str] = None) -> str:
    return _fmt(
        run_kubectl(
            ["get", "events", "-n", namespace, "--sort-by=.lastTimestamp"],
            context=context,
        )
    )


def get_deployment(name: str, namespace: str, context: Optional[str] = None) -> str:
    return _fmt(run_kubectl(["describe", "deployment", name, "-n", namespace], context=context))


def list_pods(
    namespace: str,
    selector: Optional[str] = None,
    context: Optional[str] = None,
) -> str:
    args = ["get", "pods", "-n", namespace, "-o", "wide"]
    if selector:
        args += ["-l", selector]
    return _fmt(run_kubectl(args, context=context))


def get_service(name: str, namespace: str, context: Optional[str] = None) -> str:
    return _fmt(run_kubectl(["describe", "svc", name, "-n", namespace], context=context))


def get_node(name: str, context: Optional[str] = None) -> str:
    return _fmt(run_kubectl(["describe", "node", name], context=context))


def get_configmap(name: str, namespace: str, context: Optional[str] = None) -> str:
    return _fmt(run_kubectl(["get", "cm", name, "-n", namespace, "-o", "yaml"], context=context))


def top_pods(namespace: str, context: Optional[str] = None) -> str:
    return _fmt(run_kubectl(["top", "pods", "-n", namespace], context=context))


def top_nodes(context: Optional[str] = None) -> str:
    return _fmt(run_kubectl(["top", "nodes"], context=context))


def get_replicaset(name: str, namespace: str, context: Optional[str] = None) -> str:
    return _fmt(run_kubectl(["describe", "rs", name, "-n", namespace], context=context))


def get_resource_quota(namespace: str, context: Optional[str] = None) -> str:
    return _fmt(run_kubectl(["get", "resourcequota", "-n", namespace], context=context))
