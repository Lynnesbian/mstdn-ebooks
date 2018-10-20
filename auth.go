// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at http://mozilla.org/MPL/2.0/.

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"os"

	"github.com/mattn/go-mastodon"
)

func ensureApp(ctx context.Context, cfg *mastodon.Config) {
	if b, err := ioutil.ReadFile(*flagApp); os.IsNotExist(err) {
		log.Println("No clientcred.secret, registering application")

		app, err := mastodon.RegisterApp(ctx, &mastodon.AppConfig{
			Server:       *flagServer,
			ClientName:   "lynnesbian_mastodon_ebooks",
			Website:      "https://github.com/Lynnesbian/mstdn-ebooks",
			Scopes:       scopes,
			RedirectURIs: noRedirect,
		})
		checkError(err, "Could not register app")

		cfg.ClientID = app.ClientID
		cfg.ClientSecret = app.ClientSecret

		checkError(ioutil.WriteFile(*flagApp, []byte(app.ClientID+"\n"+app.ClientSecret+"\n"), 0644), "Could not save app credentials")

		// If the app credentials were just generated, the user access
		// token cannot possibly be valid.
		_ = os.Remove(*flagUser)
	} else {
		checkError(err, "Could not read app credentials")

		lines := bytes.Split(b, []byte{'\n'})

		// consider final newline to be optional
		if len(lines) == 3 && len(lines[2]) == 0 {
			lines = lines[:2]
		}

		if len(lines) != 2 {
			log.Fatalf("App credentials (%q) malformed. Cannot proceed.", *flagApp)
		}

		cfg.ClientID = string(lines[0])
		cfg.ClientSecret = string(lines[1])
	}
}

func ensureUser(ctx context.Context, cfg *mastodon.Config) {
	if b, err := ioutil.ReadFile(*flagUser); os.IsNotExist(err) {
		log.Println("No usercred.secret, registering application")
		authURL, err := url.Parse(*flagServer)
		checkError(err, "Could not parse instance root URL")
		authURL.Path = "/oauth/authorize"
		authURL.RawQuery = url.Values{
			"scope":         {scopes},
			"response_type": {"code"},
			"redirect_uri":  {noRedirect},
			"client_id":     {cfg.ClientID},
		}.Encode()
		log.Println("Visit this url:", authURL)
		fmt.Print("Secret: ")
		var authCode string
		_, err = fmt.Scanln(&authCode)
		checkError(err, "Failed to read authorization code")

		authURL.Path = "/oauth/token"
		authURL.RawQuery = ""

		resp, err := http.PostForm(authURL.String(), url.Values{
			"client_id":     {cfg.ClientID},
			"client_secret": {cfg.ClientSecret},
			"grant_type":    {"authorization_code"},
			"code":          {authCode},
			"redirect_uri":  {noRedirect},
		})
		checkError(err, "Failed to request access token")

		defer func() {
			checkError(resp.Body.Close(), "Error closing response body")
		}()

		if resp.StatusCode == http.StatusOK {
			var payload struct {
				AccessToken string `json:"access_token"`
			}
			checkError(json.NewDecoder(resp.Body).Decode(&payload), "Error decoding authentication response")

			cfg.AccessToken = payload.AccessToken

			checkError(ioutil.WriteFile(*flagUser, []byte(payload.AccessToken+"\n"), 0644), "Error saving access token")
		} else {
			body, err := ioutil.ReadAll(resp.Body)
			checkError(err, "Network error reading authentication error")

			log.Fatalln("Authentication failed:", string(body))
		}
	} else {
		checkError(err, "Could not read user access token")

		cfg.AccessToken = string(bytes.TrimSuffix(b, []byte{'\n'}))
	}
}
