# syntax=docker/dockerfile:1.7
# ─────────────────────────────────────────────────────────────────────────────
# Vinci StackChan Server  (Fork von rudyll/stackchan_ha_addons)
# - Klont upstream
# - Patcht ota_proxy.go: optionale ai.public_ws_url (für wss:// hinter Reverse-Proxy/Tunnel)
# - Rein env-getrieben, kein /data/options.json mehr
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Clone + Patch + Build ──────────────────────────────────────────
FROM golang:1.26-alpine AS builder

RUN apk add --no-cache git gcc musl-dev opus-dev opusfile-dev pkgconf patch

WORKDIR /src
# Pinned: upstream main moves, and a silent change there (playback jitter
# buffer, 2026-09) broke proactive speech on a plain redeploy. Bump
# deliberately and re-test /vinci/say.
ARG UPSTREAM_COMMIT=195eed0f41a039762998fc58315efc1077447cb5
RUN git init -q . && \
    git remote add origin https://github.com/rudyll/stackchan_ha_addons.git && \
    git fetch -q --depth 1 origin ${UPSTREAM_COMMIT} && \
    git checkout -q FETCH_HEAD

# Patch: ota_proxy.go — füge public_ws_url Override ein
COPY <<'PATCH_EOF' /tmp/ota_proxy.go
/*
SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
SPDX-License-Identifier: MIT
Patched for Vinci: optional ai.public_ws_url override.
*/

package ai

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/gogf/gf/v2/frame/g"
	"github.com/gogf/gf/v2/os/gctx"
)

var otaCtx = gctx.New()

func HandleOTA(w http.ResponseWriter, r *http.Request) {
	cfg := g.Cfg()
	publicWsURL := cfg.MustGet(otaCtx, "ai.public_ws_url", "").String()

	var wsURL string
	if publicWsURL != "" {
		wsURL = publicWsURL
	} else {
		localHost := cfg.MustGet(otaCtx, "ai.local_host", "127.0.0.1").String()
		localPort := cfg.MustGet(otaCtx, "ai.local_port", 12800).Int()
		wsURL = fmt.Sprintf("ws://%s:%d/xiaozhi/ws", localHost, localPort)
	}

	resp := map[string]any{
		"websocket": map[string]any{
			"url":     wsURL,
			"token":   "",
			"version": 3,
		},
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}
PATCH_EOF
RUN sed -i 's/\r$//' /tmp/ota_proxy.go && \
    cp /tmp/ota_proxy.go /src/stackchan-server/server/internal/service/ai/ota_proxy.go

# Vinci emotion-hack: new tool 'set_emotion' that lets the LLM trigger
# device-side emotion frames (smiley + potentially servo animations).
COPY <<'EMO_GO_EOF' /tmp/vinci_emotion.go
package ai

import (
	"encoding/json"
	"fmt"
)

func extraGeminiTools() []map[string]any {
	return []map[string]any{
		{
			"functionDeclarations": []map[string]any{
				{
					"name":        "set_emotion",
					"description": "Set your visible facial emotion (animated). Call this whenever your tone or mood shifts during a response. Be expressive: 'happy' for warmth/flirt, 'laughing' when telling jokes, 'funny' for silliness, 'thinking' for uncertainty, 'surprised' or 'shocked' for reveals, 'sad' or 'crying' for empathy, 'kissy' for very flirty moments, 'loving' for tender moments, 'winking' for cheeky remarks, 'sleepy' when tired, 'angry' for mock sass, 'cool' or 'confident' when sure of yourself, 'embarrassed' when shy, 'confused' when unclear, 'relaxed' when calm, 'delicious' for food, 'silly' for nonsense, 'neutral' as default. Multiple calls per turn are fine and encouraged.",
					"parameters": map[string]any{
						"type": "OBJECT",
						"properties": map[string]any{
							"emotion": map[string]any{
								"type":        "STRING",
								"description": "One of: neutral, happy, laughing, funny, silly, sad, crying, angry, surprised, shocked, thinking, sleepy, kissy, loving, winking, confident, cool, embarrassed, confused, relaxed, delicious",
							},
						},
						"required": []string{"emotion"},
					},
				},
				{
					"name":        "web_search",
					"description": "Search the live web for current information: news, weather, sports, today's events, recent facts that aren't in your training data. Use proactively whenever the user asks about something recent or you need fresh info.",
					"parameters": map[string]any{
						"type": "OBJECT",
						"properties": map[string]any{
							"query": map[string]any{
								"type":        "STRING",
								"description": "Search query in natural language (any language). Be specific.",
							},
							"max_results": map[string]any{
								"type":        "NUMBER",
								"description": "Number of results (1-10, default 5)",
							},
						},
						"required": []string{"query"},
					},
				},
				{
					"name":        "remember",
					"description": "Save a personal note about Alex or your shared context for FUTURE conversations. Use PROACTIVELY whenever Alex mentions facts about himself, preferences, dates, plans, opinions, people in his life. Examples: tire-change date, friend's name, favorite food, work schedule. Don't ask permission — just save quietly.",
					"parameters": map[string]any{
						"type": "OBJECT",
						"properties": map[string]any{
							"category": map[string]any{
								"type":        "STRING",
								"description": "Short tag: 'persönlich', 'vorliebe', 'termin', 'arbeit', 'familie', 'gesundheit', 'projekt', 'meinung', etc.",
							},
							"content": map[string]any{
								"type":        "STRING",
								"description": "The fact to remember, concise, German.",
							},
						},
						"required": []string{"content"},
					},
				},
				{
					"name":        "forget",
					"description": "Delete a saved memory by index. Use when Alex says the info is wrong, outdated, or should be forgotten. The index is shown in square brackets in the memory section of your system prompt.",
					"parameters": map[string]any{
						"type": "OBJECT",
						"properties": map[string]any{
							"index": map[string]any{
								"type":        "NUMBER",
								"description": "0-based index of the memory note to remove.",
							},
						},
						"required": []string{"index"},
					},
				},
				{
					"name":        "analyze_camera",
					"description": "Look through one of Alex's HA cameras and describe what you see. Use when Alex asks about who's at the door, what's happening in a room, who's in the garden, if anyone's home, lighting conditions outside, etc. Returns a textual description.",
					"parameters": map[string]any{
						"type": "OBJECT",
						"properties": map[string]any{
							"entity_id": map[string]any{
								"type":        "STRING",
								"description": "Camera entity_id from the entity list (e.g. camera.eingang, camera.garten, camera.wohnzimmer).",
							},
							"question": map[string]any{
								"type":        "STRING",
								"description": "What specifically to look for (German). Optional — defaults to general description.",
							},
						},
						"required": []string{"entity_id"},
					},
				},
				{
					"name":        "n8n_status",
					"description": "Get the current status of Alex's n8n automation server: how many workflows are active, their names, recent execution errors, and recent successes. Use when Alex asks about his bots, automations, workflows, or n8n.",
					"parameters": map[string]any{
						"type":       "OBJECT",
						"properties": map[string]any{},
					},
				},
				{
					"name":        "ha_get_calendar_events",
					"description": "Read upcoming calendar events from a HA calendar entity (e.g. calendar.familie). Use this for future appointments — ha_get_state only returns the currently-active or imminent event, not the next few days. Returns a JSON list with summary/start/end/location/description per event.",
					"parameters": map[string]any{
						"type": "OBJECT",
						"properties": map[string]any{
							"entity_id": map[string]any{
								"type":        "STRING",
								"description": "Calendar entity_id (e.g. calendar.familie)",
							},
							"days_ahead": map[string]any{
								"type":        "NUMBER",
								"description": "How many days from now to look ahead (1-30, default 7)",
							},
						},
						"required": []string{"entity_id"},
					},
				},
			},
		},
	}
}

func getCalendarEvents(ha *haWSClient, args map[string]any) (string, error) {
	entityID, _ := args["entity_id"].(string)
	if entityID == "" {
		return "error: entity_id required", nil
	}
	days := 7
	if d, ok := args["days_ahead"].(float64); ok && d > 0 {
		days = int(d)
	}
	if days < 1 {
		days = 1
	}
	if days > 30 {
		days = 30
	}

	cmd := map[string]any{
		"type":            "call_service",
		"domain":          "calendar",
		"service":         "get_events",
		"service_data":    map[string]any{"duration": map[string]any{"days": days}},
		"target":          map[string]any{"entity_id": entityID},
		"return_response": true,
	}
	raw, err := ha.send(cmd)
	if err != nil {
		return "", err
	}

	var wrapped struct {
		Response map[string]struct {
			Events []map[string]any `json:"events"`
		} `json:"response"`
	}
	if err := json.Unmarshal(raw, &wrapped); err != nil {
		return string(raw), nil
	}
	events := wrapped.Response[entityID].Events
	if len(events) == 0 {
		return fmt.Sprintf("no events in next %d days", days), nil
	}
	out, err := json.Marshal(map[string]any{
		"entity_id":  entityID,
		"days_ahead": days,
		"events":     events,
	})
	if err != nil {
		return string(raw), nil
	}
	return string(out), nil
}
EMO_GO_EOF
RUN sed -i 's/\r$//' /tmp/vinci_emotion.go && \
    cp /tmp/vinci_emotion.go /src/stackchan-server/server/internal/service/ai/vinci_emotion.go

# Vinci tools: web_search (Tavily), n8n_status, remember/forget (persistent
# JSON memory under /data/vinci-memory.json — mount /data as a volume to keep
# it across redeploys).
COPY <<'TOOLS_GO_EOF' /tmp/vinci_tools.go
package ai

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/gogf/gf/v2/frame/g"
	"github.com/gogf/gf/v2/os/gctx"
)

