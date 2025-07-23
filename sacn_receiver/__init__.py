"""Integration for sACN Receiver."""

from homeassistant.const import Platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_UNIVERSE, CONF_LIGHTS, CONF_MODE
from .models import SacnUniverse

PLATFORMS = [Platform.BUTTON]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up sACN Receiver from a config entry."""
    # Setup logic will go here
    universe = SacnUniverse(entry.data[CONF_UNIVERSE], entry.data[CONF_LIGHTS], entry.data[CONF_MODE], hass)
    entry.runtime_data = universe
    return True

async def async_unload_entry(_hass: HomeAssistant, entry: ConfigEntry) -> bool:
    universe: SacnUniverse = entry.runtime_data
    universe.stop()
    return True
