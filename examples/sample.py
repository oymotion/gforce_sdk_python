# Sample code to get 1000 data

import asyncio
import os
import signal
import sys
import numpy as np

current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from lib_gforce import gforce


# Device filters
DEV_NAME_PREFIX = "gForceProX"
DEV_MIN_RSSI = -64


def convert_raw_emg_to_uv(
    data: bytes, resolution: gforce.SampleResolution
) -> np.ndarray[np.float32]:
    min_voltage = -1.25  # volt
    max_voltage = 1.25  # volt

    match resolution:
        case gforce.SampleResolution.BITS_8:
            div = 127.0
            sub = 128
        case gforce.SampleResolution.BITS_12:
            div = 2047.0
            sub = 2048
        case _:
            raise Exception(f"Unsupported resolution {resolution}")

    gain = 1200.0
    conversion_factor = (max_voltage - min_voltage) / gain / div

    emg_data = (data.astype(np.float32) - sub) * conversion_factor

    return emg_data.reshape(-1, len(data))


class Application:

    def __init__(self):
        signal.signal(signal.SIGINT, lambda signal, frame: self._signal_handler())
        self.terminated = False

    def _signal_handler(self):
        print("You pressed ctrl-c, exit")
        self.terminated = True

    async def main(self):
        gforce_device = gforce.GForce(DEV_NAME_PREFIX, DEV_MIN_RSSI)

        await gforce_device.connect()
        print("Connected to {0}".format(gforce_device.device_name))

        await gforce_device.set_emg_raw_data_config(
            gforce.EmgRawDataConfig(
                gforce.SamplingRate.HZ_500, 0xFF, 16, gforce.SampleResolution.BITS_12
            )
        )
        await gforce_device.set_subscription(
            gforce.DataSubscription.EMG_RAW | gforce.DataSubscription.ACCELERATE
        )

        q = await gforce_device.start_streaming()

        while not self.terminated:
            v = await q.get()
            v = convert_raw_emg_to_uv(v, gforce_device.resolution)
            print(v)

        await gforce_device.stop_streaming()
        await gforce_device.disconnect()


if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main())
