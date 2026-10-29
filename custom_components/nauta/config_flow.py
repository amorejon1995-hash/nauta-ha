"""Config flow for Nauta ETECSA Autologin integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_INTERVAL,
    DEFAULT_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=3600)
        ),
    }
)


class NautaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nauta ETECSA Autologin."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # We don't strictly validate login since the portal may be unreachable
            # when the user is setting this up offline.
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Nauta ({user_input[CONF_USERNAME]})",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the options flow, para poder cambiar usuario/contrasena sin recrear."""
        return NautaOptionsFlowHandler()


class NautaOptionsFlowHandler(config_entries.OptionsFlow):
    """Permite actualizar usuario/contrasena/intervalo de una cuenta Nauta ya configurada.

    Util porque las cuentas Nauta suelen ser temporales: cuando se agota el
    tiempo, aqui se puede meter la cuenta nueva sin borrar toda la integracion.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Formulario para actualizar credenciales."""
        errors: dict[str, str] = {}

        if user_input is not None:
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        current = self.config_entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME, default=current.get(CONF_USERNAME, "")
                ): cv.string,
                vol.Required(
                    CONF_PASSWORD, default=current.get(CONF_PASSWORD, "")
                ): cv.string,
                vol.Optional(
                    CONF_INTERVAL, default=current.get(CONF_INTERVAL, DEFAULT_INTERVAL)
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )