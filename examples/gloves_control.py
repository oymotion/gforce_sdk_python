# Sample code to get gloves data

import asyncio
import os
import signal
import socket
import sys


# Add the parent directory to the Python path for lib_gforce
current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from lib_gforce import gforce
from lib_gforce.gforce import EmgRawDataConfig, SampleResolution

# Degree of freedom settings, modify EXTRA_FINGERS to distinguish between 5 DOF and 6 DOFgloves.
NUM_FINGERS = 5
EXTRA_FINGERS = 1

# Device filters
DEV_NAME_PREFIX = "gForceBLE"
DEV_MIN_RSSI = -128

# sample resolution:BITS_8 or BITS_12
SAMPLE_RESOLUTION = 12

NUM_CHANNELS = NUM_FINGERS + EXTRA_FINGERS
# Channel0: thumb, Channel1: index, Channel2: middle, Channel3: ring, Channel4: pinky, Channel5: thumb root
INDEX_CHANNELS = [7, 6, 0, 3, 4, 5]

# Socket server
HOST = None  # Symbolic name meaning all available interfaces
PORT = 50007  # Arbitrary non-privileged port


def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))


def interpolate(n, from_min, from_max, to_min, to_max):
    return (n - from_min) / (from_max - from_min) * (to_max - to_min) + to_min


class Application:

    def __init__(self):
        """
        Initializes the Application object.

        This method sets up the signal handler for the SIGINT signal (Ctrl+C), initializes the `terminated` flag to False,
        creates an `asyncio.Event` object to signal the thread to stop, and initializes the `gforce_device` object with
        the specified device name prefix and minimum RSSI.

        Args:
            self: The instance of the Application class.
        """
        # 注册SIGINT信号，当接收到SIGINT信号时，调用self._signal_handler()方法
        signal.signal(signal.SIGINT, lambda signal, frame: self._signal_handler())
        # 初始化terminated为False
        self.terminated = False
        # 初始化gforce_device为gforce.GForce(DEV_NAME_PREFIX, DEV_MIN_RSSI)
        self.gforce_device = gforce.GForce(DEV_NAME_PREFIX, DEV_MIN_RSSI)
        # 初始化battery_level为0
        self.battery_level = 0

    def _signal_handler(self):
        """
        Signal handler for the SIGINT signal (Ctrl+C).

        This method is called when the user presses Ctrl+C to terminate the program.
        It sets the `terminated` flag to True, which will cause the main loop in the `main` method to exit.

        Args:
            self: The instance of the Application class.
        """
        # 打印提示信息
        print("You pressed ctrl-c, exit")
        # 设置终止标志为True
        self.terminated = True

    async def get_battery_level(self):
        """
        Continuously retrieves and prints the battery level of the gForce device.

        This method runs in a separate thread and periodically queries the device for its current battery level.
        It continues to do so until the terminated is set, indicating that the task should terminate.

        Args:
            self: The instance of the Application class.
        """
        # 循环直到终止
        while not self.terminated:
            # 获取电池电量
            self.battery_level = await self.gforce_device.get_battery_level()
            # 打印电池电量
            print("Battery level: {0}%".format(self.battery_level))
            # 等待1秒，非阻塞
            await asyncio.sleep(1)

        print("Battery level thread stopped.")

    async def main(self):
        """
        The main entry point of the application.

        This method initializes the data arrays for EMG data, minimum and maximum EMG values, and finger data.
        It then attempts to connect to the gForce device, sets the subscription to EMG raw data, and starts streaming data.
        It calibrates the EMG data by collecting 256 samples of data while the user spreads their fingers, makes a fist and rotate thumb root.
        It then creates a new task to continuously retrieve and print the battery level of the device.
        Finally, it enters a loop to continuously process the streaming data, interpolate and clamp the finger data, and print the results.
        The loop continues until the `terminated` flag is set, at which point it stops streaming and disconnects from the device.

        Args:
            self: The instance of the Application class.
        """
        emg_data = [0 for _ in range(NUM_CHANNELS)]
        emg_min = [0 for _ in range(NUM_CHANNELS)]
        emg_max = [0 for _ in range(NUM_CHANNELS)]
        finger_data = [0 for _ in range(NUM_CHANNELS)]

        # GForce.connect() may get exception, but we just ignore for gloves
        try:
            await self.gforce_device.connect()
        except Exception as e:
            print(e)

        if self.gforce_device.client == None or not self.gforce_device.client.is_connected:
            exit(-1)

        print("Connected to {0}".format(self.gforce_device.device_name))

        # Set the EMG raw data configuration, default configuration is 8 bits, 16 batch_len
        if SAMPLE_RESOLUTION == 12:
            cfg = EmgRawDataConfig(fs=100, channel_mask=0xff, batch_len = 8, resolution = SampleResolution.BITS_12)
            await self.gforce_device.set_emg_raw_data_config(cfg)

        await self.gforce_device.set_subscription(gforce.DataSubscription.EMG_RAW)
        q = await self.gforce_device.start_streaming()

        print("Please spread your fingers")

        for _ in range(256):
            v = await q.get()
            # print(v)

            for i in range(len(v)):
                for j in range(NUM_CHANNELS):
                    emg_max[j] = round((emg_max[j] + v[i][INDEX_CHANNELS[j]]) / 2)

        # print(emg_max)

        print("Please make a fist")

        for _ in range(256):
            v = await q.get()
            # print(v)

            for i in range(len(v)):
                for j in range(NUM_CHANNELS):
                    emg_min[j] = round((emg_max[j] + v[i][INDEX_CHANNELS[j]]) / 2)
        
        # For extra fingers
        if NUM_CHANNELS > NUM_FINGERS:
            print("Please spread your fingers, then rotate thumb")

            for _ in range(256):
                v = await q.get()
                for i in range(len(v)):
                    emg_min[5] = round((emg_min[5] + v[i][INDEX_CHANNELS[5]]) / 2)
  
        # print(emg_min)

        for i in range(NUM_CHANNELS):
            print("MIN/MAX of finger {0}: {1}-{2}".format(i, emg_min[i], emg_max[i]))

        # Create a new task
        battery_task = asyncio.create_task(self.get_battery_level())

        while not self.terminated:
            v = await q.get()
            print(v)

            for i in range(len(v)):
                for j in range(NUM_CHANNELS):
                    emg_data[j] = round((emg_data[j] + v[i][INDEX_CHANNELS[j]]) / 2)
                    finger_data[j] = round(interpolate(emg_data[j], emg_min[j], emg_max[j], 65535, 0))
                    finger_data[j] = clamp(finger_data[j], 0, 65535)

            # print(finger_data)

        await battery_task  # 等待后台任务结束
        await self.gforce_device.stop_streaming()
        await self.gforce_device.disconnect()

        print("Disconnected from {0}.".format(self.gforce_device.device_name))
        print("Terminated.")

if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main())
