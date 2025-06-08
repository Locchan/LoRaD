import hashlib

import lorad.common.utils.globs as globs


def get_username_from_headers(headers):
    return headers["Authorization"].split(",")[0]

def hash_password(password):
    return hashlib.sha512(password.encode('utf-8') + "Mei8HrFsNkEnEXs$J5#q22DA4hdZZ#4964EEvYL2$4G4WDRBJ%z&&Nfg8&EBxRHK".encode("utf-8")).hexdigest()

def get_yandex_stations():
    stations = globs.RADIO_YANDEX.radio.get_stations()
    stations_parsed = {}
    for astation in stations:
        stations_parsed[astation['station']['name']] = f"{astation['station']['id']['type']}:{astation['station']['id']['tag']}"
    return stations_parsed