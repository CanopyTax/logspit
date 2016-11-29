__author__ = 'nhumrich'

import re
import time
from datetime import datetime, timedelta

from dateutil import parser
from docker import Client

from .streamers import syslog
from .objects import Container, Log

docker = Client(base_url='unix://var/run/docker.sock')

containers = dict()
last_timestamps = dict()
start_time = datetime.utcnow()


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
            last_time = logs[-1].timestamp.replace(tzinfo=None) \
                        + timedelta(seconds=1)
            last_timestamps[c.id] = last_time
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
        logs_str = log.split('\n')
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