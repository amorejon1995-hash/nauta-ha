# 🇨🇺 Nauta ETECSA Autologin — Home Assistant integration

A Home Assistant custom integration that **keeps a Nauta (ETECSA, Cuba) internet
connection logged in automatically**. If your Home Assistant host gets its internet
through a Nauta account — Nauta Hogar or a Nauta WiFi zone — the captive portal
drops the session whenever the modem reboots, the line hiccups or the session
expires, and everything behind it goes offline until someone logs in by hand.
This integration detects the portal, logs in with your account, watches the
session, and reconnects on its own.

Built and run in production in Cienfuegos, Cuba, keeping a home's Home Assistant
online around the clock.

---

## What it does

- **Automatic login** to the ETECSA captive portal (`secure.etecsa.net:8443`)
  whenever the connection is found logged out — modem reboots included.
- **Internet status** binary sensor: tells apart "real internet", "captive
  portal in the way" and "portal unreachable".
- **Remaining-time sensor** ("Tiempo restante"): your Nauta account's remaining
  time, read from the portal and counted down live between portal queries,
  with the raw `HH:MM:SS` value as an attribute.
- **Connect / Disconnect buttons** in Home Assistant: log in or out on demand,
  with a clean logout (the portal session is closed properly, so your
  remaining time is not left burning).
- **Autologin switch**: turn the automatic behaviour off without deleting the
  integration.
- **Session persistence**: the portal session parameters are saved to disk, so
  a Home Assistant restart can still log out (or resume) the session it opened
  instead of orphaning it.
- Everything is configured from the UI (config flow) — **username, password and
  check interval**; no YAML, and credentials live only in Home Assistant's own
  config entry storage.

## How it works (the mechanism)

1. **Connectivity check.** Every check interval (default 60 s) the integration
   probes well-known connectivity endpoints (`clients3.google.com/generate_204`
   and `captive.apple.com`). A genuine success page/204 means real internet; a
   redirect or portal page means the ETECSA captive portal is intercepting.
2. **Portal check.** If there is no real internet, it verifies the portal
   itself is reachable before trying anything — if the modem is still booting,
   it simply waits for the next cycle.
3. **Login.** It fetches the portal login page and scrapes the per-session
   `CSRFHW` token, then posts the login form to the portal's `LoginServlet`
   with your Nauta username and password — the same flow a browser performs.
   (The portal's TLS is pinned to TLS 1.2 with its own certificate behaviour,
   so the client uses a dedicated SSL context for `secure.etecsa.net`.)
4. **Verification.** A few seconds after login it re-checks connectivity and
   only then marks the session as connected.
5. **Remaining time.** It queries the portal's `EtecsaQueryServlet` for the
   account's remaining time and then counts it down locally, second by second,
   so the sensor stays live without hammering the portal.
6. **Logout.** Disconnect (or a resumed session at shutdown) posts to
   `LogoutServlet` with the saved session parameters, closing the session
   cleanly instead of letting it time out while it consumes your balance.

## Requirements

- Home Assistant **2023.6.0 or newer**.
- The Home Assistant host must be **behind the Nauta connection itself** —
  its traffic must go through the ETECSA captive portal (typical Nauta Hogar
  setup: the HA box sits on the LAN of the modem that dials Nauta).
- A Nauta account (`usuario@nauta.co.cu`, `usuario@nautaplus`, …).

## Installation

### Option A — HACS (recommended)

1. In HACS → **Integrations** → ⋮ → **Custom repositories**, add:
   ```
   https://github.com/amorejon1995-hash/nauta-ha
   ```
   with category **Integration**.
2. Install **Nauta ETECSA Autologin** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → "Nauta"**, and enter
   your Nauta username, password and the check interval (60 s by default).

### Option B — Manual

1. Copy the `custom_components/nauta` folder from this repository into your
   Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Add the integration from **Settings → Devices & services**, as above.

## Entities

| Entity | Type | What it shows / does |
|---|---|---|
| Internet Status | binary sensor | On = real internet access through Nauta |
| Tiempo restante | sensor | Remaining account time, live countdown (`Xd Xh Xmin Xs`) |
| Autologin Enabled | switch | Master switch for the automatic login |
| Conectar | button | Log in now |
| Desconectar | button | Log out now (clean portal logout) |

## 🇪🇸 En español

Integración personalizada de Home Assistant que **mantiene iniciada la sesión
de internet de Nauta (ETECSA) de forma automática**. Si tu Home Assistant se
conecta a través de una cuenta Nauta — Nauta Hogar o zona WiFi Nauta — el
portal cautivo cierra la sesión cuando el módem se reinicia, la línea parpadea
o la sesión caduca, y todo queda sin internet hasta que alguien entra a mano.
Esta integración detecta el portal, inicia sesión con tu cuenta, vigila la
conexión y reconecta sola.

**Mecanismo:** cada intervalo configurable (60 s por defecto) comprueba si hay
internet real con los endpoints de conectividad habituales; si lo que responde
es el portal cautivo, verifica que el portal esté alcanzable y hace login en
`secure.etecsa.net:8443` reproduciendo el flujo del navegador (token `CSRFHW`
de la página de acceso y envío del formulario al `LoginServlet`). Después
consulta el tiempo restante de la cuenta (`EtecsaQueryServlet`) y lo descuenta
en vivo, segundo a segundo. Los botones **Conectar/Desconectar** usan el mismo
flujo, con cierre de sesión limpio en el portal para no dejar el tiempo
corriendo, y la sesión se guarda en disco para poder cerrarla o retomarla tras
un reinicio de Home Assistant.

**Instalación:** por HACS como repositorio personalizado (categoría
Integration) o copiando `custom_components/nauta` a tu carpeta de
configuración; se configura desde la interfaz con usuario, contraseña e
intervalo. Requisito clave: el equipo de Home Assistant tiene que estar
**detrás de la propia conexión Nauta**, en la LAN del módem que la marca.

## Credits and license

Released under the [MIT license](LICENSE). The code was written by an
**AI assistant**, working under the direction of the repository's owner,
who led the process, made the design decisions and validated everything
on the real installation.
The portal login flow follows ETECSA's own portal behaviour and the community
documentation referenced in [`NOTICE`](NOTICE). Not affiliated with ETECSA.
