import os
import json
import numpy as np
import pandas as pd
import xarray as xr
import psycopg2
from psycopg2.extras import execute_values


# =========================
# CONFIG
# =========================

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "data_storage",
    "user": "minio_custom",
    "password": "super_secure_database_password123!",
}

FILE_PATH = "data/results/results_3di.nc"


# =========================
# VARIABLE MAPPING
# =========================

VARIABLE_MAPPING = {
    "Mesh2D_s1": {
        "mesh_type": "2D",
        "element_type": "node",
        "id_var": "Mesh2DNode_id",
        "x_var": "Mesh2DFace_xcc",
        "y_var": "Mesh2DFace_ycc",
    },
    "Mesh2D_vol": {
        "mesh_type": "2D",
        "element_type": "node",
        "id_var": "Mesh2DNode_id",
        "x_var": "Mesh2DFace_xcc",
        "y_var": "Mesh2DFace_ycc",
    },
    "Mesh2D_rain": {
        "mesh_type": "2D",
        "element_type": "node",
        "id_var": "Mesh2DNode_id",
        "x_var": "Mesh2DFace_xcc",
        "y_var": "Mesh2DFace_ycc",
    },
    "Mesh2D_ucx": {
        "mesh_type": "2D",
        "element_type": "node",
        "id_var": "Mesh2DNode_id",
        "x_var": "Mesh2DFace_xcc",
        "y_var": "Mesh2DFace_ycc",
    },
    "Mesh2D_ucy": {
        "mesh_type": "2D",
        "element_type": "node",
        "id_var": "Mesh2DNode_id",
        "x_var": "Mesh2DFace_xcc",
        "y_var": "Mesh2DFace_ycc",
    },
    "Mesh2D_q": {
        "mesh_type": "2D",
        "element_type": "line",
        "id_var": "Mesh2DLine_id",
        "x_var": "Mesh2DLine_xcc",
        "y_var": "Mesh2DLine_ycc",
    },
    "Mesh1D_s1": {
        "mesh_type": "1D",
        "element_type": "node",
        "id_var": "Mesh1DNode_id",
        "x_var": "Mesh1DNode_xcc",
        "y_var": "Mesh1DNode_ycc",
    },
    "Mesh1D_q": {
        "mesh_type": "1D",
        "element_type": "line",
        "id_var": "Mesh1DLine_id",
        "x_var": "Mesh1DLine_xcc",
        "y_var": "Mesh1DLine_ycc",
    },
}


# =========================
# DATABASE
# =========================

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# =========================
# HELPERS
# =========================

def json_safe(obj):
    def convert(o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, pd.Timestamp):
            return str(o)
        return str(o)

    return json.dumps(obj, default=convert)


# =========================
# EXTRACT FILE METADATA
# =========================

def extract_file_metadata(ds, file_path):
    filename = os.path.basename(file_path)

    attrs = dict(ds.attrs)

    simulation_id = int(attrs.get("simulation_id"))
    model_id = int(attrs.get("model_id")) if attrs.get("model_id") is not None else None
    schematisation_id = int(attrs.get("schematisation_id")) if attrs.get("schematisation_id") is not None else None
    revision_id = int(attrs.get("revision_id")) if attrs.get("revision_id") is not None else None

    times = pd.to_datetime(ds["time"].values)

    timestamp = times[0].to_pydatetime()
    date = timestamp.date()

    dimensions = {
        dim: int(size)
        for dim, size in ds.sizes.items()
    }

    coordinates = {
        coord: {
            "dims": list(ds[coord].dims),
            "shape": list(ds[coord].shape),
            "dtype": str(ds[coord].dtype),
        }
        for coord in ds.coords
    }

    epsg = None
    if "projected_coordinate_system" in ds:
        epsg = ds["projected_coordinate_system"].attrs.get("epsg")

    return {
        "simulation_id": simulation_id,
        "model_id": model_id,
        "schematisation_id": schematisation_id,
        "revision_id": revision_id,
        "filename": filename,
        "file_path": file_path,
        "date": date,
        "timestamp": timestamp,
        "time_steps": len(times),
        "epsg": epsg,
        "result_type": attrs.get("result_type"),
        "source": attrs.get("source"),
        "dimensions": dimensions,
        "coordinates": coordinates,
        "global_attributes": attrs,
    }


# =========================
# INSERT NETCDF FILE
# =========================

