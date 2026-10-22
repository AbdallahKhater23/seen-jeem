"""مخطط SQLite وترحيلاته التراكمية.

الإصدار 2 يضيف محرك الاختيار ثلاثي الطبقات:
- هوية المجموعة الواقعية `fact_group_id` لكل سؤال.
- عدّاد الاستخدام وموضع السحب `deck_position`.
- الفئات الاثنتي عشرة الأصلية واختيار ست فئات لكل مباراة.
- جداول التزامن (`harvester_cursors`, `sync_jobs`) وسجل الوقائع (`fact_records`).

الإصدار 3 يجعل القوى مملوكة ومفعّلة من الخادم:
- `match_powers` لاختيارات السحب ولمرة استخدام واحدة لكل فريق.
- جلسة سؤال على الخانة (`opened_at`, `revealed_at`, `active_team`, `noise_until`).

الإصدار 4 يحمي عمليات التغيير بتوكن المضيف:
- `matches.host_token_hash` يخزّن بصمة SHA-256 لتوكن يُصدر مرة واحدة عند الإنشاء.
- كل مسار تغيير (`draft`, `open`, `reveal`, `abandon`, `activate`, `resolve`,
  `reroll`, `adjust`, `complete`) يطلب ترويسة `X-Host-Token` المطابقة.

الإصدار 5 يضيف الهوية ومنع التكرار على مستوى المشارك:
- `users`: ملفات لاعبين مسماة وظلّية (للأجهزة بدون ملف).
- `device_installations`: سجل تثبيت لكل جهاز ببصمة اعتماد عشوائية + ظلّه.
- `match_participants`: عضوية المباراة المطبّعة (مباراة، لاعب، فريق).
- `user_question_history`: أول تعرّض لكل (لاعب، سؤال) بفريدة قاعدية.
- `matches.host_installation_id`: التثبيت المضيف للمباراة.

الإصدار 6 يضيف بصمات كلمات المرور وجلسات الحسابات وربط المضيف بالحساب.

الإصدار 7 يوسّع المحتوى ويضيف اشتقاق المصدر:
- 17 فئة و51 دلوًا (5 فئات جديدة: القرآن، الألقاب، التقنية، ألعاب الفيديو، الأعواد).
- `source_license` و`source_claim` على `questions` و`fact_records`.
- ألغاز الأعواد تُخزّن كنوع `text` مع `payload.kind='matchstick'` حفاظًا على
  قيد النوع الحالي، ويحوّلها المحوّل إلى نوع واجهة مستقل.

الترقية تراكمية: قواعد الإصدارات 1-6 تُرقّى بـ ALTER TABLE فقط دون حذف صفوف.
الأعمدة الجديدة تُضاف قابلة للـ NULL، والقيود الصارمة مفروضة في طبقة الخدمة.
"""

from __future__ import annotations

SCHEMA_VERSION = 8

FOOTBALL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS football_entities (
    id TEXT PRIMARY KEY,
    display_name_ar TEXT NOT NULL,
    aliases_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(aliases_json))
);
CREATE TABLE IF NOT EXISTS football_events (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    event_year INTEGER NULL
);
CREATE TABLE IF NOT EXISTS football_facts (
    id TEXT PRIMARY KEY,
    event_id TEXT NULL REFERENCES football_events(id),
    topic_id TEXT NOT NULL,
    primary_entity_id TEXT NOT NULL REFERENCES football_entities(id)
);
CREATE INDEX IF NOT EXISTS idx_football_facts_event ON football_facts(event_id);
CREATE INDEX IF NOT EXISTS idx_football_facts_entity ON football_facts(primary_entity_id);
CREATE TABLE IF NOT EXISTS question_metadata (
    question_id INTEGER PRIMARY KEY REFERENCES questions(id) ON DELETE RESTRICT,
    fact_id TEXT NOT NULL REFERENCES football_facts(id),
    era TEXT NOT NULL DEFAULT 'unknown'
        CHECK (era IN ('classic','golden_era','modern_peak','contemporary','unknown')),
    archetype TEXT NOT NULL,
    mechanic TEXT NOT NULL DEFAULT 'direct_recall',
    tone TEXT NOT NULL DEFAULT 'neutral',
    template_family TEXT NOT NULL,
    secondary_entities_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(secondary_entities_json)),
    quality_score REAL NOT NULL CHECK (quality_score BETWEEN 0 AND 1),
    difficulty_confidence REAL NULL CHECK (difficulty_confidence BETWEEN 0 AND 1),
    editorial_note TEXT NOT NULL,
    aliases_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(aliases_json)),
    tolerance_type TEXT NOT NULL DEFAULT 'exact',
    record_as_of_date TEXT NULL,
    visual_json TEXT NULL CHECK (visual_json IS NULL OR json_valid(visual_json)),
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','published','quarantined')),
    content_version INTEGER NOT NULL DEFAULT 1 CHECK (content_version >= 1)
);
CREATE INDEX IF NOT EXISTS idx_question_metadata_fact ON question_metadata(fact_id);
CREATE INDEX IF NOT EXISTS idx_question_metadata_review ON question_metadata(review_status,question_id);
CREATE TABLE IF NOT EXISTS football_category_policy (
    category_id INTEGER PRIMARY KEY REFERENCES categories(id),
    verified_only INTEGER NOT NULL DEFAULT 1 CHECK (verified_only IN (0,1))
);
CREATE TABLE IF NOT EXISTS content_reviews (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    content_version INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('published','quarantined')),
    rubric_json TEXT NOT NULL CHECK (json_valid(rubric_json)),
    reviewed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(question_id,content_version)
);
CREATE TABLE IF NOT EXISTS match_question_allocations (
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    fact_id TEXT NULL REFERENCES football_facts(id),
    PRIMARY KEY(match_id,question_id),
    UNIQUE(match_id,fact_id)
);
CREATE TRIGGER IF NOT EXISTS trg_match_initial_allocation
AFTER INSERT ON match_tiles
BEGIN
    INSERT INTO match_question_allocations(match_id,question_id,fact_id)
    VALUES (NEW.match_id,NEW.question_id,
        (SELECT fact_id FROM question_metadata WHERE question_id=NEW.question_id));
