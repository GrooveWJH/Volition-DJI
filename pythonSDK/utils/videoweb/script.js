document.addEventListener('DOMContentLoaded', () => {
    const videoSources = [
        { name: 'Drone001', url: 'http://grve.me:8888/live/Drone001/index.m3u8' },
        { name: 'Drone002', url: 'http://grve.me:8888/live/Drone002/index.m3u8' },
        { name: 'Drone003', url: 'http://grve.me:8888/live/Drone003/index.m3u8' }
    ];

    const videoContainer = document.getElementById('video-container');

    // Centralized function to handle OSD updates
    const startOsdUpdates = (wrapper, videoElement, hlsInstance) => {
        const osd = wrapper.querySelector('.osd');
        let lastDecodedFrames;
        
        // Clear any existing interval for this wrapper
        if (wrapper.fpsInterval) clearInterval(wrapper.fpsInterval);

        wrapper.fpsInterval = setInterval(() => {
            if (videoElement.readyState < 2) {
                osd.innerHTML = "Status: Buffering...";
                return;
            }

            // Resolution
            let resText;
            if (videoElement.videoWidth > 0) {
                resText = `Res: ${videoElement.videoWidth}x${videoElement.videoHeight}`;
            } else {
                resText = "Res: Detecting...";
            }

            // FPS using the standard getVideoPlaybackQuality() API
            let fpsText;
            if (typeof videoElement.getVideoPlaybackQuality === 'function') {
                const quality = videoElement.getVideoPlaybackQuality();
                const currentDecodedFrames = quality.totalVideoFrames;

                if (typeof lastDecodedFrames === 'undefined') {
                    lastDecodedFrames = currentDecodedFrames;
                    fpsText = "FPS: Calculating...";
                } else {
                    const fps = currentDecodedFrames - lastDecodedFrames;
                    lastDecodedFrames = currentDecodedFrames;
                    fpsText = `FPS: ${fps}`;
                }
            } else {
                // Fallback for older browsers
                fpsText = "FPS: N/A";
            }

            osd.innerHTML = `${resText}<br>${fpsText}`;
        }, 1000);
    };

    const createHlsPlayer = (wrapper, videoElement, source) => {
        const statusIndicator = wrapper.querySelector('.status-indicator');
        const statusText = wrapper.querySelector('.status-text');
        const videoPath = wrapper.querySelector('.video-path');

        videoPath.textContent = source.url;

        const setStatus = (status, message) => {
            statusIndicator.className = `status-indicator ${status}`;
            statusText.textContent = message;
            if (status === 'online') {
                wrapper.classList.add('has-stream');
            } else {
                wrapper.classList.remove('has-stream');
                if (wrapper.fpsInterval) clearInterval(wrapper.fpsInterval);
                wrapper.querySelector('.osd').innerHTML = '';
            }
        };

        if (Hls.isSupported()) {
            const hls = new Hls({
                backBufferLength: 90,
                liveSyncDurationCount: 3,
                liveMaxLatencyDurationCount: 5,
            });

            hls.loadSource(source.url);
            hls.attachMedia(videoElement);

            videoElement.addEventListener('playing', () => {
                setStatus('online', 'Online');
                startOsdUpdates(wrapper, videoElement, hls);
            });

            hls.on(Hls.Events.MANIFEST_PARSED, function() {
                videoElement.play().catch(e => console.warn("Autoplay was prevented:", e));
            });
            
            let errorTimeout;
            hls.on(Hls.Events.ERROR, function (event, data) {
                if (data.fatal) {
                    console.error(`Fatal HLS error for ${source.url}:`, data.details);
                    setStatus('offline', 'Offline');
                    hls.destroy();

                    clearTimeout(errorTimeout);
                    errorTimeout = setTimeout(() => createHlsPlayer(wrapper, videoElement, source), 2000);
                }
            });

        } else if (videoElement.canPlayType('application/vnd.apple.mpegurl')) {
            videoElement.src = source.url;
            videoElement.addEventListener('playing', function() {
                setStatus('online', 'Online (Native)');
                startOsdUpdates(wrapper, videoElement, null); // No HLS instance for native
            });
             videoElement.addEventListener('error', function() {
                setStatus('offline', 'Offline');
             });
             videoElement.play().catch(e => console.warn("Autoplay was prevented:", e));
        } else {
            console.error('HLS is not supported in this browser.');
            setStatus('offline', 'Unsupported');
        }
    };

    videoSources.forEach((src, i) => {
        const wrapper = document.getElementById(`video-wrapper-${i + 1}`);
        if (wrapper) {
            const videoElement = wrapper.querySelector('video');
            const sourceName = wrapper.querySelector('.source-name');
            sourceName.textContent = src.name;
            createHlsPlayer(wrapper, videoElement, src);
        }
    });

    videoContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('zoom-btn')) {
            const btn = e.target;
            const targetId = btn.dataset.target;
            const wrapper = document.getElementById(`video-wrapper-${targetId}`);
            
            if (wrapper.classList.contains('zoomed')) {
                wrapper.classList.remove('zoomed');
                videoContainer.classList.remove('zoomed-in');
                btn.textContent = 'Zoom';
                btn.classList.remove('shrink-btn');
            } else {
                const currentlyZoomed = document.querySelector('.video-wrapper.zoomed');
                if (currentlyZoomed) {
                    currentlyZoomed.classList.remove('zoomed');
                    const oldZoomBtn = currentlyZoomed.querySelector('.zoom-btn');
                    if(oldZoomBtn) {
                        oldZoomBtn.textContent = 'Zoom';
                        oldZoomBtn.classList.remove('shrink-btn');
                    }
                }

                wrapper.classList.add('zoomed');
                videoContainer.classList.add('zoomed-in');
                btn.textContent = 'Shrink';
                btn.classList.add('shrink-btn');
            }
        }
    });
});
