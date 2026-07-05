from pydantic import BaseModel, Field, model_validator


class SettingsUpdate(BaseModel):
    priceStrategy: str | None = None
    favoriteSets: list[str] | None = None
    compareDate: str | None = None
    pageSize: int | None = Field(default=None, ge=25, le=100)
    collectionCardScale: int | None = Field(default=None, ge=75, le=150)
    setSortMode: str | None = None
    setPickerMode: str | None = None
    defaultStorageLocation: str | None = None


class StorageLocationCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class StorageLocationUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


def _resolve_finish_field(values: dict) -> dict:
    if values.get("finish") is not None:
        return values
    foil = values.get("foil")
    if foil is not None:
        values["finish"] = foil
        return values
    raise ValueError("finish or foil is required")


class OwnershipUpdate(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)
    collectorNumber: str = Field(min_length=1, max_length=32)
    finish: int | None = Field(default=None, ge=0, le=2)
    foil: int | None = Field(default=None, ge=0, le=2)
    owned: bool
    purchaseValue: float | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_finish(cls, values):
        if isinstance(values, dict):
            return _resolve_finish_field(values)
        return values


class OwnershipFinishChange(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)
    collectorNumber: str = Field(min_length=1, max_length=32)
    fromFinish: int | None = Field(default=None, ge=0, le=2)
    toFinish: int | None = Field(default=None, ge=0, le=2)
    fromFoil: int | None = Field(default=None, ge=0, le=2)
    toFoil: int | None = Field(default=None, ge=0, le=2)

    @model_validator(mode="before")
    @classmethod
    def resolve_finishes(cls, values):
        if not isinstance(values, dict):
            return values
        if values.get("fromFinish") is None and values.get("fromFoil") is not None:
            values["fromFinish"] = values["fromFoil"]
        if values.get("toFinish") is None and values.get("toFoil") is not None:
            values["toFinish"] = values["toFoil"]
        if values.get("fromFinish") is None or values.get("toFinish") is None:
            raise ValueError("fromFinish and toFinish are required")
        return values


class OwnershipBulkItem(BaseModel):
    collectorNumber: str = Field(min_length=1, max_length=32)
    finish: int | None = Field(default=None, ge=0, le=2)
    foil: int | None = Field(default=None, ge=0, le=2)
    owned: bool
    purchaseValue: float | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_finish(cls, values):
        if isinstance(values, dict):
            return _resolve_finish_field(values)
        return values


class OwnershipBulkUpdate(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)
    items: list[OwnershipBulkItem] = Field(min_length=1)


class BulkAssignItem(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)
    collectorNumber: str = Field(min_length=1, max_length=32)
    finish: int | None = Field(default=None, ge=0, le=2)
    foil: int | None = Field(default=None, ge=0, le=2)

    @model_validator(mode="before")
    @classmethod
    def resolve_finish(cls, values):
        if isinstance(values, dict):
            return _resolve_finish_field(values)
        return values


class BulkAssignStorage(BaseModel):
    locationSlug: str = Field(min_length=1, max_length=120)
    items: list[BulkAssignItem] = Field(min_length=1)


class CopyAdjust(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)
    collectorNumber: str = Field(min_length=1, max_length=32)
    finish: int | None = Field(default=None, ge=0, le=2)
    foil: int | None = Field(default=None, ge=0, le=2)
    delta: int = Field(ge=-1, le=1)
    locationSlug: str | None = Field(default=None, max_length=120)

    @model_validator(mode="before")
    @classmethod
    def resolve_finish(cls, values):
        if isinstance(values, dict):
            return _resolve_finish_field(values)
        return values


class CopyStorageUpdate(BaseModel):
    locationSlug: str = Field(min_length=1, max_length=120)


class CopyAllocationItem(BaseModel):
    locationSlug: str = Field(min_length=1, max_length=120)
    count: int = Field(ge=0, le=99)


class SetCopyAllocations(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)
    collectorNumber: str = Field(min_length=1, max_length=32)
    finish: int | None = Field(default=None, ge=0, le=2)
    foil: int | None = Field(default=None, ge=0, le=2)
    allocations: list[CopyAllocationItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def resolve_finish(cls, values):
        if isinstance(values, dict):
            return _resolve_finish_field(values)
        return values


class ManagerSetCreate(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)


class ArtStyleRule(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    all: bool | None = None
    firstNumber: int | None = None
    lastNumber: int | None = None
    prefix: str | None = Field(default=None, max_length=16)
    suffix: str | None = Field(default=None, max_length=16)


class ArtStyleRulesUpdate(BaseModel):
    rules: list[ArtStyleRule] = Field(min_length=1)


class DeckCardAdd(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)
    collectorNumber: str = Field(min_length=1, max_length=32)
    finish: int | None = Field(default=None, ge=0, le=2)
    foil: int | None = Field(default=None, ge=0, le=2)
    section: str = Field(default="main", min_length=1, max_length=16)
    qty: int = Field(default=1, ge=1, le=99)

    @model_validator(mode="before")
    @classmethod
    def resolve_finish(cls, values):
        if isinstance(values, dict):
            return _resolve_finish_field(values)
        return values


class DeckCardRemove(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)
    collectorNumber: str = Field(min_length=1, max_length=32)
    finish: int | None = Field(default=None, ge=0, le=2)
    foil: int | None = Field(default=None, ge=0, le=2)
    section: str = Field(default="main", min_length=1, max_length=16)
    qty: int = Field(default=1, ge=1, le=99)

    @model_validator(mode="before")
    @classmethod
    def resolve_finish(cls, values):
        if isinstance(values, dict):
            return _resolve_finish_field(values)
        return values


class DeckCardQtyAdjust(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)
    collectorNumber: str = Field(min_length=1, max_length=32)
    finish: int | None = Field(default=None, ge=0, le=2)
    foil: int | None = Field(default=None, ge=0, le=2)
    section: str = Field(default="main", min_length=1, max_length=16)
    delta: int = Field(ge=-1, le=1)

    @model_validator(mode="before")
    @classmethod
    def resolve_finish(cls, values):
        if isinstance(values, dict):
            return _resolve_finish_field(values)
        return values


class DeckRename(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class DeckCreateCard(BaseModel):
    setCode: str = Field(min_length=1, max_length=16)
    collectorNumber: str = Field(min_length=1, max_length=32)
    finish: int | None = Field(default=None, ge=0, le=2)
    foil: int | None = Field(default=None, ge=0, le=2)

    @model_validator(mode="before")
    @classmethod
    def resolve_finish(cls, values):
        if isinstance(values, dict):
            return _resolve_finish_field(values)
        return values


class DeckCreate(BaseModel):
    format: str = Field(default="commander", min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=120)
    commanders: list[DeckCreateCard] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_create(self):
        deck_format = self.format.strip().lower()
        if deck_format not in {"commander"}:
            raise ValueError("Unsupported deck format")
        if deck_format == "commander" and len(self.commanders) < 1:
            raise ValueError("At least one commander is required")
        return self
