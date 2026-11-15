from lorad.api.orm import Token  # noqa: F401 — model from purest MysqlAuthBackend


def gen_token(username):
    from lorad.api.auth_backend import get_auth_backend

    return get_auth_backend().issue_token(username)


def validate_token(username, token) -> bool:
    from lorad.api.auth_backend import get_auth_backend

    return get_auth_backend().validate_token(username, token)


def check_caps(username, needed_cap):
    from lorad.api.auth_backend import get_auth_backend

    return get_auth_backend().check_capability(username, needed_cap)
