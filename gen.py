#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from mastodon import Mastodon
import argparse, json, re
import functions

parser = argparse.ArgumentParser(description='Generate and post a toot.')
parser.add_argument('-c', '--cfg', dest='cfg', default='config.json', nargs='?',
	help="Specify a custom location for config.json.")
parser.add_argument('-s', '--simulate', dest='simulate', action='store_true',
	help="Print the toot without actually posting it. Use this to make sure your bot's actually working.")

args = parser.parse_args()

cfg = json.load(open(args.cfg))

client = None

if not args.simulate:
	client = Mastodon(
	  client_id=cfg['client']['id'],
	  client_secret=cfg['client']['secret'],
	  access_token=cfg['secret'],
	  api_base_url=cfg['site'])

if __name__ == '__main__':
	toot = functions.make_toot(cfg)
	if cfg['strip_paired_punctuation']:
		toot = re.sub(r"[\[\]\(\)\{\}\"“”«»„]", "", toot)
	if not args.simulate:
		try:
			client.status_post(toot, visibility = 'unlisted', spoiler_text = cfg['cw'])
		except Exception as err:
			toot = "An error occurred while submitting the generated post. Contact lynnesbian@fedi.lynnesbian.space for assistance."
			client.status_post(toot, visibility = 'unlisted', spoiler_text = "Error!")
	try:
		print(toot)
	except UnicodeEncodeError:
		print(toot.encode("ascii", "ignore")) # encode as ASCII, dropping any non-ASCII characters
