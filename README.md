# 💎 Crystal Material Sample Management System & 晶体材料样品管理系统

[简体中文](README_zh.md)

A local web application designed to manage all information regarding samples obtained from crystal growth experiments.

## Features

- **Sample Management** — Create, view, edit, delete, search, and manually sort samples via drag-and-drop.
- **Basic Info** — Sample ID, Target Product, Status (Success/Fail/Pending/Growing/Completed), Unique Measurements (Electric/Magnetic), Growth Process & Sintering Time Tracking, Results, Notes.
- **Enhanced Navigation & UX** — One-click fast previous/next navigation, auto-resizing textareas, intelligent anti-scroll during saves, and smart duplication that preserves custom reference elements.
- **Mass Calculation** — Intuitive display of current context (ID/Product); input element molar ratios + mass of one reference element to automatically calculate the required mass for other elements.
- **Export** — Export all samples as CSV or PPTX, or export individual sample reports (bilingual) directly to Microsoft Word (`.docx`). The PPTX export starts with an overview table containing Sample ID, Target Sample, and Status, followed by one slide per sample with a color-coded title and separate result/growth-method areas. Intelligent filename generation based on ID, target product, and status.
- **Photos & XRD** — Multiple photo/XRD image uploads (supports camera capture), automatic lazy-loaded thumbnails, zoom preview, and perfectly restored original filenames upon download. XRD/EDX statuses are automatically adjusted based on uploads. Non-image data files in XRD and other sections support direct inline opening (PDF) or downloading. Word export perfectly formats image spacing and omits filenames for physical photos to maintain report cleanliness.
- **EDX Analysis** — Upload EDX spectrum images (auto-generates thumbnails) → uses GPT Vision API to automatically recognize INCA-style elemental composition, with manual reordering support for EDX data cards.
- **Data & Other Files** — Upload/download `.dat/.csv/.txt/.pdf` and any other ad-hoc attachment files with reliable strict original filename retention.
- **Microsoft To Do Integration** — Bind your Microsoft account to automatically sync sintering end times directly to To Do for robust cross-device reminders.
- **Global Timezone Configuration** — Independent timezone setting decoupled from server location to ensure consistent time synchronization between frontend and database.
- **Bilingual & Responsive UI** — Seamless dynamic i18n switching (EN/ZH); deep layout and touch optimizations for mobile and tablet, plus a widescreen fullscreen mode.
- **Bilingual Results & Growth Process with Manual Translation** — Chinese and English results are stored separately (`results` / `results_en`), and growth processes are stored separately (`growth_process` / `growth_process_en`). Legacy Chinese growth text is preserved during migration; the new English field starts empty and is not batch-translated. The Chinese UI shows the `en to cn` button and the English UI shows `cn to en` for both sections. Translation uses `POST /api/results/translate`, directly reusing the same OpenAI-compatible API, client, and configuration as EDX image recognition. It updates only the current form draft; use manual save by clicking Save/保存, with no auto-save to the database. Copying a sample preserves both growth-process fields while results remain cleared.
- **Language-Specific Word/CSV/PPTX Export** — Word exports use the `lang` value to select corresponding saved fields (`zh` → `growth_process` / `results`, `en` → `growth_process_en` / `results_en`) and never fall back across languages. Total CSV/PPTX exports first open a sample-selection dialog, default to all samples, and export only the checked samples in dialog order. CSV has five columns: Sample ID, Target Sample, Status, Result Text, and Growth Method; element ratios are placed on the first line of the Growth Method cell and the language-specific growth process follows on a new line. PPTX creates one slide per selected sample. The CSV/PPTX GET routes continue to export all samples for backward compatibility; selected exports use POST with a JSON `sample_ids` list. Unsaved drafts are not included in exported files.
- **Auto Backup** — Immediate automatic backup on startup + scheduled incremental hot backups (daily) + full compressed zip backups (weekly), alongside a comprehensive CLI restoration utility.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python / Flask / Pillow / python-pptx (PPTX export) |
| Database | SQLite |
| Frontend | HTML / CSS / Vanilla JavaScript |
| AI Vision | OpenAI-compatible APIs (GPT-4o / Gemini) |

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Configuration

Copy `config.py.example` to `config.py` and enter your own password and API Key:

```bash
cp config.py.example config.py
```

Then edit `config.py`:

```python
LOGIN_PASSWORD = "your-password"                # Login password
APP_PORT = 5000                                 # Server port
TIMEZONE_OFFSET_HOURS = 8                       # Timezone offset (e.g. 8 for CST)
OPENAI_API_KEY = "sk-your-api-key"              # API Key for EDX recognition
OPENAI_BASE_URL = "https://api.openai.com/v1/"  # Reverse proxy / base URL
OPENAI_MODEL = "gpt-4o"                         # Model name
```

