from evaltrim.models import Behavior, RunStats, Tags, TestCase
from evaltrim.scoring import value_score


def test_score_bounds_and_critical_boost():
    critical = TestCase(
        id="c",
        input="x",
        expected="y",
        tags=Tags(critical=True),
        run_stats=RunStats(runs=10, passes=5, failures=5),
    )
    ordinary = TestCase(id="o", input="x", expected="y")
    b_c = Behavior(domain="privacy", action="refusal", conditions=["destructive"], critical=True)
    b_o = Behavior(domain="support", action="apology", critical=False)
    s_c = value_score(critical, b_c, unique_atoms=["condition:destructive"], total_atoms=8, max_cost=1.0)
    s_o = value_score(ordinary, b_o, unique_atoms=[], total_atoms=8, max_cost=1.0)
    assert 0 <= s_c <= 100
    assert 0 <= s_o <= 100
    assert s_c > s_o
