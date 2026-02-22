"""
Squash all migrations to a single baseline for fresh installations.

USAGE:
    python scripts/squash_to_baseline.py

WARNING:
    Do NOT run this if any shared environment (staging, production) has
    the existing migration chain applied. This is for NEW databases only.
"""
import sys


def main():
    print("Migration squashing is not yet implemented.")
    print("For fresh installations, run: alembic upgrade head")
    print("For existing installations, the incremental chain is preserved.")
    sys.exit(0)


if __name__ == "__main__":
    main()
