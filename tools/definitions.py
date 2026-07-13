"""
Tool schemas for both Claude (tool_use API) and Gemini (functionDeclarations).
Both providers share the same 12 tools; only the schema envelope differs.
"""

# ── Shared tool specs (provider-agnostic) ─────────────────────────────────

_TOOLS = [
    {
        "name": "list_pods",
        "description": (
            "List all pods in a namespace with their status, restarts, node, and IP. "
            "Use this first to get an overview of pod health and find unhealthy pods."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace to list pods in.",
                },
                "selector": {
                    "type": "string",
                    "description": "Optional label selector (e.g. 'app=nginx') to filter pods.",
                },
            },
            "required": ["namespace"],
        },
    },
    {
        "name": "describe_pod",
        "description": (
            "Get detailed description of a pod: status, conditions, container states, "
            "resource requests/limits, volume mounts, and recent events. "
            "Essential for diagnosing CrashLoopBackOff, OOMKilled, Pending, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Pod name."},
                "namespace": {"type": "string", "description": "Namespace the pod is in."},
            },
            "required": ["name", "namespace"],
        },
    },
    {
        "name": "get_pod_logs",
        "description": (
            "Fetch container logs for a pod. Set previous=true to get logs from the "
            "last crashed container instance (critical for CrashLoopBackOff diagnosis)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Pod name."},
                "namespace": {"type": "string", "description": "Namespace."},
                "previous": {
                    "type": "boolean",
                    "description": "If true, fetch logs from the previous (crashed) container instance.",
                },
                "tail": {
                    "type": "integer",
                    "description": "Number of log lines to return from the end. Default 100.",
                },
            },
            "required": ["name", "namespace"],
        },
    },
    {
        "name": "get_events",
        "description": (
            "List Kubernetes events for a namespace sorted by timestamp. "
            "Events reveal scheduler failures, image pull errors, OOM kills, "
            "liveness probe failures, and more. Always check events early."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace to get events for."},
                "since": {
                    "type": "string",
                    "description": "Time window (e.g. '1h', '30m'). Default '1h'.",
                },
            },
            "required": ["namespace"],
        },
    },
    {
        "name": "get_deployment",
        "description": (
            "Describe a deployment: replica counts, strategy, selector, pod template spec, "
            "and rollout conditions. Use to diagnose replica mismatches or stuck rollouts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Deployment name."},
                "namespace": {"type": "string", "description": "Namespace."},
            },
            "required": ["name", "namespace"],
        },
    },
    {
        "name": "get_service",
        "description": (
            "Describe a Kubernetes Service: type, selector, endpoints, ports. "
            "Use to diagnose selector mismatches (service has no endpoints) "
            "or connectivity issues."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Service name."},
                "namespace": {"type": "string", "description": "Namespace."},
            },
            "required": ["name", "namespace"],
        },
    },
    {
        "name": "get_node",
        "description": (
            "Describe a node: conditions (Ready, MemoryPressure, DiskPressure), "
            "capacity, allocatable resources, and running pods. "
            "Use to diagnose NotReady nodes or resource pressure."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Node name."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_configmap",
        "description": (
            "Retrieve a ConfigMap's contents as YAML. "
            "Use to verify config values when a pod fails due to missing or invalid config."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "ConfigMap name."},
                "namespace": {"type": "string", "description": "Namespace."},
            },
            "required": ["name", "namespace"],
        },
    },
    {
        "name": "top_pods",
        "description": (
            "Show real-time CPU and memory usage for pods in a namespace. "
            "Requires metrics-server. Use to confirm OOM pressure or CPU throttling."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace."},
            },
            "required": ["namespace"],
        },
    },
    {
        "name": "top_nodes",
        "description": (
            "Show real-time CPU and memory usage for all nodes. "
            "Requires metrics-server. Use to identify nodes under resource pressure."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_replicaset",
        "description": (
            "Describe a ReplicaSet: desired/current/ready replicas, owner reference, "
            "pod template. Use to diagnose stuck deployments or replica set issues."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "ReplicaSet name."},
                "namespace": {"type": "string", "description": "Namespace."},
            },
            "required": ["name", "namespace"],
        },
    },
    {
        "name": "get_resource_quota",
        "description": (
            "List resource quotas for a namespace: CPU, memory, pod count limits. "
            "Use to diagnose pods stuck in Pending due to quota exhaustion."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace."},
            },
            "required": ["namespace"],
        },
    },
]


# ── Claude tool_use format ─────────────────────────────────────────────────

CLAUDE_TOOLS = [
    {
        "name": t["name"],
        "description": t["description"],
        "input_schema": t["parameters"],
    }
    for t in _TOOLS
]


# ── Gemini functionDeclarations format ────────────────────────────────────

GEMINI_TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            }
            for t in _TOOLS
        ]
    }
]
