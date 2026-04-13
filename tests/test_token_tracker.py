"""Tests for token_tracker.py — TokenTracker and TokenUsage."""

import sys
from pathlib import Path as PP
sys.path.insert(0, str(PP(__file__).parent.parent))

from client.token_tracker import TokenTracker, TokenUsage


# ---------------------------------------------------------------------------
# TokenUsage dataclass
# ---------------------------------------------------------------------------

class TestTokenUsage:
    def test_defaults(self):
        u = TokenUsage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.total_tokens == 0
        assert u.cost_usd is None


# ---------------------------------------------------------------------------
# TokenTracker — parse_json_response
# ---------------------------------------------------------------------------

class TestTokenTrackerParseJsonResponse:
    def test_no_json_returns_raw(self):
        tt = TokenTracker()
        result, usage, is_limited = tt.parse_json_response("plain text output")
        assert result == "plain text output"
        assert usage is None
        assert is_limited is False

    def test_extracts_result_text(self):
        tt = TokenTracker()
        raw = '{"result": "Hello world", "usage": {"input_tokens": 100, "output_tokens": 200}}'
        result, usage, is_limited = tt.parse_json_response(raw)
        assert result == "Hello world"
        assert usage.total_tokens == 300

    def test_extracts_usage(self):
        tt = TokenTracker()
        raw = '{"result": "done", "usage": {"input_tokens": 50, "output_tokens": 150}}'
        _, usage, _ = tt.parse_json_response(raw)
        assert usage.input_tokens == 50
        assert usage.output_tokens == 150
        assert usage.total_tokens == 200

    def test_missing_usage_yields_none(self):
        tt = TokenTracker()
        raw = '{"result": "done"}'
        _, usage, _ = tt.parse_json_response(raw)
        assert usage is None

    def test_raises_429_detected(self):
        tt = TokenTracker()
        raw = '{"result": "rate limit exceeded", "error": "429"}'
        _, _, is_limited = tt.parse_json_response(raw)
        assert is_limited is True

    def test_invalid_json_returns_raw(self):
        tt = TokenTracker()
        raw = "not json at all {"
        result, usage, _ = tt.parse_json_response(raw)
        assert "not json at all" in result
        assert usage is None

    def test_strips_leading_trailing_whitespace(self):
        tt = TokenTracker()
        raw = '  \n{"result": "  trimmed  "}  \n'
        result, _, _ = tt.parse_json_response(raw)
        assert result == "  trimmed  "  # .strip() removes only leading/trailing


# ---------------------------------------------------------------------------
# TokenTracker — _detect_rate_limit
# ---------------------------------------------------------------------------

class TestTokenTrackerDetectRateLimit:
    def test_detects_429_string(self):
        tt = TokenTracker()
        assert tt._detect_rate_limit("Error 429") is True

    def test_detects_rate_limit_words(self):
        tt = TokenTracker()
        assert tt._detect_rate_limit("Rate limit exceeded") is True
        assert tt._detect_rate_limit("TOO MANY REQUESTS") is True
        assert tt._detect_rate_limit("rate_limit_exceeded") is True

    def test_detects_try_again_later(self):
        tt = TokenTracker()
        assert tt._detect_rate_limit("please try again later") is True
        assert tt._detect_rate_limit("retry after 60 seconds") is True
        assert tt._detect_rate_limit("quota exceeded") is True

    def test_returns_false_for_normal_output(self):
        tt = TokenTracker()
        assert tt._detect_rate_limit("Hello world, here is your result") is False


# ---------------------------------------------------------------------------
# TokenTracker — parse_streaming_output
# ---------------------------------------------------------------------------

