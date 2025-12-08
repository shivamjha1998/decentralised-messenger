import socket
import threading
import json
import sys
import time

# --- CONFIGURATION ---
# We will use the Port number as the "ID" of the node for simplicity.
# In a real DHT (Kademlia), this would be a long SHA-256 hash.

class DHTNode:
    def __init__(self, host, port, bootstrap_node=None):
        self.host = host
        self.port = port
        self.id = port # Simplified ID
        self.peers = [] # List of known neighbors: {'id': 123, 'host': '...', 'port': 123}
        self.data_store = {} # The storage for this node
        
        # Start the listener
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen()
        
        print(f"[*] Node started at {self.host}:{self.port} (ID: {self.id})")

        # Start listening thread
        threading.Thread(target=self.listen).start()
        
        # If we have a bootstrap node (an entry point), connect to it
        if bootstrap_node:
            self.connect_to_network(bootstrap_node)

    def listen(self):
        """ Listens for incoming requests from other nodes """
        while True:
            client, addr = self.server.accept()
            threading.Thread(target=self.handle_client, args=(client,)).start()

    def handle_client(self, client):
        """ Handles the JSON messages """
        try:
            data = client.recv(1024).decode('utf-8')
            msg = json.loads(data)
            
            command = msg.get('type')
            
            if command == 'JOIN':
                # A new node wants to join. We add them and give them our peers.
                new_peer = msg.get('node')
                self.add_peer(new_peer)
                # Send back our list of peers so they can expand their network
                response = {'type': 'PEERS', 'peers': self.peers + [{'id': self.id, 'host': self.host, 'port': self.port}]}
                client.send(json.dumps(response).encode('utf-8'))
                
            elif command == 'STORE':
                # Request to store data
                key = int(msg.get('key'))
                value = msg.get('value')
                print(f"[*] Received STORE request for Key {key}")
                self.handle_store(key, value)
                
            elif command == 'RETRIEVE':
                # Request to find data
                key = int(msg.get('key'))
                print(f"[*] Received RETRIEVE request for Key {key}")
                result = self.handle_retrieve(key)
                client.send(json.dumps({'result': result}).encode('utf-8'))
                
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client.close()

    # --- CORE DHT LOGIC ---

    def distance(self, k1, k2):
        """ Calculates distance between two IDs (Simple absolute difference) """
        return abs(k1 - k2)

    def find_closest_peer(self, key):
        """ Finds the peer in our list who is 'closest' to the target Key """
        if not self.peers:
            return None
        
        # Sort peers by distance to the key
        best_peer = min(self.peers, key=lambda p: self.distance(p['id'], key))
        return best_peer

    def handle_store(self, key, value):
        """ Decide: Do I store this? Or do I forward it? """
        # Am I the closest node to this Key?
        closest_peer = self.find_closest_peer(key)
        
        # If I am closer than my closest peer, or I have no peers, I keep it.
        my_dist = self.distance(self.id, key)
        peer_dist = self.distance(closest_peer['id'], key) if closest_peer else float('inf')
        
        if my_dist <= peer_dist:
            print(f"[!] I am closest. Storing Key {key} = {value}")
            self.data_store[key] = value
        else:
            print(f"[->] Forwarding STORE {key} to Node {closest_peer['id']}")
            self.send_msg(closest_peer, {'type': 'STORE', 'key': key, 'value': value})

    def handle_retrieve(self, key):
        """ Decide: Do I have this? Or do I ask someone else? """
        if key in self.data_store:
            print(f"[!] Found Key {key} in local storage.")
            return self.data_store[key]
        
        closest_peer = self.find_closest_peer(key)
        my_dist = self.distance(self.id, key)
        peer_dist = self.distance(closest_peer['id'], key) if closest_peer else float('inf')

        if my_dist <= peer_dist:
            # If I should have it but don't, it doesn't exist
            return "NOT FOUND"
        else:
            # Forward the question to the closer node
            print(f"[->] Forwarding RETRIEVE {key} to Node {closest_peer['id']}")
            response = self.send_msg(closest_peer, {'type': 'RETRIEVE', 'key': key}, wait_response=True)
            return response.get('result')

    # --- NETWORKING HELPERS ---

    def connect_to_network(self, bootstrap_node):
        """ Initial handshake to join the network """
        print(f"[*] Contacting bootstrap node {bootstrap_node}...")
        host, port = bootstrap_node
        # Send a Hello message
        response = self.send_msg({'host': host, 'port': port}, 
                                 {'type': 'JOIN', 'node': {'id': self.id, 'host': self.host, 'port': self.port}},
                                 wait_response=True)
        if response and 'peers' in response:
            for p in response['peers']:
                self.add_peer(p)

    def add_peer(self, peer):
        # Add peer if not already known and not self
        if peer['id'] != self.id and not any(p['id'] == peer['id'] for p in self.peers):
            self.peers.append(peer)
            print(f"[*] Added new peer: Node {peer['id']}")

    def send_msg(self, target, msg, wait_response=False):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((target['host'], target['port']))
            client.send(json.dumps(msg).encode('utf-8'))
            
            response = None
            if wait_response:
                response = json.loads(client.recv(1024).decode('utf-8'))
            
            client.close()
            return response
        except:
            print(f"[X] Failed to talk to Node {target.get('port')}")
            return None

    # --- USER INTERFACE ---
    def interact(self):
        time.sleep(1)
        while True:
            cmd = input(f"Node {self.id} >> ").split()
            if not cmd: continue
            
            if cmd[0] == "peers":
                print(f"Known Peers: {[p['id'] for p in self.peers]}")
            elif cmd[0] == "store":
                # usage: store 5050 "Hello"
                key = int(cmd[1])
                val = " ".join(cmd[2:])
                self.handle_store(key, val)
            elif cmd[0] == "get":
                # usage: get 5050
                key = int(cmd[1])
                print(f"Result: {self.handle_retrieve(key)}")
            elif cmd[0] == "mydata":
                print(self.data_store)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dht_node.py <MY_PORT> [BOOTSTRAP_PORT]")
        sys.exit(1)
        
    my_port = int(sys.argv[1])
    bootstrap_port = int(sys.argv[2]) if len(sys.argv) > 2 else None
    bootstrap_node = ('127.0.0.1', bootstrap_port) if bootstrap_port else None
    
    node = DHTNode('127.0.0.1', my_port, bootstrap_node)
    node.interact()
