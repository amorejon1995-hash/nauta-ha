import httpx
import ssl
import re
import json
import logging
from bs4 import BeautifulSoup as bs

_LOGGER = logging.getLogger(__name__)

class nauta():
    def __init__(self):
        self.close_data = None
        self.data_time = None
        self.attribute_uuid = None
        self.attribute_uuid_patron = None
        self.error = None
        self.errors = None
        self.data_log = None
        self.password = None
        self.username = None
        self.login_dat = None
        self.response = None
        self.soup = None
        self.token_csrf = None
        self.wlanuserip = None
        self.logger_id = None

        self.url = 'https://secure.etecsa.net:8443'
        self.url_login = 'https://secure.etecsa.net:8443/LoginServlet'
        self.url_logout = 'https://secure.etecsa.net:8443/LogoutServlet'
        self.url_query = 'https://secure.etecsa.net:8443/EtecsaQueryServlet'

        self.headers = {
            "User-Agent": "Mozilla/5.0(Windows NT 10.0; Win64; x64; rv: 117.0.1)"
        }
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_alpn_protocols(["http/1.1"])
        try:
            ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        except ssl.SSLError:
            pass
        if hasattr(ssl, 'OP_IGNORE_UNEXPECTED_EOF'):
            ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
        self.cliente = httpx.Client(verify=ctx)

    def test_net(self):
        try:
            self.response = self.cliente.get(self.url, timeout=5)
            _LOGGER.debug('test_net: status_code=%s', self.response.status_code)
            if self.response.status_code == 200:
                self.soup = bs(self.response.content, 'html.parser')
                return True
            else:
                _LOGGER.debug('test_net: unexpected status %s, body preview: %s', self.response.status_code, self.response.text[:200])
                return False
        except Exception as e:
            _LOGGER.debug('test_net EXCEPTION: %s: %s', type(e).__name__, e)
            return False

    def login_net(self, username, password):
        try:
            self.token_csrf = self.soup.find('input', {'name': 'CSRFHW'}).get('value')
            self.logger_id = self.soup.find('input', {'name': 'loggerId'}).get('value')
            self.wlanuserip = self.soup.find('input', {'name': 'wlanuserip'}).get('value')

            self.login_dat = {
                'loggerId': self.logger_id,
                'wlanuserip': self.wlanuserip,
                'CSRFHW': self.token_csrf,
                'username': username,
                'password': password
            }
            self.username = username
            self.password = password

            self.data_log = self.cliente.post(self.url_login, data=self.login_dat, timeout=5, follow_redirects=True)
            errors = re.compile(r'alert\((.*?)\)')
            error = re.findall(errors, self.data_log.text)

            if len(error) == 12:
                self.attribute_uuid_patron = r'ATTRIBUTE_UUID=([A-F0-9]+)'
                self.attribute_uuid = re.findall(self.attribute_uuid_patron, self.data_log.text)
                self.attribute_uuid = self.attribute_uuid[1]
                return True
            else:
                return error[2]
        except Exception as e:
            return e

    def save_data(self, ruta):
        try:
            datos_para_cerrar = {
                'ATTRIBUTE_UUID': self.attribute_uuid,
                'loggerId': self.logger_id,
                'wlanuserip': self.wlanuserip,
                'CSRFHW': self.token_csrf,
                'username': self.username,
                'password': self.password,
                'remove': 1
            }
            with open(ruta, 'w') as archivo:
                json.dump(datos_para_cerrar, archivo)
            return True
        except:
            _LOGGER.debug('save_data failed')
            return False

    def load_data(self, ruta):
        try:
            with open(ruta, 'r') as archivo:
                datos_cargados = json.load(archivo)
            return datos_cargados
        except:
            return 'error_cargar_datos'

    def get_time(self):
        self.data_time = {
            'op': 'getLeftTime',
            'ATTRIBUTE_UUID': self.attribute_uuid,
            'CSRFHW': self.token_csrf,
            'wlanuserip': self.wlanuserip,
            'logger_id': self.logger_id + f' {self.username}',
            'username': self.username
        }
        try:
            time = self.cliente.post(self.url_query, data=self.data_time, timeout=5)
            return time.text
        except:
            return False

    def logout(self):
        close_data = {
            'ATTRIBUTE_UUID': self.attribute_uuid,
            'CSRFHW': self.token_csrf,
            'wlanuserip': self.wlanuserip,
            'loggerId': self.logger_id + f'{self.username}',
            'username': self.username,
            'remove': 1
        }
        try:
            self.cliente.post(self.url_logout, data=close_data, timeout=5, follow_redirects=True)
            return True
        except:
            return False

    def logout_back(self, ruta):
        try:
            data = self.load_data(ruta)
            self.cliente.post(self.url_logout, data=data, timeout=5, follow_redirects=True)
            return True
        except:
            return False

    def reanude_login(self, ruta):
        try:
            datos = self.load_data(ruta)
            del datos['password']
            del datos['remove']
            datos['op'] = 'getLeftTime'
            time = self.cliente.post(self.url_query, data=datos, timeout=5)
            return time.text
        except:
            return False