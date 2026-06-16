# Tasks

No `make` on this dev box, so tasks are documented here instead of a Makefile.

## test
Run the full offline test suite:

    pytest -q

## test-cov
Run the suite with coverage:

    pytest -q --cov=scanner --cov-report=term-missing
