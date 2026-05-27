#!/usr/bin/env python3
"""
fetch_reminders.py - Export Apple Reminders via iCloud CalDAV (Linux / cross-platform)

Replaces the macOS Shortcuts-based export step with a CalDAV client that
connects to iCloud and exports all reminders as JSON files compatible with
the existing organize.py post-processor.

Usage:
    python3 scripts/fetch_reminders.py [--output ./reminders]

Requirements:
    pip install caldav python-dateutil
    (or: pip install -r requirements.txt)

Authentication:
    Use an iCloud App-Specific Password generated at appleid.apple.com.
    Your regular Apple ID password will NOT work because Apple requires 2FA.
    Steps: appleid.apple.com → Sign-In and Security → App-Specific Passwords

Limitations vs macOS Shortcuts export:
    - Smart Lists are not available via CalDAV (Apple limitation)
    - Attachments are not synced over CalDAV (Apple limitation)
    - Tags/categories and subtasks are supported where iCloud exposes them
"""

import argparse
import getpass
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import caldav
except ImportError:
    print(
        "Error: 'caldav' package not installed.\n"
        "Run: pip install caldav python-dateutil\n"
        "  or: pip install -r requirements.txt"
    )
    sys.exit(1)

try:
    from dateutil import parser as date_parser  # noqa: F401 (validates install)
except ImportError:
    print(
        "Error: 'python-dateutil' package not installed.\n"
        "Run: pip install caldav python-dateutil\n"
        "  or: pip install -r requirements.txt"
    )
    sys.exit(1)


ICLOUD_CALDAV_URL = "https://caldav.icloud.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def priority_from_ical(ical_priority: int) -> str:
    """Convert iCalendar PRIORITY (0–9) to a human-readable label.

    iCalendar RFC 5545 §3.8.1.9:
        0        = undefined
        1–4      = high
        5        = medium
        6–9      = low
    """
    if ical_priority is None or ical_priority == 0:
        return "None"
    if 1 <= ical_priority <= 4:
        return "High"
    if ical_priority == 5:
        return "Medium"
    return "Low"


def format_datetime(value) -> str | None:
    """Return an ISO 8601 string from a vObject date/datetime property, or None."""
    if value is None:
        return None
    # vObject properties wrap the real value in a .dt attribute
    dt = getattr(value, "dt", value)
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    # plain date
    return dt.isoformat()


def get_prop(component, name, default=None):
    """Safely retrieve a vObject property value."""
    try:
        return getattr(component, name).value
    except AttributeError:
        return default


def todo_to_dict(todo, list_name: str) -> dict | None:
    """Convert a CalDAV VTODO into a dict matching the Shortcuts JSON schema.

    Returns None if the todo cannot be parsed.
    """
    try:
        component = todo.vobject_instance.vtodo
    except Exception:
        return None

    title = get_prop(component, "summary", "(No Title)")
    notes = get_prop(component, "description", "")
    status = (get_prop(component, "status", "NEEDS-ACTION") or "NEEDS-ACTION").upper()
    is_completed = status == "COMPLETED"

    # Priority
    try:
        priority_val = int(get_prop(component, "priority", 0) or 0)
    except (ValueError, TypeError):
        priority_val = 0
    priority = priority_from_ical(priority_val)

    # Dates — access the raw vObject property so format_datetime can unwrap .dt
    due_date = format_datetime(getattr(component, "due", None))
    created = format_datetime(
        getattr(component, "created", None) or getattr(component, "dtstamp", None)
    )
    completed_date = format_datetime(getattr(component, "completed", None))

    # Tags / categories
    try:
        raw_cats = component.categories.value
        if isinstance(raw_cats, str):
            tags = [t.strip() for t in raw_cats.split(",") if t.strip()]
        elif isinstance(raw_cats, (list, tuple)):
            tags = [str(t).strip() for t in raw_cats if str(t).strip()]
        else:
            tags = []
    except AttributeError:
        tags = []

    # Use the VTODO UID as the filename so re-runs are idempotent
    uid = get_prop(component, "uid") or str(uuid.uuid4())
    safe_uid = re.sub(r"[^\w\-]", "_", uid)

    return {
        "filename": f"{safe_uid}.json",
        "data": {
            "Title": title,
            "Notes": notes,
            "List": list_name,
            "Is Completed": is_completed,
            "Priority": priority,
            "Due Date": due_date,
            "Creation Date": created,
            "Completion Date": completed_date,
            "Tags": tags,
        },
    }


