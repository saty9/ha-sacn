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
    SacnUniverse(entry.data[CONF_UNIVERSE], entry.data[CONF_LIGHTS], entry.data[CONF_MODE], hass)
    return True

