# Each endpoint module has to have ENDP_PATH attribute that specifies the endpoint path
#  as well as impl_X(headers, data*)** where X is method (e.g. impl_GET)
# All impl_X methods should be decorated with @lrd_api_endp.
# impl_X implement the method and return a tuple: (resp_code, json_data) or just
#  json_data dict (may be empty ({}) but should always be present!).
# No explicit response code will imply 200 response code.
#
# * - data is not required for requests that consume no data e.g. GET
# ** - the order is super important, the first arg should always be headers

from types import ModuleType

from lorad.api.endpoints import openapi, version, apidoc, whatsplaying, current_player, available_players, locale, switch_player, enabled_features
from lorad.api.endpoints import users
from lorad.api.endpoints import yandex
from lorad.api.endpoints import radio
from lorad.api.endpoints import admin

endpoints_to_register : list[ModuleType] = \
[
version, apidoc, openapi, whatsplaying, current_player, available_players, locale, switch_player, enabled_features, # root
users.auth, users.whoami, users.register, users.remove, # user
yandex.available_stations, yandex.current_station, yandex.switch_station, # yandex
radio.available_stations, radio.current_station, radio.switch_station, # radio
admin.get_config, admin.set_config # admin
]
