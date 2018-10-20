// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"context"
	"flag"
	"log"
	"time"

	"github.com/mattn/go-mastodon"
)

var flagServer = flag.String("server", "https://botsin.space", "base URL of Mastodon server")
var flagApp = flag.String("app", "clientcred.secret", "location of Mastodon app credentials")
var flagUser = flag.String("user", "usercred.secret", "location of Mastodon user access token")
var flagData = flag.String("data", "ebooks.dat", "location of bot cache")

const (
	scopes     = "read:statuses read:accounts read:follows write:statuses"
	noRedirect = "urn:ietf:wg:oauth:2.0:oob"
)

func main() {
	log.SetFlags(0)

	flag.Parse()

	ctx := context.Background()

	cfg := &mastodon.Config{
		Server: *flagServer,
	}

	ensureApp(ctx, cfg)
	ensureUser(ctx, cfg)

	client := mastodon.NewClient(cfg)

	instance, err := client.GetInstance(ctx)
	checkError(err, "Could not get instance metadata")
	me, err := client.GetAccountCurrentUser(ctx)
	checkError(err, "Could not get current user")

	log.Println("Logged in as", me.Acct+"@"+instance.URI)

	feed, err := client.NewWSClient().StreamingWSUser(ctx)
	checkError(err, "Could not connect to user feed")

	var following []*mastodon.Account
	var pg mastodon.Pagination
	isFollowing := make(map[mastodon.ID]*mastodon.Account)
	for {
		fs, err := client.GetAccountFollowing(ctx, me.ID, &pg)
		checkError(err, "Failed to get followed accounts")

		following = append(following, fs...)
		for _, f := range fs {
			isFollowing[f.ID] = f
		}

		if pg.MaxID == "" {
			break
		}
	}

	downloadToots(ctx, instance, following)
	log.Println("Initial history downloaded.")

	go func() {
		for range markovDirty {
			saveMarkov()
		}
	}()

	// Synchronize to the next half hour interval
	halfHourSync := time.After(time.Hour/2 - time.Since(time.Now().Truncate(time.Hour/2)))
	var halfHour <-chan time.Time

	for {
		select {
		case event := <-feed:
			switch e := event.(type) {
			case *mastodon.ErrorEvent:
				log.Println("Mastodon error:", e)
			case *mastodon.DeleteEvent:
				// Ignore (for now)
			case *mastodon.NotificationEvent:
				if e.Notification.Type != "mention" {
					log.Printf("Ignoring notification of type %q", e.Notification.Type)
					continue
				}
				_, err := client.PostStatus(ctx, genToot(ctx, me, e.Notification.Status))
				checkError(err, "Error replying to mention %q", e.Notification.Status.URL)
			case *mastodon.UpdateEvent:
				if _, ok := isFollowing[e.Status.Account.ID]; !ok {
					continue
				}
				if e.Status.Visibility != "unlisted" && e.Status.Visibility != "public" {
					continue
				}
				if e.Status.Sensitive {
					continue
				}
				insertStatus(ctx, e.Status.Account.ID, e.Status.URI, e.Status.Content)
			default:
				log.Printf("Unexpected event type: %T", e)
			}
		case <-halfHourSync:
			halfHourSync = nil
			halfHour = time.Tick(time.Hour / 2)
			_, err := client.PostStatus(ctx, genToot(ctx, me, nil))
			checkError(err, "Error posting status")
		case <-halfHour:
			_, err := client.PostStatus(ctx, genToot(ctx, me, nil))
			checkError(err, "Error posting status")
		}
	}
}

func checkError(err error, message string, arguments ...interface{}) {
	if err == nil {
		return
	}

	log.Panicf(message+": %v", append(arguments, err)...)
}
