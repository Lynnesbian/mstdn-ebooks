// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"context"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strings"
	"sync"

	"github.com/mattn/go-mastodon"
	"golang.org/x/net/html"
	"golang.org/x/net/html/atom"
)

type accountCache struct {
	LatestRemoteTootID uint64
}

func downloadToots(ctx context.Context, instance *mastodon.Instance, following []*mastodon.Account) {
	loadData()

	var wg sync.WaitGroup
	wg.Add(len(following))

	markovLock.Lock()
	for _, f := range following {
		go func(account *mastodon.Account, start uint64) {
			defer wg.Done()

			log.Printf("Downloading toots for user %s, starting from %d", account.Acct, start)

			acct := account.Acct
			if !strings.Contains(acct, "@") {
				acct += "@" + instance.URI
			}

			loadAllToots(ctx, acct, account.URL, start, func(id, content string) {
				insertStatus(ctx, account.ID, id, content)
			})
		}(f, markov.Accounts[f.ID].LatestRemoteTootID)
	}
	markovLock.Unlock()

	wg.Wait()
}

func cleanContent(s string) string {
	paragraphs, err := html.ParseFragment(strings.NewReader(s), &html.Node{
		Type:     html.ElementNode,
		Data:     "div",
		DataAtom: atom.Div,
	})
	checkError(err, "Failed to parse HTML %q", s)

	var body []byte
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		for n != nil {
			if n.Type == html.TextNode {
				body = append(body, n.Data...)
			} else if n.Type == html.ElementNode {
				var isMention bool
				if n.DataAtom == atom.A {
					for _, a := range n.Attr {
						if a.Key == "class" {
							for _, c := range strings.Fields(a.Val) {
								if c == "mention" {
									isMention = true
									break
								}
							}
							break
						}
					}
				} else if n.DataAtom == atom.Img {
					for _, a := range n.Attr {
						if a.Key == "alt" {
							body = append(body, a.Val...)
							break
						}
					}
				}

				if !isMention {
					walk(n.FirstChild)
				}
			}
			n = n.NextSibling
		}
	}

	for i, p := range paragraphs {
		if i != 0 {
			body = append(body, "\n\n"...)
		}
		walk(p.FirstChild)
	}

	return string(body)
}

func getJSON(ctx context.Context, uri string, v interface{}) {
	resp, err := http.Get(uri)
	checkError(err, "Could not download %q", uri)
	defer func() {
		checkError(resp.Body.Close(), "Error when closing %q", uri)
	}()

	if resp.StatusCode != http.StatusOK {
		log.Panicf("Error downloading %q: %v", uri, resp.Status)
	}

	checkError(json.NewDecoder(resp.Body).Decode(v), "Error decoding %q", uri)
}

func loadAllToots(ctx context.Context, acct, userURL string, start uint64, foundStatus func(id, content string)) {
	webFingerURL := getWebFingerURL(ctx, acct, userURL)
	outbox := webFingerUserActivity(ctx, webFingerURL) + "/outbox"
	prev := fmt.Sprintf("%s?min_id=%d&page=true", outbox, start)
	for prev != "" {
		var page struct {
			OrderedItems []struct {
				Type   string          `json:"type"`
				Object json.RawMessage `json:"object"`
			} `json:"orderedItems"`
			Prev string `json:"prev"`
		}
		getJSON(ctx, prev, &page)
		for _, i := range page.OrderedItems {
			if i.Type == "Create" {
				var object struct {
					ID        string `json:"id"`
					Sensitive bool   `json:"sensitive"`
					Content   string `json:"content"`
				}
				checkError(json.Unmarshal(i.Object, &object), "Failed to decode toot JSON in %q", prev)
				if !object.Sensitive {
					foundStatus(object.ID, object.Content)
				}
			}
		}
		prev = page.Prev
	}
}

func getWebFingerURL(ctx context.Context, acct, userURL string) string {
	acct = url.QueryEscape("acct:" + acct)

	u, err := url.Parse(userURL)
	checkError(err, "Failed to parse user URL")
	u.Path = "/.well-known/host-meta"
	u.RawQuery = ""

	resp, err := http.Get(u.String())
	checkError(err, "Could not retrieve host-meta")
	defer func() {
		checkError(resp.Body.Close(), "Error closing host-meta request")
	}()
	if resp.StatusCode != http.StatusOK {
		log.Panicf("Failed to load %q: %s", u, resp.Status)
	}
	var meta struct {
		Link struct {
			Template string `xml:"template,attr"`
		} `xml:"Link"`
	}
	checkError(xml.NewDecoder(resp.Body).Decode(&meta), "Could not find webfinger URL")

	return strings.Replace(meta.Link.Template, "{uri}", acct, -1)
}

func webFingerUserActivity(ctx context.Context, uri string) string {
	var body struct {
		Links []struct {
			Href string `json:"href"`
			Rel  string `json:"rel"`
			Type string `json:"type"`
		} `json:"links"`
	}

	getJSON(ctx, uri, &body)

	for _, l := range body.Links {
		if l.Rel == "self" && l.Type == "application/activity+json" {
			return l.Href
		}
	}

	log.Panicf("Could not find ActivityPub URL in web finger response: %q", uri)
	return ""
}
