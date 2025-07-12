"""Config flow for sACN Receiver integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from .const import DOMAIN, CONF_UNIVERSE, CONF_LIGHTS, CONF_MODE
from homeassistant.components.light.const import VALID_COLOR_MODES, ColorMode
import re

CONF_REGEX="regex"

class SacnReceiverConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sACN Receiver."""

    VERSION = 1

    def load_regex_entities(self, regex: str) -> set[str]:
        if regex == "":
            return set()
        regexes = regex.split(",")
        entities = set()
        unfiltered_entities = self.hass.states.async_entity_ids("light")
        for regex in regexes:
            regex = re.compile(regex)
            entities.update(filter(regex.search, unfiltered_entities))

        return entities


    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate universe
            universe = user_input[CONF_UNIVERSE]
            if not (1 <= universe <= 63999):
                errors[CONF_UNIVERSE] = "invalid_universe"
            regex_lights = self.load_regex_entities(user_input[CONF_REGEX])
            # Validate lights
            lights = user_input[CONF_LIGHTS]
            if not lights or not all(lights):
                errors[CONF_LIGHTS] = "invalid_lights"

            if regex_lights:
                if lights:
                    lights = set(lights).union(regex_lights)
                else:
                    lights = regex_lights

            # Validate color_mode
            color_mode = user_input[CONF_MODE]
            if color_mode not in VALID_COLOR_MODES:
                errors[CONF_COLOR_MODE] = "invalid_color_mode"

            if not errors:
                return self.async_create_entry(
                    title=f"sACN Universe {universe}",
                    data={
                        CONF_UNIVERSE: universe,
                        CONF_LIGHTS: sorted(list(lights)),
                        CONF_MODE: color_mode,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_UNIVERSE, default=1): vol.All(int, vol.Range(min=1, max=63999)),
                vol.Optional(CONF_REGEX, default=""): str,
                vol.Optional(CONF_LIGHTS): selector.EntitySelector(
                    {
                        "domain": "light",
                        "multiple": True,
                    }
                ),
                vol.Required(CONF_MODE, default=ColorMode.HS): vol.In(VALID_COLOR_MODES),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