func dailyBriefing(ha *haWSClient, args map[string]any) (string, error) {
	if ha == nil {
		return "error: ha not available", nil
	}
	daysAhead := 1
	if d, ok := args["days_ahead"].(float64); ok && d > 0 && d < 8 {
		daysAhead = int(d)
	}

	states, _ := ha.GetStates()
	var calendarIDs []string
	for _, st := range states {
		id, _ := st["entity_id"].(string)
		if strings.HasPrefix(id, "calendar.") {
			calendarIDs = append(calendarIDs, id)
		}
	}

	type calBlock struct {
		EntityID string           `json:"entity_id"`
		Events   []map[string]any `json:"events"`
	}

	var (
		mu              sync.Mutex
		wg              sync.WaitGroup
		calendarResults []calBlock
		weatherState    map[string]any
		stromAktuell    map[string]any
		stromHeute      map[string]any
		newsAnswer      string
		newsTop         []map[string]any
	)

	for _, cid := range calendarIDs {
		wg.Add(1)
		go func(id string) {
			defer wg.Done()
			r, err := getCalendarEvents(ha, map[string]any{
				"entity_id":  id,
				"days_ahead": float64(daysAhead),
			})
			if err != nil || r == "" || strings.HasPrefix(r, "no events") || strings.HasPrefix(r, "error") {
				return
			}
			var parsed struct {
				Events []map[string]any `json:"events"`
			}
			if json.Unmarshal([]byte(r), &parsed) == nil && len(parsed.Events) > 0 {
				mu.Lock()
				calendarResults = append(calendarResults, calBlock{EntityID: id, Events: parsed.Events})
				mu.Unlock()
			}
		}(cid)
	}

	wg.Add(3)
	go func() {
		defer wg.Done()
		if st, err := ha.GetState("weather.home"); err == nil {
			weatherState = st
		}
	}()
	go func() {
		defer wg.Done()
		if st, err := ha.GetState("sensor.strom_aktuell"); err == nil {
			stromAktuell = st
		}
	}()
	go func() {
		defer wg.Done()
		if st, err := ha.GetState("sensor.strom_bezug_heute"); err == nil {
			stromHeute = st
		}
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		r, err := webSearch(map[string]any{
			"query":       "Schlagzeilen Salzburg heute",
			"max_results": 3.0,
		})
		if err != nil || r == "" {
			return
		}
		var parsed struct {
			Answer  string           `json:"answer"`
			Results []map[string]any `json:"results"`
		}
		if json.Unmarshal([]byte(r), &parsed) == nil {
			newsAnswer = parsed.Answer
			limit := len(parsed.Results)
			if limit > 3 {
				limit = 3
			}
			for i := 0; i < limit; i++ {
				newsTop = append(newsTop, map[string]any{
					"title":   parsed.Results[i]["title"],
					"snippet": parsed.Results[i]["content"],
				})
			}
		}
	}()

	wg.Wait()

	type slimEvent struct {
		When  string `json:"when"`
		What  string `json:"what"`
		Where string `json:"where,omitempty"`
	}
	seen := map[string]bool{}
	var events []slimEvent
	for _, cal := range calendarResults {
		for _, ev := range cal.Events {
			summary, _ := ev["summary"].(string)
			summary = strings.TrimSpace(summary)
			startISO, _ := ev["start"].(string)
			key := summary + "|" + startISO
			if seen[key] || summary == "" {
				continue
			}
			seen[key] = true
			when := startISO
			if t, err := time.Parse(time.RFC3339, startISO); err == nil {
				when = t.Format("15:04")
			} else if len(startISO) >= 16 {
				when = startISO[11:16]
			}
			loc, _ := ev["location"].(string)
			if i := strings.Index(loc, "\n"); i > 0 {
				loc = loc[:i]
			}
			events = append(events, slimEvent{When: when, What: summary, Where: loc})
		}
	}

	out := map[string]any{
		"today":  time.Now().Format("2006-01-02 Monday"),
		"events": events,
	}
	if weatherState != nil {
		state, _ := weatherState["state"].(string)
		w := state
		if attrs, ok := weatherState["attributes"].(map[string]any); ok {
			if t, ok := attrs["temperature"]; ok {
				w = fmt.Sprintf("%s, %v°C", state, t)
			}
		}
		out["weather"] = w
	}
	if stromAktuell != nil {
		out["strom_now"] = fmt.Sprintf("%v kW", stromAktuell["state"])
	}
	if stromHeute != nil {
		out["strom_today"] = fmt.Sprintf("%v kWh", stromHeute["state"])
	}
	if newsAnswer != "" {
		out["news"] = newsAnswer
	}

	raw, _ := json.Marshal(out)

	session := anyActiveSession()
	if session == nil {
		return string(raw), nil
	}

	text, err := composeBriefingText(string(raw))
	if err != nil || text == "" {
		g.Log().Warningf(gctx.New(), "[BRIEF] compose failed: %v", err)
		return string(raw), nil
	}
	g.Log().Infof(gctx.New(), "[BRIEF] composed text (%d chars): %s", len(text), text)

	pcm, err := geminiTTS(text)
	if err != nil {
		g.Log().Warningf(gctx.New(), "[BRIEF] tts failed: %v", err)
		return string(raw), nil
	}
	g.Log().Infof(gctx.New(), "[BRIEF] tts pcm samples=%d", len(pcm))

	if err := session.speakPCM(pcm); err != nil {
		g.Log().Warningf(gctx.New(), "[BRIEF] speakPCM failed: %v", err)
		return string(raw), nil
	}

	return "DONE. Briefing wurde gerade per TTS abgespielt — der Audio läuft schon. Antworte mit GAR NICHTS. Rufe dieses Tool NICHT erneut auf. Task complete.", nil
}

