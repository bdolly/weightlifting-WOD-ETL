import re
from more_itertools import pairwise
import datetime
from dateutil.parser import parse
from logger_config import get_logger

logger = get_logger(__name__)


def partition_by(regex, source):
    """Filter source list by regex pattern, returning matching items with their indices"""
    matches = []
    for idx, item in enumerate(source):
        if regex.search(str(item)):
            matches.append((idx, item))
    return matches


def get_pairwise_series_indexes(masked_arr):
    """Turn a list of indices into a nested list of index pairs
    [(0, 'item'), (1, 'item'), (2, 'item')] => [[0, 1], [1, 2], [2, 3]]
    """
    if not masked_arr:
        return []
    
    indices = [idx for idx, _ in masked_arr]
    out = []
    for current, nxt in pairwise(indices):
        out.append([current, nxt])
    return out


def get_groups(index_list, source):
    """
        [[0,1],[1,2],[2,3]], ['a','b','c','d'] => [[a,b],[b,c],[c,d]]
        given a nested list of index pairs from the source
        return a list with the content from that list
    """
    return list(map(lambda x: source[x[0]: x[1]], index_list))


def extract_date_range_from_slug_or_title(slug=None, title=None):
    """
    Extract date range from post slug or title.
    
    Handles formats like:
    - "april-1-7-2024-5-day-weightlifting-program" (slug)
    - "April 1-7, 2024 &#8211; 5 Day Weightlifting Program" (title)
    
    Returns tuple (start_date, end_date) as date objects, or (None, None) if not found.
    """
    text = None
    if slug:
        text = slug
    elif title:
        # Clean HTML entities from title
        text = title.replace('&#8211;', '-').replace('&ndash;', '-')
    
    if not text:
        return None, None
    
    # Pattern 1: "april-1-7-2024" or "april-1-7-2024" (slug format)
    # Pattern 2: "April 1-7, 2024" (title format)
    # Pattern 3: "april 1-7 2024" (variation)
    
    # Try slug format first: month-day1-day2-year
    slug_pattern = re.compile(
        r'(\w+)-(\d+)-(\d+)-(\d{4})',
        re.IGNORECASE
    )
    match = slug_pattern.search(text)
    
    if not match:
        # Try title format: "Month day1-day2, year"
        title_pattern = re.compile(
            r'(\w+)\s+(\d+)-(\d+)[,\s]+(\d{4})',
            re.IGNORECASE
        )
        match = title_pattern.search(text)
    
    if not match:
        # Try variation without comma: "Month day1-day2 year"
        variation_pattern = re.compile(
            r'(\w+)\s+(\d+)-(\d+)\s+(\d{4})',
            re.IGNORECASE
        )
        match = variation_pattern.search(text)
    
    if match:
        month_str = match.group(1)
        day1 = int(match.group(2))
        day2 = int(match.group(3))
        year = int(match.group(4))
        
        # Parse month name to number
        month_names = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        month = month_names.get(month_str.lower())
        
        if month:
            try:
                start_date = datetime.date(year, month, day1)
                end_date = datetime.date(year, month, day2)
                return start_date, end_date
            except ValueError:
                # Invalid date (e.g., Feb 30)
                return None, None
    
    return None, None


def group_source_by(regex, source):
    """Sub-divide a list by a given regex pattern"""
    matches = partition_by(regex, source)
    
    if not matches:
        return []
    
    weekday_indexes = get_pairwise_series_indexes(matches)
    
    if len(weekday_indexes):
        # add in a pair to capture to the end of the source array
        weekday_indexes.append([weekday_indexes[-1][1], len(source)])
    
    return get_groups(weekday_indexes, source)


def group_post_content_by_day(post, ctx):
    """
    Split the post text on line break (only meaningful delineation)
    Group by day(session)
    Preserves the post date, slug, and title for downstream processing.
    """
    days = ['Monday', 'Tuesday', 'Wednesday',
            'Thursday', 'Friday', 'Saturday', 'Sunday']

    # make days into regex
    session_regex = re.compile(
        '|'.join([f"({x})" for x in days]), re.IGNORECASE)

    # Extract text from dictionary if needed (from StripPostHTML step)
    if isinstance(post, dict):
        post_text_str = post.get('text', '')
        post_date = post.get('post_date')
        slug = post.get('slug')
        title = post.get('title')
    else:
        post_text_str = str(post)
        post_date = None
        slug = None
        title = None

    post_text = post_text_str.split('\n')

    sessions_lists = [
        session  # session is already a list from get_groups
        for session in group_source_by(session_regex, post_text)
    ]

    result = {"sessions": sessions_lists}
    
    # Preserve post date, slug, and title for date calculations in downstream steps
    if post_date:
        result['post_date'] = post_date
    if slug:
        result['slug'] = slug
    if title:
        result['title'] = title

    return result


