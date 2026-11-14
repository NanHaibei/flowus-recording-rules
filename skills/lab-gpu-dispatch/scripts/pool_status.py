#!/usr/bin/env python3
"""Inspect lab GPU resources and reservations without submitting any jobs."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_PLATFORM = Path('/home/jyz/project/codex_project/infra/lab-platform')
TERMINAL = {'SUCCEEDED', 'FAILED', 'CANCELED'}
GIB = 1024 ** 3


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Platform redirect refused; check LAB_URL')


class Client:
    def __init__(self, url, token, timeout):
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme not in {'http', 'https'} or not parsed.netloc
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {'', '/'}):
            raise ValueError('LAB_URL must be the platform origin, without /api or credentials')
        self.url = url.rstrip('/')
        self.token = token
        self.timeout = timeout

    def request(self, path, refresh=False):
        request = urllib.request.Request(
            self.url + '/api' + path,
            headers={'Authorization': 'Bearer ' + self.token},
            method='POST' if refresh else 'GET',
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            with opener.open(request, timeout=self.timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'Platform HTTP {exc.code} for {path}; check access/service') from None
        except urllib.error.URLError:
            raise RuntimeError('Platform unreachable; check the lab35 connection and LAB_URL') from None


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def summarize(hosts, tasks, args, now):
    reservations = {}
    active_tasks = []
    for task in tasks:
        if task.get('state') in TERMINAL:
            continue
        spec = task.get('spec', {})
        devices = [str(gpu) for gpu in spec.get('gpus', [])]
        reservations.setdefault(spec.get('host'), set()).update(devices)
        active_tasks.append({
            'id': task.get('id'), 'name': spec.get('name'), 'host': spec.get('host'),
            'state': task.get('state'), 'gpus': devices,
        })

    candidates = []
    summaries = []
    for host in hosts:
        name = host.get('id')
        if (args.host and name not in args.host) or name in args.exclude_host:
            continue
        observed = host.get('observed_at')
        age = max(0, now - observed) if finite(observed) else None
        base = []
        if host.get('online') is not True:
            base.append('offline_or_unknown')
        if host.get('maintenance'):
            base.append('maintenance')
        if host.get('stale') or age is None or age > args.max_age:
            base.append('stale_or_unknown_observation')
        docker = host.get('docker') or {}
        if docker.get('available') is not True:
            base.append('docker_unavailable')
        cpu_count, memory = host.get('cpu_count'), host.get('memory_available')
        if args.cpus and (not finite(cpu_count) or cpu_count < args.cpus):
            base.append('insufficient_or_unknown_cpu_capacity')
        if args.memory_gib and (not finite(memory) or memory < (args.memory_gib + 1) * GIB):
            base.append('insufficient_or_unknown_host_memory')
        rows = []
        for gpu in host.get('gpus', []):
            reasons = list(base)
            index, uuid = gpu.get('index'), gpu.get('uuid')
            if index is None or not isinstance(uuid, str) or not uuid:
                reasons.append('missing_device_identity')
            if gpu.get('occupancy_known') is not True:
                reasons.append('occupancy_unknown')
            if gpu.get('busy') is not False:
                reasons.append('busy_or_unknown')
            if uuid in reservations.get(name, set()) or str(index) in reservations.get(name, set()):
                reasons.append('reserved_by_active_or_unknown_task')
            total, used = gpu.get('memory_total_mb'), gpu.get('memory_used_mb')
            free = total - used if finite(total) and finite(used) and 0 <= used <= total and total > 0 else None
            if free is None or free < args.min_free_mib:
                reasons.append('insufficient_or_unknown_vram')
            driver = gpu.get('driver')
            try:
                major = int(str(driver).split('.')[0])
            except (ValueError, TypeError):
                major = None
            if args.min_driver_major and (major is None or major < args.min_driver_major):
                reasons.append('incompatible_or_unknown_driver_major')
            row = {
                'index': index, 'uuid': uuid, 'model': gpu.get('name'), 'driver': driver,
                'free_mib': free, 'utilization_percent': gpu.get('utilization'),
                'resource_candidate': not reasons, 'reasons': reasons,
            }
            rows.append(row)
            if not reasons:
                candidates.append({
                    'host': name, 'index': index, 'uuid': uuid,
                    'model': gpu.get('name'), 'driver': driver, 'free_mib': free,
                })
        summaries.append({
            'id': name, 'online': host.get('online'), 'maintenance': bool(host.get('maintenance')),
            'observation_age_seconds': round(age, 1) if age is not None else None,
            'cpu_count': cpu_count,
            'memory_available_gib': round(memory / GIB, 2) if finite(memory) else None,
            'docker_available': docker.get('available') is True,
            'host_reasons': base, 'gpus': rows,
        })
    return {
        'queried_at': now, 'eligibility': 'resources_only_not_image_qualification_or_reservation',
        'candidate_count': len(candidates), 'candidates': candidates,
        'hosts': summaries, 'active_tasks': active_tasks,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform-dir', type=Path, default=Path(os.environ.get('LAB_PLATFORM_DIR', DEFAULT_PLATFORM)))
    parser.add_argument('--url', default=os.environ.get('LAB_URL', 'http://127.0.0.1:18735'))
    parser.add_argument('--token-file', type=Path, help='Defaults to LAB_TOKEN_FILE or PLATFORM_DIR/.runtime/token')
    parser.add_argument('--host', action='append', default=[], help='Include a host; repeatable')
    parser.add_argument('--exclude-host', action='append', default=[], help='Exclude a host; repeatable')
    parser.add_argument('--refresh', action='store_true', help='Refresh monitoring probes; never submit jobs')
    parser.add_argument('--min-free-mib', type=float, default=0)
    parser.add_argument('--cpus', type=float, default=0, help='Requested CPU capacity')
    parser.add_argument('--memory-gib', type=float, default=0, help='Requested host memory; adds 1 GiB headroom')
    parser.add_argument('--min-driver-major', type=int, default=0, help='Optional resource filter, not a compatibility test')
    parser.add_argument('--max-age', type=float, default=45, help='Maximum observation age in seconds')
    parser.add_argument('--timeout', type=float, default=30, help='Seconds per API request')
    args = parser.parse_args(argv)
    for name in ['min_free_mib', 'cpus', 'memory_gib', 'min_driver_major']:
        if not finite(getattr(args, name)) or getattr(args, name) < 0:
            parser.error('--' + name.replace('_', '-') + ' must be finite and nonnegative')
    for name in ['max_age', 'timeout']:
        if not finite(getattr(args, name)) or getattr(args, name) <= 0:
            parser.error('--' + name.replace('_', '-') + ' must be finite and positive')
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        token = os.environ.get('LAB_TOKEN', '').strip()
        if not token:
            token_file = args.token_file or Path(os.environ.get('LAB_TOKEN_FILE', args.platform_dir / '.runtime/token'))
            token = token_file.expanduser().read_text().strip()
        if not token:
            raise ValueError('Platform token file is empty')
        client = Client(args.url, token, args.timeout)
        hosts = client.request('/hosts')
        if not isinstance(hosts, list) or not all(isinstance(host, dict) for host in hosts):
            raise ValueError('Unexpected platform host response')
        known = {host.get('id') for host in hosts}
        if set(args.host) - known:
            raise ValueError('Requested host is not present in platform inventory')
        hosts = [host for host in hosts if (not args.host or host.get('id') in args.host)
                 and host.get('id') not in args.exclude_host]
        if args.refresh and hosts:
            def refresh(host):
                name = urllib.parse.quote(str(host['id']), safe='')
                return client.request('/hosts/' + name + '/refresh', refresh=True)
            with ThreadPoolExecutor(max_workers=min(4, len(hosts))) as pool:
                hosts = list(pool.map(refresh, hosts))
        tasks = client.request('/tasks')
        if not isinstance(tasks, list) or not all(isinstance(task, dict) for task in tasks):
            raise ValueError('Unexpected platform task response')
        report = summarize(hosts, tasks, args, time.time())
        report['refreshed'] = args.refresh
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
