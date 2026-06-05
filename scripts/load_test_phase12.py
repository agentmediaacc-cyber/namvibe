import time
import requests
import threading
import statistics

BASE_URL = "http://localhost:5000"
NUM_USERS = 100
REQUESTS_PER_USER = 10

def simulate_user(user_id):
    latencies = []
    for _ in range(REQUESTS_PER_USER):
        start = time.time()
        try:
            # Random mix of high-traffic endpoints
            resp = requests.get(f"{BASE_URL}/feed/?tab=for_you", timeout=5)
            latencies.append((time.time() - start) * 1000)
        except Exception as e:
            print(f"User {user_id} failed: {e}")
    return latencies

def run_load_test():
    print(f"Starting load test with {NUM_USERS} concurrent users...")
    all_latencies = []
    threads = []
    
    start_time = time.time()
    
    for i in range(NUM_USERS):
        t = threading.Thread(target=lambda: all_latencies.extend(simulate_user(i)))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    duration = time.time() - start_time
    
    if not all_latencies:
        print("Test failed: No latencies recorded.")
        return

    print("\n--- LOAD TEST REPORT ---")
    print(f"Total Requests: {len(all_latencies)}")
    print(f"Total Duration: {duration:.2f}s")
    print(f"Avg Latency: {statistics.mean(all_latencies):.2f}ms")
    print(f"P95 Latency: {statistics.quantiles(all_latencies, n=20)[18]:.2f}ms")
    print(f"Requests/sec: {len(all_latencies) / duration:.2f}")
    print("------------------------\n")

if __name__ == "__main__":
    run_load_test()
