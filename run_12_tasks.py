import urllib.request
import urllib.error
import json
import time
import subprocess
import os
import signal

tasks = [
    # 4-5 simple lookup/search tasks
    {"task": "Search Google for the capital of France and return just the city name.", "intent": "RESEARCH"},
    {"task": "Go to wikipedia.org and tell me the main headline.", "intent": "VISIBLE_BROWSER_TASK"},
    {"task": "Open news.ycombinator.com and list the top 2 story titles.", "intent": "VISIBLE_BROWSER_TASK"},
    {"task": "Search Google for the current Python stable version and return it.", "intent": "RESEARCH"},
    {"task": "Go to example.org and extract the last paragraph.", "intent": "VISIBLE_BROWSER_TASK"},
    
    # 2-3 repeated tasks from same task family with different targets
    {"task": "Go to github.com/trending and tell me the top trending repository name.", "intent": "VISIBLE_BROWSER_TASK"},
    {"task": "Go to github.com/trending/python and tell me the top trending repository name.", "intent": "VISIBLE_BROWSER_TASK"},
    {"task": "Go to github.com/trending/javascript and tell me the top trending repository name.", "intent": "VISIBLE_BROWSER_TASK"},
    
    # 2-3 multi-step/complex tasks
    {"task": "Go to Wikipedia, search for 'Apollo 11', navigate to the article, and extract the names of the three astronauts.", "intent": "RESEARCH"},
    {"task": "Go to news.ycombinator.com, find a story about AI, click into its comments, and summarize the top comment. If there are no stories about AI, just summarize the top comment of the first story.", "intent": "RESEARCH"},
    
    # 1-2 failure/recovery or edge-case tasks
    {"task": "Navigate to http://localhost:9999/does-not-exist and tell me what the page says.", "intent": "VISIBLE_BROWSER_TASK"},
    {"task": "Search for xqzxqzqxyzqxyqzx on Google and tell me the top result. If there are no results, tell me that.", "intent": "RESEARCH"}
]

print("Starting Chrome...")
chrome_proc = subprocess.Popen(
    ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--headless", "--remote-debugging-port=9222"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

print("Starting agent_service.py...")
env = os.environ.copy()
agent_proc = subprocess.Popen(
    [os.path.expanduser("~/.comex/.venv/bin/python") if os.path.exists(os.path.expanduser("~/.comex/.venv/bin/python")) else ".venv/bin/python", "agent_service.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

time.sleep(5)  # Wait for services to start

try:
    for i, t in enumerate(tasks):
        task_text = t["task"]
        intent = t["intent"]
        task_id = f"batch_task_{i+1}"
        print(f"\n--- Running Task {i+1}/{len(tasks)}: {task_id} ---")
        print(f"Task: {task_text}")
        
        req_data = json.dumps({
            "task": task_text,
            "tabId": "tab1",
            "taskId": task_id,
            "intent": intent
        }).encode('utf-8')
        
        req = urllib.request.Request("http://localhost:8000/agent/run", data=req_data, headers={'Content-Type': 'application/json'})
        
        try:
            start_time = time.time()
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                elapsed = time.time() - start_time
                print(f"Success: {result.get('success')}")
                print(f"Duration: {elapsed:.2f}s")
                print(f"Result snippet: {str(result.get('result'))[:200]}")
                if result.get('error'):
                    print(f"Error: {result.get('error')}")
        except Exception as e:
            print(f"Request failed: {e}")
            
finally:
    print("\nShutting down services...")
    agent_proc.terminate()
    chrome_proc.terminate()
    try:
        agent_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        agent_proc.kill()
    try:
        chrome_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        chrome_proc.kill()
    print("Done.")
