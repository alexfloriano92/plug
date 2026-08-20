import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\User\.gemini\antigravity-ide\brain\9bd38036-3cf9-40da-beea-8e3172356342\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check steps 100-174 - show everything
for i in range(len(lines)):
    data = json.loads(lines[i])
    step = data.get('step_index', '?')
    if not isinstance(step, int) or step < 100:
        continue
    source = data.get('source', '?')
    typ = data.get('type', '?')
    content = data.get('content', '')
    tool_calls = data.get('tool_calls', [])
    thinking = data.get('thinking', '')
    
    if content or tool_calls or thinking:
        print(f"\n=== Step {step} ({source}/{typ}) ===")
        if thinking:
            print(f"THINKING: {thinking[:300]}")
        if content:
            print(f"CONTENT: {content[:500]}")
        if tool_calls:
            for tc in tool_calls:
                name = tc.get('name', '?')
                args = tc.get('args', {})
                print(f"TOOL: {name}")
                for k, v in args.items():
                    vstr = str(v)
                    if len(vstr) > 200:
                        vstr = vstr[:200] + '...'
                    print(f"  {k}: {vstr}")
