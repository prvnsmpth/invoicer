# Invoicer - Dead Simple Google Calendar Invoice Generator

A command-line tool that integrates with Google Calendar to generate professional PDF invoices based on your calendar events.

## Features

- 🔐 Google OAuth authentication for secure calendar access
- 📅 Fetch events from any date range
- 💼 Create and manage invoice cycles
- 📄 Generate PDF invoices in two formats:
  - **Summary**: Single line item with total hours
  - **Detailed**: Individual line items per calendar event
- 💰 Flexible billing configuration (client details, payment info)
- 🗄️ Local SQLite database for data persistence

## Installation

1. Install dependencies using uv:
```bash
uv pip install -r requirements.txt
```

2. Set up Google Calendar API:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Google Calendar API
   - Create OAuth 2.0 credentials (Desktop app type)
   - Download the credentials JSON
   - Save it as `credentials/credentials.json`

## Usage

### 1. Authenticate with Google
```bash
python main.py auth
```

### 2. Fetch calendar events
```bash
python main.py fetch --start 2025-07-01 --end 2025-07-31
```

### 3. Create an invoice cycle
```bash
python main.py cycle create "Client Name - July 2025" \
  --start 2025-07-01 \
  --end 2025-07-31 \
  --rate 150 \
  --client-name "Acme Corp Pvt. Ltd." \
  --client-address "123 Business Park,\nBengaluru" \
  --client-gstin "29AABCU9603R1ZM"
```

### 4. Assign events to cycle
```bash
python main.py cycle assign 1
# Interactive selection: enter event numbers like "1,3,5-8" or "all"
```

### 5. Generate invoice
```bash
# Summary format (single line item)
python main.py generate 1 --rate 150

# Detailed format (individual line items)
python main.py generate 1 --rate 150 --detailed

# Custom invoice date and payment terms
python main.py generate 1 --invoice-date 2025-07-31 --due-days 30
```

### 6. Manage your profile
```bash
python main.py profile
```

## Commands Overview

- `auth` - Authenticate with Google Calendar
- `logout` - Clear stored credentials
- `fetch` - Fetch events from calendar
- `cycle create` - Create new invoice cycle
- `cycle list` - List all invoice cycles
- `cycle assign` - Assign events to a cycle
- `generate` - Generate PDF invoice
- `profile` - View/edit user profile

## Invoice Formats

### Summary Invoice
Shows total consulting hours as a single line item:
```
Consulting Charges - July '25 (17.5 hours * 150 USD/hour)    17.5    2,625.00
```

### Detailed Invoice
Lists each calendar event separately:
```
Project Meeting            07/15    2.0    150    300.00
Code Review               07/16    1.5    150    225.00
Development Sprint        07/17    4.0    150    600.00
```

## Data Storage

- **Database**: `invoicer.db` (SQLite)
- **Credentials**: `credentials/` directory
- **Generated Invoices**: `invoices/` directory
- **OAuth Token**: `credentials/token.json`

## Tips

- Events are fetched once and stored locally for quick access
- You can create multiple invoice cycles and assign different events to each
- Profile information is saved and reused for future invoices
- Use `--detailed` flag for itemized invoices when needed