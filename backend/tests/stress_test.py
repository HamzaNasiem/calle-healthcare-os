import asyncio
import time
import httpx
import sys
import os

# Measure memory if psutil is available
try:
    import psutil
    def get_memory_use_mb():
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
except ImportError:
    def get_memory_use_mb():
        return 0.0

BASE_URL = "http://localhost:8000"

async def make_request(client, request_id, latencies):
    start_time = time.time()
    try:
        # Simulate voice AI extraction webhook payload
        payload = {
            "event": "call_analyzed",
            "call_id": f"stress_call_{request_id}_{int(time.time())}",
            "call_status": "completed",
            "direction": "inbound",
            "from_number": "+15551234567",
            "to_number": "+15755734355",
            "duration_ms": 45000,
            "transcript": "Hello, I would like to book an appointment with Dr. Hamza on next Monday at 10:00 AM.",
            "agent_id": "agent_dummy_123"
        }
        headers = {
            "x-retell-signature": "dummy_signature_verify_bypassed_in_dev_env",
            "Content-Type": "application/json"
        }
        
        resp = await client.post(f"{BASE_URL}/api/v1/webhooks/retell/", json=payload, headers=headers)
        latency = time.time() - start_time
        latencies.append(latency)
        return resp.status_code
    except Exception as e:
        latency = time.time() - start_time
        latencies.append(latency)
        return f"Error: {str(e)}"

async def run_stress_load(concurrency):
    print(f"\n=============================================")
    print(f"   BYTELYTIC OS: STRESS & PERFORMANCE TEST")
    print(f"=============================================")
    print(f"Simulating {concurrency} concurrent voice AI extraction webhook requests...")
    
    start_mem = get_memory_use_mb()
    if start_mem > 0:
        print(f"Initial Memory Usage: {start_mem:.2f} MB")
        
    start_time = time.time()
    latencies = []
    
    # Configure connection pool for high concurrency
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        tasks = [make_request(client, i, latencies) for i in range(concurrency)]
        results = await asyncio.gather(*tasks)
        
    end_time = time.time()
    end_mem = get_memory_use_mb()
    total_time = end_time - start_time
    
    # Parse outcomes
    success_count = sum(1 for r in results if r == 204 or r == 200)
    error_count = concurrency - success_count
    
    # Latency calculations
    latencies.sort()
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    p95_latency = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99_latency = latencies[int(len(latencies) * 0.99)] if latencies else 0
    
    print("\n---------------- RESULTS ----------------")
    print(f"Total Requests:        {concurrency}")
    print(f"Successful (200/204):  {success_count}")
    print(f"Failed/Blocked:        {error_count}")
    print(f"Total Execution Time:  {total_time:.3f} seconds")
    print(f"Throughput:            {concurrency / total_time:.2f} requests/sec")
    
    print("\n--------------- LATENCY -----------------")
    print(f"Average Latency:       {avg_latency:.3f} seconds")
    print(f"95th Percentile:       {p95_latency:.3f} seconds")
    print(f"99th Percentile:       {p99_latency:.3f} seconds")
    
    if end_mem > 0:
        print("\n--------------- MEMORY ------------------")
        print(f"Final Memory Usage:    {end_mem:.2f} MB")
        print(f"Memory Growth:         {end_mem - start_mem:.2f} MB")
        
    print("=============================================\n")

if __name__ == "__main__":
    concurrency_level = 100
    if len(sys.argv) > 1:
        try:
            concurrency_level = int(sys.argv[1])
        except ValueError:
            pass
            
    asyncio.run(run_stress_load(concurrency_level))
