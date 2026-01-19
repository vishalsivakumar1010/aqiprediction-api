#!/bin/bash
# Run validation study in background with output logging

cd "/Users/vishalsivakumar/Library/Application Support/Knowledge/PurpleAir Download 1-9-2026/FINAL MODEL DATA PAIC"

# Run in background, save output to log file
nohup python3 validation_study.py \
  --addresses "2523 Bishop Ave, Fremont, CA 94536,39400 Paseo Padre Pkwy, Fremont, CA 94538,4620 Mattos Dr, Fremont, CA 94536,5400 Mowry Ave, Fremont, CA 94538,36007 Pizarro Dr, Fremont, CA 94536,3377 Alder Ave, Fremont, CA 94536,34665 Allegheny Ct, Fremont, CA 94555,1251 Peralta Blvd, Fremont, CA 94536,40500 Paseo Padre Pkwy, Fremont, CA 94538,41800 Blacow Rd, Fremont, CA 94538" \
  --api-key "C258449D-E52B-11F0-B596-4201AC1DC123" \
  --hours 12 \
  --interval 60 \
  > validation_results/validation_run_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# Get the process ID
PID=$!
echo "Validation study started in background"
echo "Process ID: $PID"
echo "Output being logged to: validation_results/validation_run_*.log"
echo ""
echo "To check status: ps -p $PID"
echo "To view log: tail -f validation_results/validation_run_*.log"
echo "To stop: kill $PID"
echo ""
echo "PID saved to: validation_results/validation.pid"
echo $PID > validation_results/validation.pid
