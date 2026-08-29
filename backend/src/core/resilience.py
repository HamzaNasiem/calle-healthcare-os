import time
import asyncio
from typing import Callable, Any

class CircuitBreakerOpenException(Exception):
    """Exception raised when a request is blocked by an open circuit breaker."""
    pass

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout_seconds: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.failure_count = 0
        self.last_state_change = time.time()

    def record_success(self):
        self.failure_count = 0
        if self.state != "CLOSED":
            print(f"[CircuitBreaker-{self.name}] Success recorded. State transition: {self.state} -> CLOSED.")
            self.state = "CLOSED"
            self.last_state_change = time.time()

    def record_failure(self):
        self.failure_count += 1
        if self.state == "CLOSED" and self.failure_count >= self.failure_threshold:
            print(f"[CircuitBreaker-{self.name}] Failure threshold ({self.failure_threshold}) reached. State transition: CLOSED -> OPEN.")
            self.state = "OPEN"
            self.last_state_change = time.time()
        elif self.state == "HALF-OPEN":
            print(f"[CircuitBreaker-{self.name}] Trial execution failed. State transition: HALF-OPEN -> OPEN.")
            self.state = "OPEN"
            self.last_state_change = time.time()

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            # Check if recovery timeout has elapsed
            elapsed = time.time() - self.last_state_change
            if elapsed > self.recovery_timeout_seconds:
                print(f"[CircuitBreaker-{self.name}] Recovery timeout expired. State transition: OPEN -> HALF-OPEN.")
                self.state = "HALF-OPEN"
                self.last_state_change = time.time()
                return True
            return False
        
        # HALF-OPEN state allows test requests
        return True

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if not self.allow_request():
            raise CircuitBreakerOpenException(
                f"Circuit breaker '{self.name}' is OPEN. Downstream service is currently offline or failing."
            )
        
        try:
            # Execute synchronously or asynchronously depending on function type
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise e
