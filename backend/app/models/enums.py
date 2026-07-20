from enum import StrEnum


class DataSource(StrEnum):
    MANUAL = "manual"
    STRAVA = "strava"
    OURA = "oura"
    APPLE_HEALTH = "apple_health"
    GARMIN = "garmin"
    CSV = "csv"
    FIT_UPLOAD = "fit_upload"
    LINX_CGM = "linx_cgm"
    DEXCOM = "dexcom"
    LIBRE = "libre"
    OPEN_METEO = "open_meteo"


class RunType(StrEnum):
    EASY = "easy"
    LONG = "long"
    INTERVAL = "interval"
    TEMPO = "tempo"
    RECOVERY = "recovery"
    RACE = "race"
    OTHER = "other"


class RunTypeSource(StrEnum):
    USER = "user"
    EXTRACTED = "extracted"
    DEFAULT = "default"
    INFERRED = "inferred"


class CyclePhase(StrEnum):
    MENSTRUAL = "menstrual"
    FOLLICULAR = "follicular"
    OVULATORY = "ovulatory"
    LUTEAL = "luteal"


class OAuthProvider(StrEnum):
    STRAVA = "strava"
    OURA = "oura"


class ImportJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ImportJobType(StrEnum):
    INITIAL_SYNC = "initial_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    CSV_UPLOAD = "csv_upload"
    FILE_UPLOAD = "file_upload"
