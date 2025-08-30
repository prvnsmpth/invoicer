from datetime import datetime, timedelta
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from dateutil import parser
import pytz
from auth import authenticate
from config import DEFAULT_TIMEZONE


class CalendarClient:
    def __init__(self):
        self.creds = authenticate()
        self.service = build('calendar', 'v3', credentials=self.creds)
        self.timezone = pytz.timezone(DEFAULT_TIMEZONE)
    
    def list_calendars(self) -> List[Dict]:
        """List all available calendars for the authenticated user."""
        try:
            calendar_list = self.service.calendarList().list().execute()
            calendars = []
            for calendar in calendar_list.get('items', []):
                calendars.append({
                    'id': calendar['id'],
                    'summary': calendar.get('summary', 'Unnamed Calendar'),
                    'primary': calendar.get('primary', False)
                })
            return calendars
        except Exception as e:
            raise Exception(f"Failed to list calendars: {str(e)}")
    
    def fetch_events(self, start_date: str, end_date: str, calendar_id: str = 'primary') -> List[Dict]:
        """
        Fetch calendar events between start_date and end_date.
        
        Args:
            start_date: ISO format date string (YYYY-MM-DD)
            end_date: ISO format date string (YYYY-MM-DD)
            calendar_id: Calendar ID (default: 'primary')
        
        Returns:
            List of event dictionaries with calculated duration
        """
        try:
            # Parse dates and add time components
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            
            # Make timezone aware
            start_dt = self.timezone.localize(start_dt)
            end_dt = self.timezone.localize(end_dt)
            
            # Convert to RFC3339 format
            time_min = start_dt.isoformat()
            time_max = end_dt.isoformat()
            
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            processed_events = []
            for event in events:
                # Skip all-day events for now
                if 'dateTime' not in event.get('start', {}):
                    continue
                
                start = parser.parse(event['start']['dateTime'])
                end = parser.parse(event['end']['dateTime'])
                duration = end - start
                duration_hours = duration.total_seconds() / 3600
                
                processed_events.append({
                    'id': event['id'],
                    'summary': event.get('summary', 'No Title'),
                    'description': event.get('description', ''),
                    'start': start.isoformat(),
                    'end': end.isoformat(),
                    'duration_hours': round(duration_hours, 2),
                    'attendees': [att.get('email', '') for att in event.get('attendees', [])]
                })
            
            return processed_events
            
        except Exception as e:
            raise Exception(f"Failed to fetch events: {str(e)}")
    
    def get_total_hours(self, events: List[Dict]) -> float:
        """Calculate total hours from a list of events."""
        return sum(event['duration_hours'] for event in events)