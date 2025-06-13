import json

from kraken.credentials.integrity import (
    ALIAS,
    CONNECTION_STRING,
    PASSWORD,
    PLATFORM,
    USERNAME,
)
from kraken.exceptions import CredentialError


class Credentials:
    """A Kraken Credential object, holding details about a service including its connections string"""

    def __init__(
        self,
        *,
        alias: str,
        username: str,
        platform: str,
        connection_string: str,
        password: str | None = None,
    ):
        self.alias = alias
        self.username = username
        self.password = password
        self.platform = platform
        self.connection_string = connection_string

    @classmethod
    def from_json(cls, json_string: str) -> "Credentials":
        """Alternative constructor to create a Credentials object from a JSON string."""
        try:
            elements: dict[str, str] = json.loads(json_string)
            return cls(
                alias=elements.get(ALIAS, ""),
                username=elements.get(USERNAME, ""),
                password=elements.get(PASSWORD),
                platform=elements.get(PLATFORM, ""),
                connection_string=elements.get(CONNECTION_STRING, ""),
            )
        except json.JSONDecodeError as e:
            raise CredentialError(f"Invalid JSON data: {e}") from e

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"alias='{self.alias}', "
            f"username='{self.username}', "
            f"platform='{self.platform}', "
            f"connection_string='{self.__scrub_password()}'"
            f")"
        )

    def __scrub_password(self) -> str | None:
        return (
            self.connection_string
            if not self.password
            else self.connection_string.replace(self.password, "******")
        )

    @property
    def json(self) -> str:
        elements = {
            ALIAS: self.alias,
            USERNAME: self.username,
            PASSWORD: self.password,
            PLATFORM: self.platform,
            CONNECTION_STRING: self.connection_string,
        }
        return json.dumps(elements)