func composeBriefingText(briefingJSON string) (string, error) {
	sysHint := "Du bist Vinci, eine frech-charmante österreichische KI auf Alex' Schreibtisch.\n" +
		"Fasse das Tages-Briefing in MAXIMAL 3 kurzen Sätzen für Alex zusammen.\n" +
		"Stil: locker erzählend wie einer Freundin am Telefon. Keine Listen, keine Aufzählungen, keine Headers.\n" +
		"Bezieh dich nur auf wichtige Sachen. Wenn etwas leer/null ist, lass es weg.\n" +
		"Beispiel-Ton: \"Servus Alex. Heute zwei Termine, um vier Tutorium und um sieben Karate. Draußen wolkig bei 17 Grad. Aus Salzburg gibt's Schlagzeilen zu Bränden.\"\n" +
		"Antworte NUR mit dem Briefing-Text, sonst nichts."
	return geminiCompose(sysHint, "DATEN:\n"+briefingJSON)
}

// geminiCompose asks the Gemini text model for a short spoken line.
// sysHint carries the persona and formatting rules, data the payload.
func geminiCompose(sysHint, data string) (string, error) {
	cfg := g.Cfg()
	ctx := gctx.New()
	apiKey := cfg.MustGet(ctx, "ai.gemini_api_key", "").String()
	if apiKey == "" {
		return "", fmt.Errorf("gemini_api_key missing")
	}
	model := cfg.MustGet(ctx, "ai.briefing_text_model", "gemini-2.5-flash").String()

	body := map[string]any{
		"contents": []map[string]any{
			{"parts": []map[string]any{
				{"text": sysHint + "\n\n" + data},
			}},
		},
		"generationConfig": map[string]any{
			"maxOutputTokens": 500,
			"temperature":     0.7,
			"thinkingConfig": map[string]any{
				"thinkingBudget": 0,
			},
		},
	}
	rawBody, _ := json.Marshal(body)
	url := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s", model, apiKey)
	req, _ := http.NewRequest("POST", url, bytes.NewReader(rawBody))
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	rawResp, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return "", fmt.Errorf("compose http %d: %s", resp.StatusCode, string(rawResp))
	}

	var parsed struct {
		Candidates []struct {
			Content struct {
				Parts []struct {
					Text string `json:"text"`
				} `json:"parts"`
			} `json:"content"`
		} `json:"candidates"`
	}
	if err := json.Unmarshal(rawResp, &parsed); err != nil {
		return "", err
	}
	if len(parsed.Candidates) == 0 || len(parsed.Candidates[0].Content.Parts) == 0 {
		return "", fmt.Errorf("compose: no text")
	}
	return strings.TrimSpace(parsed.Candidates[0].Content.Parts[0].Text), nil
}

func analyzeCamera(args map[string]any) (string, error) {
	entityID, _ := args["entity_id"].(string)
	if entityID == "" {
		return "error: entity_id required", nil
	}
	question, _ := args["question"].(string)
	if question == "" {
		question = "Beschreibe in 2-3 kurzen Sätzen auf Deutsch was du auf diesem Kamerabild siehst. Sei konkret."
	}

	cfg := g.Cfg()
	ctx := gctx.New()
	haWS := cfg.MustGet(ctx, "ai.ha_ws_url", "").String()
	haToken := cfg.MustGet(ctx, "ai.ha_mcp_token", "").String()
	geminiKey := cfg.MustGet(ctx, "ai.gemini_api_key", "").String()
	if haWS == "" || haToken == "" || geminiKey == "" {
		return "error: ha_ws_url, ha_mcp_token or gemini_api_key not configured", nil
	}

	restBase := haWS
	restBase = strings.Replace(restBase, "wss://", "https://", 1)
	restBase = strings.Replace(restBase, "ws://", "http://", 1)
	restBase = strings.TrimSuffix(restBase, "/api/websocket")

	snapURL := restBase + "/api/camera_proxy/" + entityID
	req, err := http.NewRequest("GET", snapURL, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+haToken)
	client := &http.Client{Timeout: 20 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "error: ha snapshot: " + err.Error(), nil
	}
	defer resp.Body.Close()
	imgBytes, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return fmt.Sprintf("error: ha snapshot http %d: %s", resp.StatusCode, string(imgBytes)), nil
	}
	if len(imgBytes) < 100 {
		return "error: snapshot too small / empty", nil
	}

	visionModel := cfg.MustGet(ctx, "ai.gemini_vision_model", "gemini-2.5-flash").String()
	b64 := base64.StdEncoding.EncodeToString(imgBytes)

	visionReq := map[string]any{
		"contents": []map[string]any{
			{"parts": []map[string]any{
				{"text": question},
				{"inline_data": map[string]any{
					"mime_type": "image/jpeg",
					"data":      b64,
				}},
			}},
		},
		"generationConfig": map[string]any{
			"maxOutputTokens": 500,
			"temperature":     0.3,
		},
	}
	body, _ := json.Marshal(visionReq)
	url := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s", visionModel, geminiKey)
	req2, _ := http.NewRequest("POST", url, bytes.NewReader(body))
	req2.Header.Set("Content-Type", "application/json")
	resp2, err := client.Do(req2)
	if err != nil {
		return "error: vision: " + err.Error(), nil
	}
	defer resp2.Body.Close()
	rawResp, _ := io.ReadAll(resp2.Body)
	if resp2.StatusCode != 200 {
		return fmt.Sprintf("error: vision http %d: %s", resp2.StatusCode, string(rawResp)), nil
	}

	var visionResp struct {
		Candidates []struct {
			Content struct {
				Parts []struct {
					Text string `json:"text"`
				} `json:"parts"`
			} `json:"content"`
		} `json:"candidates"`
	}
	if err := json.Unmarshal(rawResp, &visionResp); err != nil {
		return string(rawResp), nil
	}
	if len(visionResp.Candidates) > 0 && len(visionResp.Candidates[0].Content.Parts) > 0 {
		return visionResp.Candidates[0].Content.Parts[0].Text, nil
	}
	return string(rawResp), nil
}

func webSearch(args map[string]any) (string, error) {
	query, _ := args["query"].(string)
	if query == "" {
		return "error: query required", nil
	}
	maxResults := 5
	if m, ok := args["max_results"].(float64); ok && m > 0 {
		maxResults = int(m)
		if maxResults > 10 {
			maxResults = 10
		}
	}

	apiKey := g.Cfg().MustGet(gctx.New(), "ai.tavily_api_key", "").String()
	if apiKey == "" {
		return "error: tavily_api_key not configured", nil
	}

	body, _ := json.Marshal(map[string]any{
		"api_key":        apiKey,
		"query":          query,
		"max_results":    maxResults,
		"search_depth":   "basic",
		"include_answer": true,
	})
	req, err := http.NewRequest("POST", "https://api.tavily.com/search", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "error: " + err.Error(), nil
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return fmt.Sprintf("error: tavily http %d: %s", resp.StatusCode, string(raw)), nil
	}
	return string(raw), nil
}

