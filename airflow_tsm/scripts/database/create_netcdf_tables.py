import psycopg2


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "data_storage",
    "user": "minio_custom",
    "password": "super_secure_database_password123!",
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def create_tables():
    sql = """
    CREATE TABLE IF NOT EXISTS netcdf_files (
        id SERIAL PRIMARY KEY,

        simulation_id BIGINT NOT NULL,
        model_id BIGINT,
        schematisation_id BIGINT,
        revision_id BIGINT,

        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,

        date DATE,
        timestamp TIMESTAMP,
        time_steps INT,

        epsg TEXT,
        result_type TEXT,
        source TEXT,

        dimensions JSONB,
        coordinates JSONB,
        global_attributes JSONB,

        uploaded_at TIMESTAMP DEFAULT NOW(),

        UNIQUE(simulation_id, filename)
    );

    CREATE TABLE IF NOT EXISTS netcdf_variables (
        id SERIAL PRIMARY KEY,

        file_id INT NOT NULL REFERENCES netcdf_files(id) ON DELETE CASCADE,

        simulation_id BIGINT NOT NULL,
        model_id BIGINT,

        variable_name TEXT NOT NULL,
        long_name TEXT,
        standard_name TEXT,
        units TEXT,

        dims JSONB,
        shape JSONB,
        dtype TEXT,

        entity_type TEXT,
        entity_id_name TEXT,
        attrs JSONB,

        UNIQUE(file_id, variable_name)
    );

    CREATE TABLE IF NOT EXISTS netcdf_values (
        id BIGSERIAL PRIMARY KEY,

        file_id INT NOT NULL REFERENCES netcdf_files(id) ON DELETE CASCADE,

        simulation_id BIGINT NOT NULL,
        model_id BIGINT,

        date DATE NOT NULL,
        timestamp TIMESTAMP NOT NULL,

        variable_name TEXT NOT NULL,

        mesh_type TEXT,
        element_type TEXT,

        element_id BIGINT,
        x DOUBLE PRECISION,
        y DOUBLE PRECISION,
        value DOUBLE PRECISION
    );

    CREATE INDEX IF NOT EXISTS idx_netcdf_files_simulation
    ON netcdf_files(simulation_id);

    CREATE INDEX IF NOT EXISTS idx_netcdf_files_model
    ON netcdf_files(model_id);

    CREATE INDEX IF NOT EXISTS idx_netcdf_variables_file
    ON netcdf_variables(file_id);

    CREATE INDEX IF NOT EXISTS idx_netcdf_values_file
    ON netcdf_values(file_id);

    CREATE INDEX IF NOT EXISTS idx_netcdf_values_sim_time
    ON netcdf_values(simulation_id, timestamp);

    CREATE INDEX IF NOT EXISTS idx_netcdf_values_model_time
    ON netcdf_values(model_id, timestamp);

    CREATE INDEX IF NOT EXISTS idx_netcdf_values_var
    ON netcdf_values(variable_name);

    CREATE INDEX IF NOT EXISTS idx_netcdf_values_element
    ON netcdf_values(element_id);
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(sql)

    conn.commit()
    cur.close()
    conn.close()

    print("Created NetCDF tables successfully.")


if __name__ == "__main__":
    create_tables()