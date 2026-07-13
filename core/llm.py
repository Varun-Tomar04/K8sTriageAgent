"""
LLM provider abstraction for Claude and Gemini.
Both providers implement native tool-use (not regex ReAct).

Claude:  Anthropic Messages API with tools parameter
Gemini:  Google Generative Language API with generate_content (full conversation)

Each call() takes the full message history and returns a LLMResponse with
tool_calls OR final_text. The orchestrator drives the loop; llm.py handles
a single API round-trip.
"""
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import anthropic

from tools.definitions import CLAUDE_TOOLS, GEMINI_TOOLS


CLAUDE_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-2.5-flash-lite"


# ── Shared data structures ─────────────────────────────────────────────────

@dataclass
class ToolCall:
    id: str          # tool_use_id (Claude) or synthetic id for Gemini
    name: str
    args: dict


@dataclass
class LLMResponse:
    tool_calls: list[ToolCall] = field(default_factory=list)
    final_text: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


# ── Claude provider ────────────────────────────────────────────────────────

class ClaudeProvider:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. "
                "Export it or add it to .env"
            )
        self.client = anthropic.Anthropic(api_key=key)

    def call(
        self,
        messages: list[dict],
        system: str,
        stream_cb: Optional[Callable] = None,
    ) -> LLMResponse:
        """Single API round-trip. Returns tool calls OR final text."""
        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=system,
            tools=CLAUDE_TOOLS,
            messages=messages,
            tool_choice={"type": "auto"},
        )

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        if response.stop_reason == "tool_use":
            tool_calls = []
            for block in response.content:
                if block.type == "tool_use":
                    tc = ToolCall(id=block.id, name=block.name, args=block.input)
                    tool_calls.append(tc)
            return LLMResponse(
                tool_calls=tool_calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        # Final text response
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        return LLMResponse(
            final_text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def append_assistant_turn(
        self,
        messages: list[dict],
        tool_calls: list[ToolCall],
    ) -> list[dict]:
        """Append the assistant's tool_use content block (required before tool_result)."""
        content = [
            {
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.args,
            }
            for tc in tool_calls
        ]
        return messages + [{"role": "assistant", "content": content}]

    def append_tool_results(
        self,
        messages: list[dict],
        tool_calls: list[ToolCall],
        results: list[str],
    ) -> list[dict]:
        """Append tool_result content blocks as a user message."""
        tool_result_content = [
            {
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result,
            }
            for tc, result in zip(tool_calls, results)
        ]
        return messages + [{"role": "user", "content": tool_result_content}]


# ── Gemini provider ────────────────────────────────────────────────────────

class GeminiProvider:
    """
    Uses generate_content() with the full conversation history on each call.
    This is the correct pattern for multi-turn function calling with Gemini —
    it avoids ChatSession state management issues across tool-use iterations.
    """

    def __init__(self, api_key: Optional[str] = None):
        import warnings
        with warnings.catch_warnings():
            # google-generativeai emits a FutureWarning about the newer
            # google-genai SDK on every import. The pinned package works fine;
            # SDK migration is tracked as a v2 item.
            warnings.simplefilter("ignore", FutureWarning)
            import google.generativeai as genai
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY not set. "
                "Get a free key at https://aistudio.google.com/apikey"
            )
        genai.configure(api_key=key)
        self._genai = genai

    def _build_tools(self):
        """Build genai Tool objects from our shared definitions."""
        genai = self._genai
        # Use the raw dict format that google-generativeai accepts
        return [
            genai.protos.Tool(
                function_declarations=[
                    genai.protos.FunctionDeclaration(
                        name=fd["name"],
                        description=fd["description"],
                        parameters=_dict_to_schema(fd["parameters"]),
                    )
                    for fd in GEMINI_TOOLS[0]["functionDeclarations"]
                ]
            )
        ]

    def call(
        self,
        messages: list[dict],
        system: str,
        stream_cb: Optional[Callable] = None,
    ) -> LLMResponse:
        """Single API round-trip using generate_content with full history."""
        genai = self._genai
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
        )

        contents = _messages_to_gemini_contents(messages, genai)

        response = model.generate_content(
            contents=contents,
            tools=self._build_tools(),
            tool_config=genai.protos.ToolConfig(
                function_calling_config=genai.protos.FunctionCallingConfig(
                    mode=genai.protos.FunctionCallingConfig.Mode.AUTO,
                )
            ),
            generation_config=genai.GenerationConfig(temperature=0.1),
        )

        candidate = response.candidates[0]
        tool_calls = []
        final_text = ""

        for part in candidate.content.parts:
            if part.function_call.name:
                fc = part.function_call
                tc = ToolCall(
                    id=f"{fc.name}_{len(tool_calls)}",
                    name=fc.name,
                    args=dict(fc.args),
                )
                tool_calls.append(tc)
            elif part.text:
                final_text += part.text

        # Token usage
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        if tool_calls:
            return LLMResponse(
                tool_calls=tool_calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        return LLMResponse(
            final_text=final_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def append_assistant_turn(
        self,
        messages: list[dict],
        tool_calls: list[ToolCall],
    ) -> list[dict]:
        # For Gemini, assistant turn is included in append_tool_results
        return messages

    def append_tool_results(
        self,
        messages: list[dict],
        tool_calls: list[ToolCall],
        results: list[str],
    ) -> list[dict]:
        """
        Append model function-call turn + user function-response turn.
        Gemini requires the model turn (with function_call parts) to appear
        before the user turn (with function_response parts).
        """
        new_messages = list(messages)

        # Model turn: what the model called
        model_parts = [
            {"type": "function_call", "name": tc.name, "args": tc.args}
            for tc in tool_calls
        ]
        new_messages.append({"role": "model", "content": model_parts})

        # User turn: function responses
        response_parts = [
            {
                "type": "function_response",
                "name": tc.name,
                "response": result,
            }
            for tc, result in zip(tool_calls, results)
        ]
        new_messages.append({"role": "user", "content": response_parts})

        return new_messages


# ── Gemini content conversion helpers ─────────────────────────────────────

def _messages_to_gemini_contents(messages: list[dict], genai) -> list:
    """
    Convert our internal message list to Gemini Content protos.

    Message format:
      {"role": "user",  "content": str | list[dict]}
      {"role": "model", "content": list[dict]}  (function call parts)
    """
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        content = msg["content"]

        if isinstance(content, str):
            contents.append(
                genai.protos.Content(
                    role=role,
                    parts=[genai.protos.Part(text=content)],
                )
            )
        elif isinstance(content, list):
            parts = []
            for item in content:
                if not isinstance(item, dict):
                    parts.append(genai.protos.Part(text=str(item)))
                    continue

                item_type = item.get("type", "")

                if item_type == "function_call":
                    # Model requested a tool call
                    parts.append(
                        genai.protos.Part(
                            function_call=genai.protos.FunctionCall(
                                name=item["name"],
                                args=item["args"],
                            )
                        )
                    )
                elif item_type == "function_response":
                    # User provided tool result
                    parts.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=item["name"],
                                response={"result": item["response"]},
                            )
                        )
                    )
                elif item_type == "tool_result":
                    # Claude-style (shouldn't appear in Gemini path, but handle gracefully)
                    parts.append(genai.protos.Part(text=str(item.get("content", ""))))
                else:
                    parts.append(genai.protos.Part(text=str(item)))

            if parts:
                contents.append(genai.protos.Content(role=role, parts=parts))

    return contents


