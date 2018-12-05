#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from mastodon import Mastodon
import argparse
import sys
import traceback
import json
import create
from util import get_config

parser = argparse.ArgumentParser(description='Generate and post a toot.')
parser.add_argument('reply', metavar='reply', type=str, nargs='?',
                    help='ID of the status to reply to')
parser.add_argument('-s', '--simulate', dest='simulate', action='store_true',
                    help="Print the toot to stdout without posting it")

args = parser.parse_args()

cfg = get_config()

client = Mastodon(
    access_token=cfg['secret'],
    api_base_url=cfg['site'])

if __name__ == '__main__':
    toot = create.make_toot()
    if not args.simulate:
        try:
            if toot['media'] != None:
                mediaID = client.media_post(
                    toot['media'], description=toot['toot'])
                client.status_post(toot['toot'].replace("\n", " "),
                                   media_ids=[mediaID], visibility="unlisted", spoiler_text=cfg['cw'])
            else:
                client.status_post(
                    toot['toot'], visibility='unlisted', spoiler_text=cfg['cw'])
        except Exception as err:
            toot = {
                "toot":
                "Mistress @lynnesbian@fedi.lynnesbian.space, something has gone terribly"
                + " wrong! While attempting to post a toot, I received the following"
                + " error:\n" +
                    "\n".join(traceback.format_tb(sys.exc_info()[2]))
            }
            client.status_post(
                toot['toot'], visibility='unlisted', spoiler_text="Error!")
    print(toot['toot'])
