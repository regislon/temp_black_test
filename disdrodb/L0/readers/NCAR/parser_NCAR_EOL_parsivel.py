#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  8 11:10:46 2022

@author: kimbo
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------.
# Copyright (c) 2021-2022 DISDRODB developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -----------------------------------------------------------------------------.
import click
from disdrodb.L0 import run_L0

# -------------------------------------------------------------------------.
# CLIck Command Line Interface decorator
@click.command()  # options_metavar='<options>'
@click.argument("raw_dir", type=click.Path(exists=True), metavar="<raw_dir>")
@click.argument("processed_dir", metavar="<processed_dir>")
@click.option(
    "-l0a",
    "--l0a_processing",
    type=bool,
    show_default=True,
    default=True,
    help="Perform L0A processing",
)
@click.option(
    "-l0b",
    "--l0b_processing",
    type=bool,
    show_default=True,
    default=True,
    help="Perform L0B processing",
)
@click.option(
    "-k",
    "--keep_l0a",
    type=bool,
    show_default=True,
    default=True,
    help="Whether to keep the l0a Parquet file",
)
@click.option(
    "-f",
    "--force",
    type=bool,
    show_default=True,
    default=False,
    help="Force overwriting",
)
@click.option(
    "-v", "--verbose", type=bool, show_default=True, default=False, help="Verbose"
)
@click.option(
    "-d",
    "--debugging_mode",
    type=bool,
    show_default=True,
    default=False,
    help="Switch to debugging mode",
)
@click.option(
    "-l",
    "--lazy",
    type=bool,
    show_default=True,
    default=True,
    help="Use dask if lazy=True",
)
@click.option(
    "-s",
    "--single_netcdf",
    type=bool,
    show_default=True,
    default=True,
    help="Produce single netCDF",
)
def main(
    raw_dir,
    processed_dir,
    l0a_processing=True,
    l0b_processing=True,
    keep_l0a=False,
    force=False,
    verbose=False,
    debugging_mode=False,
    lazy=True,
    single_netcdf=True,
):
    """Script to process raw data to L0 and L1. \f

    Parameters
    ----------
    raw_dir : str
        Directory path of raw file for a specific campaign.
        The path should end with <campaign_name>.
        Example raw_dir: '<...>/disdrodb/data/raw/<campaign_name>'.
        The directory must have the following structure:
        - /data/<station_id>/<raw_files>
        - /metadata/<station_id>.json
        For each <station_id> there must be a corresponding JSON file
        in the metadata subfolder.
    processed_dir : str
        Desired directory path for the processed L0 and L1 products.
        The path should end with <campaign_name> and match the end of raw_dir.
        Example: '<...>/disdrodb/data/processed/<campaign_name>'.
    l0_processing : bool
        Whether to launch processing to generate L0 Apache Parquet file(s) from raw data.
        The default is True.
    l1_processing : bool
        Whether to launch processing to generate L1 netCDF4 file(s) from source netCDF or L0 data.
        The default is True.
    write_netcdf: bool
        Whether to save L1 as netCDF4 archive
        Write_netcdf must be True.
    force : bool
        If True, overwrite existing data into destination directories.
        If False, raise an error if there are already data into destination directories.
        The default is False
    verbose : bool
        Whether to print detailed processing information into terminal.
        The default is False.
    debugging_mode : bool
        If True, it reduces the amount of data to process.
        - For L0 processing, it processes just 3 raw data files.
        - For L1 processing, it takes a small subset of the Apache Parquet dataframe.
        The default is False.
    lazy : bool
        Whether to perform processing lazily with dask.
        If lazy=True, it employed dask.array and dask.dataframe.
        If lazy=False, it employed pandas.DataFrame and numpy.array.
        The default is True.

    Additional information:
    - The campaign name must semantically match between:
       - The ends of raw_dir and processed_dir paths
       - The attribute 'campaign' within the metadata JSON file.
    - The campaign name are set to be UPPER CASE.

    """
    ####----------------------------------------------------------------------.
    ###########################
    #### CUSTOMIZABLE CODE ####
    ###########################
    #### - Define raw data headers
    # Notes
    # - In all files, the datalogger voltage hasn't the delimeter,
    #   so need to be split to obtain datalogger_voltage and rainfall_rate_32bit
    column_names = ["TO_SPLIT"]

    ##------------------------------------------------------------------------.
    #### - Define reader options
    reader_kwargs = {}
    # - Define delimiter
    reader_kwargs["delimiter"] = "No_need_it"

    # - Avoid first column to become df index !!!
    reader_kwargs["index_col"] = False

    # - Define behaviour when encountering bad lines
    reader_kwargs["on_bad_lines"] = "skip"

    # - Define parser engine
    #   - C engine is faster
    #   - Python engine is more feature-complete
    reader_kwargs["engine"] = "python"

    # - Strings to recognize as NA/NaN and replace with standard NA flags
    #   - Already included: ‘#N/A’, ‘#N/A N/A’, ‘#NA’, ‘-1.#IND’, ‘-1.#QNAN’,
    #                       ‘-NaN’, ‘-nan’, ‘1.#IND’, ‘1.#QNAN’, ‘<NA>’, ‘N/A’,
    #                       ‘NA’, ‘NULL’, ‘NaN’, ‘n/a’, ‘nan’, ‘null’
    reader_kwargs["na_values"] = [
        "na",
        "",
        "error",
        "NA",
        "-.-",
        " NA",
    ]

    # - Define max size of dask dataframe chunks (if lazy=True)
    #   - If None: use a single block for each file
    #   - Otherwise: "<max_file_size>MB" by which to cut up larger files
    reader_kwargs["blocksize"] = None  # "50MB"

    # Cast all to string
    reader_kwargs["dtype"] = str

    ##------------------------------------------------------------------------.
    #### - Define facultative dataframe sanitizer function for L0 processing
    # - Enable to deal with bad raw data files
    # - Enable to standardize raw data files to L0 standards  (i.e. time to datetime)
    df_sanitizer_fun = None

    def df_sanitizer_fun(df, lazy=False):
        # Import dask or pandas
        if lazy:
            import dask.dataframe as dd
        else:
            import pandas as dd

        # Read date from header and then remove it
        date = df.head().loc[0][0]
        date = date[:10]
        df = df.loc[1:]

        # Temporary column name
        df.columns = ["TO_SPLIT"]

        # Parse time
        # Suppress SettingWithCopyWarning with pandas
        if not lazy:
            dd.options.mode.chained_assignment = None
        df[["time", "TO_SPLIT"]] = df["TO_SPLIT"].str.split(" ", n=1, expand=True)
        df["time"] = df["time"].str[:-3]
        df["time"] = df["time"] + "-" + date
        df["time"] = dd.to_datetime(df["time"], format="%M%S-%m/%d/%Y")

        # Split columns
        columns = [
            "rainfall_rate_32bit",
            "rainfall_accumulated_32bit",
            "reflectivity_32bit",
            "number_particles",
            "sensor_status",
            "error_code",
            "raw_drop_concentration",
            "raw_drop_average_velocity",
            # 'raw_drop_number'
        ]

        for c in columns:
            df["TO_SPLIT"] = df["TO_SPLIT"].str.strip()
            df[[c, "TO_SPLIT"]] = df["TO_SPLIT"].str.split(" ", n=1, expand=True)

        # Add 0 digits to raw_drop_number
        for i, r in df.iterrows():
            temp_raw = r["TO_SPLIT"].split(",")
            raw = ""
            for n in temp_raw:
                raw += "%03d" % int(n) + ","
            df["raw_drop_number"] = raw

        # Drop TO_SPLIT column
        df = df.drop(columns=["TO_SPLIT"])

        # Reset index
        df = df.reset_index(drop=True)

        return df

    ##------------------------------------------------------------------------.
    #### - Define glob pattern to search data files in raw_dir/data/<station_id>
    files_glob_pattern = "*.txt*"

    ####----------------------------------------------------------------------.
    #### - Create L0 products
    run_L0(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        l0a_processing=l0a_processing,
        l0b_processing=l0b_processing,
        keep_l0a=keep_l0a,
        force=force,
        verbose=verbose,
        debugging_mode=debugging_mode,
        lazy=lazy,
        single_netcdf=single_netcdf,
        # Custom arguments of the parser
        files_glob_pattern=files_glob_pattern,
        column_names=column_names,
        reader_kwargs=reader_kwargs,
        df_sanitizer_fun=df_sanitizer_fun,
    )


if __name__ == "__main__":
    main()
