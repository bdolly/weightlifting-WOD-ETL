import re
from more_itertools import pairwise
import datetime
from dateutil.parser import parse


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
    """
    days = ['Monday', 'Tuesday', 'Wednesday',
            'Thursday', 'Friday', 'Saturday', 'Sunday']

    # make days into regex
    session_regex = re.compile(
        '|'.join([f"({x})" for x in days]), re.IGNORECASE)

    # Extract text from dictionary if needed (from StripPostHTML step)
    if isinstance(post, dict):
        post_text_str = post.get('text', '')
    else:
        post_text_str = str(post)

    post_text = post_text_str.split('\n')

    sessions_lists = [
        session  # session is already a list from get_groups
        for session in group_source_by(session_regex, post_text)
    ]

    return {"sessions": sessions_lists}


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
    return {
        "segmented_sessions": segmented_sessions
    }


def sessions_to_json_records_by_day(event, ctx):
    # Handle decorator-wrapped input if needed
    if isinstance(event, dict) and 'result' in event and isinstance(event['result'], dict):
        event_data = event['result']
    else:
        event_data = event
    
    theday = datetime.date.today()
    weekday = theday.isoweekday()
    # The start of the week
    start = theday - datetime.timedelta(days=weekday)
    # build a simple range
    dates = [start + datetime.timedelta(days=d)
             for d in range(len(event_data['segmented_sessions'])+1)]

    # dates = {
    #     str(d): {
    #         session[0]:  ' '.join(session[1:])
    #         for idx, session in enumerate(event['segmented_sessions'][idx])
    #     } for idx, d in enumerate(dates[1:])
    # }

    sessions = [
        {
            session[0]:  ' '.join(session[1:])
            for idx, session in enumerate(event_data['segmented_sessions'][idx])
        } for idx, d in enumerate(dates[1:])
    ]

    session_records = [{"date": str(dates[idx]), **session}
                       for idx, session in enumerate(sessions)]

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
        
        # Fill all None values with empty string
        for key in cleaned_record:
            if cleaned_record[key] is None:
                cleaned_record[key] = ''
        
        cleaned_records.append(cleaned_record)
    
    return cleaned_records
