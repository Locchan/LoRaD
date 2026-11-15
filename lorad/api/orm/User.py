from lorad.api.orm import User  # noqa: F401 — model from purest create_auth_models


def user_register(username, password) -> bool:
    from lorad.api.auth_backend import get_auth_backend

    return get_auth_backend().register_user(username, password)


def user_remove(username) -> bool:
    from lorad.api.auth_backend import get_auth_backend

    return get_auth_backend().remove_user(username)


def user_login(username, password_to_check) -> int:
    from lorad.api.auth_backend import get_auth_backend

    return int(get_auth_backend().login(username, password_to_check))
