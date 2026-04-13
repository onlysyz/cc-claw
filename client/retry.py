"""CC-Claw Smart Retry Module - Intelligent retry with exponential backoff

Features:
- Configurable retry strategies per error type
- Circuit breaker pattern for failing services
- Retry budgeting (max cost per task)
- Jitter to prevent thundering herd
- Detailed retry logging for debugging
"""

import asyncio
import random
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any, Optional, List, Dict, Type
from functools import wraps


logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategies for different scenarios"""
    EXPONENTIAL = "exponential"           # 2^n backoff
    LINEAR = "linear"                      # n * delay
    FIBONACCI = "fibonacci"                # Fibonacci backoff
    IMMEDIATE = "immediate"               # No delay, just retry
    EXPONENTIAL_WITH_JITTER = "exp_jitter" # Exponential + random jitter


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 3
    base_delay: float = 1.0          # seconds
    max_delay: float = 60.0         # seconds
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_WITH_JITTER
    retry_on: tuple = ()            # Exception types to retry on
    timeout: float = 0.0             # 0 = no timeout
    budget_tokens: int = 0           # Max tokens to spend on retries (0 = unlimited)


@dataclass
class RetryStats:
    """Statistics for retry operations"""
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    total_delay: float = 0.0
    last_attempt: Optional[str] = None
    last_error: Optional[str] = None
    retry_history: List[Dict] = field(default_factory=list)


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject immediately
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for failing services

    Prevents repeated calls to failing services by opening the circuit
    after a threshold of failures.
    """
    name: str
    failure_threshold: int = 5           # Failures before opening
    success_threshold: int = 2            # Successes in half-open to close
    timeout: float = 60.0                # Seconds before trying half-open

    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _failure_count: int = field(default=0, repr=False)
    _success_count: int = field(default=0, repr=False)
    _last_failure_time: Optional[float] = field(default=None, repr=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for timeout transition"""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.timeout:
                    logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN after {elapsed:.1f}s")
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
        return self._state

    def record_success(self):
        """Record a successful call"""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                logger.info(f"Circuit breaker '{self.name}' closing after {self._success_count} successes")
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        elif self._state == CircuitState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        """Record a failed call"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker '{self.name}' reopening after failure in HALF_OPEN")
            self._state = CircuitState.OPEN
        elif self._state == CircuitState.CLOSED and self._failure_count >= self.failure_threshold:
            logger.warning(f"Circuit breaker '{self.name}' opening after {self._failure_count} failures")
            self._state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if a request can be executed"""
        return self.state != CircuitState.OPEN

    def get_status(self) -> Dict:
        """Get circuit breaker status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self._failure_count,
            "successes": self._success_count,
            "last_failure": self._last_failure_time,
        }


