"""
Various utility tools
"""

import json
import os
from mastodon import Mastodon
from bs4 import BeautifulSoup


def get_config():
    access_token = os.getenv("MASTODON_API_TOKEN")
    api_base_url = os.getenv("MASTODON_API_BASE_URL")

    if (access_token and api_base_url):  #  Heroku mode; use preset token
        return {
            "secret": access_token,
            "site": api_base_url,
            "is_heroku": True
        }
    else:  #  Local mode; do OAuth login dance
        scopes = ["read:statuses", "read:accounts",
                  "read:follows", "write:statuses", "read:notifications"]
        cfg = json.load(open('config.json', 'r'))

        if os.path.exists("clientcred.secret"):
            print("Upgrading to new storage method")
            cc = open("clientcred.secret").read().split("\n")
            cfg['client'] = {
                "id": cc[0],
                "secret": cc[1]
            }
            cfg['secret'] = open("usercred.secret").read().rstrip("\n")
            os.remove("clientcred.secret")
            os.remove("usercred.secret")

        if "client" not in cfg:
            print("No client credentials, registering application")
            client_id, client_secret = Mastodon.create_app("mstdn-ebooks",
                                                           api_base_url=cfg['site'],
                                                           scopes=scopes,
                                                           website="https://github.com/Lynnesbian/mstdn-ebooks")

            cfg['client'] = {
                "id": client_id,
                "secret": client_secret
            }

        if "secret" not in cfg:
            print("No user credentials, logging in")
            client = Mastodon(client_id=cfg['client']['id'],
                              client_secret=cfg['client']['secret'],
                              api_base_url=cfg['site'])

            print("Open this URL: {}".format(
                client.auth_request_url(scopes=scopes)))
            cfg['secret'] = client.log_in(
                code=input("Secret: "), scopes=scopes)

        json.dump(cfg, open("config.json", "w+"))


def extract_toot(toot):
    toot = toot.replace("&apos;", "'")
    toot = toot.replace("&quot;", '"')
    soup = BeautifulSoup(toot, "html.parser")

    # this is the code that removes all mentions
    # TODO: make it so that it removes the @ and instance but keeps the name
    for mention in soup.select("span.h-card"):
        mention.a.unwrap()
        mention.span.unwrap()

    # replace <br> with linebreak
    for lb in soup.select("br"):
        lb.insert_after("\n")
        lb.decompose()

    # replace <p> with linebreak
    for p in soup.select("p"):
        p.insert_after("\n")
        p.unwrap()

    # fix hashtags
    for ht in soup.select("a.hashtag"):
        ht.unwrap()

    # fix links
    for link in soup.select("a"):
        link.insert_after(link["href"])
        link.decompose()

    toot = soup.get_text()
    toot = toot.rstrip("\n")  # remove trailing newline
    # put a zws between @ and username to avoid mentioning
    toot = toot.replace("@", "@\u200B")
    return(toot)
