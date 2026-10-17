from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Barrier

from airport_analytics.analytics.budget import BudgetLedger
from airport_analytics.errors import BudgetExceededError
from airport_analytics.storage import Storage


def test_separate_ledgers_cannot_overreserve_shared_persistent_budget(
    tmp_path: Path,
) -> None:
    database = tmp_path / "concurrent-ledgers.sqlite3"
    ledgers = [BudgetLedger(Storage(database), monthly_cap_usd=Decimal("0.02")) for _ in range(5)]
    barrier = Barrier(len(ledgers))

    def reserve_one(ledger: BudgetLedger) -> bool:
        barrier.wait()
        try:
            ledger.reserve(
                provider_id="hosted-test",
                model_id="test-model",
                max_input_tokens=1,
                max_output_tokens=1,
                input_usd_per_million=Decimal("1000"),
                output_usd_per_million=Decimal("1000"),
                fee_fx_multiplier=Decimal("1"),
                maximum_extra_fee_usd=Decimal("0"),
            )
        except BudgetExceededError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=len(ledgers)) as pool:
        outcomes = list(pool.map(reserve_one, ledgers))

    assert sum(outcomes) == 2
    assert all(ledger.remaining_usd() == Decimal("0") for ledger in ledgers)
