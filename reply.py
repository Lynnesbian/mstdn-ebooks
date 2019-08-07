#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import mastodon
import random, re, json, argparse
import functions
from bs4 import BeautifulSoup

parser = argparse.ArgumentParser(description='Reply service. Leave running in the background.')
parser.add_argument('-c', '--cfg', dest='cfg', default='config.json', nargs='?',
	help="Specify a custom location for config.json.")

args = parser.parse_args()

cfg = json.load(open(args.cfg, 'r'))

client = mastodon.Mastodon(
  client_id=cfg['client']['id'],
  client_secret=cfg['client']['secret'],
  access_token=cfg['secret'],
  api_base_url=cfg['site'])

def extract_toot(toot):
	text = functions.extract_toot(toot)
	text = re.sub(r"^@[^@]+@[^ ]+\s*", r"", text) #remove the initial mention
	text = text.lower() #treat text as lowercase for easier keyword matching (if this bot uses it)
	return text

class ReplyListener(mastodon.StreamListener):
	def on_notification(self, notification): #listen for notifications
		if notification['type'] == 'mention': #if we're mentioned:
			acct = "@" + notification['account']['acct'] #get the account's @
			post_id = notification['status']['id']

			# check if we've already been participating in this thread
			try:
				context = client.status_context(post_id)
			except:
				print("failed to fetch thread context")
				return
			me = client.account_verify_credentials()['id']
			posts = 0
			for post in context['ancestors']:
				if post['account']['id'] == me:
					pin = post["id"] #Only used if pin is called, but easier to call here
					posts += 1
				if posts >= cfg['max_thread_length']:
					# stop replying
					print("didn't reply (max_thread_length exceeded)")
					return

			mention = extract_toot(notification['status']['content'])
			if (mention == "pin") or (mention == "unpin"): #check for keywords
				print("Found pin/unpin")
				#get a list of people the bot is following
				validusers = client.account_following(me)
				for user in validusers:
					if user["id"] == notification["account"]["id"]: #user is #valid
						print("User is valid")
						visibility = notification['status']['visibility']
						if visibility == "public":
							visibility = "unlisted"
						if mention == "pin":
							print("pin received, pinning")
							client.status_pin(pin)
							client.status_post("Toot pinned!", post_id, visibility=visibility, spoiler_text = cfg['cw'])
						else:
							print("unpin received, unpinning")
							client.status_post("Toot unpinned!", post_id, visibility=visibility, spoiler_text = cfg['cw'])
							client.status_unpin(pin)
					else:
						print("User is not valid")
			else:
				toot = functions.make_toot(cfg) #generate a toot
				toot = acct + " " + toot #prepend the @
				print(acct + " says " + mention) #logging
				visibility = notification['status']['visibility']
				if visibility == "public":
					visibility = "unlisted"
				client.status_post(toot, post_id, visibility=visibility, spoiler_text = cfg['cw']) #send toost
				print("replied with " + toot) #logging

rl = ReplyListener()
client.stream_user(rl) #go!
