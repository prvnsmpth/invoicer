# Invoicer

Invoicer is a dead simple invoicing software that integrates with Google calendar determine billable hours.

Here's how it should work:

1. Use Google OAuth to get permission to read a user's calendar
2. Fetch all events from the calendar for a specified time period (start date to end date)
3. Display all calendar entries and allow the user to pick which ones to include in the invoice
4. Have this concept of "invoice cycle" - Invoicer should allow the user to assign calendar entries (billable hours) to an invoice cycle (which will have a well-defined name).
5. Finally, it should allow the user to specify an hourly rate (in INR only, for now), and based on this, generate a PDF invoice with all the basic things (sample will be provided later).

And that's it.

# Important implementation instructions

1. Always use uv instead of pip


