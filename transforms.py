import re
import pandas as pd
import numpy as np
from more_itertools import pairwise
import datetime


def partition_by(regex, source):
    """mask our series by a regex"""
    source = pd.Series(source, dtype=str)
    return source[source.str.contains(regex)]


def get_pairwise_series_indexes(masked_arr):
    """turn anlist of nums into a nested list of num pairs
    [0,1,2,3] =>[[0,1],[1,2],[2,3]]
    """
    out = []
    for current, nxt in pairwise(masked_arr):
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
    """sub-divide a list by a given regex"""
    weekdays = partition_by(regex, source)

    weekday_indexes = get_pairwise_series_indexes(weekdays.index)

    if len(weekday_indexes):
        # add in a pair to capture to the end of the source arr
        weekday_indexes.append([weekday_indexes[-1:][0][1], len(source.index)])

    # TODO: could possibly replace get_groups with fancy indexing ex source[weekday_indexes]
    return get_groups(weekday_indexes, source)


def group_post_content_by_day(post, ctx):
    """
      split the post text on line break (only meaningful dileanation)
      group by day(session)
    """
    days = ['Monday', 'Tuesday', 'Wednesday',
            'Thursday', 'Friday', 'Saturday', 'Sunday']

    # make days into regex
    session_regex = re.compile(
        '|'.join([f"({x})" for x in days]), re.IGNORECASE)

    post_text = pd.Series(post.split('\n'))

    sessions_lists = list(
        map(lambda session:
            session.reset_index(drop=True).tolist(),
            group_source_by(session_regex, post_text)
            )
    )

    return {"sessions": sessions_lists}


def segment_days(event, ctx):
    segment_regex = re.compile(
        '(Session)|(Suggested Warm-Up)|^[A-F].$', re.IGNORECASE)
    segmented_sessions = [
        [x.tolist() for x in group_source_by(segment_regex, pd.Series(session))] for session
        in event["sessions"]
    ]
    # add in a array for session key
    segmented_sessions = list(map(lambda x: [
                              ['session', x[0][0]], *x[1:]] if len(x) else ['session', 'rest day'], segmented_sessions))
    return {
        "segmented_sessions": segmented_sessions
    }


def sessions_to_json_records_by_day(event, ctx):
    theday = datetime.date.today()
    weekday = theday.isoweekday()
    # The start of the week
    start = theday - datetime.timedelta(days=weekday)
    # build a simple range
    dates = [start + datetime.timedelta(days=d)
             for d in range(len(event['segmented_sessions'])+1)]

    dates = {
        str(d): {
            session[0]:  ' '.join(session[1:])
            for idx, session in enumerate(event['segmented_sessions'][idx])
        } for idx, d in enumerate(dates[1:])
    }

    return dates