### 3. Run the App

```bash
python app.py
```

Visit http://127.0.0.1:5000 and log in with your password.

## Project Structure

```
crystal_manager/
├── app.py              # Flask app & API routes
├── config.py.example   # Config template (copy to config.py)
├── models.py           # SQLite database operations
├── backup.py           # Incremental & full backup & scheduler
├── restore_backup.py   # CLI tool for backup restoration
├── migrate_storage.py  # File storage migration tool
├── molmass_data.py     # Element molar masses data
├── requirements.txt    # Python deps
├── templates/
│   ├── index.html      # Main UI
│   └── login.html      # Login page
├── static/
│   ├── css/style.css   # Light theme stylesheet
│   └── js/app.js       # Frontend logic
├── uploads/            # Uploaded files (organized by sample ID)
│   └── <Sample_ID>/
│       ├── photos/
│       ├── edx/
│       ├── data/
│       └── others/
├── backups/            # Incremental backup directory (auto-created)
│   ├── manifest.json   # Incremental backup manifest
│   └── <timestamp>/
│       ├── db.sqlite       # Database snapshot
│       ├── files/          # Incremental new/modified files
│       └── backup_info.json
└── full_backups/       # Full backup directory (auto-created)
    └── full_<timestamp>.zip  # Complete zip archive (DB + all uploads)
```

## Calculation Formula

Given reference element A's mass `m_A`, molar ratio `r_A`, and molar mass `M_A`, the mass of element B is calculated as:

```
m_B = m_A × (r_B / r_A) × (M_B / M_A)
```

## APIs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/samples?q=xxx` | List & Search samples |
| POST | `/api/samples` | Create new sample |
| GET | `/api/samples/<id>` | Sample details |
| PUT | `/api/samples/<id>` | Update sample |
| DELETE | `/api/samples/<id>` | Delete sample |
| POST | `/api/samples/reorder` | Update sample sorting order |
| GET, POST | `/api/samples/export?lang=zh` | Export all samples (GET) or selected samples (POST `sample_ids`) to language-specific CSV (`lang=zh` or `lang=en`) |
| GET, POST | `/api/samples/export_pptx?lang=zh` | Export all samples (GET) or selected samples (POST `sample_ids`) to a language-specific PPTX (`lang=zh` or `lang=en`) |
| GET | `/api/samples/<id>/export_word?lang=zh`| Export sample to language-specific Word (`lang=zh` or `lang=en`) |
| POST | `/api/samples/<id>/photos` | Upload photos |
| POST | `/api/samples/<id>/xrd` | Upload XRD images |
| POST | `/api/samples/<id>/edx` | Upload EDX images |
| POST | `/api/edx/<id>/recognize` | AI EDX Recognition |
| POST | `/api/results/translate` | Translate the current result or growth-process draft between Chinese and English (does not save it) |
| POST | `/api/edx/reorder` | Update EDX images order |
| POST | `/api/samples/<id>/datafiles` | Upload data files |
| POST | `/api/samples/<id>/otherfiles`| Upload other files |
| POST | `/api/calculate_mass` | Calculate element masses |

## Backup and Restore

The system supports two backup strategies running in parallel:

### Incremental Backup (Daily)

Runs on startup and every 24 hours. Only copies new/modified files from `uploads/`, while the database is fully snapshotted each time via SQLite Online Backup API.

### Full Backup (Weekly)

Runs on startup and every 7 days. Packages the **entire database + all uploads** into a single compressed zip file. Ideal for disaster recovery — restore from a single file with no dependency chain.

**Configuration (`config.py`):**
```python
# Incremental backup
BACKUP_INTERVAL_HOURS = 24           # Interval (hours)
BACKUP_KEEP_COUNT = 100000           # Max incremental backups to keep

# Full backup (zip)
FULL_BACKUP_INTERVAL_HOURS = 168     # Interval (168h = 7 days)
FULL_BACKUP_KEEP_COUNT = 10          # Max full backups to keep
```

### CLI Utilities

```bash
# List all backups (incremental + full)
python restore_backup.py list

# Trigger an incremental backup immediately
python restore_backup.py backup

# Trigger a full backup (zip) immediately
python restore_backup.py full-backup

# Interactive menu (choose backup type & action)
python restore_backup.py

# Restore from incremental backup
python restore_backup.py 2026-03-08_22-00-00

# Restore from full backup zip
python restore_backup.py full-restore full_2026-03-08_22-00-00.zip
```

> ⚠️ The application must be restarted after a restoration.
