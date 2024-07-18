# Sample code to get gloves data and controls ROHand via ModBus-RTU protocol

import asyncio
import os
import signal
import sys

current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from lib_gforce import gforce


# Device filters
DEV_NAME_PREFIX = "gForceBLE"
DEV_MIN_RSSI = -64


class Application:

    def __init__(self):
        signal.signal(signal.SIGINT, lambda signal, frame: self._signal_handler())
        self.terminated = False

    def _signal_handler(self):
        print("You pressed ctrl-c, exit")
        self.terminated = True

    async def main(self):
        gforce_device = gforce.GForce(DEV_NAME_PREFIX, DEV_MIN_RSSI)
        emg_data = [0 for _ in range(5)]

        # GForce.connect() may get exception, but we just ignore for gloves
        try:
            await gforce_device.connect()
        except Exception as e:
            print(e)

        if gforce_device.client == None or not gforce_device.client.is_connected:
            exit(-1)

        print("Connected to {0}".format(gforce_device.device_name))

        await gforce_device.set_subscription(gforce.DataSubscription.EMG_RAW)
        q = await gforce_device.start_streaming()

        print("\nPress Ctrl+C to exit\n")

        while not self.terminated:
            v = await q.get()
            # print(v)

            for i in range(len(v)):
                emg_data[0] = round((emg_data[0] + v[i][7]) / 2)  # 拇指
                emg_data[1] = round((emg_data[1] + v[i][6]) / 2)  # 食指
                emg_data[2] = round((emg_data[2] + v[i][0]) / 2)  # 中指
                emg_data[3] = round((emg_data[3] + v[i][3]) / 2)  # 无名指
                emg_data[4] = round((emg_data[4] + v[i][4]) / 2)  # 小指

            print(emg_data)

        await gforce_device.stop_streaming()
        await gforce_device.disconnect()


if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main())
