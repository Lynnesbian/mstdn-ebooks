#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import markovify
from bs4 import BeautifulSoup
from random import randint
import re, multiprocessing, sqlite3, shutil, os, html

def make_sentence(output, cfg):
	class nlt_fixed(markovify.NewlineText): #modified version of NewlineText that never rejects sentences
		def test_sentence_input(self, sentence):
			return True #all sentences are valid <3

	shutil.copyfile("toots.db", "toots-copy.db") #create a copy of the database because reply.py will be using the main one
	db = sqlite3.connect("toots-copy.db")
	db.text_factory = str
	c = db.cursor()
	if cfg['learn_from_cw']:
		toots = c.execute("SELECT content FROM `toots` ORDER BY RANDOM() LIMIT 10000").fetchall()
	else:
		toots = c.execute("SELECT content FROM `toots` WHERE cw = 0 ORDER BY RANDOM() LIMIT 10000").fetchall()

	if len(toots) == 0:
		output.send("Database is empty! Try running main.py.")
		return

	nlt = markovify.NewlineText if cfg['overlap_ratio_enabled'] else nlt_fixed

	model = nlt(
		"\n".join([toot[0] for toot in toots])
	)

	db.close()
	os.remove("toots-copy.db")

	toots_str = None

	if cfg['limit_length']:
		sentence_len = randint(cfg['length_lower_limit'], cfg['length_upper_limit'])

	sentence = None
	tries = 0
	while sentence is None and tries < 10:
		sentence = model.make_short_sentence(
			max_chars=500,
			tries=10000,
			max_overlap_ratio=cfg['overlap_ratio'] if cfg['overlap_ratio_enabled'] else 0.7,
			max_words=sentence_len if cfg['limit_length'] else None
			)
		tries = tries + 1

	# optionally remove mentions
	if cfg['mention_handling'] == 1:
		sentence = re.sub(r"^\S*@\u200B\S*\s?", "", sentence)
	elif cfg['mention_handling'] == 0:
		sentence = re.sub(r"\S*@\u200B\S*\s?", "", sentence)

	output.send(sentence)

def make_toot(cfg):
	toot = None
	pin, pout = multiprocessing.Pipe(False)
	p = multiprocessing.Process(target = make_sentence, args = [pout, cfg])
	p.start()
	p.join(5) #wait 5 seconds to get something
	if p.is_alive(): #if it's still trying to make a toot after 5 seconds
		p.terminate()
		p.join()
	else:
		toot = pin.recv()

	if toot == None:
		toot = "Toot generation failed! Contact Lynne (lynnesbian@fedi.lynnesbian.space) for assistance."
	return toot

def extract_toot(toot):
	toot = html.unescape(toot) # convert HTML escape codes to text
	soup = BeautifulSoup(toot, "html.parser")
	for lb in soup.select("br"): # replace <br> with linebreak
		lb.name = "\n"

	for p in soup.select("p"): # ditto for <p>
		p.name = "\n"

	for ht in soup.select("a.hashtag"): # convert hashtags from links to text
		ht.unwrap()

	for link in soup.select("a"): #ocnvert <a href='https://example.com>example.com</a> to just https://example.com
		if 'href' in link:
			# apparently not all a tags have a href, which is understandable if you're doing normal web stuff, but on a social media platform??
			link.replace_with(link["href"])

	text = soup.get_text()
	text = re.sub(r"https://([^/]+)/(@[^\s]+)", r"\2@\1", text) # put mastodon-style mentions back in
	text = re.sub(r"https://([^/]+)/users/([^\s/]+)", r"@\2@\1", text) # put pleroma-style mentions back in
	text = text.rstrip("\n") # remove trailing newline(s)
	return text
