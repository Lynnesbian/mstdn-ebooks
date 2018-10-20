// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"context"
	"math/rand"
	"strings"
	"sync"
	"time"

	"github.com/mattn/go-mastodon"
)

func genToot(ctx context.Context, me *mastodon.Account, replyTo *mastodon.Status) *mastodon.Toot {
	var replyToID mastodon.ID
	visibility := "public"
	var body []byte
	var seed string

	if replyTo != nil {
		replyToID = replyTo.ID
		visibility = replyTo.Visibility
		seed = cleanContent(replyTo.Content)

		body = append(body, '@')
		body = append(body, replyTo.Account.Acct...)
		body = append(body, ' ')

		for _, m := range replyTo.Mentions {
			if m.ID != me.ID && m.ID != replyTo.Account.ID {
				body = append(body, '@')
				body = append(body, m.Acct...)
				body = append(body, ' ')
			}
		}
	}

	body = append(body, generateMessage(ctx, seed)...)

	return &mastodon.Toot{
		Status:      string(body),
		Visibility:  visibility,
		InReplyToID: replyToID,
	}
}

var rngPool = sync.Pool{
	New: func() interface{} {
		return rand.New(rand.NewSource(time.Now().UnixNano()))
	},
}

func generateMessage(ctx context.Context, seed string) string {
	r := rngPool.Get().(*rand.Rand)
	defer rngPool.Put(r)

	words := strings.Fields(seed)
	if len(words) != 0 {
		for i := 0; i < 10; i++ {
			if line := genMarkov(r, words[r.Intn(len(words))]); line != nil {
				return strings.Join(line, " ")
			}
		}
	}

	return strings.Join(genMarkov(r, ""), " ")
}
