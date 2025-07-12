"""Models for sACN Receiver integration."""
import asyncio
from threading import Lock

import sacn
import itertools

from homeassistant.components.light.const import ColorMode
from homeassistant.core import HomeAssistant


class SacnSingleton:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self):
        self.receiver = sacn.sACNreceiver()
        self.receiver.start()

    def listen_to_universe(self, universe_number, callback):
        self.receiver.register_listener("universe", callback, universe=universe_number)

class SacnUniverse:
    MODE_CHANNEL_MAP = {
        ColorMode.ONOFF: 1,
        ColorMode.BRIGHTNESS: 1,
        ColorMode.COLOR_TEMP: 2,
        ColorMode.HS: 3,
        ColorMode.XY: 3,
        ColorMode.RGB: 4,
        ColorMode.RGBW: 5,
        ColorMode.RGBWW: 6,
        ColorMode.WHITE: 1,
    }
    hass: HomeAssistant = None

    def __init__(self, universe: int, entities: list[str], mode: ColorMode, hass: HomeAssistant):
        self.mode = mode
        self.entities = entities
        self.previous_values = {entity: None for entity in entities}
        if mode == ColorMode.COLOR_TEMP:
            self.init_ct_range(entities, hass)
        self.hass = hass
        self._update_lock = Lock()
        self._last_packet_lock = Lock()
        self._latest_packet = None
        SacnSingleton().listen_to_universe(universe, self.universe_data_cb)

    async def _process_updates(self) -> None:
        """Process all pending updates while holding the lock."""
        try:
            # Process packets until there are no more new ones
            while self._latest_packet is not None:
                with self._last_packet_lock:
                    current_packet = self._latest_packet
                    self._latest_packet = None  # Clear for next potential update

                # Process the current packet
                new_config = self.render_dmx_data(current_packet.dmxData)
                tasks = []
                for entity_id in self.entities:
                    new_entity_config = new_config[entity_id]
                    if self.previous_values[entity_id] != new_entity_config:
                        tasks.append(self.hass.services.async_call(
                            domain="light",
                            service="turn_on",
                            service_data={
                                "entity_id": entity_id,
                                **new_entity_config
                            }
                        ))
                        self.previous_values[entity_id] = new_entity_config

                await asyncio.gather(*tasks)
        finally:
            self._update_lock.release()




    def render_dmx_data(self, dmx_data):
        output = {}
        for (device, data) in zip(self.entities, itertools.batched(dmx_data, self.MODE_CHANNEL_MAP[self.mode])):
            match self.mode:
                case ColorMode.ONOFF:
                    output[device] = {"on": data[0] > 0}
                case ColorMode.BRIGHTNESS | ColorMode.WHITE:
                    output[device] = {"brightness": data[0]}
                case ColorMode.COLOR_TEMP:
                    # First channel is brightness, second is color temperature
                    brightness = data[0]
                    # Map color temp from 0-255 to default Kelvin range
                    ct_min, ct_range = self.ct_range[device]
                    color_temp = ct_min + ct_range * (data[1] / 255)
                    output[device] = {
                        "brightness": brightness,
                        "color_temp_kelvin": int(color_temp)
                    }
                case ColorMode.HS:
                    brightness = data[0]
                    hue = (data[1] / 255)
                    saturation = (data[2] / 255)
                    output[device] = {
                        "hs_color": (hue, saturation),
                        "brightness": brightness
                    }
                case ColorMode.XY:
                    output[device] = {
                        "brightness": data[0],
                        "xy_color": (data[1] / 255, data[2] / 255)
                    }
                case ColorMode.RGB:
                    output[device] = {
                        "brightness": data[0],
                        "rgb_color": [data[1], data[2], data[3]],
                    }
                case ColorMode.RGBW:
                    output[device] = {
                        "brightness": data[0],
                        "rgbw_color": [data[1], data[2], data[3], data[4]],
                    }
                case ColorMode.RGBWW:
                    output[device] = {
                        "brightness": data[0],
                        "rgbww_color": [data[1], data[2], data[3], data[4], data[5]],
                    }
        return output

    def universe_data_cb(self, packet):
        """Handle incoming DMX data packets."""
        if packet.dmxStartCode != 0x00:  # ignore non-DMX-data packets
            return

        # Store the latest packet
        with self._last_packet_lock:
            self._latest_packet = packet

        # Try to acquire the lock - if we can't, return immediately as another update is in progress
        if not self._update_lock.acquire(blocking=False):
            return

        self.hass.create_task(self._process_updates())

    def init_ct_range(self, entities, hass: HomeAssistant):
        self.ct_range = {}
        for entity_id in entities:
            entity = hass.states.get(entity_id)
            self.ct_range[entity_id] = (entity.min_color_temp_kelvin, entity.max_color_temp_kelvin - entity.min_color_temp_kelvin)
