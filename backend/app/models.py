"""عقود API بصيغة snake_case، مع محوّل موثّق للواجهة في integration/.

اختيار الفئات صريح: ستة معرّفات slug مختلفة بالضبط في كل مباراة.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

TeamKey = Literal["team1", "team2"]
OutcomeKey = Literal["team1", "team2", "none"]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class CategoryOut(BaseModel):
    id: int
    slug: str
    name_ar: str
    icon: str
    sort_order: int
    # عدد الأسئلة المؤهّلة غير الملعوبة (نشطة، غير محجوزة، غير مستخدمة بالدورة الحالية).
    eligible_count: int = 0
    fact_groups: int = 0
    capacity_100_matches: bool = False


class QuestionOut(BaseModel):
    id: int
    category_slug: str
    category_name: str
    difficulty: int
    question_type: str
    question_text: str
    flag_code: str | None = None
    media_url_a: str | None = None
    media_url_b: str | None = None
    payload: dict[str, Any] | None = None
    answer_text: str | None = None
    tolerance: str | None = None
    visual: dict[str, Any] | None = None
    explanation: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_checked_at: str | None = None
    source_license: str | None = None
    source_claim: str | None = None
    content_origin: str
    fact_group_id: str | None = None


class MatchOut(BaseModel):
    match_code: str
    team1_name: str
    team2_name: str
    score_team1: int
    score_team2: int
    current_turn: TeamKey
    status: str
    winner: str | None = None
    coin_toss_winner: TeamKey
    version: int
    created_at: str
    updated_at: str
    selected_categories: list[str] = Field(default_factory=list)


class TileOut(BaseModel):
    tile_key: str
    category_slug: str | None = None
    difficulty: int | None = None
    is_backup: bool
    status: str
    outcome: str | None = None
    delta_team1: int = 0
    delta_team2: int = 0
    powers_applied: list[str] = Field(default_factory=list)
    question: QuestionOut
    answered_at: str | None = None
    opened_at: str | None = None
    revealed_at: str | None = None
    active_team: TeamKey | None = None
    noise_until: str | None = None
    compatible_categories: list[str] = Field(default_factory=list)
    compatible_difficulties: list[int] = Field(default_factory=list)
    allocation_cycle: int = 1


class DraftPickOut(BaseModel):
    team: TeamKey
    power_id: str
    pick_index: int
    drafted_at: str
    used_at: str | None = None
    used_tile_key: str | None = None


class DraftOut(BaseModel):
    order: list[TeamKey]
    picks: list[DraftPickOut]
    current_team: TeamKey | None = None
    complete: bool
    remaining: int


class ParticipantOut(BaseModel):
    user_id: int
    username: str | None = None
    display_name: str
    kind: str
    team: TeamKey


class BoardOut(BaseModel):
    match: MatchOut
    tiles: list[TileOut]
    backups: list[TileOut]
    draft: DraftOut
    participants: list[ParticipantOut] = Field(default_factory=list)


class BoardCreateOut(BoardOut):
    """رد الإنشاء فقط: يحمل توكن المضيف مرة واحدة، ولا يظهر في أي قراءة."""

    host_token: str = Field(min_length=32, max_length=128)


class UserCreateIn(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    display_name: str | None = Field(default=None, max_length=40)


class UserOut(BaseModel):
    id: int
    username: str | None = None
    display_name: str
    kind: str
    is_active: bool = True
    created_at: str


class InstallationRegisterOut(BaseModel):
    installation_id: int
    install_code: str
    credential: str
    shadow_user_id: int
    created_at: str
    last_seen_at: str
    revoked: bool = False
    idempotent_replay: bool = False


class InstallationOut(BaseModel):
    installation_id: int
    install_code: str
    shadow_user_id: int
    created_at: str
    last_seen_at: str
    revoked: bool = False


class MatchCreateIn(BaseModel):
    team1_name: str = Field(min_length=1, max_length=40)
    team2_name: str = Field(min_length=1, max_length=40)
    starting_turn: TeamKey | None = None
    # توافق خلفي مع الواجهة السابقة؛ يُستخدم فقط إذا غاب starting_turn.
    coin_toss_winner: TeamKey | None = None
    category_slugs: list[str] = Field(min_length=6, max_length=6)
    # مشاركون اختياريون؛ الفراغ يعني اللعب الظلّي للتثبيت المضيف وحده.
    team1_user_ids: list[int] = Field(default_factory=list, max_length=16)
    team2_user_ids: list[int] = Field(default_factory=list, max_length=16)

    @field_validator("team1_name", "team2_name")
    @classmethod
    def strip_names(cls, value: str) -> str:
        return value.strip()

    @field_validator("category_slugs")
    @classmethod
    def exactly_six_distinct(cls, value: list[str]) -> list[str]:
        cleaned = [slug.strip() for slug in value if isinstance(slug, str) and slug.strip()]
        if len(cleaned) != 6:
            raise ValueError("اختيار الفئات لازم يكون ستة معرّفات غير فاضية.")
        if len(set(cleaned)) != 6:
            raise ValueError("الفئات الست لازم تكون مختلفة.")
        return cleaned


class DraftPickIn(BaseModel):
    power_id: str = Field(min_length=1, max_length=32)
    expected_version: int = Field(ge=1)


class DraftResultOut(BaseModel):
    match: MatchOut
    draft: DraftOut
    pick: DraftPickOut
    idempotent_replay: bool = False


class TileSessionOut(BaseModel):
    opened_at: str
    revealed_at: str | None = None
    active_team: TeamKey
    noise_until: str | None = None


class TileOpenOut(BaseModel):
    match: MatchOut
    tile: TileOut
    session: TileSessionOut
    idempotent_replay: bool = False


class TileRevealOut(BaseModel):
    match: MatchOut
    tile: TileOut
    session: TileSessionOut
    idempotent_replay: bool = False


class TileAbandonOut(BaseModel):
    match: MatchOut
    tile: TileOut
    idempotent_replay: bool = False


class PowerActivationIn(BaseModel):
    team: TeamKey
    expected_version: int = Field(ge=1)


class PowerActivationOut(BaseModel):
    match: MatchOut
    tile: TileOut
    activation: dict[str, Any]
    backup_used: str | None = None
    idempotent_replay: bool = False


class ResolveIn(BaseModel):
    outcome: OutcomeKey
    powers_applied: list[str] = Field(default_factory=list, max_length=8)
    expected_version: int = Field(ge=1)

    @field_validator("powers_applied")
    @classmethod
    def unique_powers(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class RerollIn(BaseModel):
    expected_version: int = Field(ge=1)


class AdjustmentIn(BaseModel):
    team: TeamKey
    delta: Literal[-100, 100]
    reason: str = Field(default="تعديل يدوي من المقدم", max_length=120)
    expected_version: int = Field(ge=1)


class VersionIn(BaseModel):
    expected_version: int = Field(ge=1)


class ResolveResultOut(BaseModel):
    match: MatchOut
    tile: TileOut
    score_ledger: list[dict[str, Any]]
    idempotent_replay: bool = False


class RerollResultOut(BaseModel):
    match: MatchOut
    tile: TileOut
    backup_used: str
    idempotent_replay: bool = False


class AdjustmentResultOut(BaseModel):
    match: MatchOut
    adjustment: dict[str, Any]
    idempotent_replay: bool = False


class MatchResultOut(BaseModel):
    match: MatchOut
    idempotent_replay: bool = False


class HealthOut(BaseModel):
    status: str
    database: str
    schema_version: int
    seed_complete: bool
    categories: int = 0
    total_active: int = 0


class EventsOut(BaseModel):
    events: list[dict[str, Any]]
    next_before_id: int | None = None


class SeedStatusOut(BaseModel):
    total_active: int
    buckets: dict[str, int]
    complete: bool
    content_floor_complete: bool = False
    capacity_100_matches: bool = False
    last_run: dict[str, Any] | None = None


class AdminQuestionBankOut(BaseModel):
    generated_at: str
    standards: dict[str, int]
    totals: dict[str, int]
    origins: dict[str, int]
    categories: list[dict[str, Any]]
    buckets: list[dict[str, Any]]


class AdminSeedHistoryOut(BaseModel):
    runs: list[dict[str, Any]]
    total: int


class AdminMatchesOut(BaseModel):
    matches: list[dict[str, Any]]
    total: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class AdminMatchEventsOut(BaseModel):
    match: dict[str, Any]
    events: list[dict[str, Any]]
    next_before_id: int | None = None


class SyncStartOut(BaseModel):
    accepted: bool
    status: str
    job_id: int | None = None
    job_key: str | None = None
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class SyncJobOut(BaseModel):
    jobs: list[dict[str, Any]]
    cursors: list[dict[str, Any]] = Field(default_factory=list)
    cache_dir: str = ""
    durable: bool = False
