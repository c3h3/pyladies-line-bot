from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

# try:
#     import argparse
#     flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
# except ImportError:
#     flags = None
flags = None

import os, urllib, hashlib, json, httplib2

from datetime import datetime, timedelta
from linebot.exceptions import LineBotApiError

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/calendar'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Google Calendar API Python Quickstart'

def store_credential(code, user_id):
    flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
    oauth_callback = client.OOB_CALLBACK_URN
    flow.redirect_uri = oauth_callback
    authorize_url = flow.step1_get_authorize_url()
    cre = flow.step2_exchange(code)

    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials_{}'.format(user_id))
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'calendar-python-quickstart.json')
    store = Storage(credential_path)
    #credentials = store.get()
    store.put(cre)
    cre.set_store(store)
    return cre, credential_path

def get_google_calendar_oauth2_url():
    client_id = "651212683615-s5tkgh08oln2chsu2jtoa5mpac8ub7nu.apps.googleusercontent.com"
    data = {"redirect_uri":"urn:ietf:wg:oauth:2.0:oob",
            "client_id": client_id,
            "scope":"https://www.googleapis.com/auth/calendar",
            "response_type":"code",
            "access_type":"offline"}
    url = "https://accounts.google.com/o/oauth2/auth?"+urllib.parse.urlencode(data)
    return url

def get_credentials(user_id, app_id, db):
    hash_data = {"appId": app_id, "userId": user_id}
    user_db_id = hashlib.sha256(json.dumps(hash_data, sort_keys=True).encode("utf-8")).hexdigest()
    user_data = db.users.find_one({"_id":user_db_id})

    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials_{}'.format(user_id))
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)

    credential_path = user_data["credential_path"]
    with open(credential_path, "w") as wf:
        wf.write(json.dumps(user_data["credential_data"]))

    store = Storage(credential_path)
    credentials = store.get()

    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)

    return credentials


def get_events_3(db, app_id, user_id, timeMin=None, timeMax=None):
    credentials = get_credentials(user_id, app_id, db)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    if not timeMin:
        timeMin = datetime.utcnow().isoformat() + 'Z'

    if not timeMax:
        timeMax = (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'

    eventsResult = service.freebusy().query(
        body={"items": [{'id': 'primary'}], "timeMin": timeMin, "timeMax": timeMax}).execute()
    events = eventsResult.get('calendars', [])

    if not events:
        return 'No upcoming events found.'

    return events

def create_event(db, app_id, user_id, start, end, invite_message):
    credentials  = get_credentials(user_id, app_id, db)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    body = {
        "summary": invite_message,
        "start": {
            "timeZone": "Asia/Taipei",
            "dateTime": start.isoformat()
        },
        "end": {
            "timeZone": "Asia/Taipei",
            "dateTime": end.isoformat()
        }
    }

    eventsResult = service.events().insert(
        calendarId='primary', body=body
        ).execute()
    print(eventsResult)

def save_user_profile(api, app_id, db, user_id, cre, credential_path):
    try:
        data = api.get_profile(user_id).as_json_dict()
        print(data["displayName"])
        print(data["userId"])
        print(data["pictureUrl"])
        print(data["statusMessage"])
        data["appId"] = app_id
        hash_data = {}
        for k in ["appId", "userId"]:
            hash_data[k] = data[k]

        data["_id"] = hashlib.sha256(json.dumps(hash_data,sort_keys=True).encode("utf-8")).hexdigest()
        data["gcal_token"] = cre.access_token


        with open(credential_path, "r") as rf:
            data["credential_data"] = json.loads(rf.read())
        data["credential_path"] = credential_path

        if db.users.find({"_id": data["_id"]}).count() == 0:
            db.users.insert(data)
        else:
            db.users.update({"_id":data["_id"]}, data)

        print("CALL save_user_profile SUCCESSFULLY!")

    except LineBotApiError as e:
        print(e)


def get_at_most_5_events_in_next_7_days(user_id, app_id, db):
    credentials = get_credentials(user_id, app_id, db)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    # TODO: use service object to get 5 events in the next 7 days
    # OUTPUT FORMAT:
    #     (1) 2017-04-15~2017-04-15: miniBezos 1.0.0v Launch Day!
    #     (2) 2017-04-15T22:00:00+08:00~2017-04-15T23:00:00+08:00: meet with Chia-Chi & Ann: 了解開課流程SOP
    #     (3) 2017-04-16T11:00:00+08:00~2017-04-16T13:00:00+08:00: 推進毛毛霸新功能
    #     (4) 2017-04-16T22:30:00+08:00~2017-04-16T23:30:00+08:00: DL 專欄小編會議
    #     (5) 2017-04-17T19:30:00+08:00~2017-04-17T20:30:00+08:00: MLDM Monday

