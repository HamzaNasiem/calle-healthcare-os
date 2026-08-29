import pytest
import time
import asyncio
from src.core.resilience import CircuitBreaker, CircuitBreakerOpenException
from src.core.cache import LocalCache

def test_cache_set_get_invalidate():
    cache = LocalCache(default_ttl=5)
    cache.set("key1", "val1")
    assert cache.get("key1") == "val1"
    
    cache.invalidate("key1")
    assert cache.get("key1") is None

def test_cache_expiration():
    cache = LocalCache(default_ttl=1)
    cache.set("key2", "val2")
    assert cache.get("key2") == "val2"
    
    # Wait for expiration
    time.sleep(1.1)
    assert cache.get("key2") is None

def test_circuit_breaker_transitions():
    cb = CircuitBreaker("test-cb", failure_threshold=2, recovery_timeout_seconds=0.5)
    assert cb.state == "CLOSED"
    
    # First failure
    with pytest.raises(ValueError):
        asyncio.run(cb.call(lambda: exec("raise ValueError()")))
    assert cb.state == "CLOSED"
    
    # Second failure triggers OPEN
    with pytest.raises(ValueError):
        asyncio.run(cb.call(lambda: exec("raise ValueError()")))
    assert cb.state == "OPEN"
    
    # Immediate request blocked
    with pytest.raises(CircuitBreakerOpenException):
        asyncio.run(cb.call(lambda: "success"))
        
    # Wait for recovery timeout to transition to HALF-OPEN on next check
    time.sleep(0.6)
    
    # Successful execution should close the circuit
    res = asyncio.run(cb.call(lambda: "success"))
    assert res == "success"
    assert cb.state == "CLOSED"
