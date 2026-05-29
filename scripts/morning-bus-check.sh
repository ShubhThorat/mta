#!/bin/bash
# MTA morning bus check — M42 & M15 near UN (1st Ave/42nd St)
# Runs weekdays 8:30–9:00am, sends iMessage to Shubh

STOP_M42_EAST="403248"   # E 42 ST/1 AV eastbound (towards UN)
STOP_M15="401698"        # 1 AV/E 42 ST (M15/M15+)
PHONE="+16172830499"
API="https://mcp.mta.shubhthorat.com/api/mta"

m42=$(curl -sf "${API}/arrivals?stop=${STOP_M42_EAST}&line=M42&limit=4" 2>/dev/null)
m15=$(curl -sf "${API}/arrivals?stop=${STOP_M15}&line=M15&limit=3" 2>/dev/null)

if [[ -z "$m42" && -z "$m15" ]]; then
  MSG="🚌 MTA API unavailable this morning"
else
  MSG=$(python3 - "$m42" "$m15" <<'PYEOF'
import json, sys

def fmt_arrivals(raw, label):
    if not raw:
        return f"{label}: unavailable"
    try:
        d = json.loads(raw)["data"]["arrivals"]
    except Exception:
        return f"{label}: parse error"
    if not d:
        return f"{label}: no buses"
    lines = [f"🚌 {label}"]
    for b in d[:4]:
        dist = b.get("presentableDistance", "?")
        dest = b.get("destination", "")
        dest_short = dest.split(" via ")[0].title() if dest else ""
        lines.append(f"  • {dist}" + (f" → {dest_short}" if dest_short else ""))
    return "\n".join(lines)

m42_raw, m15_raw = sys.argv[1], sys.argv[2]
parts = []
m42_fmt = fmt_arrivals(m42_raw, "M42 (→ UN)")
if m42_fmt:
    parts.append(m42_fmt)
m15_fmt = fmt_arrivals(m15_raw, "M15 (1 Ave)")
if m15_fmt:
    parts.append(m15_fmt)
print("\n\n".join(parts))
PYEOF
)
fi

osascript -e "tell application \"Messages\" to send \"${MSG}\" to buddy \"${PHONE}\" of service \"SMS\""
