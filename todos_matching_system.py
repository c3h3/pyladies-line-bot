import hashlib, json, pytz, math
from datetime import datetime, timedelta
from linebot.models import TextSendMessage

import pandas as pd

from todos_friends import list_friends_s
from todos_google_calendar import create_event, get_freebusy_events


def invite_friend(db, app_id, my_line_id, invite_message):
    hash_data = {"appId": app_id, "userId": my_line_id}
    my_hash_id = hashlib.sha256(json.dumps(hash_data, sort_keys=True).encode("utf-8")).hexdigest()

    event_data = db.events.find_one({"userId": my_hash_id, "userStatus": "Inviting"})
    print("my_hash_id = %s" % my_hash_id)
    print("event_data = %s" % event_data)

    if event_data:
        event_data["userStatus"] = "Done"
        event_data["doneAt"] = datetime.utcnow()
        db.events.update({"_id": event_data["_id"]}, event_data)

    event_data = {
        "userId": my_hash_id,
        # User Status: Inviting -> Matching -> Choosing -> WaitForConfirm -> DONE
        "userStatus": "Inviting",
        "inviteMessage": invite_message,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    friends_list = list_friends_s(db, app_id, my_line_id)
    event_data["invitingFriends"] = friends_list
    db.events.insert(event_data)

    if friends_list:
        return_list = ["(%s) %s" % (i, v["displayName"]) for i, v in enumerate(friends_list, 1)]
        return_list = ["Please invite one of the following friends:"] + return_list
        return "\n".join(return_list)
    else:
        return "Please add friends before inviting"


def match(db, api, app_id, my_line_id, friend_num, time_range, time_delta="1.5H"):
    # TODO: parse argument
    now = datetime.utcnow()
    start_time = now.isoformat() + 'Z'  # 'Z' indicates UTC time
    if time_range[-1] == "D":
        end_time = now + timedelta(days=int(time_range[:-1]))
        end_time = end_time.isoformat() + 'Z'
    elif time_range[-1] == "W":
        end_time = now + timedelta(weeks=int(time_range[:-1]))
        end_time = end_time.isoformat() + 'Z'

    # TODO: get match data
    hash_data = {"appId": app_id, "userId": my_line_id}
    my_hash_id = hashlib.sha256(json.dumps(hash_data, sort_keys=True).encode("utf-8")).hexdigest()

    event_data = db.events.find_one({"userId": my_hash_id, "userStatus": "Inviting"})
    if not event_data:
        return "Please enter 'invite' before matching"

    # TODO: get my busy time and update to db
    my_busy_time = get_freebusy_events(db, app_id, my_line_id, start_time, end_time)["primary"]["busy"]
    event_data["my_busy_time"] = my_busy_time
    print("my_busy_time: {}".format(my_busy_time))

    # TODO: get friend's busy time and update to db
    friend_line_id = event_data["invitingFriends"][int(friend_num) - 1]["userId"]
    f_busy_time = get_freebusy_events(db, app_id, friend_line_id, start_time, end_time)["primary"]["busy"]
    event_data["f_busy_time"] = f_busy_time
    print("f_busy_time: {}".format(f_busy_time))

    db.events.update({"_id": event_data["_id"]}, event_data)

    # TODO: match common free time and update to db
    matched_free_time = match_free_time(time_range, time_delta, event_data)
    print("matched_free_time = {}".format(matched_free_time))

    # TODO: change data status
    event_data["userStatus"] = "Matching"
    event_data["doneAt"] = datetime.utcnow()
    event_data["f_line_id"] = friend_line_id
    event_data["matched_free_time"] = matched_free_time
    db.events.update({"_id": event_data["_id"]}, event_data)
    # print(event_data)
    # TODO: return to friend
    if match_free_time:
        return_list = ["(%s) %s - %s" % (i, v["start"].strftime("%Y/%m/%d %H:%M"), v["end"].strftime("%H:%M")) for i, v
                       in enumerate(matched_free_time, 1)]
        return_list = ["Please select one or multiple of the following items:"] + return_list
        print("return_list = {}".format(return_list[:5]))
        return return_list
        # return "OK"
    else:
        return "Sorry, you don't have matched time."


def match_free_time(time_range, time_delta, event_data):
    assert time_range.endswith("D")
    assert isinstance(int(time_range.replace("D", "")), int)
    assert time_delta.endswith("H")
    assert isinstance(float(time_delta.replace("H", "")), float)

    time_range_days = int(time_range.replace("D", ""))
    time_delta_hours = float(time_delta.replace("H", ""))

    assert (time_range_days>0) & (time_delta_hours>0), "time_range_days and time_delta_hours must > 0"

    min_time_delta = 0.5
    time_delta_hours = math.ceil(time_delta_hours / min_time_delta) * min_time_delta
    n_sessions = math.ceil(time_delta_hours / min_time_delta)

    utc_now = datetime.utcnow()
    start_time = datetime(utc_now.year, utc_now.month, utc_now.day, utc_now.hour + 1)
    end_time = start_time + timedelta(days=time_range_days)

    twtz = pytz.timezone("Asia/Taipei")
    start_time = pytz.utc.localize(start_time).astimezone(twtz)
    end_time = pytz.utc.localize(end_time).astimezone(twtz)

    time_intervals_df = separate_into_xxxhours_sessions_for_listing(start_time, end_time, min_time_delta)
    time_intervals_df["all"] = 1

    # return time_intervals_df

    busy_time = event_data["my_busy_time"]
    busy_time_df = pd.DataFrame(busy_time)

    if busy_time_df.shape[0] > 0:

        busy_time_df["end"] = busy_time_df.end.map(parse_utc_time_str_to_twtz_time)
        busy_time_df["start"] = busy_time_df.start.map(parse_utc_time_str_to_twtz_time)
        busy_time_df["time_delta_hours"] = min_time_delta
        busy_time_df["start"] = busy_time_df.start.map(
            lambda t: datetime(t.year, t.month, t.day, t.hour, 0 if t.minute < 30 else 30, 0, 0, t.tz))
        busy_time_df["end"] = busy_time_df.end.map(
            lambda t: datetime(t.year, t.month, t.day, t.hour + 1 if t.minute > 30 else t.hour,
                               0 if (t.minute > 30 or t.minute == 0) else 30, 0, 0, t.tz))

        my_time_df = pd.concat(
            list(
                map(lambda data: separate_into_xxxhours_sessions_for_listing(**data), busy_time_df.to_dict("records"))),
            0)
        my_time_df["my"] = 0
        # my_time_df = my_time_df.set_index(["start","end"])

    else:
        my_time_df = time_intervals_df.copy()
        my_time_df["my"] = 1
        my_time_df = my_time_df[["start", "end", "my"]]

    # return my_time_df

    busy_time = event_data["f_busy_time"]
    busy_time_df = pd.DataFrame(busy_time)
    # print("busy_time_df = {v}".format(v=busy_time_df))
    # print("busy_time_df.shape = {v}".format(v=busy_time_df.shape))

    if busy_time_df.shape[0] > 0:
        busy_time_df["end"] = busy_time_df.end.map(parse_utc_time_str_to_twtz_time)
        busy_time_df["start"] = busy_time_df.start.map(parse_utc_time_str_to_twtz_time)
        busy_time_df["time_delta_hours"] = min_time_delta

        busy_time_df["start"] = busy_time_df.start.map(
            lambda t: datetime(t.year, t.month, t.day, t.hour, 0 if t.minute < 30 else 30, 0, 0, t.tz))
        busy_time_df["end"] = busy_time_df.end.map(
            lambda t: datetime(t.year, t.month, t.day, t.hour + 1 if t.minute > 30 else t.hour,
                               0 if (t.minute > 30 or t.minute == 0) else 30, 0, 0, t.tz))

        f_time_df = pd.concat(
            list(
                map(lambda data: separate_into_xxxhours_sessions_for_listing(**data), busy_time_df.to_dict("records"))),
            0)
        f_time_df["f"] = 0
        # f_time_df = f_time_df.set_index(["start","end"])
    else:
        f_time_df = time_intervals_df.copy()
        f_time_df["f"] = 1
        f_time_df = f_time_df[["start", "end", "f"]]

    my_and_f_time_df = pd.merge(pd.merge(f_time_df, my_time_df, how="outer").fillna(1), time_intervals_df,
                                how="outer").fillna(1).sort(["start"], ascending=[1])

    # return my_and_f_time_df

    for i in range(n_sessions):
        my_and_f_time_df["my_{i}".format(i=i)] = my_and_f_time_df.my.shift(-i)
        my_and_f_time_df["f_{i}".format(i=i)] = my_and_f_time_df.f.shift(-i)

    my_cols = ["my_{i}".format(i=i) for i in range(n_sessions)]
    f_cols = ["f_{i}".format(i=i) for i in range(n_sessions)]

    my_and_f_time_df["my_cols_sum"] = my_and_f_time_df[my_cols].sum(1)
    my_and_f_time_df["f_cols_sum"] = my_and_f_time_df[f_cols].sum(1)

    df = my_and_f_time_df.set_index(["start", "end"])

    filtered_df = df[df[["my_cols_sum", "f_cols_sum"]].sum(1) == 2 * n_sessions].reset_index()[["start", "end"]]
    filtered_df["end"] = filtered_df.start.map(lambda t: t + timedelta(minutes=n_sessions * min_time_delta * 60))

    return filtered_df.to_dict("records")


def separate_into_xxxhours_sessions_for_listing(start, end, time_delta_hours, session_delta=30):
    time_intervals = []
    i = 0
    tmp_start_time = start
    tmp_end_time = start + timedelta(hours=time_delta_hours)

    while tmp_end_time <= end:
        time_intervals.append({"start": tmp_start_time, "end": tmp_end_time})
        tmp_start_time += timedelta(minutes=session_delta)
        tmp_end_time += timedelta(minutes=session_delta)
    time_intervals_df = pd.DataFrame(time_intervals)
    # time_intervals_df.columns = ["start","end"]

    return time_intervals_df



def choose(db, api, app_id, my_line_id, select_nums):
    hash_data = {"appId": app_id, "userId": my_line_id}
    my_hash_id = hashlib.sha256(json.dumps(hash_data, sort_keys=True).encode("utf-8")).hexdigest()

    event_data = db.events.find_one({"userId": my_hash_id, "userStatus": "Matching"})
    if not event_data:
        return "Please enter 'match' before choosing"

    # print(event_data)
    # parse select_nums
    choose_times = []
    for i in select_nums.split(","):
        try:
            if "-" in i:
                i = i.split("-")
                start_num = int(i[0])
                end_num = int(i[1])
                choose_times.extend(event_data["matched_free_time"][start_num - 1:end_num])
            else:
                i = int(i)
                choose_times.append(event_data["matched_free_time"][i - 1])
        except:
            continue

    if not choose_times:
        return "Please enter correct number(s)"

    # change data status
    event_data["userStatus"] = "WaitForConfirm"
    event_data["doneAt"] = datetime.utcnow()
    event_data["choose_times"] = choose_times
    db.events.update({"_id": event_data["_id"]}, event_data)

    # send msg to friend
    user_data = db.users.find_one({"userId": my_line_id})

    for i in choose_times:
        i["start"] = parse_utc_time_str_to_twtz_time(i["start"].isoformat() + "Z")
        i["end"] = parse_utc_time_str_to_twtz_time(i["end"].isoformat() + "Z")

    return_list = ["(%s) %s - %s" % (i, v["start"].strftime("%Y/%m/%d %H:%M"), v["end"].strftime("%H:%M")) for i, v in
                   enumerate(choose_times, 1)]
    return_list = ["{inv_msg} ... ".format(inv_msg=event_data["inviteMessage"])] + \
                  [user_data["displayName"] + " invites you."] + \
                  ["Please select one of the following items:"] + return_list
    api.push_message(event_data["f_line_id"], TextSendMessage(text="\n".join(return_list)))

    return "Please wait for friend's confirm"


def parse_utc_time_str_to_twtz_time(time_str):
    twtz = pytz.timezone("Asia/Taipei")
    t = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
    t = pytz.utc.localize(t)
    t = t.astimezone(twtz)
    return t


def confirm(db, api, app_id, my_line_id, select_num):
    hash_data = {"appId": app_id, "userId": my_line_id}
    my_hash_id = hashlib.sha256(json.dumps(hash_data,sort_keys=True).encode("utf-8")).hexdigest()

    event_datas = list(db.events.find({"invitingFriends._id": my_hash_id, "userStatus": "WaitForConfirm", "f_line_id": my_line_id}))
    if len(event_datas) == 0:
        return "Nothing to be confirmed"
    else:
        try:
            event_data = event_datas[0]
            item = event_datas[0]['choose_times'][int(select_num)-1]
            item["start"] = parse_utc_time_str_to_twtz_time(item["start"].isoformat()+"Z")
            item["end"] = parse_utc_time_str_to_twtz_time(item["end"].isoformat()+"Z")

            return_msg = "Booking: " + "%s - %s" % (item["start"].strftime("%Y/%m/%d %H:%M"), item["end"].strftime("%H:%M"))
            sender = db.users.find_one({"_id": event_datas[0]['userId']})["userId"]

            # TODO: booking
            create_event(db, app_id, my_line_id, item["start"], item["end"], event_data["inviteMessage"])
            create_event(db, app_id, sender, item["start"], item["end"], event_data["inviteMessage"])

            # Update sender event
            event_data = db.events.find({"userId": event_datas[0]['userId'], "userStatus": "WaitForConfirm"})[0]
            event_data["userStatus"] = "Done"
            event_data["doneAt"] = datetime.utcnow()
            event_data["confirm_time"] = item
            db.events.update({"_id": event_data["_id"]}, event_data)

            api.push_message(sender, TextSendMessage(text=return_msg))

            return return_msg
        except Exception as e:
            print(e)
            return "Choose the wrong item"


def help_message():
    help_message = """this is help message!"""
    return help_message