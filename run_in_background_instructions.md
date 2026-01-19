# Running Validation Study in Background

## ⚠️ Important Notes

**Cursor/Cursor terminal limitations:**
- If you close Cursor, the background process will continue ONLY if you use `nohup` or `screen`/`tmux`
- Regular background processes (`&`) will stop when the terminal closes
- The script saves results incrementally, so you won't lose data if it stops early

## Option 1: Using nohup (Recommended - survives terminal close)

```bash
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"

# Run with nohup (no hang up - survives terminal close)
nohup python3 validation_study.py \
  --addresses "2523 Bishop Ave, Fremont, CA 94536,39400 Paseo Padre Pkwy, Fremont, CA 94538,4620 Mattos Dr, Fremont, CA 94536,5400 Mowry Ave, Fremont, CA 94538,36007 Pizarro Dr, Fremont, CA 94536,3377 Alder Ave, Fremont, CA 94536,34665 Allegheny Ct, Fremont, CA 94555,1251 Peralta Blvd, Fremont, CA 94536,40500 Paseo Padre Pkwy, Fremont, CA 94538,41800 Blacow Rd, Fremont, CA 94538" \
  --api-key "C258449D-E52B-11F0-B596-4201AC1DC123" \
  --hours 12 \
  --interval 60 \
  > validation_results/validation_$(date +%Y%m%d_%H%M%S).log 2>&1 &

echo $! > validation_results/validation.pid
echo "Started! PID: $(cat validation_results/validation.pid)"
```

**Or use the helper script:**
```bash
./run_validation_background.sh
```

## Option 2: Using screen (Best for interactive monitoring)

```bash
# Install screen if needed: brew install screen

# Start a screen session
screen -S validation

# Inside screen, run the validation
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"
python3 validation_study.py --addresses "..." --api-key "..." --hours 12 --interval 60

# Detach: Press Ctrl+A, then D
# Reattach: screen -r validation
# List sessions: screen -ls
```

## Option 3: Using tmux (Alternative to screen)

```bash
# Install tmux if needed: brew install tmux

# Start a tmux session
tmux new -s validation

# Inside tmux, run the validation
cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"
python3 validation_study.py --addresses "..." --api-key "..." --hours 12 --interval 60

# Detach: Press Ctrl+B, then D
# Reattach: tmux attach -t validation
# List sessions: tmux ls
```

## Monitoring Progress

**Check if it's running:**
```bash
# If using nohup
ps -p $(cat validation_results/validation.pid)

# Or find by name
ps aux | grep validation_study.py
```

**View live output:**
```bash
tail -f validation_results/validation_*.log
```

**Check results as they come in:**
```bash
ls -lh validation_results/*.csv
wc -l validation_results/*.csv  # Count lines (each forecast = 1 line)
```

## Stopping the Study

**If using nohup:**
```bash
kill $(cat validation_results/validation.pid)
```

**If using screen/tmux:**
- Reattach and press Ctrl+C
- Or kill the session: `screen -X -S validation quit` or `tmux kill-session -t validation`

**Find and kill by process:**
```bash
pkill -f validation_study.py
```

## Recommendations

1. **For Cursor**: Use `nohup` or the helper script - it will continue even if you close Cursor
2. **For monitoring**: Use `screen` or `tmux` so you can check progress anytime
3. **For reliability**: The script saves incrementally, so partial results are preserved

## Check Status Script

Create this to check progress anytime:

```bash
#!/bin/bash
PID_FILE="validation_results/validation.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "✓ Validation study is RUNNING (PID: $PID)"
        echo "Runtime: $(ps -o etime= -p $PID)"
        echo "Log file: validation_results/validation_*.log"
        echo "Latest results:"
        ls -t validation_results/*.csv 2>/dev/null | head -3
    else
        echo "✗ Process not running (may have completed or stopped)"
    fi
else
    echo "No PID file found - study not running"
fi
```
