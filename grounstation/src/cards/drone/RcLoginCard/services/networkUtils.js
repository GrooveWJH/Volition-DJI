// @ts-nocheck

export async function getLocalIP(defaultValue = '192.168.1.100') {
  try {
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
    });
    pc.createDataChannel('');
    await pc.createOffer().then((offer) => pc.setLocalDescription(offer));

    return await new Promise((resolve) => {
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          const candidate = event.candidate.candidate.split(' ');
          const ip = candidate[4];
          if (ip && !ip.includes(':') && ip !== '127.0.0.1') {
            resolve(ip);
          }
        }
      };
      setTimeout(() => resolve(defaultValue), 3000);
    });
  } catch {
    return defaultValue;
  }
}

export function buildLocalAccessUrl(ip, port, path = '/login') {
  const safeIp = ip || '127.0.0.1';
  const safePort = port || '8080';
  return `http://${safeIp}:${safePort}${path}`;
}
