import socket
import json
import threading
import datetime
import time
import cv2
import numpy as np
import os 


TCP_HOST = '0.0.0.0'
TCP_PORT = 4000


UDP_HOST = '0.0.0.0' 
UDP_VIDEO_SERVER_PORT = 5000 

MAX_UDP_PACKET_SIZE = 65000 
FPS = 30 
FRAME_DELAY = 1.0 / FPS


HOST_IP = '192.168.100.199' 


ANNOUNCEMENTS_FILE = 'announcements.json'  


announcements = []
connected_tcp_clients = {} 
tcp_clients_lock = threading.Lock()
announcements_lock = threading.Lock()


chat_history = [] 
chat_history_lock = threading.Lock()

active_udp_clients = {}
udp_clients_lock = threading.Lock() 

video_capture_object = None 
video_mode_active = False


stop_server_event = threading.Event()


# File Storage Functions for Announcements


def load_announcements_from_file():
    """Loads announcements from file into memory, sorted by timestamp (latest first)."""
    global announcements
    
    if not os.path.exists(ANNOUNCEMENTS_FILE):
        print(f"Announcements file '{ANNOUNCEMENTS_FILE}' not found. Starting with empty announcements.")
        announcements = []
        return
    
    try:
        with open(ANNOUNCEMENTS_FILE, 'r', encoding='utf-8') as f:
            loaded_announcements = json.load(f)
            

        valid_announcements = []
        for ann in loaded_announcements:
            if isinstance(ann, dict) and 'timestamp' in ann and 'message' in ann:
                valid_announcements.append(ann)
            else:
                print(f"Warning: Invalid announcement format found: {ann}")
        

        valid_announcements.sort(key=lambda x: x['timestamp'], reverse=True)
        
        with announcements_lock:
            announcements = valid_announcements
            
        print(f"Loaded {len(announcements)} announcements from '{ANNOUNCEMENTS_FILE}'")
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in announcements file '{ANNOUNCEMENTS_FILE}': {e}")
        print("Starting with empty announcements.")
        announcements = []
    except Exception as e:
        print(f"Error loading announcements from file '{ANNOUNCEMENTS_FILE}': {e}")
        print("Starting with empty announcements.")
        announcements = []

