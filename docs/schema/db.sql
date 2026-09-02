-- Schema SQLite de reference -- GENERE depuis src/planner/storage/db.py (MIGRATIONS).
-- user_version = 1. Ne pas editer a la main : modifier db.py puis regenerer.
CREATE TABLE courses (
        id INTEGER PRIMARY KEY,
        code TEXT NOT NULL,
        title TEXT NOT NULL,
        term TEXT NOT NULL,
        institution TEXT,
        credits INTEGER,
        instructor TEXT,
        language TEXT NOT NULL DEFAULT 'fr',
        difficulty INTEGER NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
        effort_multiplier REAL NOT NULL DEFAULT 1.0,
        archived INTEGER NOT NULL DEFAULT 0,
        UNIQUE (code, term)
    );

    CREATE TABLE sessions (
        id INTEGER PRIMARY KEY,
        course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
        start TEXT NOT NULL,
        end TEXT NOT NULL,
        room TEXT,
        start_date TEXT,
        end_date TEXT,
        except_dates TEXT NOT NULL DEFAULT '[]'
    );

    CREATE TABLE evaluations (
        id INTEGER PRIMARY KEY,
        course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        external_id TEXT NOT NULL,
        title TEXT NOT NULL,
        type TEXT NOT NULL,
        weight REAL NOT NULL,
        due_at TEXT,
        start_date TEXT,
        duration_minutes INTEGER,
        modality TEXT,
        location TEXT,
        cumulative INTEGER,
        group_work INTEGER,
        content_scope TEXT NOT NULL DEFAULT '[]',
        scope_units INTEGER,
        deliverable TEXT,
        estimated_pages INTEGER,
        resources TEXT NOT NULL DEFAULT '[]',
        notes TEXT,
        confidence TEXT NOT NULL DEFAULT 'high',
        source_excerpt TEXT,
        manual_hours_override REAL,
        status TEXT NOT NULL DEFAULT 'active',
        archived INTEGER NOT NULL DEFAULT 0,
        UNIQUE (course_id, external_id)
    );

    CREATE TABLE constraints (
        id INTEGER PRIMARY KEY,
        label TEXT NOT NULL,
        category TEXT NOT NULL,
        weekday INTEGER CHECK (weekday BETWEEN 0 AND 6),
        specific_date TEXT,
        start TEXT NOT NULL,
        end TEXT NOT NULL,
        rrule TEXT,
        priority INTEGER NOT NULL DEFAULT 0,
        color TEXT,
        CHECK ((weekday IS NULL) != (specific_date IS NULL))
    );

    CREATE TABLE generations (
        id INTEGER PRIMARY KEY,
        created_at TEXT NOT NULL,
        params_hash TEXT NOT NULL,
        coverage REAL,
        deficit_total REAL
    );

    CREATE TABLE study_blocks (
        id INTEGER PRIMARY KEY,
        evaluation_id INTEGER NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
        start_at TEXT NOT NULL,
        end_at TEXT NOT NULL,
        planned_minutes INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'planned',
        locked INTEGER NOT NULL DEFAULT 0,
        generation_id INTEGER REFERENCES generations(id),
        actual_minutes INTEGER,
        efficiency REAL,
        note TEXT
    );

    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE INDEX idx_evaluations_course ON evaluations(course_id);
    CREATE INDEX idx_blocks_evaluation ON study_blocks(evaluation_id);
    CREATE INDEX idx_blocks_start ON study_blocks(start_at);
