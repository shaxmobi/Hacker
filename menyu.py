# main.py
import socket

HOST = '0.0.0.0'
PORT = 4444

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(1)

print(f"[+] Listening on {HOST}:{PORT} ...")

conn, addr = s.accept()
print(f"[+] Connection from {addr}")

while True:
    command = input(">> ")
    conn.send(command.encode())
    data = conn.recv(1024).decode()
    print(data)