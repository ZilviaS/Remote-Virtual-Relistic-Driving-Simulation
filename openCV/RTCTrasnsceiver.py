import asyncio
import threading
import socket
import serial
import time

import cv2
import numpy as np

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.rtcrtpsender import RTCRtpSender
from av import VideoFrame
from picamera2 import Picamera2
from fractions import Fraction

# ======================
# Fisheye calibration
# ======================

DIM = (960, 720)

K = np.array([
    [686.292109, 0.0, 764.54341257],
    [0.0, 688.3148852, 512.20240423],
    [0.0, 0.0, 1.0]
], dtype=np.float64)

D = np.array([
    -0.04559606,
    0.0306632,
    -0.03954606,
    0.01535539
], dtype=np.float64)

balance = 0.0

new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
    K, D, DIM, np.eye(3), balance=balance
)

map1, map2 = cv2.fisheye.initUndistortRectifyMap(
    K, D, np.eye(3), new_K, DIM, cv2.CV_16SC2
)


# ======================
# Camera setup
# ======================

def setup_Undist_camera(camera_num):
    picam = Picamera2(camera_num=camera_num)
    # (2592, 1944)
    config = picam.create_video_configuration(
        raw={"size": (2592, 1944)},
        main={"size": DIM, "format": "RGB888"},
        controls={
            "FrameRate": 20,
            "NoiseReductionMode": 2,
            "Sharpness": 1.5,
            "Contrast": 1.1,
            "AwbEnable": True,
            "AeEnable": True,
        }
    )

    picam.configure(config)
    picam.start()
    print(f"Camera {camera_num} started")

    return picam


def setup_camera(camera_num):
    picam = Picamera2(camera_num=camera_num)

    config = picam.create_video_configuration(
        raw={"size": (3280, 2464)},
        main={"size": (640, 480), "format": "RGB888"},
        controls={
            "FrameRate": 20,
            "NoiseReductionMode": 2,
            "Sharpness": 1.5,
            "Contrast": 1.1,
            "AwbEnable": True,
            "AeEnable": True,
        }
    )

    picam.configure(config)
    picam.start()
    print(f"Camera {camera_num} started")

    return picam


picam_raw = setup_camera(0)
picam_undist = setup_Undist_camera(1)


# ======================
# Video tracks
# ======================

class RawCameraTrack(VideoStreamTrack):
    def __init__(self, picam):
        super().__init__()
        self.picam = picam

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frame = await asyncio.to_thread(
            self.picam.capture_array, "main"
        )

        resized = cv2.resize(frame, (640, 480))

        yuv = cv2.cvtColor(resized, cv2.COLOR_RGB2YUV_I420)

        video_frame = VideoFrame.from_ndarray(yuv, format="yuv420p")

        video_frame.pts = pts
        video_frame.time_base = time_base

        # video_frame.metadata = {"capture_time" : capture_time}

        return video_frame


class UndistortedCameraTrack(VideoStreamTrack):
    def __init__(self, picam):
        super().__init__()
        self.picam = picam

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frontframe = await asyncio.to_thread(
            self.picam.capture_array, "main"
        )

        # undistorted = cv2.remap(
        # frame,
        # map1,
        # map2,
        # interpolation=cv2.INTER_LINEAR,
        # borderMode=cv2.BORDER_CONSTANT
        # )

        # resized = cv2.resize(frontframe, (1280, 720))

        yuv = cv2.cvtColor(frontframe, cv2.COLOR_RGB2YUV_I420)

        video_frame = VideoFrame.from_ndarray(yuv, format="yuv420p")

        # video_frame.metadata = {"capture_time": capture_time}
        # video_frame.pts = int(capture_time*1000)
        # video_frame.time_base = Fraction(1,1000)
        video_frame.pts = pts
        video_frame.time_base = time_base

        return video_frame


# ======================
# WebRTC handler
# ======================

async def offer(request):
    pc = RTCPeerConnection()

    # Prefer H.264
    capabilities = RTCRtpSender.getCapabilities("video")
    h264 = [c for c in capabilities.codecs if c.name == "H264"]
    if h264:
        pc.getTransceivers()
        pc.addTransceiver("video", direction="sendonly").setCodecPreferences(h264)

    # Add BOTH tracks
    pc.addTrack(RawCameraTrack(picam_raw))
    pc.addTrack(UndistortedCameraTrack(picam_undist))

    @pc.on("connectionstatechange")
    def on_state():
        print("WebRTC state:", pc.connectionState)

    data = await request.json()
    offer = RTCSessionDescription(
        data["sdp"],
        data["type"]
    )

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })


# ======================
# UDP → Serial thread
# ======================

def udp_serial_server():
    try:
        ser = serial.Serial(
            "/dev/ttyACM0",
            19200,
            timeout=1.0
        )
        ser.flush()
        time.sleep(3)
        ser.reset_input_buffer()
        print("Serial OK")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", 3000))

        print("UDP server listening on port 3000")

        while True:
            message, _ = sock.recvfrom(1024)
            message = message.decode("utf-8").strip() + "\n"
            print("UDP → Arduino:", message.strip())
            ser.write(message.encode("utf-8"))

    except Exception as e:
        print("UDP/Serial error:", e)

    finally:
        try:
            ser.close()
        except:
            pass


def get_current_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't actually send data
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# ======================
# App startup
# ======================

app = web.Application()
app.router.add_post("/offer", offer)

if __name__ == "__main__":
    print("Starting UDP + WebRTC system")

    threading.Thread(
        target=udp_serial_server,
        daemon=True
    ).start()

    curIP = get_current_ip()

    print(f"Car IP Address : {curIP}")

    print("Starting WebRTC server on port 8080")
    web.run_app(app, port=8080)