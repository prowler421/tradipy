"""Q3 — measured data-to-signal and signal-to-order latency.

PHASE-2A-SPIKE.md Q3: *"What is the measured data-to-signal and signal-to-order latency?"*
§5.5's "every 30-60 seconds" full-universe refresh, §4.4's 30-120 s scan schedule and §20.1's
bar-close grace are all **assumptions**. This measures two of the three.

**Report the distribution, not the mean.** §7 says so twice, and the reason is that a mean hides
the tail that matters: a 400 ms average with a 12 s p95 is a system that misses the entry on one
signal in twenty, and the mean says it is fine. The pass thresholds are stated on p95 for exactly
that reason, and :func:`percentile` is the whole arithmetic content of this module.

**What "signal-to-order" means here, and what it does not.** It is the interval from a signal
being decided to the order acknowledgement returning from the broker. It was specified as a
``whatIf`` order preview against a paper account — a margin-check round trip that never reaches a
venue — and it therefore **understates** true fill latency and does not cover venue routing. The
report says so rather than leaving a reader to assume the number covers execution.

**No collector exists to produce that measurement.** PLAN **D30** puts the project on simulated
data, and the collection script was removed with it; ``scripts/spike2a/TEST_SETUP.md`` records
what restoring it costs. What remains here is the arithmetic and the threshold comparison, which
can be checked without a connection — and a gate, because latency is the one Q where simulated
input is not merely uninformative but actively misleading. A fabricated p95 measures the
generator's parameters. So on ``SIMULATED`` input this module reports the distribution and
**withholds the §5.5/§4.4 disposition entirely**: unmeasured is not a pass, and neither is
invented.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from scripts.spike2a.prereg import (
    Q3_MAX_DATA_TO_SIGNAL_P95_SECONDS,
    Q3_MAX_SIGNAL_TO_ORDER_P95_SECONDS,
)
from scripts.spike2a.provenance import Provenance, ProvenanceError, banner, require

#: The percentiles §7 asks to see. p95 is the threshold; the rest are context, because a
#: threshold reported alone cannot show whether it was missed narrowly or by an order of
#: magnitude.
REPORTED_PERCENTILES = (50, 75, 90, 95, 99)


def percentile(values: list[Decimal], p: int) -> Decimal | None:
    """The ``p``-th percentile by nearest-rank on the sorted sample.

    Nearest-rank rather than interpolated, deliberately: an interpolated p95 reports a latency
    that was never observed, and every value here is meant to be a measurement. With n < 20 the
    p95 is simply the maximum, which is honest — the sample is too small for the tail to mean
    anything, and :func:`report` prints n beside it so that is visible.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-p * len(ordered) // 100))  # ceil without float arithmetic
    return ordered[rank - 1]


@dataclass(frozen=True)
class Measurement:
    """One observed interval, in seconds."""

    kind: str
    seconds: Decimal
    note: str = ""


@dataclass(frozen=True)
class Summary:
    """One latency population against its §7 threshold."""

    kind: str
    n: int
    percentiles: dict[int, Decimal | None]
    threshold_seconds: int

    @property
    def p95(self) -> Decimal | None:
        return self.percentiles.get(95)

    @property
    def fails(self) -> bool:
        """True when the p95 exceeds §7's threshold. Unmeasured is **not** a pass."""
        p = self.p95
        return p is not None and p > Decimal(self.threshold_seconds)

    def __str__(self) -> str:
        if not self.n:
            return f"{self.kind:<18} no measurements — unanswered, not passed"
        cuts = "  ".join(
            f"p{p}={self.percentiles[p]:.3f}s" for p in REPORTED_PERCENTILES if self.percentiles[p]
        )
        verdict = "FAILS" if self.fails else "within"
        return (
            f"{self.kind:<18} n={self.n:<5} {cuts}\n"
            f"{'':<18} threshold p95 <= {self.threshold_seconds}s -> {verdict}"
        )


