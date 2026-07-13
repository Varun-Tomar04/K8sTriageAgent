"""
Dispatch tool call names to kubectl.py functions.
execute_tool(name, args, context) -> str
"""
from typing import Optional

from tools import kubectl


def execute_tool(name: str, args: dict, context: Optional[str] = None) -> str:
    """
    Dispatch a tool call by name to the appropriate kubectl function.
    Returns the string output to feed back to the LLM.
    """
    try:
        match name:
            case "list_pods":
                return kubectl.list_pods(
                    namespace=args["namespace"],
                    selector=args.get("selector"),
                    context=context,
                )
            case "describe_pod":
                return kubectl.describe_pod(
                    name=args["name"],
                    namespace=args["namespace"],
                    context=context,
                )
            case "get_pod_logs":
                return kubectl.get_pod_logs(
                    name=args["name"],
                    namespace=args["namespace"],
                    previous=args.get("previous", False),
                    tail=args.get("tail", 100),
                    context=context,
                )
            case "get_events":
                return kubectl.get_events(
                    namespace=args["namespace"],
                    since=args.get("since", "1h"),
                    context=context,
                )
            case "get_deployment":
                return kubectl.get_deployment(
                    name=args["name"],
                    namespace=args["namespace"],
                    context=context,
                )
            case "get_service":
                return kubectl.get_service(
                    name=args["name"],
                    namespace=args["namespace"],
                    context=context,
                )
            case "get_node":
                return kubectl.get_node(
                    name=args["name"],
                    context=context,
                )
            case "get_configmap":
                return kubectl.get_configmap(
                    name=args["name"],
                    namespace=args["namespace"],
                    context=context,
                )
            case "top_pods":
                return kubectl.top_pods(
                    namespace=args["namespace"],
                    context=context,
                )
            case "top_nodes":
                return kubectl.top_nodes(context=context)
            case "get_replicaset":
                return kubectl.get_replicaset(
                    name=args["name"],
                    namespace=args["namespace"],
                    context=context,
                )
            case "get_resource_quota":
                return kubectl.get_resource_quota(
                    namespace=args["namespace"],
                    context=context,
                )
            case _:
                return f"ERROR: Unknown tool '{name}'"

    except kubectl.KubectlSafetyError as e:
        return f"SAFETY_BLOCK: {e}"
    except kubectl.KubectlTimeoutError as e:
        return f"TIMEOUT: {e}"
    except kubectl.KubectlError as e:
        return f"KUBECTL_ERROR: {e}"
    except KeyError as e:
        return f"MISSING_ARGUMENT: required argument {e} not provided"
