import toml
import socket
from datetime import datetime
from pathlib import Path
from threading import Thread, Event
from errno import EADDRINUSE

sock = socket.socket()

try:
    sock.bind(('', 80))
    print("Using port 80")
except OSError:
    sock.bind(('', 8080))
    print("Using port 8080")


class Server:
    def __init__(self):
        self.sock = socket.socket()

        config = toml.load('config.toml')

        self.bufsize = config['bufsize']

        try:
            self.sock.bind(('', config['port']))
        except OSError as e:
            if e.errno == EADDRINUSE:
                print('port is not available, using a free port')
                self.sock.bind(('', 0))
            else:
                raise e

        self.log('server started')

        self.sock.listen()
        print(f'listening on port {self.sock.getsockname()[1]}')
        self.content_dir = Path(config['content_dir']).expanduser().resolve()

    def log(self, *values):
        with open('server.log', 'a') as f:
            print(*values, file=f)

    def handle_connection(self, conn, addr):
        requested_path = conn.recv(self.bufsize).decode().split()[1][1:]
        date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        content_type = b'text/html; charset=utf-8'
        status_code = b'200 OK'

        if requested_path:
            if not any(map(lambda x: x in requested_path,
                           ('.html', '.css', '.js', '.ico', '.jpg', '.jpeg'))):
                path = self.content_dir.joinpath('403.html').resolve()
                status_code = b'403 Forbidden'
            else:
                if '.ico' in requested_path:
                    content_type = b'image/x-icon'
                elif '.jpg' in requested_path or '.jpeg' in requested_path:
                    content_type = b'image/jpeg'
                path = self.content_dir.joinpath(requested_path).resolve()
                if not path.exists():
                    path = self.content_dir.joinpath('404.html').resolve()
                    status_code = b'404 Not Found'
                elif not path.is_relative_to(self.content_dir):
                    path = self.content_dir.joinpath('403.html').resolve()
                    status_code = b'403 Forbidden'
        else:
            requested_path = 'index.html'
            path = self.content_dir.joinpath(requested_path).resolve()

        self.log(date + '. ' + addr[0] + ' ' +
                 requested_path + ' ' + status_code.decode())

        with open(path, 'rb') as f:
            content = f.read()
            conn.sendall(b'HTTP/1.1 ' + status_code + b'''\
Connection: close
Content-Length: ''' + str(len(content)).encode() + b'''
Content-Type: ''' + content_type + b'''
Date: ''' + date.encode() + b'''
Server: SelfMadeServer v0.0.1

''' + content)

        conn.close()

    def accept_loop(self):
        self.exit_event = Event()
        self.pause_event = Event()
        self.pause_event.set()
        self.sock.settimeout(1)
        while not self.exit_event.is_set():
            self.pause_event.wait()
            try:
                conn, addr = self.sock.accept()
            except TimeoutError:
                continue
            self.log(f'connected client {addr}')
            Thread(target=self.handle_connection, args=[conn, addr]).start()

    def input_loop(self):
        while True:
            command = input('> ')
            if command == 'exit':
                self.exit_event.set()
                return
            elif command == 'pause':
                self.pause_event.clear()
            elif command == 'unpause':
                self.pause_event.set()
            elif command == 'show-logs':
                with open('server.log') as f:
                    print(f.read())
            elif command == 'clear-logs':
                open('server.log', 'w').close()
            else:
                print('unknown command')


def main():
    server = Server()
    Thread(target=server.accept_loop).start()
    server.input_loop()


if __name__ == '__main__':
    main()
