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
from lorad.api.endpoints import version
from lorad.api.endpoints.users import auth
from lorad.api.endpoints.users import whoami
from lorad.api.endpoints.users import register
from lorad.api.endpoints.users import remove

from lorad.api.endpoints.yandex import radios
from lorad.api.endpoints.yandex import current_station
from lorad.api.endpoints.yandex import current_track
from lorad.api.endpoints.yandex import switch_station

endpoints_to_register : list[ModuleType] = \
[
version, # root
auth, whoami, register, remove, # user
radios, current_station, switch_station, current_track #yandex
]