def insert_netcdf_file(file_meta):
    sql = """
    INSERT INTO netcdf_files (
        simulation_id,
        model_id,
        schematisation_id,
        revision_id,
        filename,
        file_path,
        date,
        timestamp,
        time_steps,
        epsg,
        result_type,
        source,
        dimensions,
        coordinates,
        global_attributes
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
    ON CONFLICT (simulation_id, filename)
    DO UPDATE SET
        model_id = EXCLUDED.model_id,
        schematisation_id = EXCLUDED.schematisation_id,
        revision_id = EXCLUDED.revision_id,
        file_path = EXCLUDED.file_path,
        date = EXCLUDED.date,
        timestamp = EXCLUDED.timestamp,
        time_steps = EXCLUDED.time_steps,
        epsg = EXCLUDED.epsg,
        result_type = EXCLUDED.result_type,
        source = EXCLUDED.source,
        dimensions = EXCLUDED.dimensions,
        coordinates = EXCLUDED.coordinates,
        global_attributes = EXCLUDED.global_attributes,
        uploaded_at = NOW()
    RETURNING id;
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        sql,
        (
            file_meta["simulation_id"],
            file_meta["model_id"],
            file_meta["schematisation_id"],
            file_meta["revision_id"],
            file_meta["filename"],
            file_meta["file_path"],
            file_meta["date"],
            file_meta["timestamp"],
            file_meta["time_steps"],
            file_meta["epsg"],
            file_meta["result_type"],
            file_meta["source"],
            json_safe(file_meta["dimensions"]),
            json_safe(file_meta["coordinates"]),
            json_safe(file_meta["global_attributes"]),
        ),
    )

    file_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return file_id


# =========================
# INSERT VARIABLES
# =========================

def insert_variables(ds, file_id, simulation_id, model_id):
    rows = []

    for var_name in ds.data_vars:
        var = ds[var_name]
        attrs = dict(var.attrs)

        entity_id_name = attrs.get("id")

        entity_type = None
        if entity_id_name:
            if "Node" in entity_id_name:
                entity_type = "node"
            elif "Line" in entity_id_name:
                entity_type = "line"

        rows.append(
            (
                file_id,
                simulation_id,
                model_id,
                var_name,
                attrs.get("long_name"),
                attrs.get("standard_name"),
                attrs.get("units"),
                json_safe(list(var.dims)),
                json_safe(list(var.shape)),
                str(var.dtype),
                entity_type,
                entity_id_name,
                json_safe(attrs),
            )
        )

    sql = """
    INSERT INTO netcdf_variables (
        file_id,
        simulation_id,
        model_id,
        variable_name,
        long_name,
        standard_name,
        units,
        dims,
        shape,
        dtype,
        entity_type,
        entity_id_name,
        attrs
    )
    VALUES %s
    ON CONFLICT (file_id, variable_name)
    DO UPDATE SET
        long_name = EXCLUDED.long_name,
        standard_name = EXCLUDED.standard_name,
        units = EXCLUDED.units,
        dims = EXCLUDED.dims,
        shape = EXCLUDED.shape,
        dtype = EXCLUDED.dtype,
        entity_type = EXCLUDED.entity_type,
        entity_id_name = EXCLUDED.entity_id_name,
        attrs = EXCLUDED.attrs;
    """

    conn = get_connection()
    cur = conn.cursor()

    execute_values(cur, sql, rows)

    conn.commit()
    cur.close()
    conn.close()


# =========================
# DELETE OLD VALUES
# =========================

def delete_old_values(file_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM netcdf_values WHERE file_id = %s;",
        (file_id,)
    )

    conn.commit()
    cur.close()
    conn.close()


# =========================
# INSERT VALUES
# =========================

def insert_values(ds, file_id, simulation_id, model_id, batch_size=50000):
    conn = get_connection()
    cur = conn.cursor()

    sql = """
    INSERT INTO netcdf_values (
        file_id,
        simulation_id,
        model_id,
        date,
        timestamp,
        variable_name,
        mesh_type,
        element_type,
        element_id,
        x,
        y,
        value
    )
    VALUES %s;
    """

    times = pd.to_datetime(ds["time"].values)

    for variable_name, mapping in VARIABLE_MAPPING.items():
        if variable_name not in ds:
            print(f"Skip missing variable: {variable_name}")
            continue

        print(f"Processing variable: {variable_name}")

        id_values = ds[mapping["id_var"]].values.astype(np.int64)
        x_values = ds[mapping["x_var"]].values.astype(float)
        y_values = ds[mapping["y_var"]].values.astype(float)

        data_array = ds[variable_name].values

        rows = []

        for time_idx, ts in enumerate(times):
            timestamp = ts.to_pydatetime()
            date = timestamp.date()

            values = data_array[time_idx]

            for i in range(len(values)):
                value = values[i]

                if np.isnan(value):
                    continue

                rows.append(
                    (
                        file_id,
                        simulation_id,
                        model_id,
                        date,
                        timestamp,
                        variable_name,
                        mapping["mesh_type"],
                        mapping["element_type"],
                        int(id_values[i]),
                        float(x_values[i]),
                        float(y_values[i]),
                        float(value),
                    )
                )

                if len(rows) >= batch_size:
                    execute_values(cur, sql, rows)
                    conn.commit()
                    rows = []

        if rows:
            execute_values(cur, sql, rows)
            conn.commit()

        print(f"Done variable: {variable_name}")

    cur.close()
    conn.close()


# =========================
# MAIN
# =========================

def upload_netcdf_to_database(file_path):
    ds = xr.open_dataset(file_path)

    try:
        file_meta = extract_file_metadata(ds, file_path)

        simulation_id = file_meta["simulation_id"]
        model_id = file_meta["model_id"]

        print(f"simulation_id = {simulation_id}")
        print(f"model_id      = {model_id}")

        file_id = insert_netcdf_file(file_meta)

        print(f"file_id       = {file_id}")

        insert_variables(
            ds=ds,
            file_id=file_id,
            simulation_id=simulation_id,
            model_id=model_id,
        )

        delete_old_values(file_id)

        insert_values(
            ds=ds,
            file_id=file_id,
            simulation_id=simulation_id,
            model_id=model_id,
        )

        print("Upload NetCDF thành công.")

    finally:
        ds.close()


if __name__ == "__main__":
    upload_netcdf_to_database(FILE_PATH)