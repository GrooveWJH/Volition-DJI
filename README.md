# Volition-DJI

Autonomy-focused control tooling for DJI platforms.

## Repository Structure

```
Volition-DJI/
├── grounstation/              # Astro-based web ground station
│   ├── src/
│   │   ├── cards/            # UI components for drone control
│   │   ├── components/       # Reusable UI components
│   │   ├── lib/              # Core libraries and utilities
│   │   └── config/           # Configuration files
│   ├── tests/                # Test suites (unit + integration)
│   └── public/               # Static assets
├── videoStream/              # RTMP video streaming system
│   ├── mediamtx/            # Media streaming server
│   └── rtmp_player.py       # Python video stream player
├── scripts/                  # Utility scripts and tools
├── monitor_deprecated/       # Legacy monitoring interface
└── docs/                     # Technical documentation
```

## Core Components

**Ground Station** (`grounstation/`)
- Modern web interface built with Astro
- Real-time drone control via MQTT
- Component-based architecture with Tailwind CSS
- Comprehensive test coverage

**Video Streaming** (`videoStream/`)
- MediaMTX server for RTMP/RTSP/HLS/WebRTC protocols
- Python OpenCV player for real-time video display
- Multi-protocol video distribution

**Documentation** (`docs/`)
- Technical reports and architecture diagrams
- Integration guides and API references

## Architecture

The project follows a modular design with clear separation between:
- Web-based ground control station
- Video streaming infrastructure
- Command-line utilities
- Testing frameworks

Built with modern web technologies and focused on autonomous drone operations.