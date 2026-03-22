import asyncio
import cv2
import aiohttp
import numpy as np

from aiortc import RTCPeerConnection, RTCSessionDescription
from multiprocessing import shared_memory

# ======================
# Config
# ======================

ip_inp = input("Insert Car IP:")

PI_IP = ip_inp
# PI_PORT = port_inp

PI_PORT = 8080

WIDTH = 960
HEIGHT = 720
CHANNELS = 3   # BGR

# Shared memory names
SHM_RAW_NAME = "cv_frame_raw"
SHM_UNDIST_NAME = "cv_frame"

scale = 2/3

DIM = (960, 720)

K = np.array([
    [686.292109 * scale, 0.0, 764.54341257 * scale],
    [0.0, 688.3148852 * scale, 512.20240423 * scale],
    [0.0, 0.0, 1.0]
], dtype=np.float64)

D = np.array([
    -0.04559606,
    0.0306632,
    -0.03954606,
    0.01535539
], dtype=np.float64)

balance = 0.0

new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(K, D, DIM, np.eye(3), balance=balance)

map1, map2 = cv2.fisheye.initUndistortRectifyMap(K, D, np.eye(3), new_K, DIM, cv2.CV_16SC2)


# ======================
# Shared memory setup
# ======================10.177.68.223
#10.182.159.223

def create_shm(name):
    try:
        shm = shared_memory.SharedMemory(
            name=name,
            create=True,
            size=WIDTH * HEIGHT * CHANNELS
        )
    except FileExistsError:
        shm = shared_memory.SharedMemory(name=name, create=False)

    buf = np.ndarray(
        (HEIGHT, WIDTH, CHANNELS),
        dtype=np.uint8,
        buffer=shm.buf
    )
    return shm, buf


shm_raw, shm_raw_buf = create_shm(SHM_RAW_NAME)
shm_undist, shm_undist_buf = create_shm(SHM_UNDIST_NAME)


# ======================
# WebRTC logic
# ======================

async def main():
    pc = RTCPeerConnection()
    done = asyncio.Event()

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
            target_buf = shm_raw_buf
            label = "RAW"
        elif my_index == 1:
            target_buf = shm_undist_buf
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

                    if img.shape[:2] != DIM:
                        img = cv2.resize(img, DIM)

                    if label == "UNDISTORTED":
                        img = cv2.fisheye.undistortImage(img,K,D, None, new_K)

                    img_resized = cv2.resize(img, DIM)

                    np.copyto(target_buf, img_resized)

                    #Optional preview
                    # cv2.imshow(label, img)
                    # if cv2.waitKey(1) & 0xFF == ord("q"):
                    #     done.set()

                    await asyncio.sleep(0)  # CRITICAL
            except Exception as e:
                print(f"{label} track ended:", e)
                done.set()

        asyncio.create_task(recv_frames())

    # ======================
    # Offer / Answer
    # ======================

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"http://{PI_IP}:{PI_PORT}/offer",
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
    await done.wait()

    print("Shutting down...")
    await pc.close()
    cv2.destroyAllWindows()

    shm_raw.close()
    shm_undist.close()


# ======================
# Entry point
# ======================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass