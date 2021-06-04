#!/usr/bin/env python3
# toot downloader version two!!
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from mastodon import Mastodon, MastodonUnauthorizedError
from os import path
from bs4 import BeautifulSoup
import os, sqlite3, signal, sys, json, re, shutil, argparse
import requests
import functions

parser = argparse.ArgumentParser(description='Log in and download posts.')
parser.add_argument('-c', '--cfg', dest='cfg', default='config.json', nargs='?',
	help="Specify a custom location for config.json.")

args = parser.parse_args()

scopes = ["read:statuses", "read:accounts", "read:follows", "write:statuses", "read:notifications", "write:accounts"]
#cfg defaults

cfg = {
	"site": "https://botsin.space",
	"cw": None,
	"instance_blacklist": ["bofa.lol", "witches.town", "knzk.me"], # rest in piece
	"learn_from_cw": False,
	"mention_handling": 1,
	"max_thread_length": 15,
	"strip_paired_punctuation": False
}

try:
	cfg.update(json.load(open(args.cfg, 'r')))
except FileNotFoundError:
	open(args.cfg, "w").write("{}")

print("Using {} as configuration file".format(args.cfg))

if not cfg['site'].startswith("https://") and not cfg['site'].startswith("http://"):
	print("Site must begin with 'https://' or 'http://'. Value '{}' is invalid - try 'https://{}' instead.".format(cfg['site']))
	sys.exit(1)

if "client" not in cfg:
	print("No application info -- registering application with {}".format(cfg['site']))
	client_id, client_secret = Mastodon.create_app("mstdn-ebooks",
		api_base_url=cfg['site'],
		scopes=scopes,
		website="https://github.com/Lynnesbian/mstdn-ebooks")

	cfg['client'] = {
		"id": client_id,
		"secret": client_secret
	}

if "secret" not in cfg:
	print("No user credentials -- logging in to {}".format(cfg['site']))
	client = Mastodon(client_id = cfg['client']['id'],
		client_secret = cfg['client']['secret'],
		api_base_url=cfg['site'])

	print("Open this URL and authenticate to give mstdn-ebooks access to your bot's account: {}".format(client.auth_request_url(scopes=scopes)))
	cfg['secret'] = client.log_in(code=input("Secret: "), scopes=scopes)

json.dump(cfg, open(args.cfg, "w+"))

def extract_toot(toot):
	toot = functions.extract_toot(toot)
	toot = toot.replace("@", "@\u200B") #put a zws between @ and username to avoid mentioning
	return(toot)

client = Mastodon(
	client_id=cfg['client']['id'],
	client_secret = cfg['client']['secret'],
	access_token=cfg['secret'],
	api_base_url=cfg['site'])

try:
	me = client.account_verify_credentials()
except MastodonUnauthorizedError:
	print("The provided access token in {} is invalid. Please delete {} and run main.py again.".format(args.cfg, args.cfg))
	sys.exit(1)

following = client.account_following(me.id)

db = sqlite3.connect("toots.db")
db.text_factory=str
c = db.cursor()
c.execute("CREATE TABLE IF NOT EXISTS `toots` (sortid INTEGER UNIQUE PRIMARY KEY AUTOINCREMENT, id VARCHAR NOT NULL, cw INT NOT NULL DEFAULT 0, userid VARCHAR NOT NULL, uri VARCHAR NOT NULL, content VARCHAR NOT NULL)")
c.execute("CREATE TRIGGER IF NOT EXISTS `dedup` AFTER INSERT ON toots FOR EACH ROW BEGIN DELETE FROM toots WHERE rowid NOT IN (SELECT MIN(sortid) FROM toots GROUP BY uri ); END; ")
db.commit()

tableinfo = c.execute("PRAGMA table_info(`toots`)").fetchall()
found = False
columns = []
for entry in tableinfo:
	if entry[1] == "sortid":
		found = True
		break
	columns.append(entry[1])

if not found:
	print("Migrating to new database format. Please wait...")
	print("WARNING: If any of the accounts your bot is following are Pleroma users, please delete toots.db and run main.py again to create it anew.")
	try:
		c.execute("DROP TABLE `toots_temp`")
	except:
		pass

	c.execute("CREATE TABLE `toots_temp` (sortid INTEGER UNIQUE PRIMARY KEY AUTOINCREMENT, id VARCHAR NOT NULL, cw INT NOT NULL DEFAULT 0, userid VARCHAR NOT NULL, uri VARCHAR NOT NULL, content VARCHAR NOT NULL)")
	for f in following:
		user_toots = c.execute("SELECT * FROM `toots` WHERE userid LIKE ? ORDER BY id", (f.id,)).fetchall()
		if user_toots == None:
			continue

		if columns[-1] == "cw":
			for toot in user_toots:
				c.execute("INSERT INTO `toots_temp` (id, userid, uri, content, cw) VALUES (?, ?, ?, ?, ?)", toot)
		else:
			for toot in user_toots:
				c.execute("INSERT INTO `toots_temp` (id, cw, userid, uri, content) VALUES (?, ?, ?, ?, ?)", toot)

	c.execute("DROP TABLE `toots`")
	c.execute("ALTER TABLE `toots_temp` RENAME TO `toots`")
	c.execute("CREATE TRIGGER IF NOT EXISTS `dedup` AFTER INSERT ON toots FOR EACH ROW BEGIN DELETE FROM toots WHERE rowid NOT IN (SELECT MIN(sortid) FROM toots GROUP BY uri ); END; ")

db.commit()

def handleCtrlC(signal, frame):
	print("\nPREMATURE EVACUATION - Saving chunks")
	db.commit()
	sys.exit(1)

signal.signal(signal.SIGINT, handleCtrlC)

patterns = {
	"handle": re.compile(r"^.*@(.+)"),
	"url": re.compile(r"https?:\/\/(.*)"),
	"uri": re.compile(r'template="([^"]+)"'),
	"pid": re.compile(r"[^\/]+$"),
}


def insert_toot(oii, acc, post, cursor): # extracted to prevent duplication
	pid = patterns["pid"].search(oii['object']['id']).group(0)
	cursor.execute("REPLACE INTO toots (id, cw, userid, uri, content) VALUES (?, ?, ?, ?, ?)", (
		pid,
		1 if (oii['object']['summary'] != None and oii['object']['summary'] != "") else 0,
		acc.id,
		oii['object']['id'],
		post
	))


for f in following:
	last_toot = c.execute("SELECT id FROM `toots` WHERE userid LIKE ? ORDER BY sortid DESC LIMIT 1", (f.id,)).fetchone()
	if last_toot != None:
		last_toot = last_toot[0]
	else:
		last_toot = 0
	print("Downloading posts for user @{}, starting from {}".format(f.acct, last_toot))

	#find the user's activitypub outbox
	print("WebFingering...")
	instance = patterns["handle"].search(f.acct)
	if instance == None:
		instance = patterns["url"].search(cfg['site']).group(1)
	else:
		instance = instance.group(1)

	if instance in cfg['instance_blacklist']:
		print("skipping blacklisted instance: {}".format(instance))
		continue

	try:
		# 1. download host-meta to find webfinger URL
		r = requests.get("https://{}/.well-known/host-meta".format(instance), timeout=10)
		# 2. use webfinger to find user's info page
		uri = patterns["uri"].search(r.text).group(1)
		uri = uri.format(uri = "{}@{}".format(f.username, instance))
		r = requests.get(uri, headers={"Accept": "application/json"}, timeout=10)
		j = r.json()
		found = False
		for link in j['links']:
			if link['rel'] == 'self':
				#this is a link formatted like "https://instan.ce/users/username", which is what we need
				uri = link['href']
				found = True
				break
		if not found:
			print("Couldn't find a valid ActivityPub outbox URL.")

		# 3. download first page of outbox
		uri = "{}/outbox?page=true".format(uri)
		r = requests.get(uri, timeout=15)
		j = r.json()
	except:
		print("oopsy woopsy!! we made a fucky wucky!!!\n(we're probably rate limited, please hang up and try again)")
		sys.exit(1)

	pleroma = False
	if 'next' not in j and 'prev' not in j:
		# there's only one page of results, don't bother doing anything special
		pass
	elif 'prev' not in j:
		print("Using Pleroma compatibility mode")
		pleroma = True
		if 'first' in j:
			# apparently there used to be a 'first' field in pleroma's outbox output, but it's not there any more
			# i'll keep this for backwards compatibility with older pleroma instances
			# it was removed in pleroma 1.0.7 - https://git.pleroma.social/pleroma/pleroma/-/blob/841e4e4d835b8d1cecb33102356ca045571ef1fc/CHANGELOG.md#107-2019-09-26
			j = j['first']
	else:
		print("Using standard mode")
		uri = "{}&min_id={}".format(uri, last_toot)
		r = requests.get(uri)
		j = r.json()

	print("Downloading and saving posts", end='', flush=True)
	done = False
	try:
		while not done and len(j['orderedItems']) > 0:
			for oi in j['orderedItems']:
				if oi['type'] != "Create":
					continue #this isn't a toot/post/status/whatever, it's a boost or a follow or some other activitypub thing. ignore

				# its a toost baby
				content = oi['object']['content']
				toot = extract_toot(content)
				# print(toot)
				try:
					if pleroma:
						if c.execute("SELECT COUNT(*) FROM toots WHERE uri LIKE ?", (oi['object']['id'],)).fetchone()[0] > 0:
							#we've caught up to the notices we've already downloaded, so we can stop now
							#you might be wondering, "lynne, what if the instance ratelimits you after 40 posts, and they've made 60 since main.py was last run? wouldn't the bot miss 20 posts and never be able to see them?" to which i reply, "i know but i don't know how to fix it"
							done = True
							continue
					if 'lang' in cfg:
						try:
							if oi['object']['contentMap'][cfg['lang']]: # filter for language
								insert_toot(oi, f, toot, c)
						except KeyError:
							#JSON doesn't have contentMap, just insert the toot irregardlessly
							insert_toot(oi, f, toot, c)
					else:
						insert_toot(oi, f, toot, c)
					pass
				except:
					pass #ignore any toots that don't successfully go into the DB

			# get the next/previous page
			try:
				if not pleroma:
					r = requests.get(j['prev'], timeout=15)
				else:
					r = requests.get(j['next'], timeout=15)
			except requests.Timeout:
				print("HTTP timeout, site did not respond within 15 seconds")
			except KeyError:
				print("Couldn't get next page - we've probably got all the posts")
			except:
				print("An error occurred while trying to obtain more posts.")

			j = r.json()
			print('.', end='', flush=True)
		print(" Done!")
		db.commit()
	except requests.HTTPError as e:
		if e.response.status_code == 429:
			print("Rate limit exceeded. This means we're downloading too many posts in quick succession. Saving toots to database and moving to next followed account.")
			db.commit()
		else:
			# TODO: remove duplicate code
			print("Encountered an error! Saving posts to database and moving to next followed account.")
			db.commit()
	except:
		print("Encountered an error! Saving posts to database and moving to next followed account.")
		db.commit()

print("Done!")

db.commit()
db.execute("VACUUM") #compact db
db.commit()
db.close()
