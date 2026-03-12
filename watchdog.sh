#!/bin/bash
# TAO Mining Watchdog - checks all miners are running, restarts if down

LOG="/root/tao/watchdog.log"
TS=$(date '+%Y-%m-%d %H:%M:%S')

check_pm2() {
    local name=$1
    local status=$(pm2 jlist 2>/dev/null | python3 -c "
import sys,json
for p in json.load(sys.stdin):
    if p['name']=='$name':
        print(p['pm2_env']['status'])
        break
" 2>/dev/null)
    
    if [ "$status" != "online" ]; then
        echo "[$TS] $name is $status — restarting" >> "$LOG"
        pm2 restart "$name" 2>/dev/null
        return 1
    fi
    return 0
}

check_systemd() {
    local name=$1
    if ! systemctl is-active --quiet "$name"; then
        echo "[$TS] $name is down — restarting" >> "$LOG"
        systemctl restart "$name"
        return 1
    fi
    return 0
}

# Check all miners
check_pm2 "vanta-miner"
check_pm2 "jane-vanta-bridge"
check_pm2 "sn33-miner"
check_systemd "jane.service"

# Trim log to last 500 lines
if [ -f "$LOG" ] && [ $(wc -l < "$LOG") -gt 500 ]; then
    tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
