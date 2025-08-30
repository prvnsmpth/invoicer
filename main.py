#!/usr/bin/env python3
import click
import sys
from datetime import datetime, timedelta
from typing import List
from pathlib import Path

from auth import authenticate, is_authenticated, clear_credentials
from calendar_client import CalendarClient
from database import (
    init_db, InvoiceCycle, CalendarEvent, Invoice, UserProfile
)
from config import CREDENTIALS_FILE


@click.group()
def cli():
    """Dead simple invoicing tool that integrates with Google Calendar."""
    init_db()


@cli.command()
def auth():
    """Authenticate with Google Calendar."""
    if CREDENTIALS_FILE.exists():
        click.echo("Authenticating with Google Calendar...")
        try:
            authenticate()
            click.echo("✓ Successfully authenticated!")
        except Exception as e:
            click.echo(f"✗ Authentication failed: {str(e)}", err=True)
            sys.exit(1)
    else:
        click.echo(f"✗ Please download your OAuth2 credentials from Google Cloud Console")
        click.echo(f"  and save them to: {CREDENTIALS_FILE}")
        click.echo("\nSteps:")
        click.echo("1. Go to https://console.cloud.google.com/")
        click.echo("2. Create a new project or select existing")
        click.echo("3. Enable Google Calendar API")
        click.echo("4. Create OAuth 2.0 credentials (Desktop app)")
        click.echo("5. Download the credentials JSON file")
        click.echo(f"6. Save it as: {CREDENTIALS_FILE}")
        sys.exit(1)


@cli.command()
def logout():
    """Clear stored authentication credentials."""
    if clear_credentials():
        click.echo("✓ Logged out successfully")
    else:
        click.echo("No credentials to clear")


