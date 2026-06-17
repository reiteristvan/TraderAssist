#!/usr/bin/env python3
"""DEPRECATED — replaced by scan.py.

Use:
  python scan.py scan --strategy pullback --file universes/sample.txt
  python scan.py scan --strategy breakout --file universes/sample.txt
  python scan.py scan --ticker AAPL

The full legacy source is preserved in legacy/swing_scanner.py for reference.
"""
import sys

print(
    "swing_scanner.py is deprecated.\n"
    "Use: python scan.py scan --strategy pullback|breakout [--ticker X | --file U.txt]\n"
    "Legacy source: legacy/swing_scanner.py",
    file=sys.stderr,
)
sys.exit(1)
