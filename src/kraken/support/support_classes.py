from typing import Any


class AttributeDict(dict[str, Any]):
    def __getattr__(self, attr: str) -> Any:
        if attr in self:
            return self[attr]
        else:
            raise AttributeError(f"'AttributeDict' object has no attribute '{attr}'")

    def __setattr__(self, attr: str, value: Any) -> None:
        self[attr] = value

    def __dir__(self) -> list[str]:
        return list(super().__dir__()) + list(self.keys())