END;
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name_ar TEXT NOT NULL,
    icon TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS fact_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_group_id TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_entity_id TEXT NULL,
    source_url TEXT NULL,
    source_license TEXT NULL,
    source_claim TEXT NULL,
    verification_status TEXT NOT NULL DEFAULT 'curated',
    payload_json TEXT NOT NULL,
    content_version INTEGER NOT NULL DEFAULT 1,
    retrieved_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (fact_group_id, fact_type, source_name)
);
CREATE INDEX IF NOT EXISTS idx_fact_records_group ON fact_records(fact_group_id);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    difficulty INTEGER NOT NULL CHECK (difficulty IN (200, 400, 600)),
    question_type TEXT NOT NULL CHECK (question_type IN ('flag', 'text', 'career', 'spot_diff')),
    question_text TEXT NOT NULL,
    flag_code TEXT NULL,
    media_url_a TEXT NULL,
    media_url_b TEXT NULL,
    payload_json TEXT NULL,
    answer_text TEXT NOT NULL,
    tolerance TEXT NOT NULL DEFAULT 'مطابق تماماً',
    explanation TEXT NULL,
    source_name TEXT NULL,
    source_url TEXT NULL,
    source_checked_at TEXT NULL,
    source_license TEXT NULL,
    source_claim TEXT NULL,
    content_origin TEXT NOT NULL CHECK (content_origin IN ('curated', 'api_sourced', 'generated_puzzle')),
    fingerprint TEXT UNIQUE NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    is_reserved_backup INTEGER NOT NULL DEFAULT 0 CHECK (is_reserved_backup IN (0, 1)),
    fact_group_id TEXT NULL,
    source_entity_id TEXT NULL,
    verification_status TEXT NOT NULL DEFAULT 'curated',
    content_version INTEGER NOT NULL DEFAULT 1,
    times_played INTEGER NOT NULL DEFAULT 0,
    last_played_match_id INTEGER NULL,
    deck_position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_questions_cat_diff_active
    ON questions(category_id, difficulty, is_active);
CREATE INDEX IF NOT EXISTS idx_questions_backup
    ON questions(is_reserved_backup, is_active);
CREATE INDEX IF NOT EXISTS idx_questions_shoe
    ON questions(category_id, difficulty, is_active, times_played, deck_position);
CREATE INDEX IF NOT EXISTS idx_questions_fact_group
    ON questions(fact_group_id);

CREATE TABLE IF NOT EXISTS question_buckets (
    category_id INTEGER NOT NULL REFERENCES categories(id),
    difficulty INTEGER NOT NULL CHECK (difficulty IN (200, 400, 600)),
    cycle INTEGER NOT NULL DEFAULT 1 CHECK (cycle >= 1),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (category_id, difficulty)
);

