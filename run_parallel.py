import asyncio
import json
import uuid
import random
import os
import glob

async def run_worker(sem, run_info):
    async with sem:
        cmd = f".venv/bin/python worker.py '{json.dumps(run_info)}'"
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()

async def main():
    runs = []
    for p_name in ["P1_Overlay", "P2_Scroll", "P3_Hover"]:
        for t_name in ["T1_Overlay", "T2_Scroll", "T3_Hover"]:
            for cond in ["BASELINE", "PROCEDURAL"]:
                for rep in range(1, 4):
                    runs.append({
                        "run_id": str(uuid.uuid4()),
                        "procedure_id": p_name,
                        "task_id": t_name,
                        "condition": cond,
                        "rep": rep
                    })
    random.shuffle(runs)
    
    # Run 10 concurrently
    sem = asyncio.Semaphore(10)
    tasks = [run_worker(sem, run_info) for run_info in runs]
    
    print(f"Starting {len(runs)} workers...")
    await asyncio.gather(*tasks)
    
    print("Aggregating results...")
    with open("phase14_v3_results.jsonl", "w") as out:
        for f in glob.glob("res_*.json"):
            with open(f, "r") as res_f:
                out.write(res_f.read().strip() + "\n")
            os.remove(f)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
