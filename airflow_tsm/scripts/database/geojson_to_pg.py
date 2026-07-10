import os
import json
from datetime import datetime
import boto3
import psycopg2
from botocore.config import Config
from psycopg2.extras import execute_values


# =========================
# CONFIG
# =========================
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "https://storage.9web.vn")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "airflow")
MINIO_SECRET_KEY = os.getenv(
    "MINIO_SECRET_KEY", "KQfCfEwmO7irPY4RITfszEu9f15wWoCnvwtbSRXO"
)
BUCKET_NAME = os.getenv("FLOOD_MINIO_BUCKET", "flood-results-full")
GEOJSON_PREFIX_NAME = "flood_road_"


# =========================
# DATABASE
# =========================

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "data_storage",
    "user": "minio_custom",
    "password": "super_secure_database_password123!",
}


def get_minio_client():

    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def get_latest_folder():

    s3 = get_minio_client()

    paginator = s3.get_paginator("list_objects_v2")

    folders = {}

    for page in paginator.paginate(Bucket=BUCKET_NAME):

        for obj in page.get("Contents", []):

            key = obj["Key"]

            if "/" not in key:
                continue

            folder = key.split("/")[0] + "/"

            folders[folder] = max(
                folders.get(folder, obj["LastModified"]),
                obj["LastModified"],
            )

    if not folders:
        raise Exception("No folders found")

    return max(
        folders.items(),
        key=lambda x: x[1]
    )[0]


def get_flood_road_geojson(folder):

    s3 = get_minio_client()

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(
        Bucket=BUCKET_NAME,
        Prefix=folder,
    ):

        for obj in page.get("Contents", []):

            filename = obj["Key"].split("/")[-1]

            if (
                filename.startswith("flood_road_")
                and filename.endswith(".geojson")
            ):
                return obj["Key"]

    raise Exception("Flood road geojson not found")


def load_geojson(key):

    s3 = get_minio_client()

    response = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=key,
    )

    return json.loads(
        response["Body"].read().decode("utf-8")
    )


def parse_timestamp(folder):

    return datetime.strptime(
        folder.rstrip("/"),
        "%Y%m%dT%H%M%S"
    )


def save_file_metadata(
    cur,
    timestamp,
    source_file,
    geojson,
):

    cur.execute(
        """
        INSERT INTO flood_road_file (
            timestamp,
            source_file,
            geojson_type,
            feature_count
        )
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (source_file)
        DO UPDATE SET
            timestamp = EXCLUDED.timestamp,
            geojson_type = EXCLUDED.geojson_type,
            feature_count = EXCLUDED.feature_count
        RETURNING id
        """,
        (
            timestamp,
            source_file,
            geojson.get("type"),
            len(geojson.get("features", [])),
        ),
    )

    return cur.fetchone()[0]


def delete_old_values(
    cur,
    file_id,
):

    cur.execute(
        """
        DELETE FROM flood_road_values
        WHERE file_id = %s
        """,
        (file_id,),
    )


def build_rows(
    file_id,
    timestamp,
    geojson,
):

    rows = []

    for feature in geojson.get("features", []):

        road_name = feature["properties"].get(
            "road_name"
        )

        geometry_json = json.dumps(
            feature["geometry"]
        )

        for item in feature["properties"].get(
            "timeseries",
            []
        ):

            rows.append(
                (
                    file_id,
                    timestamp,
                    road_name,
                    item["time"],
                    item["depth"],
                    geometry_json,
                )
            )

    return rows


def insert_values(cur, rows):
    if not rows:
        return

    execute_values(
        cur,
        """
        INSERT INTO flood_road_values (
            file_id,
            timestamp,
            road_name,
            forecast_time,
            depth,
            geom
        )
        VALUES %s
        """,
        rows,
        template="""
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s::jsonb
        )
        """,
        page_size=1000,
    )


def main():

    latest_folder = get_latest_folder()

    geojson_key = get_flood_road_geojson(
        latest_folder
    )

    geojson = load_geojson(
        geojson_key
    )

    timestamp = parse_timestamp(
        latest_folder
    )

    source_file = os.path.basename(
        geojson_key
    )

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    file_id = save_file_metadata(
        cur,
        timestamp,
        source_file,
        geojson,
    )

    delete_old_values(
        cur,
        file_id,
    )

    rows = build_rows(
        file_id,
        timestamp,
        geojson,
    )

    insert_values(
        cur,
        rows,
    )

    conn.commit()

    cur.close()
    conn.close()

    print(
        f"Inserted {len(rows)} rows"
    )


if __name__ == "__main__":
    main()