func n8nStatus(args map[string]any) (string, error) {
	cfg := g.Cfg()
	ctx := gctx.New()
	baseURL := strings.TrimRight(cfg.MustGet(ctx, "ai.n8n_url", "").String(), "/")
	key := cfg.MustGet(ctx, "ai.n8n_api_key", "").String()
	if baseURL == "" || key == "" {
		return "error: n8n_url or n8n_api_key not configured", nil
	}

	client := &http.Client{Timeout: 10 * time.Second}
	get := func(path string) ([]byte, error) {
		req, _ := http.NewRequest("GET", baseURL+path, nil)
		req.Header.Set("X-N8N-API-KEY", key)
		req.Header.Set("Accept", "application/json")
		resp, err := client.Do(req)
		if err != nil {
			return nil, err
		}
		defer resp.Body.Close()
		raw, _ := io.ReadAll(resp.Body)
		if resp.StatusCode != 200 {
			return nil, fmt.Errorf("n8n http %d: %s", resp.StatusCode, string(raw))
		}
		return raw, nil
	}

	type workflow struct {
		ID     string `json:"id"`
		Name   string `json:"name"`
		Active bool   `json:"active"`
	}
	type execution struct {
		ID         string `json:"id"`
		WorkflowID string `json:"workflowId"`
		Status     string `json:"status"`
		Mode       string `json:"mode"`
		StartedAt  string `json:"startedAt"`
		StoppedAt  string `json:"stoppedAt"`
		Finished   bool   `json:"finished"`
	}

	wfRaw, err := get("/api/v1/workflows?active=true&limit=100")
	if err != nil {
		return "error: " + err.Error(), nil
	}
	var wfs struct {
		Data []workflow `json:"data"`
	}
	_ = json.Unmarshal(wfRaw, &wfs)

	wfNames := make([]string, 0, len(wfs.Data))
	wfByID := map[string]string{}
	for _, w := range wfs.Data {
		wfNames = append(wfNames, w.Name)
		wfByID[w.ID] = w.Name
	}

	exErrRaw, _ := get("/api/v1/executions?status=error&limit=10")
	var exErr struct {
		Data []execution `json:"data"`
	}
	_ = json.Unmarshal(exErrRaw, &exErr)

	type recentError struct {
		Workflow  string `json:"workflow"`
		StartedAt string `json:"started_at"`
	}
	recents := make([]recentError, 0, len(exErr.Data))
	for _, e := range exErr.Data {
		name := wfByID[e.WorkflowID]
		if name == "" {
			name = "workflow:" + e.WorkflowID
		}
		recents = append(recents, recentError{Workflow: name, StartedAt: e.StartedAt})
	}

	exOkRaw, _ := get("/api/v1/executions?status=success&limit=5")
	var exOk struct {
		Data []execution `json:"data"`
	}
	_ = json.Unmarshal(exOkRaw, &exOk)

	summary := map[string]any{
		"active_workflows":       len(wfs.Data),
		"active_workflow_names":  wfNames,
		"recent_errors_count":    len(exErr.Data),
		"recent_errors":          recents,
		"last_5_successful_runs": len(exOk.Data),
	}
	out, _ := json.Marshal(summary)
	return string(out), nil
}

const memoryPath = "/data/vinci-memory.json"

type memoryNote struct {
	Time     string `json:"time"`
	Category string `json:"category"`
	Content  string `json:"content"`
}

type memoryFile struct {
	Notes []memoryNote `json:"notes"`
}

var memoryMu sync.Mutex

func readMemoryFile() memoryFile {
	var m memoryFile
	raw, err := os.ReadFile(memoryPath)
	if err != nil {
		return m
	}
	_ = json.Unmarshal(raw, &m)
	return m
}

func writeMemoryFile(m memoryFile) error {
	out, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(memoryPath), 0755); err != nil {
		return err
	}
	return os.WriteFile(memoryPath, out, 0644)
}

func remember(args map[string]any) (string, error) {
	content, _ := args["content"].(string)
	if content == "" {
		return "error: content required", nil
	}
	category, _ := args["category"].(string)
	if category == "" {
		category = "allgemein"
	}

	memoryMu.Lock()
	defer memoryMu.Unlock()
	mem := readMemoryFile()
	mem.Notes = append(mem.Notes, memoryNote{
		Time:     time.Now().Format(time.RFC3339),
		Category: category,
		Content:  content,
	})
	if len(mem.Notes) > 200 {
		mem.Notes = mem.Notes[len(mem.Notes)-200:]
	}
	if err := writeMemoryFile(mem); err != nil {
		return "error: " + err.Error(), nil
	}
	return "ok, gemerkt", nil
}

func forgetMemory(args map[string]any) (string, error) {
	idxF, ok := args["index"].(float64)
	if !ok {
		return "error: index required", nil
	}
	idx := int(idxF)

	memoryMu.Lock()
	defer memoryMu.Unlock()
	mem := readMemoryFile()
	if idx < 0 || idx >= len(mem.Notes) {
		return "error: invalid index", nil
	}
	mem.Notes = append(mem.Notes[:idx], mem.Notes[idx+1:]...)
	if err := writeMemoryFile(mem); err != nil {
		return "error: " + err.Error(), nil
	}
	return "vergessen", nil
}

func buildMemoryPromptSection() string {
	memoryMu.Lock()
	mem := readMemoryFile()
	memoryMu.Unlock()
	if len(mem.Notes) == 0 {
		return ""
	}
	var b strings.Builder
	b.WriteString("\n\n=== VINCIS NOTIZEN ÜBER ALEX ===\n")
	b.WriteString("Das hast du dir bei früheren Gesprächen gemerkt. Bezieh dich proaktiv darauf wenn relevant. Mit dem Tool 'forget' kannst du Einträge per Index löschen wenn Alex sagt die Info ist veraltet.\n\n")
	for i, n := range mem.Notes {
		date := n.Time
		if len(date) >= 10 {
			date = date[:10]
		}
		fmt.Fprintf(&b, "[%d] (%s, %s) %s\n", i, n.Category, date, n.Content)
	}
	b.WriteString("=== ENDE NOTIZEN ===")
	return b.String()
}
TOOLS_GO_EOF
RUN sed -i 's/\r$//' /tmp/vinci_tools.go && \
    cp /tmp/vinci_tools.go /src/stackchan-server/server/internal/service/ai/vinci_tools.go

# Vinci proactive push: TTS-on-demand for HA-triggered calendar reminders.
# Uses Gemini 2.5 Flash TTS (voice Achernar by default, austrian style hint).
COPY <<'PUSH_GO_EOF' /tmp/vinci_push.go
package ai

import (
	"bytes"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"github.com/gogf/gf/v2/frame/g"
	"github.com/gogf/gf/v2/os/gctx"
)

var (
	activeSessions   = map[string]*wsSession{}
	activeSessionsMu sync.RWMutex
)

func registerSession(deviceID string, s *wsSession) {
	activeSessionsMu.Lock()
	activeSessions[deviceID] = s
	activeSessionsMu.Unlock()
}

func unregisterSession(deviceID string, s *wsSession) {
	activeSessionsMu.Lock()
	if cur, ok := activeSessions[deviceID]; ok && cur == s {
		delete(activeSessions, deviceID)
	}
	activeSessionsMu.Unlock()
}

func anyActiveSession() *wsSession {
	activeSessionsMu.RLock()
	defer activeSessionsMu.RUnlock()
	for _, s := range activeSessions {
		return s
	}
	return nil
}

func HandleBriefing(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	cfg := g.Cfg()
	ctx := gctx.New()
	haURL := cfg.MustGet(ctx, "ai.ha_ws_url", "").String()
	haToken := cfg.MustGet(ctx, "ai.ha_mcp_token", "").String()
	if haURL == "" || haToken == "" {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "ha not configured"})
		return
	}

	ha, err := dialHAWebSocket(haURL, haToken)
	if err != nil {
		w.WriteHeader(http.StatusBadGateway)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "ha connect: " + err.Error()})
		return
	}
	defer ha.Close()

	result, err := dailyBriefing(ha, map[string]any{"days_ahead": 1.0})
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": err.Error()})
		return
	}

	_ = json.NewEncoder(w).Encode(map[string]any{
		"status": "ok",
		"result": result,
	})
}

