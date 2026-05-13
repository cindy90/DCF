"""
DCF Agent 共享模块
Shared utilities for all DCF model build scripts.
Eliminates code duplication across build_e_block1/2, build_comps_sheet, build_valuation_summary.
"""
from .style_utils import *
from .excel_helpers import *
from .state_io import read_state, write_state_key, read_key_cells, get_key_row
from .data_utils import nv, stat, exch
from .config_loader import load_project_config, ProjectConfig
from .source_reader import read_source_financials, compute_file_hash
from .validators import (
    CA_KEYS, NCA_KEYS, CL_KEYS, NCL_KEYS, EQ_KEYS,
    assert_bs_balance, check_unit_scale, cross_validate,
    run_all_validations, DataValidationError,
)
