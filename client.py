import socket
import threading
import rsa

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

# 1. GENERATE KEYS
# We generate a private key (for us to keep) and public key (to share)
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
public_key = private_key.public_key()

# Convert public key to PEM format (bytes) so we can send it over the network
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# A placeholder to store the OTHER person's public key
partner_public_key = None

nickname = input("Choose your nickname: ")

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('127.0.0.1', 12345))

def receive():
    global partner_public_key
    while True:
        try:
            # We receive raw bytes from the server
            message = client.recv(4096) # Increased buffer size for keys
            
            # CASE A: Server asking for Nickname
            if message == b'NICK':
                client.send(nickname.encode('ascii'))
            
            # CASE B: Receiving a Public Key (This is a simplified exchange)
            elif b'-----BEGIN PUBLIC KEY' in message:
                # In a real app, we'd map this key to a specific user.
                print("Received a Public Key from partner!")
                partner_public_key = serialization.load_pem_public_key(message)
                
            # CASE C: Receiving an Encrypted Message
            else:
                # If we have the private key, we try to decrypt it
                try:
                    decrypted_message = private_key.decrypt(
                        message,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None
                        )
                    )
                    print(f"Decrypted: {decrypted_message.decode('ascii')}")
                except:
                    # If decryption fails, it might be a server system message
                    print(f"System/Unencrypted: {message.decode('ascii', errors='ignore')}")

        except Exception as e:
            print(f"An error occurred: {e}")
            client.close()
            break

def write():
    # FIRST ACTION: Broadcast our Public Key so others can find us
    import time
    time.sleep(1)
    client.send(public_pem)

    while True:
        msg_content = input("")

        if partner_public_key:
            # Encrypt the message using the PARTNER'S Public Key
            ciphertext = partner_public_key.encrypt(
                msg_content.encode('ascii'),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            client.send(ciphertext)
        else:
            print("No partner key found yet. Message sent in plaintext (or wait for key).")

# Threads
receive_thread = threading.Thread(target=receive)
receive_thread.start()

write_thread = threading.Thread(target=write)
write_thread.start()