CREATE TABLE IF NOT EXISTS question_usage (
    question_id INTEGER NOT NULL REFERENCES questions(id),
    cycle INTEGER NOT NULL CHECK (cycle >= 1),
    used_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (question_id, cycle)
);
CREATE INDEX IF NOT EXISTS idx_question_usage_cycle ON question_usage(cycle);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_code TEXT UNIQUE NOT NULL,
    team1_name TEXT NOT NULL,
    team2_name TEXT NOT NULL,
    score_team1 INTEGER NOT NULL DEFAULT 0,
    score_team2 INTEGER NOT NULL DEFAULT 0,
    current_turn TEXT NOT NULL DEFAULT 'team1' CHECK (current_turn IN ('team1', 'team2')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    winner TEXT NULL CHECK (winner IN ('team1', 'team2', 'tie')),
    coin_toss_winner TEXT NOT NULL DEFAULT 'team1' CHECK (coin_toss_winner IN ('team1', 'team2')),
    selected_categories_json TEXT NOT NULL DEFAULT '[]',
    host_token_hash TEXT NULL,
    host_installation_id INTEGER NULL REFERENCES device_installations(id) ON DELETE SET NULL,
    host_user_id INTEGER NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_finished
    ON matches(status, updated_at);

CREATE TABLE IF NOT EXISTS match_tiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    tile_key TEXT NOT NULL,
    category_id INTEGER NULL REFERENCES categories(id),
    difficulty INTEGER NULL CHECK (difficulty IS NULL OR difficulty IN (200, 400, 600)),
    question_id INTEGER NOT NULL REFERENCES questions(id),
    is_backup INTEGER NOT NULL DEFAULT 0 CHECK (is_backup IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'unplayed' CHECK (status IN ('unplayed', 'played', 'rerolled')),
    outcome TEXT NULL CHECK (outcome IN ('team1', 'team2', 'none')),
    delta_team1 INTEGER NOT NULL DEFAULT 0,
    delta_team2 INTEGER NOT NULL DEFAULT 0,
    powers_applied_json TEXT NULL,
    compatible_categories_json TEXT NULL,
    compatible_difficulties_json TEXT NULL,
    answered_at TEXT NULL,
    opened_at TEXT NULL,
    revealed_at TEXT NULL,
    active_team TEXT NULL,
    noise_until TEXT NULL,
    rerolled_from_question_id INTEGER NULL REFERENCES questions(id),
    resolved_request_id TEXT NULL,
    allocation_cycle INTEGER NOT NULL DEFAULT 1 CHECK (allocation_cycle >= 1),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(match_id, tile_key),
    CHECK (
        (is_backup = 0 AND category_id IS NOT NULL AND difficulty IS NOT NULL)
        OR (is_backup = 1)
    ),
    CHECK (
        (is_backup = 1 AND compatible_categories_json IS NOT NULL)
        OR (is_backup = 0)
    )
);
CREATE INDEX IF NOT EXISTS idx_match_tiles_board
    ON match_tiles(match_id, is_backup, status);
CREATE INDEX IF NOT EXISTS idx_match_tiles_question
    ON match_tiles(question_id, status);
CREATE INDEX IF NOT EXISTS idx_match_tiles_bucket
    ON match_tiles(match_id, category_id, difficulty, is_backup);
CREATE UNIQUE INDEX IF NOT EXISTS idx_match_tiles_request
    ON match_tiles(match_id, resolved_request_id)
    WHERE resolved_request_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS match_powers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    team_key TEXT NOT NULL CHECK (team_key IN ('team1', 'team2')),
    power_id TEXT NOT NULL,
    pick_index INTEGER NOT NULL CHECK (pick_index >= 0 AND pick_index < 6),
    drafted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    used_at TEXT NULL,
    used_tile_key TEXT NULL,
    UNIQUE(match_id, pick_index),
    UNIQUE(match_id, team_key, power_id)
);
CREATE INDEX IF NOT EXISTS idx_match_powers_match
    ON match_powers(match_id, pick_index);
