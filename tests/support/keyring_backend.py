import keyring
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

CONFIG_TEST_PREFIX = "KRAKEN_TEST_"


# ----------------------------------------------------------------------- #
# Hybrid keyring backend: test aliases in-memory, real aliases pass through
# ----------------------------------------------------------------------- #
class KrakenTestKeyring(KeyringBackend):
    """
    Hybrid test keyring:
      - For services whose name starts with 'KRAKEN_TEST_', store credentials
        in an in-memory dict (per process, per test run).
      - For everything else, delegate to the real OS keyring backend.
    """

    priority = 20  # higher than the default, but we're setting it explicitly anyway

    def __init__(self, real_backend: KeyringBackend) -> None:
        self._real = real_backend
        self._test_prefix = CONFIG_TEST_PREFIX
        self._store: dict[tuple[str, str], str] = {}

    def _is_test_service(self, service: str | None) -> bool:
        return bool(service) and service.startswith(self._test_prefix)  # type: ignore

    def get_password(self, service: str, username: str) -> str | None:
        if self._is_test_service(service):
            return self._store.get((service, username))
        return self._real.get_password(service, username)

    def set_password(self, service: str, username: str, password: str) -> None:
        if self._is_test_service(service):
            self._store[(service, username)] = password
        else:
            self._real.set_password(service, username, password)

    def delete_password(self, service: str, username: str) -> None:
        if self._is_test_service(service):
            key = (service, username)
            if key in self._store:
                del self._store[key]
            else:
                raise PasswordDeleteError(f"No such password: {service}/{username}")
        else:
            self._real.delete_password(service, username)


_installed = False


def install_test_keyring() -> None:
    """Install the hybrid keyring once per process."""
    global _installed
    if _installed:
        return

    real_backend = keyring.get_keyring()
    test_backend = KrakenTestKeyring(real_backend)
    keyring.set_keyring(test_backend)
    _installed = True


install_test_keyring()
