#!/bin/bash

TARGET=$(pgrep --parent 1 -a chrome | tee /dev/stderr | head -1 | awk '{print $1}')
[[ -z "$TARGET" ]] && {
	>&2 echo "process not found"
	exit 1
}

NOW=$(date +%s)
CPU_USAGE=$(grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print int(usage)}')

>&2 echo $CPU_USAGE
CPU_TRIGGER_USAGE=20
if [[ "$CPU_USAGE" -gt "$CPU_TRIGGER_USAGE" ]]; then
	# Assumes dependencies are available
	python main.py --pid "$TARGET" | jq -c '
	select(.cpu_times.total_cpu_delta > 0)
	| {
		name: .name,
		pct: .cpu_times.total_cpu_pct,
		pid: .pid,
		ppid: .ppid,
		threads: [
			.threads[]
			| select(.total_delta > 0)
			| {tid: .tid, pct: .total_pct}
		]
	}'
else
	>&2 echo "CPU less than $CPU_TRIGGER_USAGE at $NOW"
fi
