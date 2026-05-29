#!/bin/zsh
# Module: MTA Bus Alert (Claude-assisted)
# Reads Home calendar events, passes location to Claude to figure out route + send alert
# Deduplicates — max one alert per 60 min

LOG_FILE="$HOME/.claude/logs/checker.log"
LAST_ALERT_FILE="/tmp/last-bus-alert.txt"
CURRENT_TIME=$(date '+%A %B %d %Y %I:%M %p %Z')

# Skip if we already sent an alert in the last 60 min
if [[ -f "$LAST_ALERT_FILE" ]]; then
  LAST=$(cat "$LAST_ALERT_FILE")
  NOW=$(date +%s)
  if (( NOW - LAST < 3600 )); then
    exit 0
  fi
fi

# Get Home calendar events starting in next 25–90 min (with location)
EVENTS=$(osascript <<'ASEOF'
set now to current date
set windowStart to now + (25 * 60)
set windowEnd to now + (90 * 60)
set output to ""
tell application "Calendar"
  repeat with c in calendars
    if name of c is "Home" then
      set evts to (events of c whose start date >= windowStart and start date <= windowEnd)
      repeat with e in evts
        set evtTitle to summary of e
        set evtStart to start date of e as string
        set evtLoc to ""
        try
          set evtLoc to location of e
        end try
        set output to output & evtTitle & "|" & evtStart & "|" & evtLoc & "\n"
      end repeat
    end if
  end repeat
end tell
return output
ASEOF
)

if [[ -z "$EVENTS" ]]; then
  exit 0
fi

echo "[$(date)] mta-bus: events found, running claude" >> "$LOG_FILE"

PROMPT="You are a commute assistant for Shubh in NYC. Check upcoming calendar events and send an iMessage with relevant MTA bus arrivals.

Current time: $CURRENT_TIME

Shubh's addresses:
- Home: 405 E 45th St, New York, NY 10017 (near 1 Ave / 45th St)
- Work: 1440 Broadway, New York, NY 10018 (near Broadway / 40th St)

Upcoming calendar events (title|start|location):
$EVENTS

Steps:
1. Look at the event location (or title if no location). Figure out if Shubh is commuting somewhere that requires a bus.
2. If heading TO work (1440 Broadway area): check M42 westbound at stop 403251 (E 42 ST/1 AV westbound) using mta_arrivals
3. If heading FROM work (405 E 45th area, or UN/1 Ave area): check M42 eastbound at stop 403248 (E 42 ST/1 AV eastbound)
4. For other destinations: use mta_stops_near with the destination lat/lon to find the right stop, then check arrivals for the most relevant route
5. If it's clearly a WFH/virtual event (no physical location, or location = home), do nothing and exit

Format the iMessage as:
🚌 [Event title] in ~X min
[Line] ([direction]):
  • [presentableDistance]
  • [presentableDistance]

Send the iMessage to +16172830499 using:
osascript -e 'tell application \"Messages\" to send \"MESSAGE\" to buddy \"+16172830499\" of service \"SMS\"'

After sending, write the current unix timestamp to /tmp/last-bus-alert.txt"

HOME=/Users/ai ~/.local/bin/claude --dangerously-skip-permissions \
  -p "$PROMPT" >> "$LOG_FILE" 2>&1

echo "[$(date)] mta-bus: done" >> "$LOG_FILE"
