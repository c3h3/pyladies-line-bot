import hashlib
import json
from linebot.exceptions import LineBotApiError
from datetime import datetime
import pandas as pd

def upsert_user_profile(api, app_id, db, user_id):
    try:
        data = api.get_profile(user_id).as_json_dict()
        # print(data["displayName"])
        # print(data["userId"])
        # print(data["pictureUrl"])
        # print(data["statusMessage"])
        data["appId"] = app_id
        hash_data = {}
        for k in ["appId", "userId"]:
            hash_data[k] = data[k]
        
        data.update(hash_data)
        data["_id"] = hashlib.sha256(json.dumps(hash_data,sort_keys=True).encode("utf-8")).hexdigest()

        if db.users.find({"_id": data["_id"]}).count() == 0:
            db.users.insert(data)
        else:
            db.users.update({"_id":data["_id"]}, data)

        print("CALL save_user_profile SUCCESSFULLY!")

    except LineBotApiError as e:
        print(e)

def add_friend(db, app_id, my_line_id, f_line_id):  # whoIAm->myFirend
    try:
        data = {}
        hash_data = {"appId": app_id, "userId": my_line_id}
        data["whoIAm"] = hashlib.sha256(json.dumps(hash_data, sort_keys=True).encode("utf-8")).hexdigest()
        hash_data = {"appId": app_id, "userId": f_line_id}
        data["myFirend"] = hashlib.sha256(json.dumps(hash_data, sort_keys=True).encode("utf-8")).hexdigest()
        data["_id"] = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
        
        data.update(hash_data)
        data["createAt"] = datetime.utcnow()
        db.friends.insert(data)
    except Exception as e:
        print(e)


def remove_friend(db, app_id, my_line_id, f_line_id):
    pass

def display_friend_list(friends_list):
    if friends_list:
        return_list = ["(%s) %s" % (i, v["displayName"]) for i, v in enumerate(friends_list, 1)]
        return "\n".join(return_list)


def get_friends_s(db, app_id, my_line_id):
    friends_list = list_friends_s(db, app_id, my_line_id)
    return display_friend_list(friends_list)


def get_friends_r(db, app_id, my_line_id):
    friends_list = list_friends_r(db, app_id, my_line_id)
    return display_friend_list(friends_list)


def list_friends_s(db, app_id, my_line_id):
    try:
        hash_data = {"appId": app_id, "userId": my_line_id}
        my_hash_id = hashlib.sha256(json.dumps(hash_data, sort_keys=True).encode("utf-8")).hexdigest()

        friends_df = pd.DataFrame(list(db.friends.find({"whoIAm": my_hash_id})))
        friends_list = list(db.users.find({"_id": {"$in": friends_df.myFirend.tolist()}}))
        return friends_list

    except Exception as e:
        print(e)


def list_friends_r(db, app_id, my_line_id):
    pass
