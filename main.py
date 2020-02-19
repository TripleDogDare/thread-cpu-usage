from decimal import Decimal
from json import encoder
from time import sleep
import psutil
import simplejson as json

attrs = [
        'pid',
        'ppid',
        'name',
        'cpu_times',
        'num_threads',
        'threads',
        'cmdline',
        'create_time',
        'exe',
    ]
# EXAMPLE OUTPUT
# {
#     "pid": 816,
#     "threads": [
#         {
#             "id": 816,
#             "user_time": 0.02,
#             "system_time": 0.01
#         },
#         {
#             "id": 823,
#             "user_time": 2.54,
#             "system_time": 3.04
#         },
#         {
#             "id": 864,
#             "user_time": 0.02,
#             "system_time": 0.0
#         }
#     ],
#     "cpu_times": {
#         "user": 2.59,
#         "system": 3.05,
#         "children_user": 0.0,
#         "children_system": 0.0,
#         "iowait": 0.0
#     },
#     "cmdline": [
#         "/usr/lib/accountsservice/accounts-daemon"
#     ],
#     "num_threads": 3,
#     "ppid": 1,
#     "exe": "/usr/lib/accountsservice/accounts-daemon",
#     "name": "accounts-daemon",
#     "create_time": 1581216030.43
# }


def floatfmt(f, precision=3):
    """ Creates a normalized Decimal with the given precision from a number.
    Useful for serializing floating point numbers with simplejson with a given precision.
    """
    q = Decimal(10) ** -precision
    return Decimal(f).quantize(q).normalize()

def collect_processes(pid=None):
    """ Gets a list of processes
    If pid is None or 0 then it will return all processes
    """
    if pid:
        p = psutil.Process(pid)
        result = {p.pid: p}
        result.update({c.pid: c for c in p.children(recursive=True)})
    else:
        result = {p.pid: p for p in psutil.process_iter(attrs=attrs)}
    return result

def main(pid=None, interval=1, lines=None, sort_key='total_cpu_pct'):
    children = collect_processes(pid)

    # START OF CRITICAL SECTION
    # This begins the critical section until the second set of timing data is collected
    # Too much processing inside the critical section will skew CPU usage percentage results

    # get cpu times
    cpu_time1 = psutil.cpu_times(percpu=False)
    
    # track data in dictionaries keyed by PID
    data = {}
    garbage = []
    for pid, child in children.items():
        try:
            data[pid] = child.as_dict(attrs=attrs)
        except psutil.NoSuchProcess:
            garbage.append(pid)
    for pid in garbage:
        del data[pid]

    # sleep for a bit so the CPU actually does things
    sleep(interval)

    # second timing data is used to calculate deltas/percentages
    cpu_time2 = psutil.cpu_times(percpu=False)
    for pid, child in children.items():
        value = data[pid]
        try:
            value.update({
                'cpu_times2':  child.cpu_times(),
                'threads2':  child.threads(),
            })
        except psutil.NoSuchProcess:
            # Just give terminated processes duplicate timings.
            # They can be filtered out by sorting later
            value.update({
                'cpu_times2':  value['cpu_times'] or None,
                'threads2':  value['threads'] or None,
            })
    # END OF CRITICAL SECTION

    # post processing to calculate cpu percentages
    cpu_delta = sum(cpu_time2) - sum(cpu_time1)
    for tid, item in data.items():
        # calculate cpu times of process and children
        t1 = item.pop('cpu_times')
        t2 = item.pop('cpu_times2')
        p_user_delta = t2.user - t1.user
        p_system_delta = t2.system - t1.system
        c_user_delta = t2.children_user - t1.children_user
        c_system_delta = t2.children_system - t1.children_system
        io_delta = t2.iowait - t1.iowait
        cpu_times = {
            "user_delta": floatfmt(p_user_delta),
            "system_delta": floatfmt(p_system_delta),
            "process_delta": floatfmt(p_user_delta + p_system_delta),
            "children_user_delta": floatfmt(c_user_delta),
            "children_system_delta": floatfmt(c_system_delta),
            "children_delta": floatfmt(c_user_delta + c_system_delta),
            "process_cpu_pct": floatfmt(100.0 * (p_user_delta + p_system_delta) / cpu_delta),
            "children_cpu_pct": floatfmt(100.0 * (c_user_delta + c_system_delta) / cpu_delta),
            "total_cpu_delta": floatfmt((p_user_delta + p_system_delta + c_user_delta + c_system_delta)),
            "total_cpu_pct": floatfmt(100.0*(p_user_delta + p_system_delta + c_user_delta + c_system_delta) / cpu_delta),
            "io_delta": floatfmt(io_delta),
        }
        # calculate thread cpu percentages
        threads1 = {t.id: t for t in item.pop('threads')}
        threads2 = {t.id: t for t in item.pop('threads2')}
        thread_deltas = {}
        for tid, t1 in threads1.items():
            t2 = threads2.get(tid)
            if t2:
                user_delta = t2.user_time - t1.user_time
                system_delta = t2.system_time - t1.system_time
                thread_deltas[tid] = {
                    'tid': tid,
                    'user_time_delta': floatfmt(user_delta),
                    'system_time_delta': floatfmt(system_delta),
                    'total_delta': floatfmt(user_delta+system_delta),
                    'total_pct': floatfmt(100.0 * (user_delta + system_delta) / cpu_delta),
                }
        item.update({
            'cpu_times': cpu_times,
            'threads': list(thread_deltas.values()),
        })

    data = list(data.values())
    data = sorted(data, key=lambda x: x['cpu_times'][sort_key], reverse=True)

    if lines:
        data = data[:lines]

    try:
        for item in data:
            print(json.dumps(item, sort_keys=True))
    except BrokenPipeError:
        pass # ignore error caused by piping to head

def get_default_args(func):
    """ Helper for argparse to pass default values to main
    """
    import inspect
    signature = inspect.signature(func)
    return {
        k: v.default
        for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }

if __name__ == '__main__':
    import argparse
    default = get_default_args(main)
    parser = argparse.ArgumentParser(
        description='Get CPU percentages for a process and children. Emits a JSON line for each process. `jq` will be helpful for post processing.')
    parser.add_argument('--interval', type=float, dest='interval', default=default.get('interval'),
        help='Time between timing measurements in seconds')
    parser.add_argument('-n','--lines', type=int, dest='lines', default=default.get('lines'),
        help='Number of lines to emit')
    parser.add_argument('-p', '--pid', type=int, dest='pid', default=default.get('pid'),
        help='PID of target process')
    parser.add_argument('--sort-key', type=str, dest='sort_key', default=default.get('sort_key'),
        help='Sort by this key inside the "cpu_times" field'
        )
    args = parser.parse_args()
    main(**vars(args))