class SmartRetry:
    """Smart retry wrapper with intelligent backoff"""

    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._stats: Dict[str, RetryStats] = {}
        self._token_budgets: Dict[str, int] = {}

    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a service"""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(name=name)
        return self._circuit_breakers[name]

    def get_stats(self, operation: str) -> RetryStats:
        """Get retry stats for an operation"""
        if operation not in self._stats:
            self._stats[operation] = RetryStats()
        return self._stats[operation]

    def calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for given attempt using configured strategy"""
        if config.strategy == RetryStrategy.IMMEDIATE:
            return 0.0

        if config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * attempt

        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (2 ** attempt)

        elif config.strategy == RetryStrategy.EXPONENTIAL_WITH_JITTER:
            base = config.base_delay * (2 ** attempt)
            # Add jitter: random value between 0% and 100% of base delay
            jitter = base * random.uniform(0, 1)
            delay = base + jitter

        elif config.strategy == RetryStrategy.FIBONACCI:
            # Fibonacci: 1, 1, 2, 3, 5, 8...
            fib = self._fibonacci(attempt + 1)
            delay = config.base_delay * fib

        else:
            delay = config.base_delay

        return min(delay, config.max_delay)

    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number"""
        if n <= 1:
            return 1
        a, b = 1, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b

    async def execute(
        self,
        operation: str,
        func: Callable,
        *args,
        config: Optional[RetryConfig] = None,
        circuit_breaker_name: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Execute function with retry logic

        Args:
            operation: Name for tracking stats
            func: Async function to execute
            *args: Positional args for func
            config: Retry configuration
            circuit_breaker_name: Optional service to apply circuit breaker
            **kwargs: Keyword args for func
        """
        if config is None:
            config = RetryConfig()

        stats = self.get_stats(operation)
        stats.attempts += 1
        stats.last_attempt = datetime.now().isoformat()

        # Check circuit breaker
        cb = None
        if circuit_breaker_name:
            cb = self.get_circuit_breaker(circuit_breaker_name)
            if not cb.can_execute():
                stats.failures += 1
                stats.last_error = f"Circuit breaker open for {circuit_breaker_name}"
                raise CircuitBreakerOpen(f"Circuit breaker is open for {circuit_breaker_name}")

        last_error = None
        for attempt in range(config.max_retries + 1):
            try:
                # Apply timeout if configured
                if config.timeout > 0:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=config.timeout
                    )
                else:
                    result = await func(*args, **kwargs)

                # Success
                if attempt > 0:
                    logger.info(f"Operation '{operation}' succeeded on attempt {attempt + 1}")
                    stats.successes += 1
                    stats.retry_history.append({
                        "attempt": attempt + 1,
                        "success": True,
                        "delay": stats.total_delay,
                    })

                if cb:
                    cb.record_success()

                return result

            except asyncio.TimeoutError as e:
                last_error = f"Timeout after {config.timeout}s"
                logger.warning(f"Operation '{operation}' timed out (attempt {attempt + 1})")

            except CircuitBreakerOpen:
                raise

            except Exception as e:
                last_error = str(e)
                error_type = type(e).__name__

                # Check if we should retry this error type
                if config.retry_on and not any(isinstance(e, exc_type) for exc_type in config.retry_on):
                    logger.info(f"Operation '{operation}' failed with {error_type}, not retrying")
                    stats.failures += 1
                    stats.last_error = last_error
                    raise

                logger.warning(f"Operation '{operation}' failed: {error_type}: {last_error} (attempt {attempt + 1})")

            # Calculate and apply delay
            if attempt < config.max_retries:
                delay = self.calculate_delay(attempt, config)
                stats.total_delay += delay
                logger.debug(f"Retrying '{operation}' in {delay:.2f}s...")
                await asyncio.sleep(delay)

        # All retries exhausted
        stats.failures += 1
        stats.last_error = last_error
        stats.retry_history.append({
            "attempt": config.max_retries + 1,
            "success": False,
            "error": last_error,
        })
        raise MaxRetriesExceeded(f"Operation '{operation}' failed after {config.max_retries + 1} attempts: {last_error}")

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get all retry statistics"""
        return {
            "operations": {
                name: {
                    "attempts": s.attempts,
                    "successes": s.successes,
                    "failures": s.failures,
                    "total_delay": s.total_delay,
                    "last_attempt": s.last_attempt,
                    "last_error": s.last_error,
                }
                for name, s in self._stats.items()
            },
            "circuit_breakers": {
                name: cb.get_status()
                for name, cb in self._circuit_breakers.items()
            }
        }


class MaxRetriesExceeded(Exception):
    """Raised when all retries are exhausted"""
    pass


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open"""
    pass


# Global retry manager
_retry_manager: Optional[SmartRetry] = None


def get_retry_manager() -> SmartRetry:
    """Get or create global retry manager"""
    global _retry_manager
    if _retry_manager is None:
        _retry_manager = SmartRetry()
    return _retry_manager


def with_retry(
    operation: Optional[str] = None,
    config: Optional[RetryConfig] = None,
    circuit_breaker: Optional[str] = None,
):
    """Decorator to add retry logic to async functions

    Usage:
        @with_retry(operation="fetch_data", config=RetryConfig(max_retries=3))
        async def fetch_data(url):
            ...
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            manager = get_retry_manager()
            return await manager.execute(
                op_name,
                func,
                *args,
                config=config,
                circuit_breaker_name=circuit_breaker,
                **kwargs
            )
        return wrapper
    return decorator


# Predefined retry configs for common scenarios
RETRY_CONFIGS = {
    "network": RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER,
        retry_on=(ConnectionError, TimeoutError, asyncio.TimeoutError),
    ),
    "api": RetryConfig(
        max_retries=5,
        base_delay=2.0,
        max_delay=60.0,
        strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER,
        retry_on=(ConnectionError, TimeoutError),
    ),
    "claude_api": RetryConfig(
        max_retries=4,
        base_delay=5.0,
        max_delay=120.0,
        strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER,
        retry_on=(ConnectionError, TimeoutError),
    ),
    "database": RetryConfig(
        max_retries=3,
        base_delay=0.5,
        max_delay=10.0,
        strategy=RetryStrategy.LINEAR,
        retry_on=(ConnectionError,),
    ),
    "fast": RetryConfig(
        max_retries=2,
        base_delay=0.1,
        max_delay=1.0,
        strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER,
    ),
}