# Live Streaming App 🎥📡

A **real-time video streaming application** built with **Python**, **OpenCV**, and **Tkinter**. This application enables live video broadcasting, real-time chat, and announcement systems using a client-server architecture with both TCP and UDP protocols.

## 🌟 Features

### 🎬 Video Streaming
- **Real-time Video Broadcasting**: Live video streaming using OpenCV and UDP
- **Multi-client Support**: Multiple viewers can connect simultaneously
- **Frame Buffering**: Efficient packet management for smooth video playback
- **Adaptive Streaming**: Handles varying network conditions
- **Host/Viewer Roles**: Dedicated streaming host and multiple viewers

### 💬 Communication
- **Real-time Chat**: TCP-based messaging system for all connected clients
- **Announcement System**: Broadcast important messages to all users
- **Chat History**: Persistent message storage and retrieval
- **User Identification**: Named clients for personalized communication

### 🔧 Technical Features
- **Dual Protocol**: TCP for reliable messaging, UDP for real-time video
- **Thread-safe Operations**: Concurrent handling of multiple operations
- **Cross-platform**: Works on Windows, macOS, and Linux
- **Modular Design**: Separate server and client components
- **Data Persistence**: JSON-based storage for announcements

## 🛠️ Technology Stack

- **Language**: Python 3.x
- **GUI Framework**: Tkinter for client interface
- **Video Processing**: OpenCV (cv2) for video capture and processing
- **Networking**: TCP/UDP sockets for client-server communication
- **Data Format**: JSON for message serialization
- **Concurrency**: Threading for multi-client support
- **Image Processing**: NumPy for frame manipulation

## 📁 Project Structure

```
├── combined_server.py         # Main server handling TCP/UDP connections
├── combined_client.py         # GUI client application
├── announcements.json         # Persistent announcement storage
├── announcements.json.backup  # Backup of announcements
└── README.md                  # Project documentation
```

## 🏗️ Architecture Overview

### Server Components (`combined_server.py`)
- **TCP Server**: Handles chat messages and announcements on port 4000
- **UDP Video Server**: Streams video frames on port 5000
- **Client Management**: Thread-safe tracking of connected clients
- **Announcement System**: Persistent storage and broadcasting
- **Video Capture**: OpenCV integration for video streaming

### Client Components (`combined_client.py`)
- **GUI Interface**: Tkinter-based user interface
- **TCP Client**: Chat and announcement handling
- **UDP Client**: Video frame reception and display
- **Frame Assembly**: Reconstructs video from UDP packets
- **User Roles**: Host (streaming) and Viewer modes

## 🚀 Installation & Setup

### Prerequisites
- Python 3.6 or higher
- OpenCV (`cv2`)
- NumPy
- Tkinter (usually included with Python)
- Network camera or webcam for streaming

### Dependencies Installation
```bash
pip install opencv-python numpy
```

### Getting Started

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Abdullahkhan1010/Live-Streaming-App.git
   cd Live-Streaming-App
   ```

2. **Configure Network Settings**:
   Update IP addresses in both files:
   ```python
   # In combined_server.py
   HOST_IP = '192.168.100.199'  # Your server IP
   
   # In combined_client.py
   TCP_HOST = '192.168.100.199'  # Server IP
   UDP_SERVER_HOST = '192.168.100.199'  # Server IP
   ```

3. **Start the server**:
   ```bash
   python combined_server.py
   ```

4. **Launch clients**:
   ```bash
   # For the host (streaming client)
   python combined_client.py
   
   # For viewers (additional clients)
   python combined_client.py
   ```

## 📱 How to Use

### Starting a Stream

1. **Launch the server** on the host machine
2. **Start the host client** - this will be the streaming source
3. **Configure camera settings** in the host client
4. **Begin streaming** - video will be broadcast to all connected viewers

### Joining as a Viewer

1. **Ensure server is running**
2. **Launch client application**
3. **Enter device name** when prompted
4. **Connect to stream** - video and chat will be available immediately

### Chat System

- **Send Messages**: Type in the chat input and press Enter
- **View History**: All messages are displayed in the chat window
- **Real-time Updates**: Messages appear instantly for all connected users

### Announcements

- **Create Announcements**: Host can broadcast important messages
- **Persistent Storage**: Announcements are saved to JSON file
- **Auto-display**: New announcements appear for all connected clients

## 🔧 Configuration

### Network Settings
```python
# Server Configuration
TCP_HOST = '0.0.0.0'    # Listen on all interfaces
TCP_PORT = 4000         # TCP port for chat/announcements
UDP_HOST = '0.0.0.0'    # UDP listen address
UDP_VIDEO_SERVER_PORT = 5000  # UDP port for video streaming

