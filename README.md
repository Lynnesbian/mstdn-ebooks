# mstdn-ebooks

**Lynnear Edition**

This version makes quite a few changes from [the original](https://github.com/Jess3Jane/mastodon-ebooks), such as:
- Unicode support
- Non-Markov stuff
- Stores toots in a sqlite database rather than a text file
  - Doesn't unnecessarily redownload all toots every time
  
## Install/usage guide
An installation and usage guide is available [here](https://cloud.lynnesbian.space/s/jozbRi69t4TpD95). It's primarily targeted at Linux, but it should be possible on BSD, macOS, etc. I've also put some effort into providing steps for Windows, but I can't make any guarantees as to its effectiveness.

## Compatibility
| Software  | Downloading statuses | Posting | Replying                                                    |
|-----------|----------------------|---------|-------------------------------------------------------------|
| Mastodon  | Yes                  | Yes     | Yes                                                         |
| Pleroma   | Somewhat             | Yes     | [No](https://git.pleroma.social/pleroma/pleroma/issues/416) |
| Misskey   | Yes                  | No      | No                                                          |
| diaspora* | No                   | No      | No                                                          |
| Others    | Probably             | No      | No                                                          |

## Configuration
Configuring mstdn-ebooks is accomplished by editing `config.json`. If you want to use a different file for configuration, specify it with the `--cfg` argument. For example, if you want to use `/home/lynne/c.json` instead, you would run `python3 main.py --cfg /home/lynne/c.json` instead of just `python3 main.py`

| Setting | Default | Meaning |
|--------------------|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| site | https://botsin.space | The instance your bot will log in to and post from. |
| cw | null | The content warning (aka subject) mstdn-ebooks will apply to non-error posts. |
| instance_blacklist | ["bofa.lol", "witches.town", "knzk.me"] | If your bot is following someone from a blacklisted instance, it will skip over them and not download their posts. This is useful for ensuring that mstdn-ebooks doesn't download posts from dead instances, without you having to unfollow the user(s) from them. |
| learn_from_cw | false |  If true, mstdn-ebooks will learn from CW'd posts. |
| mention_handling | 1 |  0: Never use mentions. 1: Only generate fake mentions in the middle of posts, never at the start. 2: Use mentions as normal (old behaviour). |
| max_thread_length | 15 | The maximum number of bot posts in a thread before it stops replying. A thread can be 10 or 10000 posts long, but the bot will stop after it has posted `max_thread_length` times. |
| strip_paired_punctuation | false | If true, mstdn-ebooks will remove punctuation that commonly appears in pairs, like " and (). This avoids the issue of posts that open a bracket without closing it. |
