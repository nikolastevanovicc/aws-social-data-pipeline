-- PostgreSQL schema for Superset dashboard tables.
-- These tables mirror the current gold Parquet outputs under gold/hacker-news/
-- and gold/x/ so a loader can copy S3 gold metrics into PostgreSQL later.

CREATE TABLE IF NOT EXISTS hn_daily_item_counts (
    date DATE NOT NULL,
    platform TEXT NOT NULL,
    year TEXT,
    month TEXT,
    day TEXT,
    gold_processed_at_utc TIMESTAMPTZ,
    story_count INTEGER,
    ask_count INTEGER,
    comment_count INTEGER,
    job_count INTEGER,
    poll_count INTEGER,
    total_count INTEGER
);

CREATE TABLE IF NOT EXISTS hn_daily_users_metric (
    date DATE NOT NULL,
    platform TEXT NOT NULL,
    year TEXT,
    month TEXT,
    day TEXT,
    gold_processed_at_utc TIMESTAMPTZ,
    total_users BIGINT,
    active_users BIGINT
);

CREATE TABLE IF NOT EXISTS hn_top_story_posts (
    date DATE NOT NULL,
    platform TEXT NOT NULL,
    year TEXT,
    month TEXT,
    day TEXT,
    gold_processed_at_utc TIMESTAMPTZ,
    rank INTEGER,
    post_id TEXT,
    source_post_id TEXT,
    author_user_id TEXT,
    author_username TEXT,
    post_type TEXT,
    title TEXT,
    url TEXT,
    score NUMERIC
);

CREATE TABLE IF NOT EXISTS hn_top_job_posts (
    date DATE NOT NULL,
    platform TEXT NOT NULL,
    year TEXT,
    month TEXT,
    day TEXT,
    gold_processed_at_utc TIMESTAMPTZ,
    rank INTEGER,
    post_id TEXT,
    source_post_id TEXT,
    author_user_id TEXT,
    author_username TEXT,
    post_type TEXT,
    title TEXT,
    url TEXT,
    score NUMERIC
);

CREATE TABLE IF NOT EXISTS hn_top_users_by_karma (
    date DATE NOT NULL,
    platform TEXT NOT NULL,
    year TEXT,
    month TEXT,
    day TEXT,
    gold_processed_at_utc TIMESTAMPTZ,
    rank INTEGER,
    user_id TEXT,
    source_user_id TEXT,
    username TEXT,
    karma_score NUMERIC
);

CREATE TABLE IF NOT EXISTS hn_bottom_users_by_karma (
    date DATE NOT NULL,
    platform TEXT NOT NULL,
    year TEXT,
    month TEXT,
    day TEXT,
    gold_processed_at_utc TIMESTAMPTZ,
    rank INTEGER,
    user_id TEXT,
    source_user_id TEXT,
    username TEXT,
    karma_score NUMERIC
);