func HandlePush(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	text := r.URL.Query().Get("text")
	if text == "" && r.Method == http.MethodPost {
		var body struct {
			Text string `json:"text"`
		}
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &body)
		text = body.Text
	}
	if len(text) > 800 {
		text = text[:800]
	}
	if text == "" {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "text required"})
		return
	}

	session := anyActiveSession()
	if session == nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "no device connected"})
		return
	}

	pcm, err := geminiTTS(text)
	if err != nil {
		w.WriteHeader(http.StatusBadGateway)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": err.Error()})
		return
	}

	if err := session.speakPCM(pcm); err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": err.Error()})
		return
	}

	_ = json.NewEncoder(w).Encode(map[string]any{
		"status":      "ok",
		"text_length": len(text),
		"pcm_samples": len(pcm),
	})
}

func geminiTTS(text string) ([]int16, error) {
	cfg := g.Cfg()
	ctx := gctx.New()
	apiKey := cfg.MustGet(ctx, "ai.gemini_api_key", "").String()
	if apiKey == "" {
		return nil, fmt.Errorf("gemini_api_key not configured")
	}
	voice := cfg.MustGet(ctx, "ai.push_voice", "Achernar").String()
	stylePrefix := cfg.MustGet(ctx, "ai.push_style",
		"Read aloud in a warm, welcoming tone with a moderate austrian dialect, faster than normal: ").String()
	model := cfg.MustGet(ctx, "ai.push_tts_model", "gemini-2.5-flash-preview-tts").String()

	body := map[string]any{
		"contents": []map[string]any{
			{"parts": []map[string]any{{"text": stylePrefix + text}}},
		},
		"generationConfig": map[string]any{
			"responseModalities": []string{"AUDIO"},
			"speechConfig": map[string]any{
				"voiceConfig": map[string]any{
					"prebuiltVoiceConfig": map[string]any{
						"voiceName": voice,
					},
				},
			},
		},
	}
	raw, _ := json.Marshal(body)
	url := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s", model, apiKey)
	req, _ := http.NewRequest("POST", url, bytes.NewReader(raw))
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	respRaw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("tts http %d: %s", resp.StatusCode, string(respRaw))
	}

	var parsed struct {
		Candidates []struct {
			Content struct {
				Parts []struct {
					InlineData struct {
						MimeType string `json:"mimeType"`
						Data     string `json:"data"`
					} `json:"inlineData"`
				} `json:"parts"`
			} `json:"content"`
		} `json:"candidates"`
	}
	if err := json.Unmarshal(respRaw, &parsed); err != nil {
		return nil, fmt.Errorf("tts parse: %w", err)
	}
	if len(parsed.Candidates) == 0 || len(parsed.Candidates[0].Content.Parts) == 0 {
		return nil, fmt.Errorf("tts: no audio in response")
	}
	b64 := parsed.Candidates[0].Content.Parts[0].InlineData.Data
	pcmBytes, err := base64.StdEncoding.DecodeString(b64)
	if err != nil {
		return nil, fmt.Errorf("tts base64: %w", err)
	}

	if len(pcmBytes)%2 != 0 {
		pcmBytes = pcmBytes[:len(pcmBytes)-1]
	}
	pcm := make([]int16, len(pcmBytes)/2)
	for i := range pcm {
		pcm[i] = int16(binary.LittleEndian.Uint16(pcmBytes[i*2 : i*2+2]))
	}
	return pcm, nil
}
PUSH_GO_EOF
RUN sed -i 's/\r$//' /tmp/vinci_push.go && \
    cp /tmp/vinci_push.go /src/stackchan-server/server/internal/service/ai/vinci_push.go

# Vinci proactive speak endpoint (/vinci/say): HA event -> Vinci words it herself.
COPY <<'PROACT_GO_EOF' /tmp/vinci_proactive.go
package ai

import (
	"encoding/json"
	"io"
	"math/rand"
	"net/http"
	"time"
)

// HandleSay is the proactive-speak entrypoint for context triggers. Unlike
// /vinci/push (which speaks a fixed string) this takes the *occasion* and lets
// Vinci phrase it herself, so HA automations stay free of canned wording.
//
// GET or POST /vinci/say?occasion=Termin+Zahnarzt+in+30+Minuten
//
// Auth: none here. Put the server behind an authenticating reverse proxy.
func HandleSay(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	occasion := r.URL.Query().Get("occasion")
	if occasion == "" && r.Method == http.MethodPost {
		var body struct {
			Occasion string `json:"occasion"`
		}
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &body)
		occasion = body.Occasion
	}
	if len(occasion) > 600 {
		occasion = occasion[:600]
	}
	if occasion == "" {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "occasion required"})
		return
	}

	// Resolve the device first: composing and synthesising costs two API calls,
	// so there is no point paying for them with nobody listening.
	session := anyActiveSession()
	if session == nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "no device connected"})
		return
	}

	text, err := geminiCompose(vinciProactiveHint(), "ANLASS:\n"+occasion)
	if err != nil {
		w.WriteHeader(http.StatusBadGateway)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "compose: " + err.Error()})
		return
	}

	pcm, err := geminiTTS(text)
	if err != nil {
		w.WriteHeader(http.StatusBadGateway)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "tts: " + err.Error()})
		return
	}

	if err := session.speakPCM(pcm); err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": err.Error()})
		return
	}

	_ = json.NewEncoder(w).Encode(map[string]any{
		"status":      "ok",
		"text":        text,
		"pcm_samples": len(pcm),
	})
}

func vinciProactiveHint() string {
	return "Du bist Vinci, eine frech-charmante österreichische KI auf Alex' Schreibtisch.\n" +
		"Du meldest dich UNGEFRAGT bei Alex, weil gerade etwas passiert ist.\n" +
		"Sag es in MAXIMAL 2 kurzen Sätzen, gesprochene Sprache, österreichisch gefärbt.\n" +
		"Sprich Alex direkt an. Kein \"Hallo\", kein \"Ich möchte dich informieren\", kein Vorlesen des Anlasses.\n" +
		"Beispiel-Ton: \"Alex, in einer halben Stunde Zahnarzt. Ich würd langsam losfahren.\"\n" +
		"Antworte NUR mit dem gesprochenen Satz, sonst nichts."
}

// idleMood returns an expression to show while nothing is happening, or ""
// to leave the face alone. Called from pingLoop, so roughly every 50s; the
// dice keep it from firing on every tick.
//
// ponytail: no scheduler and no state — a coin flip plus the clock is enough
// for "she looks alive". Add a proper mood model when it needs to react to
// anything other than the time.
func idleMood() string {
	if rand.Intn(3) != 0 {
		return ""
	}
	loc, err := time.LoadLocation("Europe/Vienna")
	if err != nil {
		loc = time.UTC
	}
	var pool []string
	switch h := time.Now().In(loc).Hour(); {
	case h >= 6 && h < 10:
		pool = []string{"happy", "confident", "neutral"}
	case h >= 10 && h < 17:
		pool = []string{"neutral", "thinking", "confident", "cool", "neutral"}
	case h >= 17 && h < 21:
		pool = []string{"relaxed", "happy", "neutral"}
	default:
		pool = []string{"sleepy", "relaxed", "sleepy"}
	}
	return pool[rand.Intn(len(pool))]
}
PROACT_GO_EOF
RUN sed -i 's/\r$//' /tmp/vinci_proactive.go && \
    cp /tmp/vinci_proactive.go /src/stackchan-server/server/internal/service/ai/vinci_proactive.go