class TestTokenTrackerParseStreamingOutput:
    def test_parses_usage_line(self):
        tt = TokenTracker()
        raw = '{"type": "usage", "usage": {"input_tokens": 10, "output_tokens": 20}}\n'
        result, usage, _ = tt.parse_streaming_output(raw)
        assert usage.total_tokens == 30
        assert usage.input_tokens == 10
        assert usage.output_tokens == 20

    def test_parses_content_line(self):
        tt = TokenTracker()
        raw = '{"type": "content", "content": "Hello there"}\n'
        result, _, _ = tt.parse_streaming_output(raw)
        assert "Hello there" in result

    def test_parses_content_list(self):
        tt = TokenTracker()
        raw = '{"type": "content", "content": [{"type": "text", "text": "part1"}, {"type": "text", "text": "part2"}]}\n'
        result, _, _ = tt.parse_streaming_output(raw)
        assert "part1" in result
        assert "part2" in result

    def test_accumulates_multiple_usage_lines(self):
        tt = TokenTracker()
        raw = ('{"type": "usage", "usage": {"input_tokens": 5, "output_tokens": 10}}\n'
               '{"type": "usage", "usage": {"input_tokens": 3, "output_tokens": 7}}\n')
        _, usage, _ = tt.parse_streaming_output(raw)
        assert usage.input_tokens == 8
        assert usage.output_tokens == 17

    def test_error_type_rate_limit_sets_flag(self):
        tt = TokenTracker()
        raw = '{"type": "error", "error": {"type": "rate_limit_error"}}\n'
        _, _, is_limited = tt.parse_streaming_output(raw)
        assert is_limited is True

    def test_non_json_line_appended_as_text(self):
        tt = TokenTracker()
        raw = 'just some plain text\n'
        result, _, _ = tt.parse_streaming_output(raw)
        assert "plain text" in result

    def test_empty_output(self):
        tt = TokenTracker()
        result, usage, _ = tt.parse_streaming_output("")
        assert result == ""
        assert usage is None


# ---------------------------------------------------------------------------
# TokenTracker — _estimate_cost
# ---------------------------------------------------------------------------

class TestTokenTrackerEstimateCost:
    def test_returns_cost_for_known_model(self):
        tt = TokenTracker(model="claude-sonnet-4-5")
        cost = tt._estimate_cost(1_000_000, 500_000, 500_000)
        # sonnet: input $3/M, output $15/M
        # 0.5M input * 3 + 0.5M output * 15 = 1.5 + 7.5 = 9.0
        assert cost == 9.0

    def test_returns_none_for_unknown_model(self):
        tt = TokenTracker(model="unknown-model")
        cost = tt._estimate_cost(1000, 500, 500)
        assert cost is None

    def test_rounds_to_6_decimals(self):
        tt = TokenTracker(model="claude-sonnet-4-5")
        # 1 input token at $3/M = 0.000003; output=0
        cost = tt._estimate_cost(1, 1, 0)
        assert cost == 3e-06

    def test_haiku_pricing(self):
        tt = TokenTracker(model="claude-haiku-4-5")
        # 1M tokens: input $0.8, output $4
        cost = tt._estimate_cost(1_000_000, 600_000, 400_000)
        # 0.6*0.8 + 0.4*4 = 0.48 + 1.6 = 2.08
        assert cost == 2.08


# ---------------------------------------------------------------------------
# TokenTracker — _build_usage
# ---------------------------------------------------------------------------

class TestTokenTrackerBuildUsage:
    def test_builds_usage_from_dict(self):
        tt = TokenTracker(model="claude-sonnet-4-5")
        usage_data = {"input_tokens": 1000, "output_tokens": 2000}
        usage = tt._build_usage(usage_data)
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 2000
        assert usage.total_tokens == 3000

    def test_returns_none_for_empty_dict(self):
        tt = TokenTracker()
        assert tt._build_usage({}) is None

    def test_returns_none_for_none(self):
        tt = TokenTracker()
        assert tt._build_usage(None) is None

    def test_returns_none_on_exception(self):
        tt = TokenTracker()
        # Pass invalid type that causes exception in .get
        assert tt._build_usage({"input_tokens": "not an int"}) is None


# ---------------------------------------------------------------------------
# TokenTracker — format_usage_report
# ---------------------------------------------------------------------------

class TestTokenTrackerFormatUsageReport:
    def test_format_contains_token_counts(self):
        tt = TokenTracker()
        usage = TokenUsage(input_tokens=1000, output_tokens=2000, total_tokens=3000)
        report = tt.format_usage_report(usage)
        assert "1,000" in report
        assert "2,000" in report
        assert "3,000" in report

    def test_format_contains_cost_when_present(self):
        tt = TokenTracker()
        usage = TokenUsage(input_tokens=1000, output_tokens=2000, total_tokens=3000, cost_usd=0.01)
        report = tt.format_usage_report(usage)
        assert "$" in report

    def test_format_omits_cost_when_none(self):
        tt = TokenTracker()
        usage = TokenUsage(input_tokens=100, output_tokens=100, total_tokens=200)
        report = tt.format_usage_report(usage)
        assert "cost" not in report.lower()