@cli.command()
@click.option('--start', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end', required=True, help='End date (YYYY-MM-DD)')
@click.option('--calendar', default='primary', help='Calendar ID (default: primary)')
def fetch(start, end, calendar):
    """Fetch calendar events for a date range."""
    if not is_authenticated():
        click.echo("✗ Please authenticate first: python main.py auth", err=True)
        sys.exit(1)
    
    try:
        client = CalendarClient()
        click.echo(f"Fetching events from {start} to {end}...")
        
        events = client.fetch_events(start, end, calendar)
        
        if not events:
            click.echo("No events found in the specified date range.")
            return
        
        # Store events in database
        CalendarEvent.bulk_insert(events)
        
        click.echo(f"\n✓ Found {len(events)} events:")
        click.echo("-" * 60)
        
        total_hours = 0
        for i, event in enumerate(events, 1):
            start_time = datetime.fromisoformat(event['start']).strftime('%Y-%m-%d %H:%M')
            click.echo(f"{i:3}. {event['summary'][:40]:40} | {start_time} | {event['duration_hours']:.1f}h")
            total_hours += event['duration_hours']
        
        click.echo("-" * 60)
        click.echo(f"Total: {total_hours:.1f} hours")
        
    except Exception as e:
        click.echo(f"✗ Failed to fetch events: {str(e)}", err=True)
        sys.exit(1)


@cli.group()
def cycle():
    """Manage invoice cycles."""
    pass


@cycle.command('create')
@click.argument('name')
@click.option('--start', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end', required=True, help='End date (YYYY-MM-DD)')
@click.option('--rate', type=float, help='Hourly rate in INR')
@click.option('--client-name', help='Client company name')
@click.option('--client-address', help='Client address')
@click.option('--client-gstin', help='Client GSTIN')
def create_cycle(name, start, end, rate, client_name, client_address, client_gstin):
    """Create a new invoice cycle."""
    try:
        cycle_id = InvoiceCycle.create(
            name=name,
            start_date=start,
            end_date=end,
            hourly_rate=rate,
            client_name=client_name,
            client_address=client_address,
            client_gstin=client_gstin
        )
        click.echo(f"✓ Created invoice cycle '{name}' (ID: {cycle_id})")
    except Exception as e:
        click.echo(f"✗ Failed to create cycle: {str(e)}", err=True)
        sys.exit(1)


@cycle.command('list')
def list_cycles():
    """List all invoice cycles."""
    cycles = InvoiceCycle.list_all()
    
    if not cycles:
        click.echo("No invoice cycles found.")
        return
    
    click.echo("\nInvoice Cycles:")
    click.echo("-" * 80)
    click.echo(f"{'ID':4} {'Name':30} {'Period':25} {'Rate':10} {'Client':20}")
    click.echo("-" * 80)
    
    for c in cycles:
        period = f"{c['start_date']} to {c['end_date']}"
        rate = f"₹{c['hourly_rate']}/h" if c['hourly_rate'] else "Not set"
        client = c['client_name'] or "Not set"
        click.echo(f"{c['id']:4} {c['name'][:30]:30} {period:25} {rate:10} {client[:20]:20}")


@cycle.command('assign')
@click.argument('cycle_id', type=int)
def assign_events(cycle_id):
    """Interactively assign events to an invoice cycle."""
    cycle = InvoiceCycle.get(cycle_id)
    if not cycle:
        click.echo(f"✗ Invoice cycle {cycle_id} not found", err=True)
        sys.exit(1)
    
    # Get unassigned events within cycle dates
    events = CalendarEvent.get_unassigned(cycle['start_date'], cycle['end_date'])
    
    if not events:
        click.echo(f"No unassigned events found for cycle period {cycle['start_date']} to {cycle['end_date']}")
        return
    
    click.echo(f"\nAssigning events to cycle: {cycle['name']}")
    click.echo(f"Period: {cycle['start_date']} to {cycle['end_date']}")
    click.echo("-" * 80)
    
    for i, event in enumerate(events, 1):
        start_time = datetime.fromisoformat(event['start_time']).strftime('%Y-%m-%d %H:%M')
        click.echo(f"{i:3}. {event['title'][:40]:40} | {start_time} | {event['duration_hours']:.1f}h")
    
    click.echo("-" * 80)
    total_available = sum(e['duration_hours'] for e in events)
    click.echo(f"Total available: {total_available:.1f} hours")
    
    selection = click.prompt(
        "\nEnter event numbers to include (e.g., 1,3,5-8 or 'all')",
        type=str
    )
    
    if selection.lower() == 'all':
        selected_ids = [e['id'] for e in events]
    else:
        selected_indices = parse_selection(selection, len(events))
        selected_ids = [events[i-1]['id'] for i in selected_indices]
    
    if selected_ids:
        CalendarEvent.assign_to_cycle(selected_ids, cycle_id)
        selected_hours = sum(e['duration_hours'] for e in events if e['id'] in selected_ids)
        click.echo(f"✓ Assigned {len(selected_ids)} events ({selected_hours:.1f} hours) to cycle")
    else:
        click.echo("No events selected")


@cli.command()
@click.argument('cycle_id', type=int)
@click.option('--rate', type=float, help='Hourly rate in INR (overrides cycle rate)')
@click.option('--detailed', is_flag=True, help='Generate detailed invoice with individual line items')
@click.option('--invoice-date', help='Invoice date (YYYY-MM-DD), defaults to today')
@click.option('--due-days', default=30, help='Payment terms in days (default: 30)')
def generate(cycle_id, rate, detailed, invoice_date, due_days):
    """Generate PDF invoice for a cycle."""
    cycle = InvoiceCycle.get(cycle_id)
    if not cycle:
        click.echo(f"✗ Invoice cycle {cycle_id} not found", err=True)
        sys.exit(1)
    
    # Determine hourly rate
    hourly_rate = rate or cycle['hourly_rate']
    if not hourly_rate:
        hourly_rate = click.prompt('Enter hourly rate in INR', type=float)
        InvoiceCycle.update_rate(cycle_id, hourly_rate)
    
    # Get events for this cycle
    events = CalendarEvent.get_by_cycle(cycle_id)
    if not events:
        click.echo(f"✗ No events assigned to this cycle", err=True)
        sys.exit(1)
    
    # Get user profile
    profile = UserProfile.get_or_create()
    if profile['full_name'] == 'Your Name':
        click.echo("\n⚠ Please update your profile first:")
        profile['full_name'] = click.prompt('Your full name')
        profile['address'] = click.prompt('Your address (multi-line, use \\n for new lines)')
        profile['account_name'] = click.prompt('Bank account name', default=profile['full_name'])
        profile['account_number'] = click.prompt('Bank account number')
        profile['ifsc_code'] = click.prompt('IFSC code')
        profile['bank_name'] = click.prompt('Bank name and branch')
        profile['account_type'] = click.prompt('Account type', default='SAVING')
        profile['pan'] = click.prompt('PAN number')
        UserProfile.update(profile)
    
    # Import PDF generator (will create this next)
    from pdf_generator import generate_invoice_pdf
    
    try:
        pdf_path = generate_invoice_pdf(
            cycle=cycle,
            events=events,
            profile=profile,
            hourly_rate=hourly_rate,
            detailed=detailed,
            invoice_date=invoice_date,
            due_days=due_days
        )
        click.echo(f"✓ Invoice generated: {pdf_path}")
    except Exception as e:
        click.echo(f"✗ Failed to generate invoice: {str(e)}", err=True)
        sys.exit(1)


@cli.group()
def invoices():
    """Manage invoices."""
    pass


@invoices.command()
def list():
    """List all generated invoices."""
    invoice_list = Invoice.list_all()
    
    if not invoice_list:
        click.echo("No invoices generated yet.")
        return
    
    click.echo("\nGenerated Invoices:")
    click.echo("-" * 80)
    click.echo(f"{'Invoice #':<12} {'Date':<12} {'Cycle':<20} {'Client':<25} {'Amount':<15}")
    click.echo("-" * 80)
    
    for inv in invoice_list:
        invoice_date = inv['invoice_date'][:10] if inv['invoice_date'] else ''
        cycle_name = inv['cycle_name'][:18] if inv['cycle_name'] else ''
        client_name = inv['client_name'][:23] if inv['client_name'] else ''
        amount = f"₹{inv['total_amount']:,.0f}"
        
        click.echo(f"{inv['invoice_number']:<12} {invoice_date:<12} {cycle_name:<20} {client_name:<25} {amount:<15}")
    
    click.echo("-" * 80)
    click.echo(f"Total invoices: {len(invoice_list)}")


@invoices.command()
@click.argument('invoice_number')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
def delete(invoice_number, yes):
    """Delete an invoice by invoice number."""
    # Get invoice details first
    invoice = Invoice.get_by_number(invoice_number)
    if not invoice:
        click.echo(f"✗ Invoice {invoice_number} not found.")
        sys.exit(1)
    
    # Show invoice details
    click.echo(f"\nInvoice to delete:")
    click.echo(f"  Invoice #: {invoice['invoice_number']}")
    click.echo(f"  Date: {invoice['invoice_date']}")
    click.echo(f"  Cycle: {invoice['cycle_name']}")
    click.echo(f"  Client: {invoice['client_name']}")
    click.echo(f"  Amount: ₹{invoice['total_amount']:,.0f}")
    
    # Confirm deletion unless --yes flag is used
    if not yes:
        click.echo("\n⚠️  This will delete both the database record and PDF file.")
        if not click.confirm("Are you sure you want to delete this invoice?"):
            click.echo("Operation cancelled.")
            return
    
    # Delete the invoice
    if Invoice.delete(invoice_number):
        click.echo(f"✓ Invoice {invoice_number} deleted successfully.")
    else:
        click.echo(f"✗ Failed to delete invoice {invoice_number}.")
        sys.exit(1)


@cli.command()
def profile():
    """View/edit user profile for invoices."""
    profile = UserProfile.get_or_create()
    
    click.echo("\nCurrent Profile:")
    click.echo("-" * 40)
    for key, value in profile.items():
        if key not in ['id', 'created_at', 'logo_path']:
            click.echo(f"{key.replace('_', ' ').title():20} : {value or 'Not set'}")
    
    if click.confirm("\nDo you want to update your profile?"):
        profile['full_name'] = click.prompt('Full name', default=profile['full_name'])
        profile['address'] = click.prompt('Address', default=profile['address'])
        profile['account_name'] = click.prompt('Account name', default=profile.get('account_name', ''))
        profile['account_number'] = click.prompt('Account number', default=profile.get('account_number', ''))
        profile['ifsc_code'] = click.prompt('IFSC code', default=profile.get('ifsc_code', ''))
        profile['bank_name'] = click.prompt('Bank name', default=profile.get('bank_name', ''))
        profile['account_type'] = click.prompt('Account type', default=profile.get('account_type', 'SAVING'))
        profile['pan'] = click.prompt('PAN', default=profile.get('pan', ''))
        
        UserProfile.update(profile)
        click.echo("✓ Profile updated successfully")


def parse_selection(selection: str, max_num: int) -> List[int]:
    """Parse selection string like '1,3,5-8' into list of indices."""
    selected = set()
    parts = selection.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            start, end = int(start), int(end)
            for i in range(start, min(end + 1, max_num + 1)):
                selected.add(i)
        else:
            num = int(part)
            if 1 <= num <= max_num:
                selected.add(num)
    
    return sorted(list(selected))


if __name__ == '__main__':
    cli()