# ---------------------------------------------------------------------------
# Core export
# ---------------------------------------------------------------------------

def fetch_reminders(apple_id: str, app_password: str, output_dir: str, verbose: bool = False) -> int:
    """Connect to iCloud CalDAV and export all reminders as JSON files.

    Returns the total number of reminders exported.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\nConnecting to iCloud CalDAV as {apple_id} …")
    try:
        client = caldav.DAVClient(
            url=ICLOUD_CALDAV_URL,
            username=apple_id,
            password=app_password,
        )
        principal = client.principal()
    except Exception as exc:
        print(f"\nError connecting to iCloud: {exc}")
        print(
            "\nTroubleshooting:\n"
            "  • Use an App-Specific Password, not your regular Apple ID password\n"
            "  • Generate one at: appleid.apple.com → Sign-In and Security → App-Specific Passwords\n"
            "  • Make sure iCloud Reminders sync is enabled on your Apple device"
        )
        sys.exit(1)

    print("Connected. Discovering reminder lists …")

    try:
        calendars = principal.calendars()
    except Exception as exc:
        print(f"Error fetching calendars: {exc}")
        sys.exit(1)

    total_exported = 0
    total_lists = 0

    for calendar in calendars:
        # Resolve the display name of this calendar
        try:
            props = calendar.get_properties([caldav.dav.DisplayName()])
            list_name = props.get("{DAV:}displayname") or ""
        except Exception:
            list_name = ""
        if not list_name:
            # Fall back to the last URL path segment
            list_name = str(calendar.url).rstrip("/").split("/")[-1] or "Unknown"

        # Fetch TODOs; skip calendars that don't support them (event calendars)
        try:
            todos = calendar.todos(include_completed=True)
        except Exception:
            continue

        if not todos:
            continue

        total_lists += 1
        list_count = 0
        print(f"\nList: {list_name!r}  ({len(todos)} reminder(s))")

        for todo in todos:
            result = todo_to_dict(todo, list_name)
            if result is None:
                continue

            out_file = output_path / result["filename"]
            with open(out_file, "w", encoding="utf-8") as fh:
                json.dump(result["data"], fh, indent=2, ensure_ascii=False, default=str)

            list_count += 1
            if verbose:
                status_marker = "✓" if result["data"]["Is Completed"] else "○"
                print(f"  {status_marker} {result['data']['Title']}")

        total_exported += list_count
        if not verbose:
            print(f"  Exported {list_count} reminder(s)")

    print(
        f"\n✓ Done! Exported {total_exported} reminder(s) from {total_lists} list(s)"
        f" → {output_path.resolve()}"
    )
    return total_exported


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def prompt_credentials() -> tuple[str, str]:
    print("\n=== iCloud CalDAV Authentication ===")
    print("Use an App-Specific Password (NOT your regular Apple ID password).")
    print("Generate one at: appleid.apple.com → Sign-In and Security → App-Specific Passwords\n")
    apple_id = input("Apple ID (email): ").strip()
    app_password = getpass.getpass("App-Specific Password: ")
    return apple_id, app_password


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export Apple Reminders to JSON via iCloud CalDAV.\n"
            "Linux/cross-platform replacement for the macOS Shortcuts-based export."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output", "-o",
        default="./reminders",
        metavar="DIR",
        help="Directory to write JSON files into (default: ./reminders)",
    )
    parser.add_argument(
        "--apple-id",
        metavar="EMAIL",
        help="Your Apple ID email address (prompted if omitted)",
    )
    parser.add_argument(
        "--app-password",
        metavar="PASSWORD",
        help=(
            "iCloud App-Specific Password (prompted if omitted). "
            "Generate at appleid.apple.com → Sign-In and Security → App-Specific Passwords"
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print each reminder title as it is exported",
    )
    args = parser.parse_args()

    apple_id = args.apple_id
    app_password = args.app_password

    if not apple_id or not app_password:
        apple_id, app_password = prompt_credentials()

    fetch_reminders(apple_id, app_password, args.output, args.verbose)


if __name__ == "__main__":
    main()
