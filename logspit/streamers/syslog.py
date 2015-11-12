__author__ = 'nhumrich'
import os
import socket

syslog_host = os.getenv('SYSLOG_HOST', 'localhost')
syslog_port = os.getenv('SYSLOG_PORT', 514)
debug = os.getenv('DEBUG', 'False')


def send(log):
    if isinstance(log, str):
        log = log.encode('utf-8')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(log, (syslog_host, syslog_port))

    if bool(debug):
        print(log)


# if __name__ == "__main__":
#     send('this is a python test')