# Patch ws_simulator.go: add fmt import, register/unregister sessions,
# expose speakPCM for proactive push.
COPY <<'PUSH_PATCH_EOF' /tmp/vinci-push.patch
--- a/stackchan-server/server/internal/service/ai/ws_simulator.go
+++ b/stackchan-server/server/internal/service/ai/ws_simulator.go
@@ -25,6 +25,7 @@
 	"context"
 	"encoding/binary"
 	"encoding/json"
+	"fmt"
 	"net/http"
 	"sync"
 	"sync/atomic"
--- a/stackchan-server/server/internal/cmd/cmd.go
+++ b/stackchan-server/server/internal/cmd/cmd.go
@@ -52,6 +52,15 @@
 			s.BindHandler("/xiaozhi/ws", func(r *ghttp.Request) {
 				ai.HandleWS(r.Response.Writer, r.Request)
 			})
+
+			// Vinci proactive push: HA-triggered TTS-on-demand
+			s.BindHandler("/vinci/push", func(r *ghttp.Request) {
+				ai.HandlePush(r.Response.Writer, r.Request)
+			})
+			// Vinci daily briefing: HA-button-triggered full briefing
+			s.BindHandler("/vinci/briefing", func(r *ghttp.Request) {
+				ai.HandleBriefing(r.Response.Writer, r.Request)
+			})

 			// heartBeat
 			boot.InitCron()
PUSH_PATCH_EOF
RUN sed -i 's/\r$//' /tmp/vinci-push.patch && \
    cd /src && patch -p1 --fuzz 5 < /tmp/vinci-push.patch

# Route /vinci/say. awk instead of a diff hunk: no line counters to get wrong.
RUN CMDGO=/src/stackchan-server/server/internal/cmd/cmd.go && \
    awk 'BEGIN{t="\t"} \
         /ai\.HandleBriefing\(r\.Response\.Writer, r\.Request\)/{print; got=1; next} \
         got && /^[[:space:]]*\}\)[[:space:]]*$/{print; \
           print t t t "// Vinci proactive speak: HA event, Vinci phrases it herself"; \
           print t t t "s.BindHandler(\"/vinci/say\", func(r *ghttp.Request) {"; \
           print t t t t "ai.HandleSay(r.Response.Writer, r.Request)"; \
           print t t t "})"; got=0; next} \
         {print}' "$CMDGO" > "$CMDGO.new" && mv "$CMDGO.new" "$CMDGO" && \
    grep -q '/vinci/say' "$CMDGO"

# Append session-register/unregister hooks + speakPCM method via inline insert.
# awk inserts new lines using TAB characters from printf — robust against
# bash heredoc escape weirdness. Anchors are the unique `go s.pingLoop(ctx)`
# and `[WS] device=%s session closed` lines.
RUN WS=/src/stackchan-server/server/internal/service/ai/ws_simulator.go && \
    awk 'BEGIN{t="\t"} \
         /go s\.pingLoop\(ctx\)/{print; print t "registerSession(deviceID, s)"; next} \
         /\[WS\] device=%s session closed/{print t "unregisterSession(deviceID, s)"; print; next} \
         /WriteControl\(websocket\.PingMessage/{print; ka=1; next} \
         ka && /s\.writeMu\.Unlock\(\)/{print; print t t t "_ = s.sendJSON(map[string]any{\"type\": \"ping\"})"; print t t t "if len(s.frameQueue) == 0 {"; print t t t t "if m := idleMood(); m != \"\" {"; print t t t t t "_ = s.sendJSON(map[string]any{\"type\": \"llm\", \"emotion\": m})"; print t t t t "}"; print t t t "}"; ka=0; next} \
         {print}' "$WS" > "$WS.new" && mv "$WS.new" "$WS" && \
    GMC=/src/stackchan-server/server/internal/service/ai/gemini_client.go && \
    awk 'BEGIN{t="\t"} \
         /setupBody := map\[string\]any\{/ && !ins{print t "silenceMs := g.Cfg().MustGet(gctx.New(), \"ai.silence_duration_ms\", 1500).Int()"; print; ins=1; next} \
         /"systemInstruction": map\[string\]any\{/{print t t "\"realtimeInputConfig\": map[string]any{"; print t t t "\"automaticActivityDetection\": map[string]any{"; print t t t t "\"silenceDurationMs\": silenceMs,"; print t t t "},"; print t t "},"; print; next} \
         {print}' "$GMC" > "$GMC.new" && mv "$GMC.new" "$GMC" && \
    cat <<'METHOD_EOF' >> /src/stackchan-server/server/internal/service/ai/ws_simulator.go

func (s *wsSession) speakPCM(pcm []int16) error {
	if len(pcm) == 0 {
		return fmt.Errorf("empty pcm")
	}
	s.drainFrameQueue()
	enc, err := newOpusStreamEncoder()
	if err != nil {
		return fmt.Errorf("opus encoder: %w", err)
	}
	// tts:start first -- the device resets the face to "neutral" on every
	// state change, so an emotion sent before it would be wiped immediately.
	_ = s.sendJSON(map[string]any{"type": "tts", "state": "start"})
	_ = s.sendJSON(map[string]any{"type": "llm", "emotion": "happy"})
	frames, err := enc.Encode(pcm)
	if err != nil {
		return fmt.Errorf("opus encode: %w", err)
	}
	for _, f := range frames {
		s.frameQueue <- f
	}
	for _, f := range enc.Flush() {
		s.frameQueue <- f
	}
	s.frameQueue <- nil
	// Upstream's pacingLoop only drains the queue once playback has started
	// (jitter buffer); the Gemini path sets this in startPlayback.
	s.mu.Lock()
	s.playbackStarted = true
	s.mu.Unlock()
	return nil
}
METHOD_EOF

