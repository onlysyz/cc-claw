"""Tests for retry.py - SmartRetry and CircuitBreaker."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.retry import (
    SmartRetry, RetryConfig, RetryStats, CircuitBreaker, CircuitState,
    RetryStrategy, MaxRetriesExceeded, CircuitBreakerOpen,
    RETRY_CONFIGS
)


class TestCircuitBreaker:
    """Test CircuitBreaker state transitions."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_opens_after_failure_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, timeout=0.1)

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.can_execute() is True

    def test_closes_after_success_threshold_in_half_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, success_threshold=2, timeout=0.05)

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, success_threshold=2, timeout=0.05)

        cb.record_failure()
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_record_success_decrements_failure_count_in_closed_state(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        assert cb._failure_count == 2

        cb.record_success()
        assert cb._failure_count == 1

    def test_get_status(self):
        cb = CircuitBreaker(name="my-cb", failure_threshold=5)
        status = cb.get_status()

        assert status["name"] == "my-cb"
        assert status["state"] == "closed"
        assert status["failures"] == 0


class TestSmartRetryDelayCalculation:
    """Test delay calculation for different strategies."""

    def setup_method(self):
        self.retry = SmartRetry()

    def test_immediate_returns_zero(self):
        config = RetryConfig(strategy=RetryStrategy.IMMEDIATE, base_delay=1.0)
        delay = self.retry.calculate_delay(attempt=0, config=config)
        assert delay == 0.0

    def test_linear_backoff(self):
        config = RetryConfig(strategy=RetryStrategy.LINEAR, base_delay=1.0)

        assert self.retry.calculate_delay(0, config) == 0.0
        assert self.retry.calculate_delay(1, config) == 1.0
        assert self.retry.calculate_delay(2, config) == 2.0
        assert self.retry.calculate_delay(3, config) == 3.0

    def test_exponential_backoff(self):
        config = RetryConfig(strategy=RetryStrategy.EXPONENTIAL, base_delay=1.0)

        assert self.retry.calculate_delay(0, config) == 1.0
        assert self.retry.calculate_delay(1, config) == 2.0
        assert self.retry.calculate_delay(2, config) == 4.0
        assert self.retry.calculate_delay(3, config) == 8.0

    def test_exponential_with_jitter(self):
        config = RetryConfig(strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER, base_delay=1.0)

        delays = [self.retry.calculate_delay(1, config) for _ in range(10)]
        for d in delays:
            assert 2.0 <= d < 4.0

    def test_fibonacci_backoff(self):
        config = RetryConfig(strategy=RetryStrategy.FIBONACCI, base_delay=1.0)

        # Fibonacci: 1, 1, 2, 3, 5, 8... (fib(n) where n=1→1, n=2→1, n=3→2, n=4→3, n=5→5)
        # calculate_delay uses fib(attempt + 1)
        assert self.retry.calculate_delay(0, config) == 1.0  # fib(1) = 1
        assert self.retry.calculate_delay(1, config) == 2.0  # fib(2) = 2
        assert self.retry.calculate_delay(2, config) == 3.0  # fib(3) = 2
        assert self.retry.calculate_delay(3, config) == 5.0  # fib(4) = 3
        assert self.retry.calculate_delay(4, config) == 8.0  # fib(5) = 5

    def test_max_delay_cap(self):
        config = RetryConfig(strategy=RetryStrategy.EXPONENTIAL, base_delay=10.0, max_delay=30.0)

        delay = self.retry.calculate_delay(5, config)
        assert delay == 30.0


class TestSmartRetryExecute:
    """Test SmartRetry.execute() behavior."""

    def setup_method(self):
        self.retry = SmartRetry()

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        async def success_func():
            return "success"

        result = await self.retry.execute("test-op", success_func)
        assert result == "success"

        stats = self.retry.get_stats("test-op")
        assert stats.attempts == 1
        assert stats.successes == 1
        assert stats.failures == 0

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self):
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError(f"Attempt {call_count}")
            return "success"

        config = RetryConfig(max_retries=3, base_delay=0.01)
        result = await self.retry.execute("flaky", flaky_func, config=config)

        assert result == "success"
        assert call_count == 3

        stats = self.retry.get_stats("flaky")
        assert stats.successes == 1
        assert stats.failures == 0

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        async def always_fail():
            raise ConnectionError("always fails")

        config = RetryConfig(max_retries=2, base_delay=0.01)

        with pytest.raises(MaxRetriesExceeded) as exc_info:
            await self.retry.execute("fail", always_fail, config=config)

        assert "fail" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        async def type_error_func():
            raise TypeError("not retryable")

        config = RetryConfig(
            max_retries=3,
            base_delay=0.01,
            retry_on=(ConnectionError,)
        )

        with pytest.raises(TypeError):
            await self.retry.execute("type-err", type_error_func, config=config)

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_when_open(self):
        async def failing_func():
            raise ConnectionError("fails")

        cb = self.retry.get_circuit_breaker("test-service")
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        config = RetryConfig(max_retries=1, base_delay=0.01)

        with pytest.raises(CircuitBreakerOpen):
            await self.retry.execute(
                "cb-test", failing_func,
                config=config,
                circuit_breaker_name="test-service"
            )

    @pytest.mark.asyncio
    async def test_timeout_enforced(self):
        async def slow_func():
            await asyncio.sleep(0.5)
            return "done"

        config = RetryConfig(timeout=0.1, base_delay=0.01, max_retries=2)

        with pytest.raises(asyncio.TimeoutError):
            await self.retry.execute("timeout-test", slow_func, config=config)