def summarize(measurements: list[Measurement]) -> list[Summary]:
    """One :class:`Summary` per latency kind, thresholds attached from §7."""
    thresholds = {
        "data_to_signal": Q3_MAX_DATA_TO_SIGNAL_P95_SECONDS,
        "signal_to_order": Q3_MAX_SIGNAL_TO_ORDER_P95_SECONDS,
    }
    out: list[Summary] = []
    for kind, threshold in thresholds.items():
        values = [m.seconds for m in measurements if m.kind == kind]
        out.append(
            Summary(
                kind=kind,
                n=len(values),
                percentiles={p: percentile(values, p) for p in REPORTED_PERCENTILES},
                threshold_seconds=threshold,
            )
        )
    return out


def report(measurements: list[Measurement], prov: Provenance) -> str:
    """D3, distribution first."""
    summaries = summarize(measurements)
    lines = [
        "Q3 — measured latency",
        "=" * 62,
        "",
        *banner(prov),
        "",
        *(f"{s}\n" for s in summaries),
    ]

    failing = [s.kind for s in summaries if s.fails]
    unmeasured = [s.kind for s in summaries if not s.n]

    if not prov.answers_prereg:
        lines += [
            "§5.5 / §4.4 disposition WITHHELD",
            "  These intervals were not observed on a wire. A p95 computed from simulated input",
            "  reports the generator's parameters, so it can neither pass nor fail §7 — and a",
            "  latency figure is the easiest number in this spike to quote out of context.",
            "  Q3 stays unanswered until the ladder reaches PAPER (PLAN D30).",
        ]
        return "\n".join(lines)

    lines.append("§5.5 / §4.4 disposition")
    if failing:
        lines += [
            f"  ASSUMPTION FAILS for: {', '.join(failing)}.",
            "  §4.4's scan schedule and §20.1's bar_close_grace_ms are both revisited before",
            "  Phase 5, per §6. Raise as a spec question; do not retune in code.",
        ]
    elif unmeasured:
        lines.append(f"  PARTIAL — no measurements for: {', '.join(unmeasured)}.")
    else:
        lines.append("  Both p95s within §7's thresholds on this sample.")

    lines += [
        "",
        "caveat carried into D3: signal_to_order is a whatIf preview round trip, not a fill.",
        "It understates true execution latency and does not cover venue routing.",
    ]
    return "\n".join(lines)


def from_csv_row(row: dict[str, str]) -> Measurement | None:
    """Parse ``kind,seconds[,note]``, where ``kind`` is data_to_signal or signal_to_order."""
    try:
        return Measurement(
            kind=row["kind"].strip().lower(),
            seconds=Decimal(row["seconds"]),
            note=(row.get("note") or "").strip(),
        )
    except (KeyError, ValueError, ArithmeticError):
        return None


def main(argv: list[str]) -> int:
    """``python -m scripts.spike2a.q3_latency <latency.csv>``

    The collection side — connecting to a gateway, timestamping a bar arrival against the signal
    decision, and issuing the order preview — does not exist under D30. It is also the one part
    of the spike that could never have been verified without the connection: guessing at a
    broker library's event ordering before seeing it produces a measurement of the guess. This
    module is the arithmetic and the threshold comparison, which can be checked now, on declared
    input, without claiming to have answered Q3.
    """
    if not argv:
        print(__doc__)
        print("usage: python -m scripts.spike2a.q3_latency <latency.csv>")
        return 2

    path = Path(argv[0])
    try:
        prov = require(path)
    except ProvenanceError as exc:
        print(f"refusing to measure: {exc}", file=sys.stderr)
        return 3

    with path.open(newline="", encoding="utf-8") as fh:
        parsed = [from_csv_row(r) for r in csv.DictReader(fh)]
    measurements = [m for m in parsed if m is not None]

    print(report(measurements, prov))
    if len(parsed) != len(measurements):
        print(f"\n{len(parsed) - len(measurements)} unparsable row(s) skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
