"""
Utilities to format measurement data from the consolidated physical table
`delta_lake.default.all_gigameter_measurement_data` (Trino prd).

This table is pre-joined with school metadata (admin1/admin2, school_area_type,
connectivity, lat/lon), unit-converted (Mbps), and ISP-cleaned (isp_name,
isp_asn). Both DailyCheckApp and Chrome-extension/MLab measurements live in
the same table, distinguished by `rt_source`.

This replaces the prior cross-catalog join machinery against
gigameter_production_db.public.measurements + gigamaps_production_db.

Notes on data quality:
- `pass_fail_overall` is a measurement-validity threshold (imperfect). Don't
  use it as a use-case verdict; possibly use it as a noise filter later.
- `detected_server` is unreliable (sourced from a stale mlab-ns ndt5 endpoint).
  Identify the EITC on-net mesh server via the UUID prefix (`ubuntu`) once the
  uuid column is populated in the physical table.
"""

import pandas as pd


_MEASUREMENT_TABLE = "default.all_gigameter_measurement_data"


def _quote_list(values):
    """Quote a single value or list of values for an IN (...) / = '...' clause."""
    if isinstance(values, (list, tuple, set)):
        joined = "', '".join(str(v) for v in values)
        return f"('{joined}')"
    return f"'{values}'"


def get_gigameter_measurements_query(
    country=None,
    iso3=None,
    source=None,
    limit=None,
    since=None,
    get_uuid=True,  # kept for backward compatibility; uuid is just a column now
):
    """
    Generate a SQL query against the consolidated physical measurements table.

    Args:
        country: Country name(s) to filter on (`country` column).
                 String or list. None for no country filter.
        iso3:    ISO3 code(s) to filter on (`iso3_code` column).
                 String or list. Preferred over `country` for efficiency.
        source:  `rt_source` value(s), e.g. 'GigaMeter'. None for no filter.
        limit:   Optional row limit.
        since:   Only return rows after this date (exclusive). Accepts date,
                 datetime, or 'YYYY-MM-DD' string. Used for incremental refresh.
        get_uuid: Ignored (kept for backward-compat). uuid is included in
                  SELECT * once the column is populated upstream.

    Returns:
        SQL query string.
    """
    where_clauses = ["1=1"]

    if iso3 is not None:
        if isinstance(iso3, (list, tuple, set)):
            where_clauses.append(f"iso3_code IN {_quote_list([s.upper() for s in iso3])}")
        else:
            where_clauses.append(f"iso3_code = '{iso3.upper()}'")

    if country is not None:
        if isinstance(country, (list, tuple, set)):
            where_clauses.append(f"country IN {_quote_list(country)}")
        else:
            where_clauses.append(f"country = '{country}'")

    if source is not None:
        if isinstance(source, (list, tuple, set)):
            where_clauses.append(f"rt_source IN {_quote_list(source)}")
        else:
            where_clauses.append(f"rt_source = '{source}'")

    if since is not None:
        where_clauses.append(f"date > DATE '{since}'")

    query = f"SELECT *\nFROM {_MEASUREMENT_TABLE}\nWHERE " + "\n  AND ".join(where_clauses)

    if limit:
        query += f"\nLIMIT {limit}"

    return query


def format_measurements_dataframe(df):
    """
    Light post-processing for measurements pulled from the physical table.

    The physical table already does unit conversion, ISP cleaning, country join,
    and JSON extraction. This shim only normalises types so downstream code
    doesn't need to care whether data came from cache or a fresh Trino pull.

    Args:
        df: DataFrame from all_gigameter_measurement_data.

    Returns:
        DataFrame with date/timestamp columns parsed.
    """
    df_formatted = df.copy()

    if "date" in df_formatted.columns:
        df_formatted["date"] = pd.to_datetime(df_formatted["date"]).dt.date

    for ts_col in ("created_timestamp", "local_created_timestamp"):
        if ts_col in df_formatted.columns:
            df_formatted[ts_col] = pd.to_datetime(df_formatted[ts_col], errors="coerce")

    return df_formatted


def get_measurements_core_columns():
    """
    Core column list for measurement analysis (IQB-aligned).

    Returns:
        List of essential measurement columns, in display order.
    """
    return [
        "measurement_id",
        "measurement_uuid",
        "date",
        "created_timestamp",
        "local_hour_of_measurement",
        "is_weekday",
        "measurement_time_window",
        "iso3_code",
        "country",
        "school_id_giga",
        "school_id_govt",
        "school_name",
        "admin1",
        "admin2",
        "school_area_type",
        "connectivity",
        "connectivity_type_govt",
        "education_level",
        "rt_source",
        "app_version",
        "isp_name",
        "isp_asn",
        "ip_address",
        "detected_server",
        "device_id",
        "browser_id",
        "download_speed",
        "upload_speed",
        "latency",
        "packet_loss_rate",
        "data_usage_gb",
        "pass_fail_overall",
        "reasons_failed_overall",
        "latitude",
        "longitude",
    ]


def get_measurements_core_dataframe(df):
    """
    Return measurements DataFrame with only core columns (in order),
    excluding any not present.
    """
    core_cols = get_measurements_core_columns()
    available_cols = [col for col in core_cols if col in df.columns]
    return df[available_cols]


# Example usage
if __name__ == "__main__":
    print("Single ISO3, single source:")
    print(get_gigameter_measurements_query(iso3="MNG", source="GigaMeter", limit=10))
    print("\n" + "=" * 80 + "\n")

    print("Multiple countries, all sources, since cutoff:")
    print(get_gigameter_measurements_query(
        country=["Mongolia", "Moldova"],
        since="2025-10-15",
    ))
    print("\n" + "=" * 80 + "\n")

    print("All countries, no filters:")
    print(get_gigameter_measurements_query())
