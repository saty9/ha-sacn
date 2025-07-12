"""Models for sACN Receiver integration."""
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
        print(packet)
        print(packet.dmxData)
        if packet.dmxStartCode != 0x00:  # ignore non-DMX-data packets
            return

        new_config = self.render_dmx_data(packet.dmxData)
        for entity_id in self.entities:
            new_entity_config = new_config[entity_id]
            # TODO periodic write everything anyway
            if self.previous_values[entity_id] != new_entity_config:
                self.hass.services.call(
                    domain="light",
                    service="turn_on",
                    service_data={
                        "entity_id": entity_id,
                        **new_entity_config
                    }
                )

    def init_ct_range(self, entities, hass: HomeAssistant):
        self.ct_range = {}
        for entity_id in entities:
            entity = hass.states.get(entity_id)
            self.ct_range[entity_id] = (entity.min_color_temp_kelvin, entity.max_color_temp_kelvin - entity.min_color_temp_kelvin)


    def __init__(self, universe: int, entities: list[str], mode: ColorMode, hass: HomeAssistant):
        self.mode = mode
        self.entities = entities
        self.previous_values = {entity: None for entity in entities}
        if mode == ColorMode.COLOR_TEMP:
            self.init_ct_range(entities, hass)
        self.hass = hass
        SacnSingleton().listen_to_universe(universe, self.universe_data_cb)
