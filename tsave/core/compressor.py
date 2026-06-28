"""Semantic compressor with relevance scoring for conversation history."""

from __future__ import annotations

from dataclasses import dataclass

import anthropic


@dataclass
class CompressedResult:
    original_messages: list[dict]
    compressed_messages: list[dict]
    original_tokens: int
    compressed_tokens: int

    @property
    def reduction_pct(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return (1 - self.compressed_tokens / self.original_tokens) * 100

    def format(self) -> str:
        return (
            f"Original:   {self.original_tokens:,} tokens ({len(self.original_messages)} messages)\n"
            f"Compressed: {self.compressed_tokens:,} tokens ({len(self.compressed_messages)} messages)\n"
            f"Reduction:  {self.reduction_pct:.1f}%"
        )


def _score_message_relevance(message: dict, query: str | None) -> float:
    content = message.get("content", "")
    if isinstance(content, list):
        content = " ".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    if not isinstance(content, str):
        return 1.0

    score = 0.5

    role = message.get("role", "")
    if role == "assistant":
        score += 0.1
    if role == "system":
        return 1.0

    has_tool_use = False
    raw_content = message.get("content", "")
    if isinstance(raw_content, list):
        for block in raw_content:
            if isinstance(block, dict) and block.get("type") in ("tool_use", "tool_result"):
                has_tool_use = True
                break
    if has_tool_use:
        score += 0.2

    if query:
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        overlap = len(query_words & content_words)
        if query_words:
            score += 0.3 * (overlap / len(query_words))

    return min(score, 1.0)


def _summarize_messages(
    client: anthropic.Anthropic,
    messages_to_summarize: list[dict],
    model: str,
) -> str:
    conversation_text = []
    for msg in messages_to_summarize:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        if isinstance(content, str) and content.strip():
            conversation_text.append(f"[{role}]: {content}")

    if not conversation_text:
        return ""

    joined = "\n".join(conversation_text)

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": (
                    "Compress this conversation into 2-3 sentences max. "
                    "Keep only facts, decisions, and key terms. No filler.\n\n"
                    f"{joined}"
                ),
            }],
        )
        return resp.content[0].text
    except Exception:
        return ""


def compress(
    client: anthropic.Anthropic,
    *,
    model: str,
    messages: list[dict],
    target_reduction: float = 0.5,
    query: str | None = None,
    keep_last_n: int = 4,
) -> CompressedResult:
    if len(messages) <= keep_last_n:
        tc = client.messages.count_tokens(model=model, messages=messages)
        return CompressedResult(
            original_messages=messages,
            compressed_messages=list(messages),
            original_tokens=tc.input_tokens,
            compressed_tokens=tc.input_tokens,
        )

    original_tc = client.messages.count_tokens(model=model, messages=messages)

    protected = messages[-keep_last_n:]
    candidates = messages[:-keep_last_n]

    if not candidates:
        compressed_tc = client.messages.count_tokens(model=model, messages=protected)
        return CompressedResult(
            original_messages=messages,
            compressed_messages=list(protected),
            original_tokens=original_tc.input_tokens,
            compressed_tokens=compressed_tc.input_tokens,
        )

    summary = _summarize_messages(client, candidates, model)

    compressed_messages = []
    if summary:
        compressed_messages.append({
            "role": "user",
            "content": f"[Prior context] {summary}",
        })
        compressed_messages.append({
            "role": "assistant",
            "content": "Understood.",
        })

    compressed_messages.extend(protected)

    if not compressed_messages:
        compressed_messages = list(protected)

    if compressed_messages and compressed_messages[0].get("role") != "user":
        compressed_messages.insert(0, {
            "role": "user",
            "content": "[Conversation continues from earlier context]",
        })

    final = []
    prev_role = None
    for msg in compressed_messages:
        role = msg.get("role")
        if role == prev_role and role in ("user", "assistant"):
            existing = final[-1].get("content", "")
            new_content = msg.get("content", "")
            if isinstance(existing, str) and isinstance(new_content, str):
                final[-1] = {**final[-1], "content": f"{existing}\n\n{new_content}"}
            else:
                final.append(msg)
        else:
            final.append(msg)
        prev_role = role

    compressed_tc = client.messages.count_tokens(model=model, messages=final)

    return CompressedResult(
        original_messages=messages,
        compressed_messages=final,
        original_tokens=original_tc.input_tokens,
        compressed_tokens=compressed_tc.input_tokens,
    )
