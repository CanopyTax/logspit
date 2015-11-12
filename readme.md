# Logspit

This is a docker image that is a conceptual fork of [logspout](https://github.com/gliderlabs/logspout)

Logspout is much more featured and is written in golang. This container is written in python and is useful for a specific usecase: sending logs to a remote UDP location.

Logspit grabs logs from all your containers, then sends them to a host listening on a UDP port. It is that simple. Logspit was designed to be used with papertrail or sumo-logic. 
You do not have to change your log handler or anything, logspit will just grab all logs from all labeled containers.

In order for logspit to work, your containers must have the `service` label. Logspit ignores all other containers.
For example, if I wanted to run a redis container I could run the following to give it a label.

    docker run -d --label service=redis redis
    
The idea behind this is that in production environments, the name of the containers is often random. But you can add labels to your containers to represent which service it is running.

## Using

Logspit needs access to the docker socket in order to get container logs. You can start up logspit using

    docker run -d -v /var/run/docker.sock:/var/run/docker.sock canopytax/logspit
    
You can set the environment variable `SYSLOG_HOST` and `SYSLOG_PORT` to specify the host name and port that logspit will push too.

## Sumo Logic

You can use this container in conjunction with sumo logic's collection container to push logs to sumo logic.

    docker run -d -p 514:514 -p 514:514/udp --name="sumo-logic" -e SUMO_ACCESS_ID=[your_id_here] -e SUMO_ACCESS_KEY=[your_key_here] -e SUMO_COLLECTOR_NAME=test sumologic/collector:latest-syslog
    docker run -d -v /var/run/docker.sock:/var/run/docker.sock -e SYSLOG_HOST sumo --link sumo-logic:sumo canopytax/logspit
    

## Papertrail

You can use this container to send logs to papertrails syslog listener

    docker run -d -v /var/run/docker.sock:/var/run/docker.sock -e SYSLOG_HOST your.papertail.url.here -e SYSLOG_PORT [your_port_here] sumo-logic:sumo canopytax/logspit



## Testing

You can also add the environment variable `DEBUG=True` is you would like to make sure the container is working. 
The debug flag just makes the container print out the logs as well as send them to the remote host. So, you can use the flag to see an aggregate of all your logs in this containers logs.

