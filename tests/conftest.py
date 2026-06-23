from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 50
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class FakeTextBlock:
    type: str = "text"
    text: str = "Hello from Claude."


@dataclass
class FakeTokenCount:
    input_tokens: int = 100


@dataclass
class FakeMessage:
    content: list = None
    model: str = "claude-sonnet-4-6"
    usage: FakeUsage = None
    stop_reason: str = "end_turn"

    def __post_init__(self):
        if self.content is None:
            self.content = [FakeTextBlock()]
        if self.usage is None:
            self.usage = FakeUsage()


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.messages.count_tokens.return_value = FakeTokenCount(input_tokens=100)
    client.messages.create.return_value = FakeMessage()
    return client