def _dict_to_schema(params: dict):
    """Convert our JSON Schema dict to a Gemini Schema proto."""
    import google.generativeai as genai

    type_map = {
        "string": genai.protos.Type.STRING,
        "integer": genai.protos.Type.INTEGER,
        "number": genai.protos.Type.NUMBER,
        "boolean": genai.protos.Type.BOOLEAN,
        "array": genai.protos.Type.ARRAY,
        "object": genai.protos.Type.OBJECT,
    }

    def convert(schema: dict) -> genai.protos.Schema:
        t = type_map.get(schema.get("type", "string"), genai.protos.Type.STRING)
        kwargs: dict[str, Any] = {"type_": t}

        if "description" in schema:
            kwargs["description"] = schema["description"]
        if "properties" in schema:
            kwargs["properties"] = {
                k: convert(v) for k, v in schema["properties"].items()
            }
        if "required" in schema:
            kwargs["required"] = schema["required"]
        if "items" in schema:
            kwargs["items"] = convert(schema["items"])

        return genai.protos.Schema(**kwargs)

    return convert(params)


# ── Provider factory ───────────────────────────────────────────────────────

def get_provider(name: str) -> "ClaudeProvider | GeminiProvider":
    name = name.lower()
    if name == "claude":
        return ClaudeProvider()
    elif name == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(f"Unknown LLM provider '{name}'. Choose 'claude' or 'gemini'.")
