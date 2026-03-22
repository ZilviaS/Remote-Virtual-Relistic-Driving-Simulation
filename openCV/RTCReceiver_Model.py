import asyncio
import time

import cv2
import aiohttp
import numpy as np
import threading

from aiortc import RTCPeerConnection, RTCSessionDescription
from multiprocessing import shared_memory

from RTCSignal import RTC_Signal

class RTC_Receiver():

    def create_shm(self,name):
        try:
            shm = shared_memory.SharedMemory(
                name=name,
                create=True,
                size= self.WIDTH * self.HEIGHT * self.CHANNELS
            )
        except FileExistsError:
            shm = shared_memory.SharedMemory(name=name, create=False)

        buf = np.ndarray(
            (self.HEIGHT, self.WIDTH, self.CHANNELS),
            dtype=np.uint8,
            buffer=shm.buf
        )
        return shm, buf

    def __init__(self, IP):
        self.PI_IP = IP
        print(self.PI_IP)

        self.signal = RTC_Signal()


        #10.177.68.223
        #10.182.159.223
        self.PI_PORT = 8080
        #1080.720
        self.WIDTH = 960
        self.HEIGHT = 720
        self.CHANNELS = 3  # BGR

        self.SHM_RAW_NAME = "cv_frame_raw"
        self.SHM_UNDIST_NAME = "cv_frame"
        self.scale = 2/3

        self.DIM = (960, 720)
        #self.DIM = (1440, 1080)

        self.K = np.array([
            [686.292109 * self.scale, 0.0, 764.54341257 * self.scale],
            [0.0, 688.3148852 * self.scale, 512.20240423 * self.scale],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)

        self.D = np.array([
            -0.04559606,
            0.0306632,
            -0.03954606,
            0.01535539
        ], dtype=np.float64)

        self.balance = 0.0

        self.new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(self.K, self.D, self.DIM, np.eye(3), balance=self.balance)
        self.map1, self.map2 = cv2.fisheye.initUndistortRectifyMap(self.K, self.D, np.eye(3), self.new_K, self.DIM, cv2.CV_16SC2)
        self.shm_raw, self.shm_raw_buf = self.create_shm(self.SHM_RAW_NAME)
        self.shm_undist, self.shm_undist_buf = self.create_shm(self.SHM_UNDIST_NAME)
        threading.Thread(target=self.start_rtc, daemon=True).start()

    def start_rtc(self):
        try:
            asyncio.run(self.WebRTC())
        except Exception as e:
            print("WebRTC crashed:", e)
            self.signal.disconnected.emit()

    def stop(self):
        print("Stopping RTC Receiver")
        if hasattr(self, "loop"):
            self.loop.call_soon_threadsafe(self.done.set)


# ======================
# WebRTC logic
# ======================

    async def WebRTC(self):
        pc = RTCPeerConnection()
        self.loop = asyncio.get_event_loop()
        self.done = asyncio.Event()
        done = self.done

        # MUST match number of tracks sent
        pc.addTransceiver("video", direction="recvonly")
        pc.addTransceiver("video", direction="recvonly")

        track_index = 0

        @pc.on("track")
        def on_track(track):
            nonlocal track_index

            if track.kind != "video":
                return

            my_index = track_index
            track_index += 1

            if my_index == 0:
                target_buf = self.shm_raw_buf
                label = "RAW"
            elif my_index == 1:
                target_buf = self.shm_undist_buf
                label = "UNDISTORTED"
            else:
                print("Unexpected extra track")
                return

            print(f"Receiving {label} camera")

            async def recv_frames():
                try:
                    while not done.is_set():
                        frame = await track.recv()

                        img = frame.to_ndarray(format="bgr24")

                        if img.shape[:2] != self.DIM:
                            img = cv2.resize(img, self.DIM)

                        if label == "UNDISTORTED":
                            #INTER_CUBIC
                            #img = cv2.fisheye.undistortImage(img,self.K, self.D, None, self.new_K)
                            img = cv2.remap(
                                img,
                                self.map1,
                                self.map2,
                                interpolation=cv2.INTER_LANCZOS4,
                                borderMode=cv2.BORDER_CONSTANT
                            )
                        np.copyto(target_buf, img)

                        #Optional preview
                        # cv2.imshow(label, img)
                        # if cv2.waitKey(1) & 0xFF == ord("q"):
                        #     done.set()

                        await asyncio.sleep(0)  # CRITICAL
                except Exception as e:
                    print(f"{label} track ended:", e)
                    self.signal.disconnected.emit()
                    done.set()

            asyncio.create_task(recv_frames())

        # ======================
        # Offer / Answer
        # ======================

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{self.PI_IP}:{self.PI_PORT}/offer",
                json={
                    "sdp": pc.localDescription.sdp,
                    "type": pc.localDescription.type,
                },
            ) as resp:

                if resp.status != 200:
                    raise RuntimeError(await resp.text())

                answer = await resp.json()

        await pc.setRemoteDescription(
            RTCSessionDescription(answer["sdp"], answer["type"])
        )

        print("WebRTC connected, receiving video...")
        self.signal.connected.emit()
        await done.wait()

        print("Shutting down...")
        self.signal.disconnected.emit()
        await pc.close()
        cv2.destroyAllWindows()

        self.shm_raw.close()
        self.shm_undist.close()
