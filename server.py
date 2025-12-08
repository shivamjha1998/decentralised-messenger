import socket
import threading

# Connection Data
HOST = '127.0.0.1'  # Localhost
PORT = 12345        # Random non-privileged port

# Starting the Server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()

# Lists to manage connections
clients = []
nicknames = []

def broadcast(message):
    """Sends a message to all connected clients."""
    for client in clients:
        try:
            client.send(message)
        except:
            # If the link is broken, remove the client
            index = clients.index(client)
            clients.remove(client)
            client.close()
            nickname = nicknames[index]
            broadcast(f'{nickname} left!'.encode('ascii'))
            nicknames.remove(nickname)
            break

def handle(client):
    """Handles an individual client connection loop."""
    while True:
        try:
            # Receive message from client
            message = client.recv(1024)
            broadcast(message)
        except:
            # Remove client on error
            if client in clients:
                index = clients.index(client)
                clients.remove(client)
                client.close()
                nickname = nicknames[index]
                broadcast(f'{nickname} left!'.encode('ascii'))
                nicknames.remove(nickname)
            break

def receive():
    """Main function to accept new connections."""
    print(f"Server is listening on {HOST}:{PORT}...")
    while True:
        # Accept Connection
        client, address = server.accept()
        print(f"Connected with {str(address)}")

        # Request Nickname
        client.send('NICK'.encode('ascii'))
        nickname = client.recv(1024).decode('ascii')
        nicknames.append(nickname)
        clients.append(client)

        print(f"Nickname is {nickname}")
        broadcast(f"{nickname} joined!".encode('ascii'))
        client.send('Connected to server!'.encode('ascii'))

        # Start Handling Thread for Client
        thread = threading.Thread(target=handle, args=(client,))
        thread.start()

if __name__ == "__main__":
    receive()
