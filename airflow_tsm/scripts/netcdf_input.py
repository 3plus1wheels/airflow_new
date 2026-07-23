import os


def calculate_depth_from_download(
    *,
    ti,
    calculate_depth_fn,
    grid_path,
    dem_path,
    output_dir,
    model_id,
):
    """Validate and process the NetCDF produced by the current simulation run."""
    sim_id = ti.xcom_pull(task_ids="1_trigger_simulation", key="sim_id")
    nc_path = ti.xcom_pull(task_ids="2_download_results", key="nc_path")

    if not nc_path:
        raise ValueError("Downloaded NetCDF path is missing from task 2_download_results XCom")

    nc_path = os.fspath(nc_path)
    if not nc_path.lower().endswith(".nc"):
        raise ValueError(f"Downloaded result is not a NetCDF file: {nc_path}")
    if not os.path.isfile(nc_path):
        raise FileNotFoundError(f"Downloaded NetCDF does not exist: {nc_path}")

    print(
        "Depth input provenance: "
        f"model_id={model_id or 'unknown'}, "
        f"simulation_id={sim_id or 'unknown'}, "
        f"netcdf={nc_path}"
    )

    return calculate_depth_fn(
        grid_path=grid_path,
        nc_path=nc_path,
        dem_path=dem_path,
        output_dir=output_dir,
    )
