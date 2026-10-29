"""Constants for the Nauta ETECSA Autologin integration."""

DOMAIN = "nauta"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_INTERVAL = "interval"

DEFAULT_INTERVAL = 60  # seconds

VERIFICATION_URL = "http://captive.apple.com"
VERIFICATION_RESPONSE = "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"
TARGET_URL = "https://secure.etecsa.net:8443/LoginServlet"