def segment_days(event, ctx):
    segment_regex = re.compile(
        '(Session)|(Suggested Warm-Up)|^[A-F].$', re.IGNORECASE)
    
    # Handle decorator-wrapped input if needed
    if isinstance(event, dict) and 'result' in event and isinstance(event['result'], dict):
        event_data = event['result']
    else:
        event_data = event
    
    segmented_sessions = [
        group_source_by(segment_regex, session)  # Already returns lists
        for session in event_data["sessions"]
    ]
    # add in an array for session key
    segmented_sessions = [
        [['session', x[0][0]], *x[1:]] if len(x) else [['session', 'rest day']]
        for x in segmented_sessions
    ]
    
    result = {
        "segmented_sessions": segmented_sessions
    }
    
    # Preserve post date, slug, and title for date calculations in downstream steps
    if 'post_date' in event_data:
        result['post_date'] = event_data['post_date']
    if 'slug' in event_data:
        result['slug'] = event_data['slug']
    if 'title' in event_data:
        result['title'] = event_data['title']
    
    return result


def sessions_to_json_records_by_day(event, ctx):
    # Handle decorator-wrapped input if needed
    if isinstance(event, dict) and 'result' in event and isinstance(event['result'], dict):
        event_data = event['result']
    else:
        event_data = event
    
    # Extract date range from slug or title (preferred method)
    slug = event_data.get('slug')
    title = event_data.get('title')
    date_range_start, date_range_end = extract_date_range_from_slug_or_title(
        slug=slug, title=title
    )
    
    # Determine the week start date
    if date_range_start:
        # Use the start date from slug/title as the first session date (Monday)
        # Calculate the Sunday before that Monday
        weekday = date_range_start.isoweekday()
        # If start date is Monday (1), go back 1 day to get Sunday
        # If start date is Tuesday (2), go back 2 days to get Sunday, etc.
        start = date_range_start - datetime.timedelta(days=weekday)
        theday = date_range_start
    elif 'post_date' in event_data:
        # Fallback to post date if slug/title date range not available
        post_date_str = event_data['post_date']
        theday = parse(post_date_str).date()
        weekday = theday.isoweekday()
        start = theday - datetime.timedelta(days=weekday)
    else:
        # Fallback to today for backward compatibility
        theday = datetime.date.today()
        weekday = theday.isoweekday()
        start = theday - datetime.timedelta(days=weekday)
    
    # build a simple range
    dates = [start + datetime.timedelta(days=d)
             for d in range(len(event_data['segmented_sessions'])+1)]

    sessions = [
        {
            session[0]:  ' '.join(session[1:])
            for idx, session in enumerate(event_data['segmented_sessions'][idx])
        } for idx, d in enumerate(dates[1:])
    ]

    # Use dates[1:] to match sessions (skip the Sunday before the week)
    session_records = [{"date": str(dates[idx + 1]), **session}
                       for idx, session in enumerate(sessions)]
    
    # Validate session dates against extracted date range if available
    if date_range_start and date_range_end:
        session_dates = [
            parse(record['date']).date() for record in session_records
        ]
        min_session_date = min(session_dates)
        max_session_date = max(session_dates)
        
        # Check if session dates overlap with the extracted date range
        # Allow some flexibility (e.g., if range is April 1-7, sessions might
        # be March 31 - April 6 due to week boundaries)
        date_range_overlaps = (
            min_session_date <= date_range_end and
            max_session_date >= date_range_start
        )
        
        if not date_range_overlaps:
            # Log warning but don't fail - dates might be off due to week
            # boundaries or the extracted range might be incorrect
            logger.warning(
                f"Session dates ({min_session_date} to {max_session_date}) "
                f"don't overlap with expected range from slug/title "
                f"({date_range_start} to {date_range_end})"
            )

    return session_records


def clean_sessions_df_records(event, ctx):
    """Clean and normalize session records using standard library"""
    column_mapping = {
        'Suggested Warm-Up': 'warm_up',
        'A.': 'segment_a',
        'B.': 'segment_b',
        'C.': 'segment_c',
        'D.': 'segment_d',
        'E.': 'segment_e'
    }
    
    # Handle decorator-wrapped input (if list was wrapped as {"result": [...]})
    if isinstance(event, dict) and 'result' in event and isinstance(event['result'], list):
        records = event['result']
    elif isinstance(event, list):
        records = event
    else:
        # Fallback: try to extract records from dict structure
        records = event.get('records', event.get('data', [event] if not isinstance(event, list) else event))
    
    # Define all expected fields that should always be present
    expected_fields = ['warm_up', 'segment_a', 'segment_b', 'segment_c', 'segment_d', 'segment_e']
    
    cleaned_records = []
    for record in records:
        # Rename columns
        cleaned_record = {}
        for old_key, value in record.items():
            new_key = column_mapping.get(old_key, old_key)
            # Drop 's' and 'r' columns
            if new_key not in ['s', 'r']:
                cleaned_record[new_key] = value
        
        # Parse and format date
        if 'date' in cleaned_record:
            date_obj = parse(cleaned_record['date'])
            cleaned_record['date'] = date_obj.strftime('%Y-%m-%d')
        
        # Fill None values
        if cleaned_record.get('session') is None:
            cleaned_record['session'] = 'Rest Day'
        
        # Ensure all expected fields are present (even if empty)
        for field in expected_fields:
            if field not in cleaned_record:
                cleaned_record[field] = ''
        
        # Fill all None values with empty string
        for key in cleaned_record:
            if cleaned_record[key] is None:
                cleaned_record[key] = ''
        
        cleaned_records.append(cleaned_record)
    
    return cleaned_records
