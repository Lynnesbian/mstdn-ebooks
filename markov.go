package main

import (
	"context"
	"encoding/gob"
	"log"
	"math/rand"
	"os"
	"path"
	"strconv"
	"strings"
	"sync"
	"unicode"

	mastodon "github.com/mattn/go-mastodon"
)

const markovPrefixLength = 2

type probableString struct {
	Order []string
	Count map[string]int
	Total int
}

func (ps probableString) insert(s string) probableString {
	if n, ok := ps.Count[s]; ok {
		ps.Count[s] = n + 1
		ps.Total++
		return ps
	}

	if ps.Count == nil {
		ps.Count = make(map[string]int)
	}

	ps.Count[s] = 1
	ps.Order = append(ps.Order, s)
	ps.Total++

	return ps
}

func (ps probableString) rand(r *rand.Rand) string {
	n := r.Intn(ps.Total)

	for _, s := range ps.Order {
		n -= ps.Count[s]
		if n < 0 {
			return s
		}
	}

	panic("unreachable")
}

var markovDirty = make(chan struct{}, 1)

func loadData() {
	markovLock.Lock()
	defer markovLock.Unlock()

	f, err := os.Open(*flagData)
	if os.IsNotExist(err) {
		return
	}
	checkError(err, "Could not open data cache")
	defer func() {
		checkError(f.Close(), "Could not close data cache")
	}()

	checkError(gob.NewDecoder(f).Decode(&markov), "Could not read data")
}

func saveMarkov() {
	markovLock.Lock()
	defer markovLock.Unlock()

	f, err := os.Create(*flagData + ".tmp")
	checkError(err, "Could not create data staging file")
	checkError(gob.NewEncoder(f).Encode(&markov), "Could not save data")
	checkError(f.Close(), "Could not close data staging file")
	checkError(os.Rename(*flagData+".tmp", *flagData), "Could not commit data update")
}

var markovLock sync.Mutex
var markov = struct {
	Accounts map[mastodon.ID]accountCache
	Next     map[[markovPrefixLength]string]probableString
	Prev     map[[markovPrefixLength]string]probableString
}{
	Accounts: make(map[mastodon.ID]accountCache),
	Next:     make(map[[markovPrefixLength]string]probableString),
	Prev:     make(map[[markovPrefixLength]string]probableString),
}

func insertStatus(ctx context.Context, account mastodon.ID, id, content string) {
	content = cleanContent(content)

	paragraphs := strings.Split(content, "\n\n")

	markovLock.Lock()
	defer markovLock.Unlock()

	cache := markov.Accounts[account]
	if n, err := strconv.ParseUint(path.Base(id), 10, 64); err == nil && n > cache.LatestRemoteTootID {
		cache.LatestRemoteTootID = n
		markov.Accounts[account] = cache
	}

	for _, p := range paragraphs {
		updateMarkov(strings.Fields(p))
	}

	select {
	case markovDirty <- struct{}{}:
	default:
	}
}

func updateMarkov(words []string) {
	const last = markovPrefixLength - 1
	var prefix [markovPrefixLength]string

	for _, word := range words {
		markov.Next[prefix] = markov.Next[prefix].insert(word)
		copy(prefix[:], prefix[1:])
		prefix[last] = normalizeWord(word)
	}

	markov.Next[prefix] = markov.Next[prefix].insert("")

	for i := 1; i < len(words); i++ {
		for l := 1; l <= markovPrefixLength; l++ {
			var suffix [markovPrefixLength]string
			copy(suffix[:l], words[i:])
			for j := range suffix {
				suffix[j] = normalizeWord(suffix[j])
			}
			markov.Prev[suffix] = markov.Prev[suffix].insert(words[i-1])
		}
	}
	for l := 1; l <= markovPrefixLength; l++ {
		var suffix [markovPrefixLength]string
		copy(suffix[:l], words)
		for j := range suffix {
			suffix[j] = normalizeWord(suffix[j])
		}
		markov.Prev[suffix] = markov.Prev[suffix].insert("")
	}
}

func genMarkov(r *rand.Rand, seed string) []string {
	const last = markovPrefixLength - 1
	var prefix [markovPrefixLength]string
	var line []string

	markovLock.Lock()
	defer markovLock.Unlock()

	if seed != "" {
		var suffix [markovPrefixLength]string
		suffix[0] = normalizeWord(seed)
		ps, ok := markov.Prev[suffix]
		if !ok {
			return nil
		}

		line = append(line, seed)

		for len(line) < 1000 {
			s := ps.rand(r)
			if s == "" {
				break
			}
			line = append(line, s)
			copy(suffix[1:], suffix[:])
			suffix[0] = normalizeWord(s)
			ps = markov.Prev[suffix]
		}

		for i, j := 0, len(line)-1; i < j; i, j = i+1, j-1 {
			line[i], line[j] = line[j], line[i]
		}

		for i, j := len(line)-1, last; i >= 0 && j >= 0; i, j = i-1, j-1 {
			prefix[j] = normalizeWord(line[i])
		}
	}

	if _, ok := markov.Next[prefix]; !ok {
		log.Panicln("No markov data available for prefix", prefix, line)
	}

	for len(line) < 1000 {
		ps := markov.Next[prefix]
		s := ps.rand(r)

		if s == "" {
			return line
		}

		line = append(line, s)
		copy(prefix[:], prefix[1:])
		prefix[last] = normalizeWord(s)
	}

	// probably an infinite loop
	return line
}

func normalizeWord(s string) string {
	return strings.Join(strings.FieldsFunc(strings.ToLower(s), unicode.IsPunct), "")
}