# Client Configuration
TCP_HOST = '192.168.100.199'  # Server IP address
UDP_SERVER_HOST = '192.168.100.199'  # Server IP for video
DEFAULT_UDP_VIDEO_CLIENT_PORT = 5001  # Client UDP port
```

### Video Settings
```python
MAX_UDP_PACKET_SIZE = 65000  # Maximum UDP packet size
FPS = 30                     # Frames per second
FRAME_DELAY = 1.0 / FPS     # Delay between frames
BUFFER_SIZE = 65536         # Network buffer size
```

## 🎯 Key Features Breakdown

### Video Streaming Engine
- **Frame Capture**: Uses OpenCV to capture video from camera
- **Frame Compression**: Optimizes frame size for network transmission
- **Packet Fragmentation**: Splits large frames into UDP packets
- **Frame Reconstruction**: Reassembles packets into complete frames
- **Buffering System**: Manages out-of-order packet delivery

### Communication System
- **TCP Messaging**: Reliable delivery for chat and announcements
- **UDP Streaming**: Low-latency video transmission
- **Client Synchronization**: Coordinates multiple viewers
- **Message Broadcasting**: Distributes messages to all clients

### User Interface
- **Video Display**: Real-time video playback window
- **Chat Interface**: Message input and history display
- **Connection Status**: Network connectivity indicators
- **User Management**: Client identification and role assignment

## 🔒 Network Security

### Port Configuration
- **TCP Port 4000**: Chat and announcement messages
- **UDP Port 5000**: Video streaming data
- **Client Ports**: Dynamic assignment starting from 5001

### Data Protection
- **Local Network**: Designed for LAN usage
- **JSON Serialization**: Structured data transmission
- **Client Authentication**: Device name identification

## 🐛 Troubleshooting

### Common Issues

**Connection Problems**:
- Verify server is running before starting clients
- Check firewall settings for ports 4000 and 5000
- Ensure IP addresses are correctly configured
- Test network connectivity between devices

**Video Issues**:
- Verify camera/webcam is properly connected
- Check OpenCV installation and camera permissions
- Monitor network bandwidth for streaming quality
- Adjust frame rate if experiencing lag

**Chat Problems**:
- Ensure TCP connection is established
- Check for network interruptions
- Verify JSON message formatting
- Monitor server logs for error messages

## 🔮 Future Enhancements

- [ ] **Audio Streaming**: Add audio transmission capability
- [ ] **Recording Feature**: Save streams to local files
- [ ] **User Authentication**: Login system with user accounts
- [ ] **Stream Quality Options**: Multiple resolution/bitrate settings
- [ ] **Mobile App**: Android/iOS companion applications
- [ ] **Web Interface**: Browser-based streaming client
- [ ] **Cloud Deployment**: Server hosting on cloud platforms
- [ ] **Advanced Chat**: File sharing and emoji support

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

## 📞 Support

For questions, bug reports, or support:

**Abdullah Khan**
- GitHub: [@Abdullahkhan1010](https://github.com/Abdullahkhan1010)
- Email: abdullah.khan1010@gmail.com

## 🎬 Demo Usage

### Typical Workflow
1. **Host Setup**: Start server, launch host client, begin streaming
2. **Viewer Connection**: Launch viewer clients, automatically receive stream
3. **Interactive Chat**: Real-time communication during streaming
4. **Announcements**: Host broadcasts important information
5. **Multi-viewer**: Multiple people can watch simultaneously

---

⭐ **Star this repository if you found it helpful!**

Made with ❤️ using Python, OpenCV & Tkinter
