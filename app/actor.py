import dataclasses


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class Actor:
    id: int
