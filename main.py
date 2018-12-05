#!/usr/bin/env python3
# toot downloader version two!!
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from mastodon import Mastodon
from os import path
import os
import sqlite3
import signal
import sys
import json
import re
import requests
from util import get_config, extract_toot

cfg = get_config()

client = Mastodon(
    access_token=cfg['secret'],
    api_base_url=cfg['site'])

me = client.account_verify_credentials()
following = client.account_following(me.id)

db = sqlite3.connect("toots.db")
db.text_factory = str
c = db.cursor()
c.execute("CREATE TABLE IF NOT EXISTS `toots` (id INT NOT NULL UNIQUE PRIMARY KEY, userid INT NOT NULL, uri VARCHAR NOT NULL, content VARCHAR NOT NULL) WITHOUT ROWID")
db.commit()


def handleCtrlC(signal, frame):
    print("\nPREMATURE EVACUATION - Saving chunks")
    db.commit()
    sys.exit(1)


signal.signal(signal.SIGINT, handleCtrlC)


def get_toots_legacy(client, id):
    i = 0
    toots = client.account_statuses(id)
    while toots is not None and len(toots) > 0:
        for toot in toots:
            if toot.spoiler_text != "":
                continue
            if toot.reblog is not None:
                continue
            if toot.visibility not in ["public", "unlisted"]:
                continue
            t = extract_toot(toot.content)
            if t != None:
                yield {
                    "toot": t,
                    "id": toot.id,
                    "uri": toot.uri
                }
            toots = client.fetch_next(toots)
            i += 1
            if i % 20 == 0:
                print('.', end='', flush=True)


for f in following:
    last_toot = c.execute(
        "SELECT id FROM `toots` WHERE userid LIKE ? ORDER BY id DESC LIMIT 1", (f.id,)).fetchone()
    if last_toot != None:
        last_toot = last_toot[0]
    else:
        last_toot = 0
    print("Harvesting toots for user @{}, starting from {}".format(f.acct, last_toot))

    # find the user's activitypub outbox
    print("WebFingering...")
    instance = re.search(r"^.*@(.+)", f.acct)
    if instance == None:
        instance = re.search(r"https?:\/\/(.*)", cfg['site']).group(1)
    else:
        instance = instance.group(1)

    if instance == "bofa.lol":
        print("rest in piece bofa, skipping")
        continue

    # print("{} is on {}".format(f.acct, instance))
    try:
        r = requests.get(
            "https://{}/.well-known/host-meta".format(instance), timeout=10)
        uri = re.search(r'template="([^"]+)"', r.text).group(1)
        uri = uri.format(uri="{}@{}".format(f.username, instance))
        r = requests.get(
            uri, headers={"Accept": "application/json"}, timeout=10)
        j = r.json()
        if len(j['aliases']) == 1:  # TODO: this is a hack on top of a hack, fix it
            uri = j['aliases'][0]
        else:
            uri = j['aliases'][1]
        uri = "{}/outbox?page=true".format(uri)
        r = requests.get(uri, timeout=10)
        j = r.json()
    except Exception:
        print("oopsy woopsy!! we made a fucky wucky!!!\n(we're probably rate limited, please hang up and try again)")
        sys.exit(1)

    pleroma = False
    if 'first' in j and type(j['first']) != str:
        print("Pleroma instance detected")
        pleroma = True
        j = j['first']
    else:
        print("Mastodon instance detected")
        uri = "{}&min_id={}".format(uri, last_toot)
        r = requests.get(uri)
        j = r.json()

    print("Downloading and parsing toots", end='', flush=True)
    done = False
    try:
        while not done and len(j['orderedItems']) > 0:
            for oi in j['orderedItems']:
                if oi['type'] != "Create":
                    continue  # not a toost. fuck outta here

                # its a toost baby
                content = oi['object']['content']
                if oi['object']['summary'] != None:
                    # don't download CW'd toots
                    continue
                toot = extract_toot(content)
                # print(toot)
                try:
                    if pleroma:
                        if c.execute("SELECT COUNT(*) FROM toots WHERE id LIKE ?", (oi['object']['id'],)).fetchone()[0] > 0:
                            # we've caught up to the notices we've already downloaded, so we can stop now
                            done = True
                            break
                    pid = re.search(r"[^\/]+$", oi['object']['id']).group(0)
                    c.execute("REPLACE INTO toots (id, userid, uri, content) VALUES (?, ?, ?, ?)",
                              (pid,
                               f.id,
                               oi['object']['id'],
                               toot
                               )
                              )
                    pass
                except:
                    pass  # ignore any toots that don't successfully go into the DB
            # sys.exit(0)
            if not pleroma:
                r = requests.get(j['prev'], timeout=15)
            else:
                r = requests.get(j['next'], timeout=15)
            j = r.json()
            print('.', end='', flush=True)
        print(" Done!")
        db.commit()
    except:
        print("Encountered an error! Saving toots to database and continuing.")
        db.commit()
        # db.close()

print("Done!")

db.commit()
db.execute("VACUUM")  # compact db
db.commit()
db.close()
