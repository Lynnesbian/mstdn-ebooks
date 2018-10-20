# mstdn-ebooks

**Lynnear Edition**

This version makes quite a few changes from [the original](https://github.com/Jess3Jane/mastodon-ebooks) and [the other original](https://github.com/Lynnesbian/mstdn-ebooks/tree/3d059d0b9b66fd31378574104f1a56f2be5a319c), such as:

- Unicode support
- Non-Markov stuff
- Doesn't unecessarily redownload all toots every time
- Uses an API called "webfinger" to allow downloading toots not known to your bot's instance
- Self-contained executable handles scheduling
- Docker support
- Written in Go

## Installation

1. Build mstdn-ebooks the same way you would build any Go program (`go get`, etc.) Alternatively, if you don't want to build it yourself, download a [precompiled release version](https://github.com/Lynnesbian/mstdn-ebooks/releases/latest).
2. If you haven't already, create an account on [botsin.space](https://botsin.space) or another instance.
3. Make sure the bot account is ONLY following you. Remove any default follows.
4. Run the `mstdn-ebooks` command. If your instance is not botsin.space, run the command as `mstdn-ebooks -server https://[your instance]`.
5. Copy the URL it generates into a browser logged into your bot account, and copy the code that Mastodon generates back to the program.
6. Congratulations! Your ebooks bot is now running. To restart it, you only need to redo step 4.
