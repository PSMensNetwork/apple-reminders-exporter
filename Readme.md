# Apple Reminders Exporter

Export Apple Reminders to JSON — on **macOS** via `Shortcuts.app`, or on **Linux** (and any other platform) via **iCloud CalDAV**.

> See also [Apple Notes Exporter](https://github.com/Kylmakalle/apple-notes-exporter)

---

## Linux / Linux Mint

Apple Reminders syncs over iCloud using the standard **CalDAV** protocol, which any machine can speak. The `scripts/fetch_reminders.py` script connects directly to `caldav.icloud.com` and exports your reminders as the same JSON files the macOS Shortcuts workflow produces.

### Prerequisites

- Python 3.9+
- An **iCloud App-Specific Password** — your regular Apple ID password won't work because Apple enforces 2FA on CalDAV access.  
  Generate one at: **appleid.apple.com → Sign-In and Security → App-Specific Passwords**
- iCloud Reminders sync enabled on at least one of your Apple devices

### Quickstart

```shell
git clone https://github.com/psmensnetwork/apple-reminders-exporter
cd apple-reminders-exporter

# Install Python dependencies
make install          # or: pip install -r requirements.txt

# Export (you will be prompted for your Apple ID and App-Specific Password)
make

# JSON files are now in ./reminders/, organised by list
```

### Running the fetcher directly

```shell
python3 scripts/fetch_reminders.py --output ./reminders

# Pass credentials on the command line (useful for scripting)
python3 scripts/fetch_reminders.py \
    --apple-id you@example.com \
    --app-password xxxx-xxxx-xxxx-xxxx \
    --output ./reminders

# Show each reminder title as it is saved
python3 scripts/fetch_reminders.py --verbose
```

### Output format

Each reminder is saved as an individual JSON file:

```json
{
  "Title": "Buy milk",
  "Notes": "Oat milk if possible",
  "List": "Groceries",
  "Is Completed": false,
  "Priority": "None",
  "Due Date": "2024-06-01T09:00:00+00:00",
  "Creation Date": "2024-05-20T14:32:00+00:00",
  "Completion Date": null,
  "Tags": ["shopping"]
}
```

Running `make organize` (or `make` which calls it automatically) groups the flat JSON files into subdirectories by list name and completion status:

```
reminders/
├── Groceries/
│   ├── <uid>.json          ← active reminders
│   └── Completed/
│       └── <uid>.json      ← completed reminders
└── Work/
    └── ...
```

### Limitations vs macOS Shortcuts export

| Feature | macOS Shortcuts | Linux CalDAV |
|---|---|---|
| All reminder lists | ✅ | ✅ |
| Title, notes, due date | ✅ | ✅ |
| Completion status & date | ✅ | ✅ |
| Priority | ✅ | ✅ |
| Tags / categories | ✅ | ✅ |
| **Smart Lists** | ❌ (Apple limitation) | ❌ (Apple limitation) |
| Attachments | ✅ | ❌ (not synced via CalDAV) |
| "When Messaging Person" | ❌ (causes hang) | ❌ (not in CalDAV) |

---

## macOS

The original Shortcuts-based workflow is unchanged and is used automatically when you run `make` on macOS.

1. Clone repository (Terminal)

```shell
git clone https://github.com/psmensnetwork/apple-reminders-exporter
cd apple-reminders-exporter
```

2. Install `Export Reminders` Shortcut using [this link](https://www.icloud.com/shortcuts/d1d24fece46d433bb8f5ab6e591764f1) or run `open "Export Reminders.shortcut"`
3. `Shortcuts.app` → Settings → Advanced → **Allow Sharing Large Amounts of Data**
4. Run `make`
   - `Shortcuts.app` will ask for your approval to save Reminders as Dictionaries (JSON). Click **Allow**.
   - If something goes wrong: `Export Reminders` Shortcut → **(i)** Shortcut details → Privacy → **Reset Privacy**, then try again.
5. Done! JSON files are at [reminders/](./reminders)

### macOS Shortcut source

I don't trust the `.shortcuts` binary format, so the visual source of `Export Reminders.shortcut` is documented in [shortcut-source/](./shortcut-source).

![Shortcut source](./shortcut-source/shortcut-2.png)

### macOS Tips & Tricks

1. Smart Lists cannot be exported. With JSON it is straightforward to replicate any filter yourself.
   - "When Messaging Person" causes the shortcut to hang — this field is skipped.
2. Exporting takes roughly 10 minutes per 1 000 reminders.
3. Filters on `Find Reminders` don't work directly. Workaround: chain a second `Find Reminders` action that consumes the `Reminders` variable from the first; filters work there.
4. Reminders are stored as `.ics` files internally, but some metadata lives in undocumented databases — hence the Shortcuts approach rather than raw file access.

---

## Alternative approaches

- [Reminders CLI](https://github.com/keith/reminders-cli) (macOS only)
- https://gist.github.com/0xdevalias/ccc2b083ff58b52aa701462f2cfb3cc8
