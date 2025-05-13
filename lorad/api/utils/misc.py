import hashlib


def get_username_from_headers(headers):
    return headers["Authorization"].split(",")[0]

def hash_password(password):
    return hashlib.sha512(password.encode('utf-8') + "Mei8HrFsNkEnEXs$J5#q22DA4hdZZ#4964EEvYL2$4G4WDRBJ%z&&Nfg8&EBxRHK".encode("utf-8")).hexdigest()