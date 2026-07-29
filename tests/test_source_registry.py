from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REGISTRY_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "app"
    / "services"
    / "source_registry.py"
)
SPEC = importlib.util.spec_from_file_location("source_registry_under_test", REGISTRY_PATH)
assert SPEC and SPEC.loader
REGISTRY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REGISTRY
SPEC.loader.exec_module(REGISTRY)


def test_banking_plan_prioritizes_financial_regulators_and_market_sources() -> None:
    plugin, sources = REGISTRY.source_plan_for("货币金融服务", "测试银行")
    source_codes = {source.code for source in sources}

    assert plugin.code == "banking"
    assert sources[0].code == "nfra_penalties"
    assert {
        "nfra_penalties",
        "nfra_statistics",
        "nfra_branches",
        "pbc_statistics",
        "pbc_penalties",
        "pbc_branches",
        "interbank_market",
        "china_bond",
        "banking_association",
    }.issubset(source_codes)
    assert {
        "company_official_site",
        "cninfo_announcements",
        "hkex_disclosure",
        "bse_disclosure",
        "enterprise_credit",
        "judicial_disclosure",
    }.issubset(source_codes)


def test_pharma_plan_has_industry_sources_without_banking_only_sources() -> None:
    plugin, sources = REGISTRY.source_plan_for("生物医药制造", "测试制药")
    source_codes = {source.code for source in sources}

    assert plugin.code == "pharma"
    assert {"nmpa", "cde", "nhsa"}.issubset(source_codes)
    assert "nfra_penalties" not in source_codes
    assert "company_official_site" in source_codes


def test_restricted_official_sources_are_routed_to_manual_authorized_mode() -> None:
    _, sources = REGISTRY.source_plan_for("银行业", "测试银行")
    restricted = {
        source.code: source
        for source in sources
        if source.code
        in {
            "enterprise_credit",
            "credit_china",
            "judicial_disclosure",
            "execution_disclosure",
        }
    }

    assert restricted
    assert all(
        source.access_mode == "manual_authorized"
        for source in restricted.values()
    )
    assert all(
        source.requires_original_verification
        for source in restricted.values()
    )
