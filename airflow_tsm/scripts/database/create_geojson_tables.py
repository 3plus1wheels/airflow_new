import os
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "data_storage",
    "user": "minio_custom",
    "password": "super_secure_database_password123!",
}

SQL = """
CREATE TABLE IF NOT EXISTS flood_road_file (
    id BIGSERIAL PRIMARY KEY,

    timestamp TIMESTAMP NOT NULL,

    source_file TEXT NOT NULL UNIQUE,

    geojson_type TEXT,
    feature_count INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flood_road_values (
    id BIGSERIAL PRIMARY KEY,

    file_id BIGINT NOT NULL
        REFERENCES flood_road_file(id)
        ON DELETE CASCADE,

    timestamp TIMESTAMP NOT NULL,

    road_name TEXT,
    forecast_time TIMESTAMP NOT NULL,
    depth DOUBLE PRECISION,

    geom JSONB,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flood_file_timestamp
ON flood_road_file(timestamp);

CREATE INDEX IF NOT EXISTS idx_flood_values_timestamp
ON flood_road_values(timestamp);

CREATE INDEX IF NOT EXISTS idx_flood_values_forecast_time
ON flood_road_values(forecast_time);

CREATE INDEX IF NOT EXISTS idx_flood_values_depth
ON flood_road_values(depth);
"""


def main():

    conn = psycopg2.connect(**DB_CONFIG)

    cur = conn.cursor()

    cur.execute(SQL)

    conn.commit()

    cur.close()
    conn.close()

    print("Tables created successfully.")


if __name__ == "__main__":
    main()