class TestRetryConfigs:
    """Test predefined retry configurations."""

    def test_network_config(self):
        cfg = RETRY_CONFIGS["network"]
        assert cfg.max_retries == 3
        assert cfg.strategy == RetryStrategy.EXPONENTIAL_WITH_JITTER
        assert ConnectionError in cfg.retry_on

    def test_api_config(self):
        cfg = RETRY_CONFIGS["api"]
        assert cfg.max_retries == 5
        assert cfg.max_delay == 60.0

    def test_claude_api_config(self):
        cfg = RETRY_CONFIGS["claude_api"]
        assert cfg.max_retries == 4
        assert cfg.base_delay == 5.0

    def test_fast_config(self):
        cfg = RETRY_CONFIGS["fast"]
        assert cfg.max_retries == 2
        assert cfg.max_delay == 1.0


class TestRetryStats:
    """Test RetryStats tracking."""

    def test_stats_initialization(self):
        stats = RetryStats()
        assert stats.attempts == 0
        assert stats.successes == 0
        assert stats.failures == 0
        assert stats.total_delay == 0.0
        assert stats.last_attempt is None
        assert stats.last_error is None
        assert stats.retry_history == []


class TestGetAllStats:
    """Test get_all_stats()."""

    def setup_method(self):
        self.retry = SmartRetry()

    def test_empty_stats(self):
        all_stats = self.retry.get_all_stats()
        assert "operations" in all_stats
        assert "circuit_breakers" in all_stats
        assert all_stats["operations"] == {}


class TestSmartRetryExecuteCircuitBreakerOnSuccess:
    """Test cb.record_success() is called on retry success (line 245)."""

    def setup_method(self):
        self.retry = SmartRetry()

    @pytest.mark.asyncio
    async def test_execute_calls_record_success_on_retry_success(self):
        """Line 245: cb.record_success() is called when a retried attempt succeeds.
        Put CB in HALF_OPEN state first so record_success() actually increments _success_count."""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError(f"Attempt {call_count}")
            return "done"

        # Inject a pre-configured CB (failure_threshold=1) so one failure opens it
        cb = CircuitBreaker(name="test-svc-half-open", failure_threshold=1, timeout=0.05)
        self.retry._circuit_breakers["test-svc-half-open"] = cb

        # Put CB into HALF_OPEN state: record failure, then wait for timeout
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        config = RetryConfig(max_retries=3, base_delay=0.01)
        result = await self.retry.execute(
            "cb-success-test", flaky_func,
            config=config,
            circuit_breaker_name="test-svc-half-open"
        )

        assert result == "done"
        # record_success was called once when the retry succeeded (HALF_OPEN → increments _success_count)
        assert cb._success_count >= 1


class TestCircuitBreakerOpenUnreachable:
    """Line 257: except CircuitBreakerOpen: raise is unreachable — CB is checked
    before the try block at line 218, not raised inside it."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_reraised_before_try_block(self):
        """CircuitBreakerOpen is raised at line 218 (before try), not caught inside it."""
        retry = SmartRetry()
        cb = retry.get_circuit_breaker("unreachable-cb")
        # Pre-open the circuit breaker so the check at line 218 fires first
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        async def dummy():
            return "ok"

        config = RetryConfig(max_retries=1, base_delay=0.01)
        with pytest.raises(CircuitBreakerOpen):
            await retry.execute("cb-open", dummy, config=config, circuit_breaker_name="unreachable-cb")


class TestGetRetryManagerSingleton:
    """Test get_retry_manager() singleton (lines 327-329)."""

    def test_singleton_returns_same_instance(self):
        from client.retry import get_retry_manager, SmartRetry, _retry_manager
        import client.retry as retry_module

        # Reset the global
        retry_module._retry_manager = None
        try:
            mgr1 = get_retry_manager()
            mgr2 = get_retry_manager()
            assert mgr1 is mgr2
            assert isinstance(mgr1, SmartRetry)
        finally:
            retry_module._retry_manager = None  # restore

    def test_singleton_creates_new_instance_after_reset(self):
        from client.retry import get_retry_manager
        import client.retry as retry_module

        retry_module._retry_manager = None
        mgr1 = get_retry_manager()
        retry_module._retry_manager = None
        mgr2 = get_retry_manager()
        assert mgr1 is not mgr2
        retry_module._retry_manager = None  # restore


class TestWithRetryDecorator:
    """Test with_retry decorator (lines 344-359)."""

    def setup_method(self):
        from client.retry import get_retry_manager, _retry_manager
        import client.retry as retry_module
        retry_module._retry_manager = None  # reset singleton

    def teardown_method(self):
        from client.retry import _retry_manager
        import client.retry as retry_module
        retry_module._retry_manager = None

    @pytest.mark.asyncio
    async def test_decorator_retries_and_succeeds(self):
        from client.retry import with_retry, RetryConfig

        call_count = 0

        @with_retry(operation="decorated-op", config=RetryConfig(max_retries=3, base_delay=0.01))
        async def flaky_op():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("flaky")
            return "success"

        result = await flaky_op()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_uses_operation_name(self):
        from client.retry import with_retry, RetryConfig, get_retry_manager

        @with_retry(operation="my-named-op")
        async def always_succeeds():
            return "ok"

        await always_succeeds()
        mgr = get_retry_manager()
        stats = mgr.get_stats("my-named-op")
        assert stats.attempts == 1