CREATE INDEX IF NOT EXISTS idx_match_powers_team
    ON match_powers(match_id, team_key, power_id);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NULL,
    kind TEXT NOT NULL DEFAULT 'named' CHECK (kind IN ('named', 'shadow')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS device_installations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    install_code TEXT UNIQUE NOT NULL,
    credential_hash TEXT UNIQUE NOT NULL,
    shadow_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    last_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    revoked INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_installations_shadow
    ON device_installations(shadow_user_id);

CREATE TABLE IF NOT EXISTS match_participants (
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    team_key TEXT NOT NULL CHECK (team_key IN ('team1', 'team2')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (match_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_participants_user
    ON match_participants(user_id, match_id);

CREATE TABLE IF NOT EXISTS user_question_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    match_id INTEGER NULL REFERENCES matches(id) ON DELETE SET NULL,
    outcome TEXT NOT NULL DEFAULT 'none' CHECK (outcome IN ('team1', 'team2', 'none')),
    played_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(user_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_history_user
    ON user_question_history(user_id, question_id);

CREATE TABLE IF NOT EXISTS account_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_account_sessions_expiry ON account_sessions(expires_at);
CREATE TABLE IF NOT EXISTS auth_attempts (
    scope TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL DEFAULT 0,
    window_start INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS score_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    request_id TEXT NOT NULL,
    team_key TEXT NOT NULL CHECK (team_key IN ('team1', 'team2')),
    delta INTEGER NOT NULL CHECK (delta IN (-100, 100)),
    reason TEXT NOT NULL DEFAULT 'تعديل يدوي من المقدم',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(match_id, request_id)
);
CREATE INDEX IF NOT EXISTS idx_adjustments_match ON score_adjustments(match_id, created_at);

CREATE TABLE IF NOT EXISTS match_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    request_key TEXT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_events_match ON match_events(match_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_request
    ON match_events(match_id, request_key)
    WHERE request_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS idempotency_keys (
    scope TEXT NOT NULL,
    key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (scope, key)
);

CREATE TABLE IF NOT EXISTS seed_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seed_version TEXT NOT NULL,
    deterministic_seed INTEGER NOT NULL,
    inserted INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    invalid INTEGER NOT NULL DEFAULT 0,
    total_active INTEGER NOT NULL DEFAULT 0,
    network_status TEXT NOT NULL DEFAULT 'offline',
    report_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS harvester_cursors (
    source_name TEXT NOT NULL,
    category_slug TEXT NOT NULL,
    cursor TEXT NOT NULL DEFAULT '0',
    last_synced_at TEXT NULL,
    total_harvested INTEGER NOT NULL DEFAULT 0,
    checkpoint_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (source_name, category_slug)
);

CREATE TABLE IF NOT EXISTS sync_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT UNIQUE NOT NULL,
    source_name TEXT NOT NULL,
    category_slug TEXT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'partial', 'failed')),
    requested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    started_at TEXT NULL,
    finished_at TEXT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sync_jobs_active
    ON sync_jobs(source_name, COALESCE(category_slug, ''))
    WHERE status IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS idx_sync_jobs_recent ON sync_jobs(requested_at);
"""

# ترقية قاعدة الإصدار 2 إلى 3: أعمدة جلسة السؤال فقط؛ جدول القوى يُنشأ
# بواسطة SCHEMA_SQL (CREATE TABLE IF NOT EXISTS).
MIGRATION_V2_TO_V3 = [
    "ALTER TABLE match_tiles ADD COLUMN opened_at TEXT NULL",
    "ALTER TABLE match_tiles ADD COLUMN revealed_at TEXT NULL",
    "ALTER TABLE match_tiles ADD COLUMN active_team TEXT NULL",
    "ALTER TABLE match_tiles ADD COLUMN noise_until TEXT NULL",
]

# ترقية قاعدة الإصدار 3 إلى 4: بصمة توكن المضيف فقط. المباريات القديمة
# بدون بصمة ترفض عمليات التغيير (HOST_TOKEN_UNSET) حتى تُنشأ مباراة جديدة.
MIGRATION_V3_TO_V4 = [
    "ALTER TABLE matches ADD COLUMN host_token_hash TEXT NULL",
]

# ترقية قاعدة الإصدار 4 إلى 5: عمود التثبيت المضيف فقط؛ الجداول الجديدة
# تُنشأ بواسطة SCHEMA_SQL (CREATE TABLE IF NOT EXISTS).
MIGRATION_V4_TO_V5 = [
    "ALTER TABLE matches ADD COLUMN host_installation_id INTEGER NULL"
    " REFERENCES device_installations(id) ON DELETE SET NULL",
]

# ترقية قاعدة الإصدار 1 إلى 2 بدون فقدان صفوف أو تاريخ المباريات.
MIGRATION_V1_TO_V2 = [
    "ALTER TABLE questions ADD COLUMN fact_group_id TEXT NULL",
    "ALTER TABLE questions ADD COLUMN source_entity_id TEXT NULL",
    "ALTER TABLE questions ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'curated'",
    "ALTER TABLE questions ADD COLUMN content_version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE questions ADD COLUMN times_played INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE questions ADD COLUMN last_played_match_id INTEGER NULL",
    "ALTER TABLE questions ADD COLUMN deck_position INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE matches ADD COLUMN selected_categories_json TEXT NOT NULL DEFAULT '[]'",
    # هوية واقعية مؤقتة وواضحة للصفوف القديمة: ليست مجموعة واقعية مزعومة.
    "UPDATE questions SET fact_group_id = 'legacy:' || fingerprint WHERE fact_group_id IS NULL",
    "UPDATE questions SET deck_position = id WHERE deck_position = 0",
    "UPDATE matches SET selected_categories_json = '[\"flags\",\"football\",\"worldcup\",\"career\",\"riddles\",\"spotdiff\"]'"
    " WHERE selected_categories_json = '[]'",
]
