# Thread CPU usage
Allows you to calculate the CPU usage of processes and threads based on `psutil`.
Allows for simple configuration changes on the CLI.
Advanced usage should use post-processing or modify the code.

## Examples

### Help
```
$ python main.py -h
usage: main.py [-h] [--interval INTERVAL] [-n LINES] [-p PID]
               [--sort-key SORT_KEY]

Get CPU percentages for a process and children. Emits a JSON line for each
process. `jq` will be helpful for post processing.

optional arguments:
  -h, --help            show this help message and exit
  --interval INTERVAL   Time between timing measurements in seconds
  -n LINES, --lines LINES
                        Number of lines to emit
  -p PID, --pid PID     PID of target process
  --sort-key SORT_KEY   Sort by this key inside the "cpu_times" field
```

### Introspection
```
$ python main.py -n 1 | jq keys
[
  "cmdline",
  "cpu_times",
  "create_time",
  "exe",
  "name",
  "num_threads",
  "pid",
  "ppid",
  "threads"
]
```
```
$ python main.py -n 1 | jq '.cpu_times | keys'
[
  "children_cpu_pct",
  "children_delta",
  "children_system_delta",
  "children_user_delta",
  "io_delta",
  "process_cpu_pct",
  "process_delta",
  "system_delta",
  "total_cpu_delta",
  "total_cpu_pct",
  "user_delta"
]
```
```
 $ python main.py -n 1 | jq '.threads[0] | keys'
[
  "system_time_delta",
  "tid",
  "total_delta",
  "total_pct",
  "user_time_delta"
]
```

### Calculate the CPU percentage used by the top 5 processes
```
$ python main.py -n 5 | jq '.cpu_times.total_cpu_pct' | jq -s '. | add'
13.922
```

### Filter all results with no cpu usage
```
$ python main.py --pid $TARGET_PID | jq -c 'select(.cpu_times.total_cpu_delta > 0) | {name: .name, pct: .cpu_times.total_cpu_pct, pid: .pid, ppid: .ppid}'
{"name":"Web Content","pct":9.322,"pid":8420,"ppid":14547}
{"name":"firefox-bin","pct":1.332,"pid":14547,"ppid":1}
{"name":"Web Content","pct":0.121,"pid":12595,"ppid":14547}
```

### Get thread info
```
$ python main.py --pid $TARGET_PID | jq -c '
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
```
```
{"name":"Web Content","pct":10.169,"pid":8420,"ppid":14547,"threads":[{"tid":28958,"pct":0.242},{"tid":8420,"pct":8.596},{"tid":8426,"pct":0.847},{"tid":8431,"pct":0.121},{"tid":8433,"pct":0.121},{"tid":8435,"pct":0.484},{"tid":8443,"pct":0.121}]}
{"name":"firefox-bin","pct":3.511,"pid":14547,"ppid":1,"threads":[{"tid":14547,"pct":0.969},{"tid":14552,"pct":0.121},{"tid":14577,"pct":1.332},{"tid":14585,"pct":0.121},{"tid":14658,"pct":0.121},{"tid":14696,"pct":0.847},{"tid":4703,"pct":0.121}]}
{"name":"WebExtensions","pct":0.121,"pid":14701,"ppid":14547,"threads":[{"tid":14701,"pct":0.121}]}
{"name":"Web Content","pct":0.121,"pid":27924,"ppid":14547,"threads":[{"tid":27924,"pct":0.121}]}
```

## Setup

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Useful tools

Browser based load generator
1. [Doom](https://playclassic.games/games/first-person-shooter-dos-games-online/play-doom-online/play)


Post-Processing
1. [jq](https://stedolan.github.io/jq/)
2. [jq play](https://jqplay.org/)


## Similar things
```
ps -Lo ppid,pid,tid,pcpu,cmd --pid $TARGET_PID
```

```
top -b n1 -H -p $TARGET_PID | sed 1,6d
```
