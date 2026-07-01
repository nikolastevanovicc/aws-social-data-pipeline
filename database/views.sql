-- Analytics views for Apache Superset dashboards.
-- Apply after database/schema.sql. These views do not mutate source tables.

CREATE OR REPLACE VIEW vw_hn_daily_activity AS
SELECT
    item_counts.date,
    item_counts.platform,
    item_counts.year,
    item_counts.month,
    item_counts.day,
    item_counts.story_count,
    item_counts.ask_count,
    item_counts.comment_count,
    item_counts.job_count,
    item_counts.poll_count,
    item_counts.total_count,
    users_metric.total_users,
    users_metric.active_users,
    COALESCE(
        GREATEST(
            item_counts.gold_processed_at_utc,
            users_metric.gold_processed_at_utc
        ),
        item_counts.gold_processed_at_utc,
        users_metric.gold_processed_at_utc
    ) AS gold_processed_at_utc
FROM hn_daily_item_counts AS item_counts
LEFT JOIN hn_daily_users_metric AS users_metric
    ON item_counts.date = users_metric.date
    AND item_counts.platform = users_metric.platform
    AND item_counts.year IS NOT DISTINCT FROM users_metric.year
    AND item_counts.month IS NOT DISTINCT FROM users_metric.month
    AND item_counts.day IS NOT DISTINCT FROM users_metric.day;

CREATE OR REPLACE VIEW vw_x_daily_activity AS
SELECT
    date,
    platform,
    year,
    month,
    day,
    total_users,
    active_users,
    gold_processed_at_utc
FROM x_daily_users_metric;

CREATE OR REPLACE VIEW vw_hn_top_posts AS
SELECT
    date,
    platform,
    year,
    month,
    day,
    rank,
    'story' AS post_category,
    post_id,
    source_post_id,
    author_user_id,
    author_username,
    post_type,
    title,
    url,
    score,
    gold_processed_at_utc
FROM hn_top_story_posts
UNION ALL
SELECT
    date,
    platform,
    year,
    month,
    day,
    rank,
    'job' AS post_category,
    post_id,
    source_post_id,
    author_user_id,
    author_username,
    post_type,
    title,
    url,
    score,
    gold_processed_at_utc
FROM hn_top_job_posts;

CREATE OR REPLACE VIEW vw_hn_top_users AS
SELECT
    date,
    platform,
    year,
    month,
    day,
    rank,
    'top_karma' AS user_bucket,
    user_id,
    source_user_id,
    username,
    karma_score,
    gold_processed_at_utc
FROM hn_top_users_by_karma
UNION ALL
SELECT
    date,
    platform,
    year,
    month,
    day,
    rank,
    'bottom_karma' AS user_bucket,
    user_id,
    source_user_id,
    username,
    karma_score,
    gold_processed_at_utc
FROM hn_bottom_users_by_karma;

CREATE OR REPLACE VIEW vw_x_top_posts AS
SELECT
    date,
    platform,
    year,
    month,
    day,
    rank,
    post_id,
    source_post_id,
    author_user_id,
    author_username,
    post_type,
    content_text,
    like_count,
    retweet_count,
    reply_count,
    quote_count,
    engagement_count,
    gold_processed_at_utc
FROM x_top_posts_by_engagement;

CREATE OR REPLACE VIEW vw_x_top_users AS
SELECT
    date,
    platform,
    year,
    month,
    day,
    rank,
    user_id,
    source_user_id,
    username,
    display_name,
    followers_count,
    following_count,
    is_verified,
    gold_processed_at_utc
FROM x_top_users_by_followers;

CREATE OR REPLACE VIEW vw_x_hashtag_trends AS
SELECT
    date,
    platform,
    year,
    month,
    day,
    rank,
    tag,
    tag_type,
    post_count,
    gold_processed_at_utc
FROM x_hashtag_trends;

CREATE OR REPLACE VIEW vw_data_quality_score AS
SELECT
    table_name,
    platform,
    data_date,
    ingest_date,
    row_count,
    column_count,
    non_null_cell_count,
    total_cell_count,
    data_quality_score,
    silver_processed_at_utc,
    gold_processed_at_utc
FROM hn_data_quality_summary
UNION ALL
SELECT
    table_name,
    platform,
    data_date,
    ingest_date,
    row_count,
    column_count,
    non_null_cell_count,
    total_cell_count,
    data_quality_score,
    silver_processed_at_utc,
    gold_processed_at_utc
FROM x_data_quality_summary;
