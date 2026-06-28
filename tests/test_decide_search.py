"""Unit tests for ResearchEngine._decide_call — the web_search-enabled decision
call. web_search is a server-side tool, so we mock the Anthropic client and
assert the right tool_choice / pause_turn / forced-fallback behaviour without
ever hitting the network."""
from aiportfolio.research.engine import ResearchEngine


class Block:
    def __init__(self, type, name=None, input=None, id="b1"):
        self.type, self.name, self.input, self.id = type, name, input, id


class Resp:
    def __init__(self, content, stop_reason="end_turn"):
        self.content, self.stop_reason = content, stop_reason


class FakeMessages:
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.scripted.pop(0)


class FakeClient:
    def __init__(self, scripted):
        self.messages = FakeMessages(scripted)


def _engine(scripted):
    eng = object.__new__(ResearchEngine)
    eng.client = FakeClient(scripted)
    eng.decision_model = "claude-sonnet-4-6"
    eng.max_tokens = 1000
    eng.temperature = 0.4
    return eng


DECISION = {"market_view": "ok", "decisions": []}


def test_search_then_submit_one_call():
    """Claude searches (server-side) and submits in the same response → 1 call,
    and that call must NOT force tool_choice (forcing would skip the search)."""
    resp = Resp([
        Block("server_tool_use", name="web_search"),
        Block("web_search_tool_result"),
        Block("tool_use", name="submit_decisions", input=DECISION),
    ], stop_reason="tool_use")
    eng = _engine([resp])
    out = eng._decide_call("sys", "msg")
    assert out == DECISION
    assert len(eng.client.messages.calls) == 1
    assert "tool_choice" not in eng.client.messages.calls[0]  # auto, lets it search


def test_pause_turn_resumes_without_extra_user_msg():
    """On pause_turn we resend to resume the server loop, with NO injected user
    message (would break the resume)."""
    first = Resp([Block("server_tool_use", name="web_search")], stop_reason="pause_turn")
    second = Resp([Block("tool_use", name="submit_decisions", input=DECISION)],
                  stop_reason="tool_use")
    eng = _engine([first, second])
    out = eng._decide_call("sys", "msg")
    assert out == DECISION
    assert len(eng.client.messages.calls) == 2
    # 2nd call's last message is the assistant turn, not a user nudge.
    assert eng.client.messages.calls[1]["messages"][-1]["role"] == "assistant"
    assert "tool_choice" not in eng.client.messages.calls[1]


def test_prose_then_forced_extraction():
    """Claude ends on prose without the tool → a 2nd, forced call extracts it."""
    first = Resp([Block("text")], stop_reason="end_turn")
    forced = Resp([Block("tool_use", name="submit_decisions", input=DECISION)],
                  stop_reason="tool_use")
    eng = _engine([first, forced])
    out = eng._decide_call("sys", "msg")
    assert out == DECISION
    assert len(eng.client.messages.calls) == 2
    forced_call = eng.client.messages.calls[1]
    assert forced_call["tool_choice"] == {"type": "tool", "name": "submit_decisions"}
    # A user nudge was appended before forcing.
    assert forced_call["messages"][-1]["role"] == "user"


def test_returns_none_when_never_submits():
    """If even the forced call won't produce the tool, return None (caller raises)."""
    first = Resp([Block("text")], stop_reason="end_turn")
    forced = Resp([Block("text")], stop_reason="end_turn")
    eng = _engine([first, forced])
    assert eng._decide_call("sys", "msg") is None
