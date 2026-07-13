"""
Agent orchestration loop.
Drives the think → tool → observe cycle until:
  - LLM returns final text (diagnosis)
  - MAX_ITERATIONS reached
  - MAX_TOKENS_PER_SESSION exceeded
"""
import json
import re
from typing import Callable, Optional

from core.llm import get_provider, LLMResponse, ToolCall
from core.prompts import SYSTEM_PROMPT, DiagnosisResult, SuggestedFix
from tools.executors import execute_tool


MAX_ITERATIONS = 10
MAX_TOKENS_PER_SESSION = 50_000


def _repair_llm_json(text: str) -> str:
    """
    Fix the most common LLM-introduced JSON syntax errors.
    JSON does not allow `\\'` as an escape — only `\\"`, `\\\\`, `\\/`, `\\b`,
    `\\f`, `\\n`, `\\r`, `\\t`, `\\uXXXX`. LLMs often emit `\\'` when the
    underlying tool output contained single-quoted strings.
    """
    # Replace invalid \' with plain ' (the only escape JSON would actually need)
    return text.replace(r"\'", "'")


def _parse_diagnosis(text: str) -> DiagnosisResult:
    """
    Extract JSON diagnosis from LLM final response.
    The LLM is prompted to output only JSON, but may wrap it in markdown fences
    or emit invalid escape sequences. Try strict parse first, then a repaired pass.
    """
    # Strip markdown code fences if present
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Second chance: repair the most common LLM mistakes and retry
        try:
            data = json.loads(_repair_llm_json(cleaned))
        except json.JSONDecodeError:
            # LLM produced non-JSON — treat entire text as root_cause
            return DiagnosisResult(
                symptom="Unknown",
                root_cause=text.strip(),
                confidence="low",
                confidence_reasoning="LLM did not return structured JSON",
            )

    fix_data = data.get("suggested_fix", {})
    fix = SuggestedFix(
        command=fix_data.get("command"),
        yaml_patch=fix_data.get("yaml_patch"),
    )

    return DiagnosisResult(
        symptom=data.get("symptom", ""),
        root_cause=data.get("root_cause", ""),
        evidence=data.get("evidence", []),
        suggested_fix=fix,
        confidence=data.get("confidence", "low"),
        confidence_reasoning=data.get("confidence_reasoning", ""),
    )


def _build_problem_statement(
    namespace: str,
    pod: Optional[str] = None,
    extra_context: str = "",
) -> str:
    if pod:
        statement = f"Pod '{pod}' in namespace '{namespace}' appears to be failing. Investigate and diagnose the root cause."
    else:
        statement = f"There are issues in namespace '{namespace}'. Find unhealthy pods and diagnose the root cause."
    if extra_context:
        statement += f"\n\nAdditional context: {extra_context}"
    return statement


def run_investigation(
    namespace: str,
    pod: Optional[str] = None,
    provider_name: str = "gemini",
    context: Optional[str] = None,
    stream_cb: Optional[Callable] = None,
    max_iterations: int = MAX_ITERATIONS,
    extra_context: str = "",
) -> DiagnosisResult:
    """
    Run the full agent loop for a given pod/namespace.

    Args:
        namespace:       Kubernetes namespace to investigate
        pod:             Specific pod name (optional — agent discovers if omitted)
        provider_name:   'gemini' or 'claude'
        context:         kubeconfig context (optional)
        stream_cb:       callback(event_type: str, data: any) for live streaming
        max_iterations:  Override iteration cap
        extra_context:   Free-text added to the problem statement

    Returns:
        DiagnosisResult with diagnosis, evidence, and suggested fix
    """
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        # Missing/invalid API key or unknown provider — surface as a result,
        # not a traceback, consistent with everything else in this function.
        return DiagnosisResult(error=str(e), provider=provider_name)

    problem = _build_problem_statement(namespace, pod, extra_context)

    messages = [{"role": "user", "content": problem}]
    total_input_tokens = 0
    total_output_tokens = 0
    iterations = 0

    if stream_cb:
        stream_cb("start", {"namespace": namespace, "pod": pod, "provider": provider_name})

    for iteration in range(max_iterations):
        iterations = iteration + 1

        # Token guard
        if total_input_tokens + total_output_tokens > MAX_TOKENS_PER_SESSION:
            return DiagnosisResult(
                error=f"Token limit exceeded ({MAX_TOKENS_PER_SESSION} tokens). "
                      f"Investigation incomplete after {iterations} iterations.",
                iterations_used=iterations,
                tokens_used=total_input_tokens + total_output_tokens,
                provider=provider_name,
            )

        # Single LLM round-trip
        try:
            resp: LLMResponse = provider.call(
                messages=messages,
                system=SYSTEM_PROMPT,
                stream_cb=stream_cb,
            )
        except Exception as e:
            return DiagnosisResult(
                error=f"LLM call failed: {e}",
                iterations_used=iterations,
                tokens_used=total_input_tokens + total_output_tokens,
                provider=provider_name,
            )

        total_input_tokens += resp.input_tokens
        total_output_tokens += resp.output_tokens

        if resp.has_tool_calls:
            # Execute all tool calls and collect results
            results = []
            for tc in resp.tool_calls:
                if stream_cb:
                    stream_cb("tool_call", tc)
                result = execute_tool(tc.name, tc.args, context=context)
                if stream_cb:
                    stream_cb("tool_result", {"tool": tc.name, "result": result})
                results.append(result)

            # Append tool calls + results to message history
            # Claude requires assistant turn before tool_result
            if provider_name == "claude":
                messages = provider.append_assistant_turn(messages, resp.tool_calls)
            messages = provider.append_tool_results(messages, resp.tool_calls, results)

        else:
            # LLM returned final text — parse diagnosis
            final_text = resp.final_text or ""
            result = _parse_diagnosis(final_text)
            result.iterations_used = iterations
            result.tokens_used = total_input_tokens + total_output_tokens
            result.provider = provider_name

            if stream_cb:
                stream_cb("complete", result)

            return result

    # Exhausted iterations without a final answer
    return DiagnosisResult(
        error=f"Max iterations ({max_iterations}) reached without a conclusive diagnosis. "
              f"The issue may require manual investigation.",
        iterations_used=iterations,
        tokens_used=total_input_tokens + total_output_tokens,
        provider=provider_name,
    )
