"""
config_loader.py — 项目配置加载器
Loads project_config.yaml and provides typed access to all project parameters.
"""
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_project_config(config_path: str) -> Dict[str, Any]:
    """
    Load a project_config.yaml and return as a nested dict.
    Resolves relative paths based on the config file's directory.
    """
    p = Path(config_path)
    with open(p, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    base_dir = p.parent

    # Resolve file paths relative to config location
    if 'paths' in cfg:
        for key in ['model_path', 'comps_data_path', 'source_data_path']:
            val = cfg['paths'].get(key)
            if val and not Path(val).is_absolute():
                cfg['paths'][key] = str(base_dir / val)

    # Derive convenience fields
    periods = cfg.get('periods', {})
    hist = periods.get('hist_years', [])
    fcst = periods.get('fcst_years', [])

    cfg['_derived'] = {
        'all_years': hist + fcst,
        'all_cols': periods.get('hist_cols', []) + periods.get('fcst_cols', []),
        'n_hist': len(hist),
        'n_fcst': len(fcst),
        'n_total': len(hist) + len(fcst),
    }

    return cfg


class ProjectConfig:
    """
    Typed wrapper around the config dict for IDE auto-complete.
    Usage:
        cfg = ProjectConfig.from_yaml('project_config.yaml')
        print(cfg.company_short)
        print(cfg.model_path)
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @classmethod
    def from_yaml(cls, path: str) -> 'ProjectConfig':
        return cls(load_project_config(path))

    # ── Identity ──
    @property
    def company_full(self) -> str:
        return self._data['identity']['company_name_full']

    @property
    def company_short(self) -> str:
        return self._data['identity']['company_name_short']

    @property
    def business_desc(self) -> str:
        return self._data['identity']['business_description']

    @property
    def unit(self) -> str:
        return self._data['identity'].get('unit', '万元')

    @property
    def unit_display(self) -> str:
        return self._data['identity'].get('unit_display', '单位: 万元')

    @property
    def accounting_standard(self) -> str:
        return self._data['identity'].get('accounting_standard', 'CN GAAP')

    # ── Paths ──
    @property
    def model_path(self) -> str:
        return self._data['paths']['model_path']

    @property
    def comps_data_path(self) -> Optional[str]:
        return self._data['paths'].get('comps_data_path')

    @property
    def source_data_path(self) -> Optional[str]:
        return self._data['paths'].get('source_data_path')

    # ── Periods ──
    @property
    def hist_years(self) -> List[str]:
        return self._data['periods']['hist_years']

    @property
    def fcst_years(self) -> List[str]:
        return self._data['periods']['fcst_years']

    @property
    def all_years(self) -> List[str]:
        return self._data['_derived']['all_years']

    @property
    def hist_cols(self) -> List[str]:
        return self._data['periods']['hist_cols']

    @property
    def fcst_cols(self) -> List[str]:
        return self._data['periods']['fcst_cols']

    @property
    def all_cols(self) -> List[str]:
        return self._data['_derived']['all_cols']

    @property
    def data_date(self) -> str:
        return self._data['periods'].get('data_date', '')

    @property
    def fin_period(self) -> str:
        return self._data['periods'].get('fin_period', '')

    # ── Comps ──
    @property
    def comps(self) -> Dict[str, Any]:
        return self._data.get('comps', {})

    @property
    def core_peers(self) -> set:
        return set(self._data.get('comps', {}).get('core_peers', []))

    @property
    def excluded_tickers(self) -> set:
        return set(self._data.get('comps', {}).get('excluded_tickers', []))

    # ── DCF cell map ──
    @property
    def dcf_cells(self) -> Dict[str, str]:
        return self._data.get('dcf_cells', {})

    # ── Anchor refs ──
    @property
    def anchor_refs(self) -> Dict[str, Dict]:
        return self._data.get('anchor_refs', {})

    # ── Source row maps (for source_reader) ──
    @property
    def source_row_maps(self) -> Optional[Dict[str, Any]]:
        return self._data.get('source_row_maps')

    # ── Valuation ──
    @property
    def valuation(self) -> Dict[str, Any]:
        return self._data.get('valuation', {})

    @property
    def current_round_value(self) -> float:
        return self._data.get('valuation', {}).get('current_round_value', 0)

    @property
    def current_round_label(self) -> str:
        return self._data.get('valuation', {}).get('current_round_label', '')

    @property
    def method_weights(self) -> Dict[str, float]:
        return self._data.get('valuation', {}).get('method_weights', {})

    # ── Summary content ──
    @property
    def summary(self) -> Dict[str, Any]:
        return self._data.get('summary', {})

    @property
    def catalysts(self) -> List[str]:
        return self._data.get('summary', {}).get('catalysts', [])

    @property
    def risks(self) -> List[str]:
        return self._data.get('summary', {}).get('risks', [])

    # ── Registry ──
    @property
    def registry_entries(self) -> List[List[str]]:
        return self._data.get('registry_entries', [])

    # ── Analyst notes ──
    @property
    def analyst_conclusion(self) -> str:
        return self._data.get('analyst_notes', {}).get('conclusion', '')

    @property
    def comps_bridge_note(self) -> str:
        return self._data.get('analyst_notes', {}).get('comps_bridge', '')

    # ── Raw access ──
    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]
