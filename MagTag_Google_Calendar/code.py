# SPDX-FileCopyrightText: 2021 Brent Rubell, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
import time
import ssl
import board
import rtc
import wifi
import socketpool
import adafruit_requests as requests
from adafruit_oauth2 import OAuth2
from adafruit_display_shapes.line import Line
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label
from adafruit_magtag.magtag import MagTag

# Calendar ID
CALENDAR_ID = "YOUR_CALENDAR_ID"

# Maximum amount of events to display
MAX_EVENTS = 3

# Amount of time to wait between refreshing the calendar, in minutes
REFRESH_TIME = 15

# Dict. of month names for pretty-printing the header
MONTHS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}
# Dict. of day names for pretty-printing the header
WEEKDAYS = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

# Add a secrets.py to your filesystem that has a dictionary called secrets with "ssid" and
# "password" keys with your WiFi credentials. DO NOT share that file or commit it into Git or other
# source control.
# pylint: disable=no-name-in-module,wrong-import-order
try:
    from secrets import secrets
except ImportError:
    print("Credentials and tokens are kept in secrets.py, please add them there!")
    raise

print("Connecting to %s" % secrets["ssid"])
wifi.radio.connect(secrets["ssid"], secrets["password"])
print("Connected to %s!" % secrets["ssid"])

pool = socketpool.SocketPool(wifi.radio)
requests = requests.Session(pool, ssl.create_default_context())

# Initialize an OAuth2 object with GCal API scope
scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
google_auth = OAuth2(
    requests,
    secrets["google_client_id"],
    secrets["google_client_secret"],
    scopes,
    secrets["google_access_token"],
    secrets["google_refresh_token"],
)


def get_current_time(time_max=False):
    """Gets local time from Adafruit IO and converts to RFC3339 timestamp."""
    # Get local time from Adafruit IO
    magtag.get_local_time(secrets["timezone"])
    # Format as RFC339 timestamp
    cur_time = r.datetime
    if time_max:  # maximum time to fetch events is midnight (4:59:59UTC)
        cur_time_max = time.struct_time(
            cur_time[0],
            cur_time[1],
            cur_time[2] + 1,
            4,
            59,
            59,
            cur_time[6],
            cur_time[7],
            cur_time[8],
        )
        cur_time = cur_time_max
    cur_time = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}{:s}".format(
        cur_time[0],
        cur_time[1],
        cur_time[2],
        cur_time[3],
        cur_time[4],
        cur_time[5],
        "Z",
    )
    return cur_time


def get_calendar_events(calendar_id, max_events, time_min):
    """Returns events on a specified calendar.
    Response is a list of events ordered by their start date/time in ascending order.
    """
    time_max = get_current_time(time_max=True)
    print("Fetching calendar events from {0} to {1}".format(time_min, time_max))

    headers = {
        "Authorization": "Bearer " + google_auth.access_token,
        "Accept": "application/json",
        "Content-Length": "0",
    }
    url = (
        "https://www.googleapis.com/calendar/v3/calendars/{0}"
        "/events?maxResults={1}&timeMin={2}&timeMax={3}&orderBy=startTime"
        "&singleEvents=true".format(calendar_id, max_events, time_min, time_max)
    )
    resp = requests.get(url, headers=headers)
    resp_json = resp.json()
    if "error" in resp_json:
        raise RuntimeError("Error:", resp_json)
    resp.close()
    # parse the 'items' array so we can iterate over it easier
    items = []
    resp_items = resp_json["items"]
    if not resp_items:
        print("No events scheduled for today!")
    for event in range(0, len(resp_items)):
        items.append(resp_items[event])
    return items


def format_datetime(datetime, pretty_date=False):
    """Formats ISO-formatted datetime returned by Google Calendar API into
    a struct_time.
    :param str datetime: Datetime string returned by Google Calendar API
    :return: struct_time

    """
    times = datetime.split("T")
    the_date = times[0]
    the_time = times[1]
    year, month, mday = [int(x) for x in the_date.split("-")]
    the_time = the_time.split("-")[0]
    if "Z" in the_time:
        the_time = the_time.split("Z")[0]
    hours, minutes, _ = [int(x) for x in the_time.split(":")]
    am_pm = "am"
    if hours >= 12:
        am_pm = "pm"
        # convert to 12hr time
        if not hours == 12:
            hours -= 12
    # via https://github.com/micropython/micropython/issues/3087
    formatted_time = "{:01d}:{:02d}{:s}".format(hours, minutes, am_pm)
    if pretty_date:  # return a nice date for header label
        formatted_date = "{} {}.{:02d}, {:04d} ".format(
            WEEKDAYS[r.datetime[6]], MONTHS[month], mday, year
        )
        return formatted_date
    # Event occurs today, return the time only
    return formatted_time


def display_calendar_events(resp_events):
    # Display all calendar events
    for event_idx in range(len(resp_events)):
        event = resp_events[event_idx]
        # wrap event name around second line if necessary
        event_name = magtag.wrap_nicely(event["summary"], 25)
        event_name = "\n".join(event_name[0:2])  # only wrap 2 lines, truncate third..
        event_start = event["start"]["dateTime"]
        print("-" * 40)
        print("Event Description: ", event_name)
        print("Event Time:", format_datetime(event_start))
        print("-" * 40)
        # Generate labels holding event info
        label_event_time = label.Label(
            font_event,
            x=7,
            y=40 + (event_idx * 35),
            color=0x000000,
            text=format_datetime(event_start),
        )
        magtag.splash.append(label_event_time)

        label_event_desc = label.Label(
            font_event,
            x=88,
            y=40 + (event_idx * 35),
            color=0x000000,
            text=event_name,
            line_spacing=0.65,
        )
        magtag.splash.append(label_event_desc)


# Create a new MagTag object
magtag = MagTag()
r = rtc.RTC()

# DisplayIO Setup
magtag.set_background(0xFFFFFF)

# Add the header
line_header = Line(0, 30, 320, 30, color=0x000000)
magtag.splash.append(line_header)

font_h1 = bitmap_font.load_font("fonts/Arial-18.pcf")
label_header = label.Label(font_h1, x=5, y=15, color=0x000000)
magtag.splash.append(label_header)

# Set up calendar event fonts
font_event = bitmap_font.load_font("fonts/Arial-12.pcf")

if not google_auth.refresh_access_token():
    raise RuntimeError("Unable to refresh access token - has the token been revoked?")
access_token_obtained = int(time.monotonic())

while True:
    # check if we need to refresh token
    if (
        int(time.monotonic()) - access_token_obtained
        >= google_auth.access_token_expiration
    ):
        print("Access token expired, refreshing...")
        if not google_auth.refresh_access_token():
            raise RuntimeError(
                "Unable to refresh access token - has the token been revoked?"
            )
        access_token_obtained = int(time.monotonic())

    # fetch calendar events!
    print("fetching local time...")
    now = get_current_time()

    # setup header label
    label_header.text = format_datetime(now, pretty_date=True)

    print("fetching calendar events...")
    events = get_calendar_events(CALENDAR_ID, MAX_EVENTS, now)

    print("displaying events")
    display_calendar_events(events)

    board.DISPLAY.show(magtag.splash)
    board.DISPLAY.refresh()

    print("Sleeping for %d minutes" % REFRESH_TIME)
    magtag.exit_and_deep_sleep(REFRESH_TIME * 60)
