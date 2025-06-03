import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox
from tkinter import simpledialog  
import socket
import json
import threading
import datetime
import time
import cv2
import numpy as np
from collections import defaultdict
import sys 


TCP_HOST = '192.168.100.199' 
TCP_PORT = 4000

UDP_HOST = '0.0.0.0' 
UDP_SERVER_HOST = '192.168.100.199'
UDP_VIDEO_SERVER_PORT = 5000 
DEFAULT_UDP_VIDEO_CLIENT_PORT = 5001 

MAX_UDP_PACKET_SIZE = 65000
BUFFER_SIZE = 65536 

tcp_client_socket = None
tcp_connected = False

frame_buffers = defaultdict(dict) 
frame_total_packets = {}          
udp_data_lock = threading.Lock()  
last_displayed_frame_id = -1      
last_udp_hello_sent_time = 0      
LAST_UDP_ACTIVITY_CHECK_INTERVAL = 5 

stop_client_event = threading.Event()

class CombinedClient(tk.Tk):
    def __init__(self, udp_port, is_host=False): 
        super().__init__()
        self.udp_listen_port = udp_port 
        self.is_host = is_host 
        
        self.device_name = self._prompt_for_device_name()
        self.client_id = self.device_name  

        title_suffix = " (Host)" if self.is_host else ""
        self.title(f"Combined Client - {self.device_name} - Port {self.udp_listen_port}{title_suffix}")
        self.geometry("1400x900") 

        self.create_widgets()

        threading.Thread(target=self._tcp_connection_loop, daemon=True).start()
        threading.Thread(target=self._udp_receive_loop, daemon=True).start()
        
        self.after(10, self._process_buffered_frames)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        print("Client: Initialization complete.")

    def _prompt_for_device_name(self):
        """Prompts the user for a device name to use in chat."""

        temp_root = tk.Tk()
        temp_root.withdraw()
        
        while True:
            device_name = simpledialog.askstring(
                "Device Name", 
                "Enter a name for this device/client:",
                parent=temp_root
            )
            
            if device_name is None:  
                temp_root.destroy()
                sys.exit("Application cancelled by user.")
            
            device_name = device_name.strip()
            if device_name:
                temp_root.destroy()
                return device_name
            else:
                messagebox.showerror("Invalid Name", "Device name cannot be empty. Please try again.")

    def create_widgets(self):
        """Creates an enhanced UI with modern dark styling."""
        # Set global window styling with darker theme
        self.configure(bg="#1a1a1a")  
        
        # Create main container with padding
        main_container = tk.Frame(self, bg="#1a1a1a")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # Top panel for device info
        top_panel = tk.Frame(main_container, bg="#2d2d30", relief="solid", bd=1)
        top_panel.pack(fill="x", pady=(0, 15))
        
        device_info_label = tk.Label(
            top_panel,
            text=f"Device: {self.device_name} | Port: {self.udp_listen_port}" + (" | HOST" if self.is_host else " | CLIENT"),
            font=("Segoe UI", 12, "bold"),
            bg="#2d2d30",
            fg="#00d4aa" if self.is_host else "#4fc3f7",
            pady=10
        )
        device_info_label.pack()

        # Main content frame
        content_frame = tk.Frame(main_container, bg="#1a1a1a")
        content_frame.pack(fill="both", expand=True)

        # Left Panel - Announcements
        announcements_panel = tk.LabelFrame(
            content_frame,
            text="📢 Announcements",
            font=("Segoe UI", 12, "bold"),
            bg="#2d2d30",
            fg="#ffffff",
            padx=15,
            pady=15,
            relief="solid",
            bd=1,
            labelanchor="n"
        )
        announcements_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Status section with improved styling
        status_frame = tk.Frame(announcements_panel, bg="#2d2d30")
        status_frame.pack(fill="x", pady=(0, 10))
        
        status_title = tk.Label(
            status_frame,
            text="Connection Status",
            font=("Segoe UI", 10, "bold"),
            bg="#2d2d30",
            fg="#b3b3b3"
        )
        status_title.pack(anchor="w")
        
        self.tcp_status_label = tk.Label(
            status_frame,
            text="● Disconnected",
            fg="#ff6b6b",
            bg="#2d2d30",
            font=("Segoe UI", 10),
            anchor="w",
            padx=5,
            pady=5
        )
        self.tcp_status_label.pack(anchor="w")
        
        self.tcp_error_label = tk.Label(
            announcements_panel,
            text="",
            fg="#ff6b6b",
            bg="#2d2d30",
            font=("Segoe UI", 9),
            wraplength=350,
            justify="left"
        )
        self.tcp_error_label.pack(pady=(0, 10), anchor="w")

        # Admin section for announcements
        admin_frame = tk.LabelFrame(
            announcements_panel,
            text="✏️ Post Announcement",
            font=("Segoe UI", 10, "bold"),
            bg="#2d2d30",
            fg="#4fc3f7",
            padx=10,
            pady=10,
            relief="solid",
            bd=1
        )
        admin_frame.pack(pady=(0, 10), fill="x")
        
        self.announcement_input = scrolledtext.ScrolledText(
            admin_frame,
            height=4,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg="#3c3c3c",
            fg="#ffffff",
            insertbackground="#4fc3f7",
            relief="flat",
            bd=5,
            selectbackground="#4fc3f7",
            selectforeground="#ffffff"
        )
        self.announcement_input.pack(fill="x", pady=(0, 10))
        
        self.send_announcement_button = tk.Button(
            admin_frame,
            text="📤 Send Announcement",
            command=self.send_announcement_message,
            font=("Segoe UI", 10, "bold"),
            bg="#00d4aa",
            fg="#ffffff",
            activebackground="#00b894",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            pady=8
        )
        self.send_announcement_button.pack(fill="x")

        if not self.is_host:
            self.announcement_input.config(state='disabled', bg="#262626")
            self.send_announcement_button.config(
                state='disabled',
                text="🔒 Host Only",
                bg="#404040",
                activebackground="#404040",
                cursor="arrow"
            )
            no_host_msg = tk.Label(
                admin_frame,
                text="Only the host client can post announcements.",
                fg="#b3b3b3",
                bg="#2d2d30",
                font=("Segoe UI", 8, "italic")
            )
            no_host_msg.pack(pady=(5, 0))

        # Announcements feed
        announcements_feed_frame = tk.LabelFrame(
            announcements_panel,
            text="📋 Announcements Feed",
            font=("Segoe UI", 10, "bold"),
            bg="#2d2d30",
            fg="#4fc3f7",
            padx=10,
            pady=10,
            relief="solid",
            bd=1
        )
        announcements_feed_frame.pack(fill="both", expand=True)
        
        self.announcements_text = scrolledtext.ScrolledText(
            announcements_feed_frame,
            state='disabled',
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg="#3c3c3c",
            fg="#ffffff",
            relief="flat",
            bd=5,
            selectbackground="#4fc3f7",
            selectforeground="#ffffff"
        )
        self.announcements_text.pack(fill="both", expand=True)

        # Center Panel - Video
        video_panel = tk.LabelFrame(
            content_frame,
            text="🎥 Video Stream",
            font=("Segoe UI", 12, "bold"),
            bg="#2d2d30",
            fg="#ffffff",
            padx=15,
            pady=15,
            relief="solid",
            bd=1,
            labelanchor="n"
        )
        video_panel.pack(side="left", fill="both", expand=True, padx=10)

        self.video_status_label = tk.Label(
            video_panel,
            text=f"🔄 Listening on port {self.udp_listen_port}...",
            fg="#4fc3f7",
            bg="#2d2d30",
            font=("Segoe UI", 10, "bold")
        )
        self.video_status_label.pack(pady=(0, 10))
        
        self.video_error_label = tk.Label(
            video_panel,
            text="",
            fg="#ff6b6b",
            bg="#2d2d30",
            font=("Segoe UI", 9),
            wraplength=300,
            justify="center"
        )
        self.video_error_label.pack(pady=(0, 10))

        # Video preview frame
        video_preview_frame = tk.Frame(video_panel, bg="#3c3c3c", relief="sunken", bd=2)
        video_preview_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        video_instruction = tk.Label(
            video_preview_frame,
            text="📺 Video Stream\n\nVideo will appear in a separate OpenCV window\n\nPress 'Q' in the video window to quit",
            font=("Segoe UI", 11),
            bg="#3c3c3c",
            fg="#b3b3b3",
            justify="center"
        )
        video_instruction.pack(expand=True)

        # Right Panel - Chat
        chat_panel = tk.LabelFrame(
            content_frame,
            text=f"💬 Live Chat - {self.device_name}",
            font=("Segoe UI", 12, "bold"),
            bg="#2d2d30",
            fg="#ffffff",
            padx=15,
            pady=15,
            relief="solid",
            bd=1,
            labelanchor="n"
        )
        chat_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # Online users indicator
        online_users_frame = tk.Frame(chat_panel, bg="#2d2d30")
        online_users_frame.pack(fill="x", pady=(0, 5))
        
        self.online_indicator = tk.Label(
            online_users_frame,
            text="🟢 You are online",
            font=("Segoe UI", 9),
            bg="#2d2d30",
            fg="#00d4aa"
        )
        self.online_indicator.pack(anchor="w")

        # Chat feed with enhanced styling
        chat_feed_frame = tk.LabelFrame(
            chat_panel,
            text="💭 Chat Messages",
            font=("Segoe UI", 10, "bold"),
            bg="#2d2d30",
            fg="#4fc3f7",
            padx=10,
            pady=10,
            relief="solid",
            bd=1
        )
        chat_feed_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Create a frame for chat with scrollbar
        chat_container = tk.Frame(chat_feed_frame, bg="#2d2d30")
        chat_container.pack(fill="both", expand=True)
        
        self.chat_text = scrolledtext.ScrolledText(
            chat_container,
            state='disabled',
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg="#1e1e1e",  # Darker background for chat
            fg="#ffffff",
            relief="flat",
            bd=5,
            selectbackground="#4fc3f7",
            selectforeground="#ffffff",
            padx=10,
            pady=5
        )
        self.chat_text.pack(fill="both", expand=True)
        
        # Configure text tags for different message types
        self.chat_text.tag_configure("own_message", foreground="#00d4aa", font=("Segoe UI", 10, "bold"))
        self.chat_text.tag_configure("other_message", foreground="#4fc3f7", font=("Segoe UI", 10, "bold"))
        self.chat_text.tag_configure("timestamp", foreground="#888888", font=("Segoe UI", 8))
        self.chat_text.tag_configure("message_text", foreground="#ffffff", font=("Segoe UI", 10))
        self.chat_text.tag_configure("system_message", foreground="#ffa726", font=("Segoe UI", 9, "italic"))

        # Chat input with enhanced styling
        chat_input_frame = tk.LabelFrame(
            chat_panel,
            text="✍️ Type your message...",
            font=("Segoe UI", 10, "bold"),
            bg="#2d2d30",
            fg="#4fc3f7",
            padx=10,
            pady=10,
            relief="solid",
            bd=1
        )
        chat_input_frame.pack(fill="x")
        
        # Input field with placeholder-like behavior
        self.chat_input = scrolledtext.ScrolledText(
            chat_input_frame,
            height=3,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            bg="#3c3c3c",
            fg="#ffffff",
            insertbackground="#4fc3f7",
            relief="flat",
            bd=5,
            selectbackground="#4fc3f7",
            selectforeground="#ffffff",
            padx=8,
            pady=5
        )
        self.chat_input.pack(fill="x", pady=(0, 10))
        
        # Bind events for better UX
        self.chat_input.bind("<Control-Return>", lambda e: self.send_chat_message())
        self.chat_input.bind("<Shift-Return>", lambda e: None)  # Allow line breaks with Shift+Enter
        self.chat_input.bind("<Return>", self._on_enter_key)
        self.chat_input.bind("<KeyPress>", self._on_typing)
        
        # Enhanced send button
        button_frame = tk.Frame(chat_input_frame, bg="#2d2d30")
        button_frame.pack(fill="x")
        
        send_chat_button = tk.Button(
            button_frame,
            text="💬 Send Message",
            command=self.send_chat_message,
            font=("Segoe UI", 10, "bold"),
            bg="#00d4aa",
            fg="#ffffff",
            activebackground="#00b894",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            pady=8,
            width=20
        )
        send_chat_button.pack(side="left")
        
        # Quick actions
        emoji_button = tk.Button(
            button_frame,
            text="😊",
            command=self._insert_emoji,
            font=("Segoe UI", 10),
            bg="#404040",
            fg="#ffffff",
            activebackground="#555555",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            width=3
        )
        emoji_button.pack(side="right", padx=(5, 0))
        
        # Keyboard shortcuts info
        shortcuts_label = tk.Label(
            chat_input_frame,
            text="💡 Tips: Enter to send • Shift+Enter for new line • Ctrl+Enter also sends",
            font=("Segoe UI", 8),
            bg="#2d2d30",
            fg="#888888"
        )
        shortcuts_label.pack(pady=(5, 0))

    def _on_enter_key(self, event):
        """Handle Enter key press in chat input."""
        if not event.state & 0x1:  
            self.send_chat_message()
            return "break"  
        return None  

    def _on_typing(self, event):
        """Handle typing events for future features like typing indicators."""
        pass

    def _insert_emoji(self):
        """Insert a random emoji into the chat input."""
        emojis = ["😊", "😂", "👍", "❤️", "🔥", "✨", "🎉", "👌", "😎", "🚀"]
        import random
        emoji = random.choice(emojis)
        self.chat_input.insert(tk.INSERT, emoji)

    def _display_chat_message_in_gui(self, chat_message):
        """Displays a chat message with enhanced styling like Twitch/YouTube chat."""
        self.chat_text.config(state='normal')
        
        try:
            dt_object = datetime.datetime.fromisoformat(chat_message['timestamp'])
            time_str = dt_object.strftime("%H:%M")
        except ValueError:
            time_str = datetime.datetime.now().strftime("%H:%M")

        sender = chat_message['sender']
        message = chat_message['message']
        
        is_own_message = sender == self.device_name
        
        self.chat_text.insert(tk.END, f"[{time_str}] ", "timestamp")
        
        if is_own_message:
            self.chat_text.insert(tk.END, f"{sender}", "own_message")
        else:
            self.chat_text.insert(tk.END, f"{sender}", "other_message")
        
        self.chat_text.insert(tk.END, ": ", "timestamp")
        
        self.chat_text.insert(tk.END, f"{message}\n", "message_text")
        
        self.chat_text.see(tk.END)
        self.chat_text.config(state='disabled')

    def send_chat_message(self):
        """Sends the chat message from the input field to the server."""
        message_text = self.chat_input.get(1.0, tk.END).strip()
        if not message_text:
            return

        if len(message_text) > 500:
            self.show_tcp_error_message("Message too long (max 500 characters).")
            return

        global tcp_connected, tcp_client_socket
        if tcp_connected and tcp_client_socket:
            try:
                payload = {"sender_id": self.device_name, "message": message_text}
                message_to_send = json.dumps({"type": "chatMessage", "payload": payload}) + '\n'
                tcp_client_socket.sendall(message_to_send.encode('utf-8'))
                self.chat_input.delete(1.0, tk.END) 
                self._clear_tcp_error_message() 
                
                self.chat_input.config(bg="#2d4a2d") 
                self.after(100, lambda: self.chat_input.config(bg="#3c3c3c")) 

            except socket.error as e:
                self.show_tcp_error_message(f"Failed to send chat message: {e}")
                print(f"TCP Client: Error sending chat message: {e}")
                self._handle_tcp_disconnect()
            except Exception as e:
                self.show_tcp_error_message(f"An unexpected error occurred while sending chat: {e}")
                print(f"TCP Client: Unexpected error sending chat: {e}")
                self._handle_tcp_disconnect()
        else:
            self.show_tcp_error_message("Not connected to chat server.")

    def _tcp_connection_loop(self):
        """Manages TCP connection and re-connection."""
        global tcp_client_socket, tcp_connected
        retries = 0
        MAX_RETRIES = 5
        RETRY_DELAY = 3

        while not stop_client_event.is_set():
            if not tcp_connected:
                self.update_tcp_status(f"Connecting to {TCP_HOST}:{TCP_PORT}...", "orange")
                try:
                    tcp_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    tcp_client_socket.connect((TCP_HOST, TCP_PORT))
                    tcp_client_socket.settimeout(1.0)

                    tcp_connected = True
                    retries = 0 
                    self.update_tcp_status("Connected", "green")
                    self.after(0, self._clear_tcp_error_message)
                    print(f"TCP Client: Successfully connected to server at {TCP_HOST}:{TCP_PORT}")

                    self._tcp_receive_messages_loop() 

                except socket.timeout:
                    print("TCP Client: Socket operation timed out during connection.")
                    self._handle_tcp_disconnect()
                except ConnectionRefusedError:
                    retries += 1
                    self.update_tcp_status(f"Connection refused. Retrying ({retries}/{MAX_RETRIES})...", "red")
                    print(f"TCP Client: Connection refused. Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                except Exception as e:
                    retries += 1
                    self.update_tcp_status(f"Connection error: {e}. Retrying ({retries}/{MAX_RETRIES})...", "red")
                    print(f"TCP Client: Connection error: {e}. Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
            else:
                time.sleep(1)

            if retries >= MAX_RETRIES and not tcp_connected:
                self.update_tcp_status("Failed to connect after multiple retries.", "darkred")
                self.show_tcp_error_message("Could not connect to announcement/chat server.")
                print("TCP Client: Failed to connect to server after multiple retries. Stopping auto-reconnect.")
                break 

        print("TCP Client: Connection loop exited.")


    def _tcp_receive_messages_loop(self):
        """Receives and processes messages from the TCP server in a loop."""
        global tcp_connected
        buffer = b''
        while tcp_connected and not stop_client_event.is_set():
            try:
                data = tcp_client_socket.recv(4096)
                if not data:
                    print("TCP Client: Server closed connection gracefully.")
                    self._handle_tcp_disconnect()
                    break

                buffer += data
                while b'\n' in buffer:
                    message_bytes, buffer = buffer.split(b'\n', 1)
                    message_str = message_bytes.decode('utf-8').strip()

                    self.after(0, lambda msg=message_str: self._process_tcp_server_message(msg))

            except socket.timeout:
                pass 
            except ConnectionResetError:
                print("TCP Client: Server reset connection forcefully.")
                self._handle_tcp_disconnect()
                break
            except BrokenPipeError:
                print("TCP Client: Broken pipe: Server closed connection.")
                self._handle_tcp_disconnect()
                break
            except Exception as e:
                print(f"TCP Client: Error during message reception: {e}")
                self._handle_tcp_disconnect()
                break

        print("TCP Client: Receive loop exited.")


    def _process_tcp_server_message(self, message_str):
        """Processes a single message received from the TCP server."""
        try:
            message = json.loads(message_str)
            msg_type = message.get("type")
            msg_payload = message.get("payload")

            if msg_type == "loadOldAnnouncements":
                self.announcements_text.config(state='normal')
                self.announcements_text.delete(1.0, tk.END) 
                self._show_no_announcements_message(False) 
                
                for ann in msg_payload:
                    self._display_announcement_in_gui(ann)
                    
                self.announcements_text.config(state='disabled')
                if not msg_payload:
                    self._show_no_announcements_message(True) 

            elif msg_type == "newAnnouncement":
                self._show_no_announcements_message(False)
                self._display_new_announcement_at_top(msg_payload)

            elif msg_type == "chatMessage": 
                self._display_chat_message_in_gui(msg_payload)
            
            elif msg_type == "loadOldChatMessages":
                self.chat_text.config(state='normal')
                self.chat_text.delete(1.0, tk.END) 
                
                self.chat_text.insert(tk.END, "🎉 Welcome to the chat! 🎉\n", "system_message")
                self.chat_text.insert(tk.END, "═══════════════════════════\n", "timestamp")
                
                if not msg_payload:
                    self.chat_text.insert(tk.END, "💬 No chat history yet. Be the first to say something!\n\n", "system_message")
                else:
                    self.chat_text.insert(tk.END, "📜 Chat History:\n", "system_message")
                    for chat_msg in msg_payload:
                        self._display_chat_message_in_gui(chat_msg)
                    self.chat_text.insert(tk.END, "\n🔴 You are now live in chat!\n", "system_message")
                    
                self.chat_text.insert(tk.END, "═══════════════════════════\n", "timestamp")
                self.chat_text.see(tk.END) 
                self.chat_text.config(state='disabled')

            elif msg_type == "announcementError":
                self.show_tcp_error_message(f"Server Error (Announcement): {msg_payload.get('message', 'Unknown Error')}")
            
            elif msg_type == "serverError": 
                self.show_tcp_error_message(f"Server Error: {msg_payload.get('message', 'Unknown Server Error')}")

            else:
                self.show_tcp_error_message(f"Unknown message type from server: {msg_type}")

        except json.JSONDecodeError:
            self.show_tcp_error_message("Invalid JSON received from server.")
        except Exception as e:
            self.show_tcp_error_message(f"Error processing server message: {e}")

    def _display_announcement_in_gui(self, announcement):
        """Appends an announcement to the Text widget (used for loading old announcements)."""
        self.announcements_text.config(state='normal')
        try:
            dt_object = datetime.datetime.fromisoformat(announcement['timestamp'])
            time_str = dt_object.strftime("%I:%M:%S %p")
            date_str = dt_object.strftime("%Y-%m-%d")
        except ValueError:
            time_str = datetime.datetime.now().strftime("%I:%M:%S %p")
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        formatted_announcement = (
            f"📢 {announcement['message']}\n"
            f"🕒 Posted: {time_str} on {date_str}\n"
            "═══════════════════════════════════\n"
        )
        self.announcements_text.insert(tk.END, formatted_announcement)
        self.announcements_text.config(state='disabled')

    def _display_new_announcement_at_top(self, announcement):
        """Inserts a new announcement at the top of the announcements feed while preserving existing ones."""
        self.announcements_text.config(state='normal')
        
        try:
            dt_object = datetime.datetime.fromisoformat(announcement['timestamp'])
            time_str = dt_object.strftime("%I:%M:%S %p")
            date_str = dt_object.strftime("%Y-%m-%d")
        except ValueError:
            time_str = datetime.datetime.now().strftime("%I:%M:%S %p")
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        formatted_announcement = (
            f"🆕 {announcement['message']}\n"
            f"🕒 Posted: {time_str} on {date_str}\n"
            "═══════════════════════════════════\n"
        )
        
        self.announcements_text.insert(1.0, formatted_announcement)
        
        self.announcements_text.see(1.0)
        
        self.announcements_text.config(state='disabled')

    def _handle_tcp_disconnect(self):
        """Handles TCP client disconnection logic."""
        global tcp_client_socket, tcp_connected
        if tcp_connected:
            tcp_connected = False
            self.update_tcp_status("Disconnected", "red")
            self.show_tcp_error_message("Connection to announcement/chat server lost. Attempting to reconnect...")
            if tcp_client_socket:
                try:
                    tcp_client_socket.shutdown(socket.SHUT_RDWR)
                    tcp_client_socket.close()
                except OSError as e:
                    print(f"TCP Client: Error during socket shutdown/close: {e}")
                finally:
                    tcp_client_socket = None
        else: 
            if tcp_client_socket:
                try:
                    tcp_client_socket.close()
                except OSError as e:
                    print(f"TCP Client: Error closing disconnected socket: {e}")
                finally:
                    tcp_client_socket = None

    def _show_no_announcements_message(self, show=True):
        """Shows or hides the 'no announcements' message."""
        self.announcements_text.config(state='normal')
        if show:
            current_content = self.announcements_text.get(1.0, tk.END).strip()
            if not current_content:
                self.announcements_text.delete(1.0, tk.END)
                self.announcements_text.insert(tk.END, "No announcements yet. Waiting for server or admin to post...")
        self.announcements_text.config(state='disabled')

    def send_announcement_message(self):
        """Sends the announcement message from the input field to the server."""
        message_text = self.announcement_input.get(1.0, tk.END).strip()
        if not message_text:
            self.show_tcp_error_message("Announcement message cannot be empty.")
            return

        global tcp_connected, tcp_client_socket
        if tcp_connected and tcp_client_socket:
            try:
                payload = {"message": message_text}
                message_to_send = json.dumps({"type": "createAnnouncement", "payload": payload}) + '\n'
                tcp_client_socket.sendall(message_to_send.encode('utf-8'))
                self.announcement_input.delete(1.0, tk.END)
                self._clear_tcp_error_message()
            except socket.error as e:
                self.show_tcp_error_message(f"Failed to send announcement: {e}")
                print(f"TCP Client: Error sending announcement: {e}")
                self._handle_tcp_disconnect()
            except Exception as e:
                self.show_tcp_error_message(f"An unexpected error occurred while sending announcement: {e}")
                print(f"TCP Client: Unexpected error sending announcement: {e}")
                self._handle_tcp_disconnect()
        else:
            self.show_tcp_error_message("Not connected to announcement server.")

    def update_tcp_status(self, message, color):
        status_symbols = {
            "green": "● Connected",
            "orange": "🔄 Connecting...",
            "red": "● Disconnected",
            "darkred": "⚠️ Failed"
        }
        display_text = status_symbols.get(color, f"● {message}")
        if color == "green":
            display_text = "✅ Connected"
            self.after(0, lambda: self.online_indicator.config(
                text="🟢 You are online", 
                fg="#00d4aa"
            ))
        elif "Connecting" in message:
            display_text = f"🔄 {message}"
            self.after(0, lambda: self.online_indicator.config(
                text="🟡 Connecting...", 
                fg="#ffa726"
            ))
        elif "Failed" in message or "error" in message.lower():
            display_text = f"⚠️ {message}"
            self.after(0, lambda: self.online_indicator.config(
                text="🔴 Offline", 
                fg="#ff6b6b"
            ))
        else:
            display_text = f"● {message}"
            self.after(0, lambda: self.online_indicator.config(
                text="🔴 Offline", 
                fg="#ff6b6b"
            ))
            
        color_map = {
            "green": "#00d4aa",
            "orange": "#ffa726",
            "red": "#ff6b6b",
            "darkred": "#d32f2f",
            "blue": "#4fc3f7"
        }
        
        self.after(0, lambda: self.tcp_status_label.config(
            text=display_text, 
            fg=color_map.get(color, color)
        ))

    def show_tcp_error_message(self, message):
        self.after(0, lambda: self.tcp_error_label.config(text=message))

    def _clear_tcp_error_message(self):
        self.after(0, lambda: self.tcp_error_label.config(text=""))


    def _display_chat_message_in_gui(self, chat_message):
        """Appends a chat message to the chat Text widget."""
        self.chat_text.config(state='normal')
        try:
            dt_object = datetime.datetime.fromisoformat(chat_message['timestamp'])
            time_str = dt_object.strftime("%I:%M:%S %p")
        except ValueError:
            time_str = datetime.datetime.now().strftime("%I:%M:%S %p")

        formatted_chat = (
            f"[{time_str}] {chat_message['sender']}: {chat_message['message']}\n"
        )
        self.chat_text.insert(tk.END, formatted_chat)
        self.chat_text.see(tk.END) 
        self.chat_text.config(state='disabled')

    def send_chat_message(self):
        """Sends the chat message from the input field to the server."""
        message_text = self.chat_input.get(1.0, tk.END).strip()
        if not message_text:
            return

        if len(message_text) > 500:
            self.show_tcp_error_message("Message too long (max 500 characters).")
            return

        global tcp_connected, tcp_client_socket
        if tcp_connected and tcp_client_socket:
            try:
                payload = {"sender_id": self.device_name, "message": message_text}
                message_to_send = json.dumps({"type": "chatMessage", "payload": payload}) + '\n'
                tcp_client_socket.sendall(message_to_send.encode('utf-8'))
                self.chat_input.delete(1.0, tk.END) 
                self._clear_tcp_error_message() 
                
                self.chat_input.config(bg="#2d4a2d")  
                self.after(100, lambda: self.chat_input.config(bg="#3c3c3c")) 

            except socket.error as e:
                self.show_tcp_error_message(f"Failed to send chat message: {e}")
                print(f"TCP Client: Error sending chat message: {e}")
                self._handle_tcp_disconnect()
            except Exception as e:
                self.show_tcp_error_message(f"An unexpected error occurred while sending chat: {e}")
                print(f"TCP Client: Unexpected error sending chat: {e}")
                self._handle_tcp_disconnect()
        else:
            self.show_tcp_error_message("Not connected to chat server.")

    def _udp_receive_loop(self):
        """Receives and reassembles UDP video packets, also sends periodic HELLO messages."""
        udp_client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_client_socket.bind((UDP_HOST, self.udp_listen_port)) 
            udp_client_socket.settimeout(0.1) 

            print(f"UDP Client: Listening for video on {UDP_HOST}:{self.udp_listen_port}")
            self.update_video_status(f"Listening for video on port {self.udp_listen_port}...", "blue")

            global frame_buffers, frame_total_packets, last_displayed_frame_id, last_udp_hello_sent_time

            self._send_udp_hello(udp_client_socket)
            last_udp_hello_sent_time = time.time()

            while not stop_client_event.is_set():
                try:
                    data, addr = udp_client_socket.recvfrom(BUFFER_SIZE)
                    
                    if time.time() - last_udp_hello_sent_time > LAST_UDP_ACTIVITY_CHECK_INTERVAL:
                        self._send_udp_hello(udp_client_socket)
                        last_udp_hello_sent_time = time.time()

                    if len(data) < 8: 
                        print("UDP Client: Received malformed packet (too short header).")
                        continue

                    frame_id = int.from_bytes(data[0:4], 'big')
                    packet_index = int.from_bytes(data[4:6], 'big')
                    total_packets = int.from_bytes(data[6:8], 'big')
                    packet_data = data[8:]

                    with udp_data_lock:
                        frame_buffers[frame_id][packet_index] = packet_data
                        frame_total_packets[frame_id] = total_packets 


                except socket.timeout:
                    if time.time() - last_udp_hello_sent_time > LAST_UDP_ACTIVITY_CHECK_INTERVAL:
                        self._send_udp_hello(udp_client_socket)
                        last_udp_hello_sent_time = time.time()
                    pass
                except Exception as e:
                    print(f"UDP Client: Error receiving packet: {e}")
                    self.update_video_status(f"Video Error: {e}", "darkred")
                    time.sleep(0.1) 


        except OSError as e: 
            print(f"UDP Client: ERROR BINDING TO PORT {self.udp_listen_port}: {e}")
            self.show_video_error_message(f"ERROR: Could not bind to port {self.udp_listen_port}. Is it already in use by another client?")
            stop_client_event.set()
        except Exception as e:
            print(f"UDP Client: Critical UDP receive loop error: {e}")
            self.show_video_error_message(f"Critical Video Error: {e}")
        finally:
            if udp_client_socket:
                try:
                    udp_client_socket.close()
                except OSError as e:
                    print(f"UDP Client: Error closing UDP socket: {e}")
            print("UDP Client: UDP receive loop exited.")

    def _send_udp_hello(self, udp_socket):
        """Sends a 'VIDEO_HELLO' message to the server's handshake port."""
        try:
            hello_message = "VIDEO_HELLO".encode('utf-8')
            udp_socket.sendto(hello_message, (UDP_SERVER_HOST, UDP_VIDEO_SERVER_PORT))
            print(f"UDP Client: Sent 'HELLO' from {self.udp_listen_port} to server's video handshake port {UDP_VIDEO_SERVER_PORT}")
            self.after(0, self._clear_video_error_message) 
        except Exception as e:
            print(f"UDP Client: Error sending periodic HELLO from {self.udp_listen_port}: {e}")
            self.show_video_error_message(f"Could not send HELLO to server: {e}")


    def _process_buffered_frames(self):
        """Attempts to reassemble and display frames from the buffer.
           This function is called periodically by Tkinter's after method."""
        global last_displayed_frame_id
        
        frame_ids_to_check = []
        with udp_data_lock:
            frame_ids_to_check = sorted([f_id for f_id in frame_buffers.keys() if f_id >= last_displayed_frame_id])

        processed_any_frame = False
        for f_id in frame_ids_to_check:
            if f_id <= last_displayed_frame_id and last_displayed_frame_id != -1:
                with udp_data_lock:
                    if f_id in frame_buffers:
                        del frame_buffers[f_id]
                    if f_id in frame_total_packets:
                        del frame_total_packets[f_id]
                continue


            with udp_data_lock:
                current_frame_packets = frame_buffers.get(f_id)
                expected_total = frame_total_packets.get(f_id)

            if current_frame_packets and expected_total is not None:
                if len(current_frame_packets) == expected_total:
                    assembled_data = b''
                    all_packets_found = True
                    for i in range(expected_total):
                        if i not in current_frame_packets:
                            all_packets_found = False
                            break
                        assembled_data += current_frame_packets[i]
                    
                    if all_packets_found:
                        self._display_video_frame(assembled_data, f_id)
                        last_displayed_frame_id = max(last_displayed_frame_id, f_id) 
                        processed_any_frame = True

                        with udp_data_lock:
                            frame_buffers.pop(f_id, None)
                            frame_total_packets.pop(f_id, None)

                elif f_id < last_displayed_frame_id - 100: 
                    with udp_data_lock:
                        frame_buffers.pop(f_id, None)
                        frame_total_packets.pop(f_id, None)

        self._opencv_gui_update_and_reschedule_frame_processing()


    def _display_video_frame(self, assembled_data, current_frame_id):
        """Decodes and displays a single video frame. Called from main thread."""
        try:
            np_arr = np.frombuffer(assembled_data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is not None:
                cv2.imshow("Video Stream", frame)
                self.update_video_status(f"Streaming (Frame {current_frame_id})", "green")
                self.after(0, self._clear_video_error_message) 
            else:
                print(f"Warning: Failed to decode frame {current_frame_id}. Data size: {len(assembled_data)}")
                self.show_video_error_message(f"Failed to decode frame {current_frame_id}. (Corrupted data?)")
        except Exception as e:
            print(f"Error displaying frame {current_frame_id}: {e}")
            self.show_video_error_message(f"Error displaying frame {current_frame_id}: {e}")

    def _opencv_gui_update_and_reschedule_frame_processing(self):
        """Handles OpenCV's required GUI updates (waitKey) and reschedules frame processing."""
        if not stop_client_event.is_set():
            if cv2.waitKey(1) & 0xFF == ord('q'): 
                self.on_closing() 
                return
            
            self.after(10, self._process_buffered_frames)
        else:
            print("Client: Not rescheduling _opencv_gui_update_and_reschedule_frame_processing due to shutdown event.")


    def update_video_status(self, message, color):
        status_symbols = {
            "green": "📺 Streaming",
            "blue": "🔄 Listening",
            "darkred": "⚠️ Error"
        }
        
        if "Streaming" in message:
            display_text = f"📺 {message}"
        elif "Listening" in message:
            display_text = f"🔄 {message}"
        elif "Error" in message:
            display_text = f"⚠️ {message}"
        else:
            display_text = message
            
        color_map = {
            "green": "#00d4aa",
            "blue": "#4fc3f7",
            "darkred": "#ff6b6b",
            "red": "#ff6b6b"
        }
        
        self.after(0, lambda: self.video_status_label.config(
            text=display_text,
            fg=color_map.get(color, color)
        ))

    def show_video_error_message(self, message):
        self.after(0, lambda: self.video_error_label.config(text=message))

    def _clear_video_error_message(self):
        self.after(0, lambda: self.video_error_label.config(text=""))

    # Global Shutdown

    def on_closing(self):
        """Handles window closing, signals threads to stop and cleans up."""
        print("Client: on_closing called. Initiating shutdown.")
        stop_client_event.set() 

        global tcp_client_socket
        if tcp_client_socket:
            try:
                tcp_client_socket.shutdown(socket.SHUT_RDWR)
                tcp_client_socket.close()
            except OSError as e:
                print(f"Client: Error closing TCP socket on exit: {e}")
            finally:
                tcp_client_socket = None
        

        cv2.destroyAllWindows()

        print("Client: Waiting for threads to finish (briefly)...")
        time.sleep(0.5) 

        self.destroy() 
        print("Client: Application destroyed.")


if __name__ == "__main__":
    print("Combined Client: Application starting...")
    
    client_udp_port = DEFAULT_UDP_VIDEO_CLIENT_PORT
    is_host_client = False 

    if len(sys.argv) > 1:
        try:
            if sys.argv[1].isdigit():
                client_udp_port = int(sys.argv[1])
                if not (1024 <= client_udp_port <= 65535):
                    raise ValueError("Port must be between 1024 and 65535.")
                if '--host' in sys.argv[2:]:
                    is_host_client = True
            elif sys.argv[1] == '--host': 
                is_host_client = True
            else:
                print(f"Invalid argument provided: {sys.argv[1]}. Using default port {DEFAULT_UDP_VIDEO_CLIENT_PORT}.")
                client_udp_port = DEFAULT_UDP_VIDEO_CLIENT_PORT
        except ValueError as ve:
            print(f"Error parsing arguments: {ve}. Using default port {DEFAULT_UDP_VIDEO_CLIENT_PORT}.")
            client_udp_port = DEFAULT_UDP_VIDEO_CLIENT_PORT
        except IndexError: 
            pass 

    app = CombinedClient(client_udp_port, is_host_client)
    app.mainloop()
    print("Combined Client: mainloop exited.")