CREATE TABLE IF NOT EXISTS hn_data_quality_summary (
    table_name TEXT NOT NULL,
    platform TEXT NOT NULL,
    data_date DATE NOT NULL,
    ingest_date DATE,
    row_count BIGINT,
    column_count INTEGER,
    non_null_cell_count BIGINT,
    total_cell_count BIGINT,
    data_quality_score NUMERIC(5, 2),
    silver_processed_at_utc TIMESTAMPTZ,
    gold_processed_at_utc TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS x_daily_users_metric (
    date DATE NOT NULL,
    platform TEXT NOT NULL,
    year TEXT,
    month TEXT,
    day TEXT,
    gold_processed_at_utc TIMESTAMPTZ,
    total_users BIGINT,
    active_users BIGINT
);

CREATE TABLE IF NOT EXISTS x_top_users_by_followers (
    date DATE NOT NULL,
    platform TEXT NOT NULL,
    year TEXT,
    month TEXT,
    day TEXT,
    gold_processed_at_utc TIMESTAMPTZ,
    rank INTEGER,
    user_id TEXT,
    source_user_id TEXT,
    username TEXT,
    display_name TEXT,
    followers_count BIGINT,
    following_count BIGINT,
    is_verified BOOLEAN
);

CREATE TABLE IF NOT EXISTS x_top_posts_by_engagement (
    date DATE NOT NULL,
    platform TEXT NOT NULL,
    year TEXT,
    month TEXT,
    day TEXT,
    gold_processed_at_utc TIMESTAMPTZ,
    rank INTEGER,
    post_id TEXT,
    source_post_id TEXT,
    author_user_id TEXT,
    author_username TEXT,
    post_type TEXT,
    content_text TEXT,
    like_count BIGINT,
    retweet_count BIGINT,
    reply_count BIGINT,
    quote_count BIGINT,
    engagement_count BIGINT
);

CREATE TABLE IF NOT EXISTS x_hashtag_trends (
    date DATE NOT NULL,
    platform TEXT NOT NULL,
    year TEXT,
    month TEXT,
    day TEXT,
    gold_processed_at_utc TIMESTAMPTZ,
    rank INTEGER,
    tag TEXT NOT NULL,
    tag_type TEXT,
    post_count BIGINT
);

CREATE TABLE IF NOT EXISTS x_data_quality_summary (
    table_name TEXT NOT NULL,
    platform TEXT NOT NULL,
    data_date DATE NOT NULL,
    ingest_date DATE,
    row_count BIGINT,
    column_count INTEGER,
    non_null_cell_count BIGINT,
    total_cell_count BIGINT,
    data_quality_score NUMERIC(5, 2),
    silver_processed_at_utc TIMESTAMPTZ,
    gold_processed_at_utc TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_hn_daily_item_counts_date
    ON hn_daily_item_counts (date);
CREATE INDEX IF NOT EXISTS idx_hn_daily_item_counts_platform
    ON hn_daily_item_counts (platform);

CREATE INDEX IF NOT EXISTS idx_hn_daily_users_metric_date
    ON hn_daily_users_metric (date);
CREATE INDEX IF NOT EXISTS idx_hn_daily_users_metric_platform
    ON hn_daily_users_metric (platform);

CREATE INDEX IF NOT EXISTS idx_hn_top_story_posts_date
    ON hn_top_story_posts (date);
CREATE INDEX IF NOT EXISTS idx_hn_top_story_posts_platform
    ON hn_top_story_posts (platform);
CREATE INDEX IF NOT EXISTS idx_hn_top_story_posts_rank
    ON hn_top_story_posts (rank);

CREATE INDEX IF NOT EXISTS idx_hn_top_job_posts_date
    ON hn_top_job_posts (date);
CREATE INDEX IF NOT EXISTS idx_hn_top_job_posts_platform
    ON hn_top_job_posts (platform);
CREATE INDEX IF NOT EXISTS idx_hn_top_job_posts_rank
    ON hn_top_job_posts (rank);

CREATE INDEX IF NOT EXISTS idx_hn_top_users_by_karma_date
    ON hn_top_users_by_karma (date);
CREATE INDEX IF NOT EXISTS idx_hn_top_users_by_karma_platform
    ON hn_top_users_by_karma (platform);
CREATE INDEX IF NOT EXISTS idx_hn_top_users_by_karma_rank
    ON hn_top_users_by_karma (rank);

CREATE INDEX IF NOT EXISTS idx_hn_bottom_users_by_karma_date
    ON hn_bottom_users_by_karma (date);
CREATE INDEX IF NOT EXISTS idx_hn_bottom_users_by_karma_platform
    ON hn_bottom_users_by_karma (platform);
CREATE INDEX IF NOT EXISTS idx_hn_bottom_users_by_karma_rank
    ON hn_bottom_users_by_karma (rank);

CREATE INDEX IF NOT EXISTS idx_hn_data_quality_summary_data_date
    ON hn_data_quality_summary (data_date);
CREATE INDEX IF NOT EXISTS idx_hn_data_quality_summary_platform
    ON hn_data_quality_summary (platform);
CREATE INDEX IF NOT EXISTS idx_hn_data_quality_summary_table_name
    ON hn_data_quality_summary (table_name);
CREATE INDEX IF NOT EXISTS idx_hn_data_quality_summary_score
    ON hn_data_quality_summary (data_quality_score);

CREATE INDEX IF NOT EXISTS idx_x_daily_users_metric_date
    ON x_daily_users_metric (date);
CREATE INDEX IF NOT EXISTS idx_x_daily_users_metric_platform
    ON x_daily_users_metric (platform);

CREATE INDEX IF NOT EXISTS idx_x_top_users_by_followers_date
    ON x_top_users_by_followers (date);
CREATE INDEX IF NOT EXISTS idx_x_top_users_by_followers_platform
    ON x_top_users_by_followers (platform);
CREATE INDEX IF NOT EXISTS idx_x_top_users_by_followers_rank
    ON x_top_users_by_followers (rank);

CREATE INDEX IF NOT EXISTS idx_x_top_posts_by_engagement_date
    ON x_top_posts_by_engagement (date);
CREATE INDEX IF NOT EXISTS idx_x_top_posts_by_engagement_platform
    ON x_top_posts_by_engagement (platform);
CREATE INDEX IF NOT EXISTS idx_x_top_posts_by_engagement_rank
    ON x_top_posts_by_engagement (rank);

CREATE INDEX IF NOT EXISTS idx_x_hashtag_trends_date
    ON x_hashtag_trends (date);
CREATE INDEX IF NOT EXISTS idx_x_hashtag_trends_platform
    ON x_hashtag_trends (platform);
CREATE INDEX IF NOT EXISTS idx_x_hashtag_trends_rank
    ON x_hashtag_trends (rank);
CREATE INDEX IF NOT EXISTS idx_x_hashtag_trends_tag
    ON x_hashtag_trends (tag);

CREATE INDEX IF NOT EXISTS idx_x_data_quality_summary_data_date
    ON x_data_quality_summary (data_date);
CREATE INDEX IF NOT EXISTS idx_x_data_quality_summary_platform
    ON x_data_quality_summary (platform);
CREATE INDEX IF NOT EXISTS idx_x_data_quality_summary_table_name
    ON x_data_quality_summary (table_name);
CREATE INDEX IF NOT EXISTS idx_x_data_quality_summary_score
    ON x_data_quality_summary (data_quality_score);
