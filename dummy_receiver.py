import socket

server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", 5000))
server.listen()
server.settimeout(1)
print("Dummy receiver waiting on port 5000... (press Ctrl+C to stop)")
while True:
    try:
        conn, _ = server.accept()
    except socket.timeout:
        continue
    with conn:
        data = conn.recv(4096)
    print(len(data), "bytes:", data.hex())