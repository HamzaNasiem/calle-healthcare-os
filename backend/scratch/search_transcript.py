import json
import re

transcript_path = r"C:\Users\LENOVO\.gemini\antigravity-cli\brain\6925af51-5e74-4839-a86f-4bd3297045a1\.system_generated\logs\transcript.jsonl"

keywords = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"db_password", re.IGNORECASE),
    re.compile(r"db_host", re.IGNORECASE),
    re.compile(r"pooler", re.IGNORECASE)
]

print("Scanning transcript for database secrets...")
try:
    with open(transcript_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            # Check if any keyword matches
            match = False
            for kw in keywords:
                if kw.search(line):
                    match = True
                    break
            if match:
                try:
                    obj = json.loads(line)
                    content = obj.get("content", "")
                    # Print matching snippets
                    if content and len(content.strip()) > 0:
                        print(f"\n[Line {idx}] Source: {obj.get('source')} Type: {obj.get('type')}")
                        for item in content.split("\n"):
                            if any(kw.search(item) for kw in keywords):
                                print(f"  {item[:150]}")
                except Exception as parse_err:
                    # If line is not JSON, search raw line
                    print(f"\n[Line {idx} Raw Match]")
                    for item in line.split("\n"):
                        if any(kw.search(item) for kw in keywords):
                            print(f"  {item[:150]}")
except Exception as e:
    print(f"Error reading transcript: {e}")
