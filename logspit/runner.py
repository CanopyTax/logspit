import os
import re
import asyncio

import aiohttp
from datetime import datetime
from dateutil import parser

from .streamers import syslog
from .objects import Container, Log

conn = aiohttp.UnixConnector(path='/var/run/docker.sock')
session = aiohttp.ClientSession(connector=conn)

ENV = os.getenv('ENV_NAME', 'local')

futures = dict()
last_timestamps = dict()
start_time = datetime.now()
loop = asyncio.get_event_loop()


def is_python_traceback(message):
    return re.match(r'^Traceback \(.*', message)


async def get_containers():
    containers = dict()
    async with session.get('http://docker.sock/containers/json') as resp:
        for container in await resp.json():
            await asyncio.sleep(0)  # play nice

            cid = container.get('Id')
            container = await inspect_container(cid)
            config = container.get('Config')
            image = config.get('Image')
            labels = config.get('Labels')

            containers[cid] = Container(image=image, id=cid, labels=labels)

    return containers


async def inspect_container(cid):
    url = 'http://docker.sock/containers/{}/json'
    async with session.get(url.format(cid)) as resp:
        return await resp.json()

async def get_logs(container, log_type):
    url = 'http://docker.sock/containers/{}/logs?follow=1&timestamps=1'  #todo add "since"
    if log_type == 'stdout':
        url += '&stderr=0&stdout=1'
    elif log_type == 'stderr':
        url += '&stderr=1&stdout=0'
    async with session.get(url.format(container.id)) as resp:
        if resp.status != 200:
            raise Exception('Bad call to docker. status:{status} '
                            'response:{response}'
                            .format(status=resp.status,
                                    response=await resp.text()))
        last_line = None
        traceback = None
        async for line in resp.content:
            line = line.decode('ISO-8859-1')
            log = parse_log(line)
            if re.match(r'^\s.*', log.message):
                future, message = last_line
                future.cancel()
                message += '\r\n' + log.message
            else:
                if traceback:
                    future, message = last_line
                    future.cancel()
                    message += '\r\n' + log.message
                    traceback = None
                else:
                    message = format_log(log, container, log_type)
                    if is_python_traceback(log.message):
                        traceback = message
            last_line = (loop.call_later(2, syslog.send, message), message)


async def stream_logs():
    while True:
        containers = await get_containers()
        for c in containers.values():
            if str(c.id) + 'stdout' not in futures \
                    and str(c.id) + 'stderr' not in futures:
                service = c.labels.get('service')
                if service is None:
                    # Do not log containers without a service label
                    continue

                stdout = asyncio.ensure_future(get_logs(c, 'stdout'))
                stderr = asyncio.ensure_future(get_logs(c, 'stderr'))
                futures[str(c.id) + 'stdout'] = stdout
                futures[str(c.id) + 'stderr'] = stderr

        # cleanup
        dead = []
        for key, future in futures.items():
            if future.done():
                dead.append(key)
                # print exceptions if there are any
                # this is really for dev purposes
                if future.exception():
                    raise future.exception()
        for k in dead:
            futures.pop(k)
        await asyncio.sleep(6)


def format_log(log, container, type):
    service = container.labels.get('service', None)
    return '{time} {env} [service:{service} image:{image} {id}] {type}: {message}'\
        .format(
            env=ENV,
            service=service,
            image=container.image,
            message=log.message,
            id=container.id[:8],
            type=type,
            time=log.timestamp
    )


def parse_log(log):
    if log:
        regex_string = r'.*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.]\d+Z) (.*)'
        regex = re.match(regex_string, log)
        timestamp = parser.parse(regex.group(1))
        return Log(timestamp=timestamp, message=regex.group(2))


def run():
    try:
        loop.run_until_complete(stream_logs())
    finally:
        session.close()
        loop.close()