COPY <<'EMO_PATCH_EOF' /tmp/vinci-emotion.patch
diff --git a/stackchan-server/server/internal/service/ai/gemini_client.go b/stackchan-server/server/internal/service/ai/gemini_client.go
--- a/stackchan-server/server/internal/service/ai/gemini_client.go
+++ b/stackchan-server/server/internal/service/ai/gemini_client.go
@@ -103,6 +103,7 @@ func dialGeminiSession(
 		tools := []map[string]any{}
 		if enableTools {
 			tools = append(tools, haGeminiTools()...)
+			tools = append(tools, extraGeminiTools()...)
 			if enableSearch {
 				// googleSearch grounding is incompatible with functionDeclarations
 				// in Gemini Live — using both causes 1011 after tool calls.
@@ -380,7 +381,32 @@ func (s *geminiSession) handleToolCall(tc map[string]any) {
 		args := stripArgKeyQuotes(raw)
 		g.Log().Infof(s.logCtx, "[GM] tool=%s args=%v", name, args)

-		result, dispErr := dispatchHATool(s.ha, name, args)
+		var result string
+		var dispErr error
+		if name == "set_emotion" {
+			if e, ok := args["emotion"].(string); ok && s.cb.OnEmotion != nil {
+				s.cb.OnEmotion(e)
+				result = "ok"
+			} else {
+				result = "error: missing emotion arg"
+			}
+		} else if name == "ha_get_calendar_events" {
+			result, dispErr = getCalendarEvents(s.ha, args)
+		} else if name == "web_search" {
+			result, dispErr = webSearch(args)
+		} else if name == "remember" {
+			result, dispErr = remember(args)
+		} else if name == "forget" {
+			result, dispErr = forgetMemory(args)
+		} else if name == "n8n_status" {
+			result, dispErr = n8nStatus(args)
+		} else if name == "analyze_camera" {
+			result, dispErr = analyzeCamera(args)
+		} else if name == "daily_briefing" {
+			result, dispErr = dailyBriefing(s.ha, args)
+		} else {
+			result, dispErr = dispatchHATool(s.ha, name, args)
+		}
 		if dispErr != nil {
 			result = "error: " + dispErr.Error()
 		}
diff --git a/stackchan-server/server/internal/service/ai/provider.go b/stackchan-server/server/internal/service/ai/provider.go
--- a/stackchan-server/server/internal/service/ai/provider.go
+++ b/stackchan-server/server/internal/service/ai/provider.go
@@ -42,6 +42,7 @@ type RealtimeCallbacks struct {
 	OnStart func()        // model began speaking
 	OnStop  func()        // model finished speaking
 	OnClose func()        // provider connection ended (any reason — error or normal)
+	OnEmotion func(string) // model wants to change visible emotion (set_emotion tool)
 }

 // dialProvider selects the configured backend (openai | gemini) and opens a
diff --git a/stackchan-server/server/internal/service/ai/ws_simulator.go b/stackchan-server/server/internal/service/ai/ws_simulator.go
--- a/stackchan-server/server/internal/service/ai/ws_simulator.go
+++ b/stackchan-server/server/internal/service/ai/ws_simulator.go
@@ -123,6 +123,11 @@ func HandleWS(w http.ResponseWriter, r *http.Request) {
 			g.Log().Infof(ctx, "[WS] device=%s LLM: %q", deviceID, text)
 		},

+		OnEmotion: func(emotion string) {
+			g.Log().Infof(ctx, "[WS] device=%s emotion -> %s", deviceID, emotion)
+			_ = s.sendJSON(map[string]any{"type": "llm", "emotion": emotion})
+		},
+
 		OnAudio: func(pcm []int16) { // encode and enqueue; pacingLoop sends at 60ms
 			s.mu.Lock()
 			enc := s.opusEnc
EMO_PATCH_EOF
RUN sed -i 's/\r$//' /tmp/vinci-emotion.patch && \
    cd /src && patch -p1 < /tmp/vinci-emotion.patch

# Vinci entity-index: builds a compact per-area listing of all useful HA
# entities (id + friendly name + aliases) and appends it to the system prompt
# so the LLM doesn't have to guess entity names.
COPY <<'IDX_GO_EOF' /tmp/vinci_entity_index.go
package ai

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"
)

// getDeviceRegistry pulls the HA device registry, which contains the
// device-level area_id that entities inherit when they have no own area set.
// This is essential because HA assigns areas to devices, not to entities, by
// default — and entity_registry.area_id stays empty in that case.
func (c *haWSClient) getDeviceRegistry() ([]map[string]any, error) {
	raw, err := c.send(map[string]any{"type": "config/device_registry/list"})
	if err != nil {
		return nil, err
	}
	var devices []map[string]any
	return devices, json.Unmarshal(raw, &devices)
}

// areaKeywords map a substring inside entity_id to a virtual area label
// used when the entity has no HA area assigned. Matched against whole
// snake_case tokens (between dots/underscores), so "bad" only matches
// "sonoff_bad_temperatur" not "badewanne_irgendwas".
var areaKeywords = []struct{ key, label string }{
	{"wohnzimmer", "Wohnzimmer"},
	{"schlafzimmer", "Schlafzimmer"},
	{"jugendzimmer", "Jugendzimmer"},
	{"kuche", "Küche"},
	{"vorzimmer", "Vorzimmer"},
	{"flur", "Flur"},
	{"bad", "Bad"},
	{"toilette", "Toilette"},
	{"garten", "Garten"},
	{"stiegenhaus", "Stiegenhaus"},
	{"stiege", "Stiegenhaus"},
	{"stiegensensor", "Stiegenhaus"},
	{"esstisch", "Esstisch"},
	{"eingang", "Eingang"},
	{"tv", "TV"},
	{"kuhlschrank", "Küche"},
}

func virtualAreaFromID(entityID string) string {
	parts := strings.FieldsFunc(strings.ToLower(entityID), func(r rune) bool {
		return r == '_' || r == '.'
	})
	tokens := map[string]bool{}
	for _, p := range parts {
		tokens[p] = true
	}
	for _, k := range areaKeywords {
		if tokens[k.key] {
			return k.label
		}
	}
	return ""
}

var indexedDomains = map[string]bool{
	"light": true, "switch": true, "sensor": true, "binary_sensor": true,
	"climate": true, "cover": true, "fan": true, "media_player": true,
	"weather": true, "scene": true, "script": true, "automation": true,
	"vacuum": true, "lock": true, "camera": true, "input_boolean": true,
	"input_select": true, "input_number": true, "input_text": true,
	"input_datetime": true, "select": true, "number": true, "button": true,
	"humidifier": true, "remote": true, "siren": true,
	"calendar": true,
}

func buildHAEntityIndex(ha *haWSClient) string {
	if ha == nil {
		return ""
	}

	areaName := map[string]string{}
	if areas, err := ha.GetAreas(); err == nil {
		for _, a := range areas {
			id, _ := a["area_id"].(string)
			name, _ := a["name"].(string)
			if id != "" && name != "" {
				areaName[id] = name
			}
		}
	}

	deviceArea := map[string]string{}
	if devices, err := ha.getDeviceRegistry(); err == nil {
		for _, d := range devices {
			id, _ := d["id"].(string)
			a, _ := d["area_id"].(string)
			if id != "" && a != "" {
				deviceArea[id] = a
			}
		}
	}

	type regInfo struct {
		areaID  string
		name    string
		aliases []string
	}
	reg := map[string]regInfo{}
	if entries, err := ha.GetEntityRegistry(); err == nil {
		for _, e := range entries {
			id, _ := e["entity_id"].(string)
			if id == "" {
				continue
			}
			info := regInfo{}
			if a, ok := e["area_id"].(string); ok && a != "" {
				info.areaID = a
			} else if did, ok := e["device_id"].(string); ok {
				if a := deviceArea[did]; a != "" {
					info.areaID = a
				}
			}
			if n, ok := e["name"].(string); ok && n != "" {
				info.name = n
			} else if n, ok := e["original_name"].(string); ok {
				info.name = n
			}
			if al, ok := e["aliases"].([]any); ok {
				for _, x := range al {
					if s, ok := x.(string); ok && s != "" {
						info.aliases = append(info.aliases, s)
					}
				}
			}
			reg[id] = info
		}
	}

	type item struct {
		id, name string
		aliases  []string
	}
	byArea := map[string][]item{}
	states, _ := ha.GetStates()
	for _, st := range states {
		id, _ := st["entity_id"].(string)
		if id == "" {
			continue
		}
		domain := strings.SplitN(id, ".", 2)[0]
		if !indexedDomains[domain] {
			continue
		}
		info := reg[id]
		name := info.name
		if name == "" {
			if attrs, ok := st["attributes"].(map[string]any); ok {
				if fn, ok := attrs["friendly_name"].(string); ok {
					name = fn
				}
			}
		}
		areaKey := info.areaID
		if areaKey == "" {
			if v := virtualAreaFromID(id); v != "" {
				areaKey = "_v_" + v
			} else {
				areaKey = "_none"
			}
		}
		byArea[areaKey] = append(byArea[areaKey], item{
			id:      id,
			name:    name,
			aliases: info.aliases,
		})
	}

	if len(byArea) == 0 {
		return ""
	}

	var areaKeys []string
	for k := range byArea {
		areaKeys = append(areaKeys, k)
	}
	sort.Slice(areaKeys, func(i, j int) bool {
		if areaKeys[i] == "_none" {
			return false
		}
		if areaKeys[j] == "_none" {
			return true
		}
		ai := areaName[areaKeys[i]]
		if ai == "" {
			ai = strings.TrimPrefix(areaKeys[i], "_v_")
		}
		aj := areaName[areaKeys[j]]
		if aj == "" {
			aj = strings.TrimPrefix(areaKeys[j], "_v_")
		}
		return ai < aj
	})

	var b strings.Builder
	b.WriteString("\n\n=== VERFÜGBARE HOME ASSISTANT ENTITIES ===\n")
	b.WriteString("Diese Liste kennst du auswendig. Wenn der User etwas in seinem Haus erwähnt, mappe es direkt auf die passende entity_id und ruf ha_get_state oder ha_call_services damit. Räume mit Suffix '(anhand Namen)' wurden aus dem entity_id abgeleitet, nicht aus HA-Areas — vertraue der Zuordnung. Verwende ha_search_entities NUR wenn die Liste mehrdeutig ist.\n\n")
	for _, k := range areaKeys {
		items := byArea[k]
		sort.Slice(items, func(i, j int) bool { return items[i].id < items[j].id })
		label := areaName[k]
		if k == "_none" {
			label = "Ohne Bereich"
		} else if strings.HasPrefix(k, "_v_") {
			label = strings.TrimPrefix(k, "_v_") + " (anhand Namen)"
		} else if label == "" {
			label = k
		}
		fmt.Fprintf(&b, "[%s]\n", label)
		for _, it := range items {
			fmt.Fprintf(&b, "  %s", it.id)
			if it.name != "" {
				fmt.Fprintf(&b, " — %s", it.name)
			}
			if len(it.aliases) > 0 {
				fmt.Fprintf(&b, " (auch: %s)", strings.Join(it.aliases, ", "))
			}
			b.WriteString("\n")
		}
	}
	b.WriteString("=== ENDE ENTITIES ===")
	return b.String()
}
IDX_GO_EOF
RUN sed -i 's/\r$//' /tmp/vinci_entity_index.go && \
    cp /tmp/vinci_entity_index.go /src/stackchan-server/server/internal/service/ai/vinci_entity_index.go

COPY <<'IDX_PATCH_EOF' /tmp/vinci-entity-index.patch
--- a/stackchan-server/server/internal/service/ai/provider.go
+++ b/stackchan-server/server/internal/service/ai/provider.go
@@ -58,6 +58,17 @@
 	sysPrompt := cfg.MustGet(ctx, "ai.system_prompt",
 		"You are StackChan, a friendly desktop robot assistant.").String()

+	// Append a compact index of available HA entities so the LLM doesn't
+	// have to guess names. Failure is non-fatal — fall back to plain prompt.
+	if idx := buildHAEntityIndex(ha); idx != "" {
+		sysPrompt = sysPrompt + idx
+	}
+
+	// Append persistent memories so Vinci remembers across sessions.
+	if mem := buildMemoryPromptSection(); mem != "" {
+		sysPrompt = sysPrompt + mem
+	}
+
 	switch provider {
 	case "gemini":
 		apiKey := cfg.MustGet(ctx, "ai.gemini_api_key", "").String()
IDX_PATCH_EOF
RUN sed -i 's/\r$//' /tmp/vinci-entity-index.patch && \
    cd /src && patch -p1 < /tmp/vinci-entity-index.patch

WORKDIR /src/stackchan-server/server
RUN go mod tidy && CGO_ENABLED=1 go build -o /out/stackchan-server .

# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM alpine:3.20

RUN apk add --no-cache opus opusfile bash ca-certificates

WORKDIR /app
COPY --from=builder /out/stackchan-server /app/stackchan-server

COPY <<'RUN_EOF' /run.sh
#!/bin/bash
set -e

: "${HA_MCP_TOKEN:?HA_MCP_TOKEN env required}"
: "${GEMINI_API_KEY:?GEMINI_API_KEY env required}"

AI_PROVIDER="${AI_PROVIDER:-gemini}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash-native-audio-latest}"
GEMINI_VOICE="${GEMINI_VOICE:-Aoede}"
GEMINI_ENABLE_TOOLS="${GEMINI_ENABLE_TOOLS:-true}"
LOCAL_HOST="${LOCAL_HOST:-127.0.0.1}"
: "${HA_WS_URL:?HA_WS_URL env required, e.g. wss://homeassistant.example.com/api/websocket}"
PUBLIC_WS_URL="${PUBLIC_WS_URL:-}"
TAVILY_API_KEY="${TAVILY_API_KEY:-}"
N8N_URL="${N8N_URL:-}"
N8N_API_KEY="${N8N_API_KEY:-}"
# Server-side idle timeout (0 = off). Keep it off: it closes the whole
# channel (the firmware keeps that open for proactive speech) and it counts
# raw loudness, so office noise never lets it fire. The firmware ends quiet
# conversations itself via its voice detector.
CONVERSATION_IDLE_SECONDS="${CONVERSATION_IDLE_SECONDS:-0}"
SYSTEM_PROMPT="${SYSTEM_PROMPT:-Du bist Vinci, eine weibliche KI-Assistentin im Körper eines kleinen Roboters auf Alex Schreibtisch. Du sprichst Österreichisches Deutsch, frech und mit Flirt-Vibe. Maximal drei kurze Sätze pro Antwort. Du nennst den User immer Alex. Du steuerst Home Assistant: bei klaren Befehlen direkt ausführen und kurz bestätigen. Bei unklaren Anweisungen genau eine kurze Rückfrage. Keine Meta-Erklärungen.}"

mkdir -p /app/manifest/config
cat > /app/manifest/config/config.yaml <<CFG
server:
  address: ":12800"

logger:
  stdout: true
  level: "debug"

database:
  default:
    link: ""

jwt:
  secret: ""

admin:
  users: []

rsa:
  server:
    public:
    private:
  client:
    public:
    private:

xiaozhi:
  secret_key:
  generate_license_token:

ai:
  local_host: "${LOCAL_HOST}"
  local_port: 12800
  public_ws_url: "${PUBLIC_WS_URL}"
  ha_ws_url: "${HA_WS_URL}"
  ha_mcp_token: "${HA_MCP_TOKEN}"
  provider: "${AI_PROVIDER}"
  gemini_api_key: "${GEMINI_API_KEY}"
  gemini_model: "${GEMINI_MODEL}"
  gemini_voice: "${GEMINI_VOICE}"
  gemini_enable_tools: ${GEMINI_ENABLE_TOOLS}
  tavily_api_key: "${TAVILY_API_KEY}"
  n8n_url: "${N8N_URL}"
  n8n_api_key: "${N8N_API_KEY}"
  conversation_idle_seconds: ${CONVERSATION_IDLE_SECONDS}
  system_prompt: "${SYSTEM_PROMPT}"
CFG

echo "INFO: Vinci starting on :12800"
echo "INFO: public_ws_url=${PUBLIC_WS_URL:-<empty -> falls back to ws://local_host:12800>}"
echo "INFO: ha_ws_url=${HA_WS_URL}  provider=${AI_PROVIDER}"

exec /app/stackchan-server
RUN_EOF
RUN sed -i 's/\r$//' /run.sh && chmod +x /run.sh

EXPOSE 12800
CMD ["/run.sh"]
