__author__ = 'nhumrich'

import re
import time

from docker import Client
from datetime import datetime
from dateutil import parser

from .streamers import syslog
from .objects import Container, Log


## Patch for "--since" option in getting logs.
## See https://github.com/docker/docker-py/pull/796/files
## Only included here because the fix is not in master at the time of writing
def datetime_to_timestamp(dt):
    """Convert a UTC datetime to a Unix timestamp"""
    epoch = datetime.utcfromtimestamp(0)
    epoch = epoch.replace(tzinfo=dt.tzinfo)
    delta = dt - epoch
    return delta.seconds + delta.days * 24 * 3600


def logs(self, container, stdout=True, stderr=True, stream=False,
         timestamps=False, tail='all', since=None):
    params = {'stderr': stderr and 1 or 0,
              'stdout': stdout and 1 or 0,
              'timestamps': timestamps and 1 or 0,
              'follow': stream and 1 or 0,
              }
    if tail != 'all' and (not isinstance(tail, int) or tail <= 0):
        tail = 'all'
    params['tail'] = tail

    if since is not None:
        if isinstance(since, datetime):
            params['since'] = datetime_to_timestamp(since) + 1
        elif isinstance(since, int) and since > 0:
            params['since'] = since + 1
        url = self._url("/containers/{0}/logs", container)
        res = self._get(url, params=params, stream=stream)
        return self._get_result(container, stream, res)
    return self.attach(
        container,
        stdout=stdout,
        stderr=stderr,
        stream=stream,
        logs=True
    )


docker = Client(base_url='unix://var/run/docker.sock')
Client.logs = logs

containers = dict()
last_timestamps = dict()
start_time = datetime.now()


def get_containers():
    global containers
    containers = dict()
    for d in docker.containers():
        id = d.get('Id')
        d = docker.inspect_container(id)
        config = d.get('Config')
        image = config.get('Image')
        labels = config.get('Labels')
        containers[id] = Container(image=image, id=id, labels=labels)


def get_all_logs():
    result = []
    for _, c in containers.items():
        service = c.labels.get('service', None)
        if service is None:
            # Do not log containers without a service label
            continue

        last_timestamp = last_timestamps.get(
            c.id,
            start_time
        )
        logs = parse_logs(
            docker.logs(c.id, since=last_timestamp, timestamps=True),
            c
        )
        # Logs should already be time sorted for specific container
        if len(logs) >= 1:
            last_timestamps[c.id] = logs[-1].timestamp
        result += logs
    return result


def stream_logs(logs):
    # sort logs by timestamp
    logs.sort(key=lambda x: x.timestamp, reverse=False)

    for log in logs:
        service = log.container.labels.get('service', None)
        # Example: 2015-11-12 16:39:48.531292+00:00 service:foobar [alpine]: hello
        #2015-11-12 16:39:48.531292+00:00 service:foobar image:alpine [containerId]: hello
        syslog.send('{time} service:{service} image:{image} [{id}]: {message}'.format(
            time=log.timestamp,
            service=service,
            image=log.container.image,
            message=log.message,
            id=log.container.id[:8]
        ))


def parse_logs(log_binary, container):
    logs = []
    if log_binary:
        log = log_binary.decode('utf-8')
        logs_str = log.split('\r\n')
        for str in logs_str:
            if not str:
                continue
            regex = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.]\d+Z) (.*)',
                             str)
            timestamp = parser.parse(regex.group(1))
            logs.append(Log(timestamp=timestamp, message=regex.group(2),
                            container=container))

    return logs


def run():
    while True:
        get_containers()
        logs = get_all_logs()
        stream_logs(logs)

        time.sleep(4)