#!/usr/bin/env python3
import socket
import threading
import select
import signal
import sys
import time
import getopt

# Listen
LISTENING_ADDR = '0.0.0.0'
LISTENING_PORT = int(sys.argv[1])

# Pass
PASS = ''

# CONST
BUFLEN = 4096 * 4
TIMEOUT = 60
DEFAULT_HOST = '127.0.0.1:1194'
RESPONSE = (
    'HTTP/1.1 101 <b><u><font color="blue">Script By Virtual t.me/Virtual_NW</font></b>\r\n'
    'Content-Length: 104857600000\r\n\r\n'
)


class Server(threading.Thread):
    def __init__(self, host, port):
        super().__init__()
        self.running = False
        self.host = host
        self.port = port
        self.threads = []
        self.threadsLock = threading.Lock()
        self.logLock = threading.Lock()

    def run(self):
        self.soc = socket.socket(socket.AF_INET)
        self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.soc.settimeout(2)
        self.soc.bind((self.host, self.port))
        self.soc.listen(0)
        self.running = True

        try:
            while self.running:
                try:
                    c, addr = self.soc.accept()
                    c.setblocking(1)
                except socket.timeout:
                    continue

                conn = ConnectionHandler(c, self, addr)
                conn.start()
                self.addConn(conn)
        finally:
            self.running = False
            self.soc.close()

    def printLog(self, log):
        with self.logLock:
            print(log)

    def addConn(self, conn):
        with self.threadsLock:
            if self.running:
                self.threads.append(conn)

    def removeConn(self, conn):
        with self.threadsLock:
            if conn in self.threads:
                self.threads.remove(conn)

    def close(self):
        self.running = False
        with self.threadsLock:
            threads = list(self.threads)
            for c in threads:
                c.close()


class ConnectionHandler(threading.Thread):
    def __init__(self, socClient, server, addr):
        super().__init__()
        self.clientClosed = False
        self.targetClosed = True
        self.client = socClient
        self.client_buffer = b''
        self.server = server
        self.log = f'Connection: {addr}'

    def close(self):
        if not self.clientClosed:
            try:
                self.client.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.client.close()
            self.clientClosed = True

        if not self.targetClosed:
            try:
                self.target.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.target.close()
            self.targetClosed = True

    def run(self):
        try:
            self.client_buffer = self.client.recv(BUFLEN)

            hostPort = self.findHeader(self.client_buffer, b'X-Real-Host')
            if hostPort == '':
                hostPort = DEFAULT_HOST

            split = self.findHeader(self.client_buffer, b'X-Split')
            if split != '':
                self.client.recv(BUFLEN)

            if hostPort != '':
                passwd = self.findHeader(self.client_buffer, b'X-Pass')
                if PASS and passwd == PASS:
                    self.method_CONNECT(hostPort)
                elif PASS and passwd != PASS:
                    self.client.send(b'HTTP/1.1 400 WrongPass!\r\n\r\n')
                elif hostPort.startswith('127.0.0.1') or hostPort.startswith('localhost'):
                    self.method_CONNECT(hostPort)
                else:
                    self.client.send(b'HTTP/1.1 403 Forbidden!\r\n\r\n')
            else:
                print('- No X-Real-Host!')
                self.client.send(b'HTTP/1.1 400 NoXRealHost!\r\n\r\n')

        except Exception as e:
            self.log += f' - error: {str(e)}'
            self.server.printLog(self.log)
        finally:
            self.close()
            self.server.removeConn(self)

    def findHeader(self, data, header):
        try:
            header_line = next((line for line in data.split(b'\r\n') if header in line), b'')
            if header_line:
                return header_line.split(b': ')[1].decode()
        except:
            pass
        return ''

    def connect_target(self, host):
        i = host.find(':')
        if i != -1:
            port = int(host[i + 1:])
            host = host[:i]
        else:
            port = int(LISTENING_PORT)

        infos = socket.getaddrinfo(host, port)[0]
        self.target = socket.socket(infos[0], infos[1], infos[2])
        self.targetClosed = False
        self.target.connect(infos[4])

    def method_CONNECT(self, path):
        self.log += ' - CONNECT ' + path
        self.connect_target(path)
        self.client.sendall(RESPONSE.encode())
        self.client_buffer = b''
        self.server.printLog(self.log)
        self.doCONNECT()

    def doCONNECT(self):
        socs = [self.client, self.target]
        count = 0
        while True:
            count += 1
            recv, _, err = select.select(socs, [], socs, 3)
            if err:
                break
            if recv:
                for in_ in recv:
                    try:
                        data = in_.recv(BUFLEN)
                        if data:
                            if in_ is self.target:
                                self.client.send(data)
                            else:
                                while data:
                                    sent = self.target.send(data)
                                    data = data[sent:]
                            count = 0
                        else:
                            return
                    except:
                        return
            if count == TIMEOUT:
                break


def print_usage():
    print('Usage: proxy.py -p <port>')
    print('       proxy.py -b <bindAddr> -p <port>')
    print('       proxy.py -b 0.0.0.0 -p 80')


def parse_args(argv):
    global LISTENING_ADDR
    global LISTENING_PORT
    try:
        opts, args = getopt.getopt(argv, "hb:p:", ["bind=", "port="])
    except getopt.GetoptError:
        print_usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print_usage()
            sys.exit()
        elif opt in ("-b", "--bind"):
            LISTENING_ADDR = arg
        elif opt in ("-p", "--port"):
            LISTENING_PORT = int(arg)


def main(host=LISTENING_ADDR, port=LISTENING_PORT):
    print("\n:-------PythonProxy-------:\n")
    print("Listening addr:", host)
    print("Listening port:", port)
    print(":-------------------------:\n")
    server = Server(host, port)
    server.start()
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        print('Stopping...')
        server.close()


if __name__ == '__main__':
    main()