def save_announcements_to_file():
    """Saves current announcements to file."""
    try:
        if os.path.exists(ANNOUNCEMENTS_FILE):
            backup_file = f"{ANNOUNCEMENTS_FILE}.backup"
            try:
                os.rename(ANNOUNCEMENTS_FILE, backup_file)
            except OSError:
                pass  
        
        with announcements_lock:
            announcements_copy = announcements.copy()
        
        with open(ANNOUNCEMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(announcements_copy, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(announcements_copy)} announcements to '{ANNOUNCEMENTS_FILE}'")
        
    except Exception as e:
        print(f"Error saving announcements to file '{ANNOUNCEMENTS_FILE}': {e}")

def add_announcement_and_save(announcement):
    """Adds a new announcement to memory and saves to file."""
    with announcements_lock:
        announcements.insert(0, announcement)
    
    save_announcements_to_file()


# TCP Announcement and Chat Server Functions


def handle_tcp_client(client_socket, addr):
    """Handles a single TCP client connection for announcements and chat."""
    print(f"TCP Server: Client connected from: {addr}")

    with tcp_clients_lock:
        connected_tcp_clients[addr] = client_socket
    

    client_socket.settimeout(1.0) 

    try:

        with announcements_lock:
            if announcements:
                initial_message = json.dumps({
                    "type": "loadOldAnnouncements",
                    "payload": announcements
                })
                try:
                    client_socket.sendall(initial_message.encode('utf-8') + b'\n')
                except socket.error as e:
                    print(f"TCP Server: Error sending initial announcements to {addr}: {e}")
                    return 

        with chat_history_lock:
            if chat_history:
                initial_chat_message = json.dumps({
                    "type": "loadOldChatMessages",
                    "payload": chat_history
                })
                try:
                    client_socket.sendall(initial_chat_message.encode('utf-8') + b'\n')
                except socket.error as e:
                    print(f"TCP Server: Error sending initial chat history to {addr}: {e}")

        
        buffer = b'' 
        while not stop_server_event.is_set():
            try:
                data = client_socket.recv(4096) 
                if not data:
                    print(f"TCP Server: Client {addr} disconnected gracefully.")
                    break 

                buffer += data
                while b'\n' in buffer:
                    message_bytes, buffer = buffer.split(b'\n', 1)
                    message_str = message_bytes.decode('utf-8').strip()
                    print(f"TCP Server: Received from {addr}: {message_str}")

                    try:
                        message = json.loads(message_str)
                        msg_type = message.get("type")
                        msg_payload = message.get("payload")

                        if msg_type == "createAnnouncement":
                            if addr[0] == HOST_IP: 
                                announcement_text = msg_payload.get("message")
                                if announcement_text and announcement_text.strip():
                                    new_announcement = {
                                        "id": str(datetime.datetime.now()),
                                        "message": announcement_text.strip(),
                                        "timestamp": datetime.datetime.now().isoformat()
                                    }
                                    
                                    add_announcement_and_save(new_announcement)
                                    
                                    print(f"TCP Server: New announcement created by host {addr}: {new_announcement['message']}")
                                    broadcast_message("newAnnouncement", new_announcement)
                                else:
                                    error_msg = json.dumps({
                                        "type": "announcementError",
                                        "payload": {"message": "Announcement message cannot be empty."}
                                    })
                                    client_socket.sendall(error_msg.encode('utf-8') + b'\n')
                            else:
                                error_msg = json.dumps({
                                    "type": "announcementError",
                                    "payload": {"message": "Only the designated host can create announcements."}
                                })
                                client_socket.sendall(error_msg.encode('utf-8') + b'\n')

                        elif msg_type == "chatMessage":
                            chat_text = msg_payload.get("message")
                            sender_id = msg_payload.get("sender_id", f"UnknownClient-{addr[1]}") 
                            if chat_text and chat_text.strip():
                                new_chat_message = {
                                    "sender": sender_id,
                                    "message": chat_text.strip(),
                                    "timestamp": datetime.datetime.now().isoformat()
                                }

                                with chat_history_lock:
                                    chat_history.append(new_chat_message)
                                
                                print(f"TCP Server: New chat message from {sender_id} ({addr}): {new_chat_message['message']}")
                                broadcast_message("chatMessage", new_chat_message)
                            else:

                                pass 

                        else:
                            error_msg = json.dumps({
                                "type": "serverError", 
                                "payload": {"message": f"Unknown message type: {msg_type}."}
                            })
                            client_socket.sendall(error_msg.encode('utf-8') + b'\n')

                    except json.JSONDecodeError:
                        print(f"TCP Server: Invalid JSON from {addr}: {message_str}")
                        error_msg = json.dumps({
                            "type": "serverError",
                            "payload": {"message": "Invalid JSON format."}
                        })
                        client_socket.sendall(error_msg.encode('utf-8') + b'\n')
                    except socket.error as e: 
                        print(f"TCP Server: Socket error sending response to {addr}: {e}")
                        break
                    except Exception as e:
                        print(f"TCP Server: Error processing message from {addr}: {e}")
                        error_msg = json.dumps({
                            "type": "serverError",
                            "payload": {"message": f"Server error: {e}"}
                        })
                        client_socket.sendall(error_msg.encode('utf-8') + b'\n')

            except socket.timeout:
                continue 
            except socket.error as e:
                print(f"TCP Server: Socket error with client {addr}: {e}")
                break
            except Exception as e:
                print(f"TCP Server: Unhandled error in client receive loop for {addr}: {e}")
                break

    except Exception as e:
        print(f"TCP Server: Unexpected error handling client {addr}: {e}")
    finally:
        print(f"TCP Server: Closing connection for client: {addr}")
        with tcp_clients_lock:
            if addr in connected_tcp_clients:
                del connected_tcp_clients[addr]
        try:
            client_socket.shutdown(socket.SHUT_RDWR)
            client_socket.close()
        except OSError as e:
            print(f"TCP Server: Error during socket shutdown/close for {addr}: {e}")

def broadcast_message(message_type, payload, exclude_sender_addr=None):
    """Sends a message to all connected TCP clients, optionally excluding one."""
    message = json.dumps({"type": message_type, "payload": payload}) + '\n'
    encoded_message = message.encode('utf-8')

    clients_to_remove = []
    with tcp_clients_lock:
        current_clients = list(connected_tcp_clients.items())

    for addr, client_socket in current_clients:
        if exclude_sender_addr and addr == exclude_sender_addr:
            continue 

        try:
            client_socket.sendall(encoded_message)
        except socket.error as e:
            print(f"TCP Server: Error sending to client {addr}: {e}")
            clients_to_remove.append(addr)
        except Exception as e:
            print(f"TCP Server: Unexpected error sending to client {addr}: {e}")
            clients_to_remove.append(addr)

    with tcp_clients_lock:
        for addr_to_remove in clients_to_remove:
            if addr_to_remove in connected_tcp_clients:
                sock = connected_tcp_clients.pop(addr_to_remove)
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                    print(f"TCP Server: Removed and closed problematic client socket for {addr_to_remove}")
                except OSError as e:
                    print(f"TCP Server: Error closing problematic socket for {addr_to_remove}: {e}")

    print(f"TCP Server: Broadcasted '{message_type}' to {len(connected_tcp_clients)} clients (excluding sender if applicable).")

def tcp_announcement_listener():
    """Listens for new TCP client connections for announcements and chat."""
    tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_server_socket.bind((TCP_HOST, TCP_PORT))
    tcp_server_socket.listen(5)
    tcp_server_socket.settimeout(1.0) 

    print(f"TCP Server: Listening for announcements and chat on {TCP_HOST}:{TCP_PORT}")

    while not stop_server_event.is_set():
        try:
            client_socket, addr = tcp_server_socket.accept()
            client_handler_thread = threading.Thread(target=handle_tcp_client, args=(client_socket, addr), daemon=True)
            client_handler_thread.start()
        except socket.timeout:
            continue 
        except Exception as e:
            if not stop_server_event.is_set():
                print(f"TCP Server: Error accepting connection: {e}")
            break

    if tcp_server_socket:
        try:
            tcp_server_socket.close()
        except OSError as e:
            print(f"TCP Server: Error closing TCP listening socket: {e}")
    print("TCP Server: Listener thread exited.")


def udp_handshake_listener():
    """Listens for initial UDP 'hello' messages from clients to discover their addresses."""
    handshake_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    handshake_socket.bind((UDP_HOST, UDP_VIDEO_SERVER_PORT)) 
    handshake_socket.settimeout(0.5)
    print(f"UDP Handshake Listener: Listening for client 'hello' on {UDP_HOST}:{UDP_VIDEO_SERVER_PORT}")

    while not stop_server_event.is_set():
        try:
            data, addr = handshake_socket.recvfrom(1024) 
            message = data.decode('utf-8').strip()
            if message == "VIDEO_HELLO":

                with udp_clients_lock:
                    active_udp_clients[addr] = time.time() 
        except socket.timeout:
            pass 
        except Exception as e:
            if not stop_server_event.is_set():
                print(f"UDP Handshake Listener: Error: {e}")
    
    if handshake_socket:
        try:
            handshake_socket.close()
        except OSError as e:
            print(f"UDP Handshake Listener: Error closing handshake socket: {e}")
    print("UDP Handshake Listener: Thread exited.")


def video_stream_server_udp():
    """Streams video frames over UDP to all known active clients."""
    udp_sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"UDP Video Server: Preparing to stream video...")

    global video_capture_object, video_mode_active
    
    video_file_path = 'C:\\Users\\abdul\\Videos\\Captures\\sample_video.mp4' 

    video_capture_object = cv2.VideoCapture(video_file_path)

    if not video_capture_object.isOpened():
        print(f"Error: Could not open video file: {video_file_path}. Video streaming disabled.")
        video_mode_active = False
    else:
        video_mode_active = True
        print(f"UDP Video Server: Streaming from video file: {video_file_path}")

    frame_id = 0
    try:
        while not stop_server_event.is_set() and video_mode_active:
            start_time = time.time()
            ret, frame = video_capture_object.read()
            if not ret:
                print("UDP Video Server: End of video stream or failed to read frame. Looping video.")
                video_capture_object.set(cv2.CAP_PROP_POS_FRAMES, 0) 
                ret, frame = video_capture_object.read()
                if not ret: 
                    print("UDP Video Server: Failed to read frame after seeking. Exiting video stream thread.")
                    break

            ret, encoded_image = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ret:
                print("UDP Video Server: Failed to encode frame to JPEG.")
                continue

            frame_data = encoded_image.tobytes()
            data_size = len(frame_data)

            num_packets = (data_size + MAX_UDP_PACKET_SIZE - 1) // MAX_UDP_PACKET_SIZE

            current_udp_clients = []
            with udp_clients_lock:
                clients_to_remove = [addr for addr, last_contact in active_udp_clients.items() if time.time() - last_contact > 10]
                for addr_to_remove in clients_to_remove:
                    del active_udp_clients[addr_to_remove]
                    print(f"UDP Video Server: Removed inactive client: {addr_to_remove}")
                current_udp_clients = list(active_udp_clients.keys()) 

            if not current_udp_clients:
                time.sleep(0.1) 
                continue 

            for i in range(num_packets):
                header = frame_id.to_bytes(4, 'big') + i.to_bytes(2, 'big') + num_packets.to_bytes(2, 'big')
                
                packet_start = i * MAX_UDP_PACKET_SIZE
                packet_end = min((i + 1) * MAX_UDP_PACKET_SIZE, data_size)
                packet_data = frame_data[packet_start:packet_end]
                
                packet = header + packet_data
                
                for client_addr in current_udp_clients:
                    try:
                        udp_sender_socket.sendto(packet, client_addr)
                    except socket.error as e:
                        print(f"UDP Video Server: Error sending to {client_addr}: {e}")

            frame_id += 1

            elapsed_time = time.time() - start_time
            if elapsed_time < FRAME_DELAY:
                time.sleep(FRAME_DELAY - elapsed_time)
        
        if not video_mode_active:
            print("UDP Video Server: Video streaming is not active (e.g., file not found).")

    except Exception as e:
        print(f"UDP Video Server: Streaming error: {e}")
    finally:
        if video_capture_object and video_capture_object.isOpened():
            video_capture_object.release()
        if udp_sender_socket:
            try:
                udp_sender_socket.close()
            except OSError as e:
                print(f"UDP Video Server: Error closing sender socket: {e}")
        print("UDP Video Server: Stream thread exited.")



# Main Server Execution


def main_server():
    print("Starting Combined Server...")
    
    load_announcements_from_file()

    tcp_thread = threading.Thread(target=tcp_announcement_listener, daemon=True)
    tcp_thread.start()

    udp_handshake_thread = threading.Thread(target=udp_handshake_listener, daemon=True)
    udp_handshake_thread.start()

    udp_stream_thread = threading.Thread(target=video_stream_server_udp, daemon=True)
    udp_stream_thread.start()

    print("Combined Server is running. Press Ctrl+C to stop.")

    try:
        while not stop_server_event.is_set():
            time.sleep(0.5) 
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Initiating server shutdown.")
    finally:
        stop_server_event.set() 
        
        print("Saving announcements before shutdown...")
        save_announcements_to_file()
        
        print("Waiting for server threads to finish...")
        tcp_thread.join(timeout=2.0)
        udp_handshake_thread.join(timeout=2.0)
        udp_stream_thread.join(timeout=2.0)
        print("All server threads stopped. Server exited.")

if __name__ == "__main__":
    main_server()