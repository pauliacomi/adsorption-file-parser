# -*- coding: utf-8 -*-
"""Parse 3P xlsx output files."""

import openpyxl

from adsorption_file_parser import logger
from adsorption_file_parser.utils import common_utils as util
from adsorption_file_parser.utils import unit_parsing

_META_DICT = {
    'material': {
        'text': ['charge name'],
        'type': 'string'
    },
    'adsorbate': {
        'text': ['adsorbate'],
        'type': 'string'
    },
    'date': {
        'text': ['started time'],
        'type': 'date'
    },
    'material_mass': {
        'text': ['sample weight'],
        'type': 'numeric'
    },
}

_DATA_DICT = {
    'measurement': {
        'text': ('id', ),
    },
    'pressure': {
        'text': ('p (', ),
    },
    'pressure_saturation': {
        'text': ('p0 (', ),
    },
    'pressure_relative': {
        'text': ('p/p0', ),
    },
    'time_point': {
        'text': ('time', ),
    },
    'loading': {
        'text': ('v (', ),
    },
}


def parse(path):
    """
    Parse an xls file generated by 3P software.

    Parameters
    ----------
    path: str
        The location of an xls file generated by a 3P instrument.

    Returns
    -------
    dict
        A dictionary containing report information.
    """
    meta = {}
    data = {}

    # open the workbook
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)

    # local for efficiency
    meta_dict = _META_DICT.copy()

    # Metadata
    info_sheet = workbook['Info']
    # we know data is left-aligned
    # so we only iterate rows
    for row in info_sheet.rows:

        # if first cell is not filled -> blank row
        first_cell = row[0]
        if not first_cell.value:
            continue

        cell_value = first_cell.value.lower()
        val = row[1].value
        try:
            key = util.search_key_in_def_dict(cell_value, meta_dict)
        except StopIteration:
            if val:
                key = cell_value.replace(' ', '_')
                meta[key] = val
            continue

        tp = meta_dict[key]['type']
        del meta_dict[key]  # delete for efficiency

        if val is None:
            meta[key] = None
        elif tp == 'numeric':
            meta[key] = val
        elif tp == 'date':
            meta[key] = util.handle_string_date(val)
        elif tp == 'string':
            meta[key] = util.handle_excel_string(val)

    # Data
    data_sheet = workbook['Isotherm']
    # Data headers
    data_val = data_sheet.values
    head, units = _parse_header(list(next(data_val)))
    meta.update(units)
    # Parse and pack data
    data = _parse_data(data_val)
    data = dict(zip(head, map(lambda *x: list(x), *data)))

    _check(meta, data, path)

    # Set extra metadata
    meta['apparatus'] = '3P'
    meta['temperature'] = 77.3  # TODO where is this stored?
    meta['temperature_unit'] = 'K'  # TODO where is this stored?

    return meta, data


def _parse_header(header_list):
    """Parse an adsorption/desorption header to get columns and units."""
    headers = ['branch']
    units = {}

    for h in header_list:
        try:
            text = h.lower()
            header = util.search_key_starts_def_dict(text, _DATA_DICT)
        except StopIteration:
            header = h

        headers.append(header)

        if header == 'loading':
            unit_string = util.RE_BETWEEN_BRACKETS.search(h).group().strip()
            unit_dict = unit_parsing.parse_loading_string(unit_string)
            units.update(unit_dict)

        if header == 'pressure':
            unit_string = util.RE_BETWEEN_BRACKETS.search(h).group().strip()
            unit_dict = unit_parsing.parse_pressure_string(unit_string)
            units.update(unit_dict)

    return headers, units


def _parse_data(data_rows):
    data = []
    branch = 0
    for row in list(data_rows):
        # If we reached the desorption branch we change
        if row[0] == '---':
            branch = 1
            continue
        data.append([branch] + list(row))
    return data


def _check(meta, data, path):
    """
    Check keys in data and logs a warning if a key is empty.

    Also logs a warning for errors found in file.
    """
    if 'loading' in data:
        empties = (k for k, v in data.items() if not v)
        for empty in empties:
            logger.info(f'No data collected for {empty} in file {path}.')
    if 'errors' in meta:
        logger.warning('\n'.join(meta['errors']))
