#!/usr/bin/env python3
import socket
import threading
import select
import sys
import time
import getopt

# Listen
LISTENING_ADDR = '127.0.0.1'
LISTENING_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 700

# Pass
PASS = ''

# CONST
BUFLEN = 4096 * 4
TIMEOUT = 60
DEFAULT_HOST = '127.0.0.1:69'
RESPONSE = b'HTTP/1.1 101 Script By Virtual\r\n\r\n'

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
        self.soc.bind((self.host, int(self.port)))
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
            hostPort = self.findHeader(self.client_buffer.decode(), 'X-Real-Host')

            if hostPort == '':
                hostPort = DEFAULT_HOST

            split = self.findHeader(self.client_buffer.decode(), 'X-Split')
            if split != '':
                self.client.recv(BUFLEN)

            if hostPort:
                passwd = self.findHeader(self.client_buffer.decode(), 'X-Pass')
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

    def findHeader(self, head, header):
        aux = head.find(header + ': ')
        if aux == -1:
            return ''
        aux = head.find(':', aux)
        head = head[aux + 2:]
        aux = head.find('\r\n')
        return head[:aux] if aux != -1 else ''

    def connect_target(self, host):
        i = host.find(':')
        port = int(host[i + 1:]) if i != -1 else (443 if hasattr(self, 'method') and self.method == 'CONNECT' else int(LISTENING_PORT))
        host = host[:i] if i != -1 else host
        addrinfo = socket.getaddrinfo(host, port)[0]
        self.target = socket.socket(addrinfo[0], addrinfo[1], addrinfo[2])
        self.target.connect(addrinfo[4])
        self.targetClosed = False

    def method_CONNECT(self, path):
        self.log += f' - CONNECT {path}'
        self.connect_target(path)
        self.client.sendall(RESPONSE)
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
                return


def print_usage():
    print('Usage: proxy.py -p <port>')
    print('       proxy.py -b <bindAddr> -p <port>')
    print('       proxy.py -b 0.0.0.0 -p 80')

def parse_args(argv):
    global LISTENING_ADDR
    global LISTENING_PORT
    try:
        opts, _ = getopt.getopt(argv, "hb:p:", ["bind=", "port="])
        for opt, arg in opts:
            if opt == '-h':
                print_usage()
                sys.exit()
            elif opt in ("-b", "--bind"):
                LISTENING_ADDR = arg
            elif opt in ("-p", "--port"):
                LISTENING_PORT = int(arg)
    except getopt.GetoptError:
        print_usage()
        sys.exit(2)

def main():
    print("\n:-------PythonProxy-------:\n")
    print("Listening addr:", LISTENING_ADDR)
    print("Listening port:", LISTENING_PORT)
    print(":-------------------------:\n")
    server = Server(LISTENING_ADDR, LISTENING_PORT)
    server.start()
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        print('Stopping...')
        server.close()

if __name__ == '__main__':
    parse_args(sys.argv[1:])
    main()
