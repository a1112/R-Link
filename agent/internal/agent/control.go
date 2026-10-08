package agent

import (
	"bytes"
	"context"
	"crypto/ecdh"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"runtime"
	"strings"
	"time"
)

type ControlClient struct {
	base   *url.URL
	token  string
	client *http.Client
}

func NewControl(server, token string) (*ControlClient, error) {
	u, e := ValidateControlURL(server)
	if e != nil {
		return nil, e
	}
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.Proxy = nil
	return &ControlClient{base: u, token: token, client: &http.Client{Transport: transport, Timeout: 8 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}, nil
}
func (c *ControlClient) request(ctx context.Context, method, path string, body, out any) error {
	var data []byte
	var e error
	if body != nil {
		data, e = json.Marshal(body)
		if e != nil {
			return e
		}
	}
	u := *c.base
	u.Path += path
	req, e := http.NewRequestWithContext(ctx, method, u.String(), bytes.NewReader(data))
	if e != nil {
		return e
	}
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "R-Link-Agent/0.1")
	resp, e := c.client.Do(req)
	if e != nil {
		return fmt.Errorf("control connection failed: %w", e)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("control HTTP %d", resp.StatusCode)
	}
	raw, e := io.ReadAll(io.LimitReader(resp.Body, 1024*1024+1))
	if e != nil || len(raw) > 1024*1024 {
		return errors.New("invalid control response size")
	}
	if out != nil && json.Unmarshal(raw, out) != nil {
		return errors.New("invalid control JSON")
	}
	return nil
}
func (c *ControlClient) Config(ctx context.Context, i Identity) (NetworkConfig, error) {
	var n NetworkConfig
	e := c.request(ctx, "GET", "/api/fabric/agent/config", nil, &n)
	if e == nil {
		e = n.Validate(i)
	}
	return n, e
}

type HeartbeatPeer struct {
	PeerID        string   `json:"peer_id"`
	Path          string   `json:"path"`
	LastHandshake int64    `json:"last_handshake,omitempty"`
	RTTMs         *float64 `json:"rtt_ms,omitempty"`
}

func (c *ControlClient) Heartbeat(ctx context.Context, candidates []Candidate, tunReady bool, peers []PeerStatus, version int64) (int64, error) {
	ps := make([]HeartbeatPeer, 0, len(peers))
	for _, p := range peers {
		path := p.Path
		if path != "direct" && path != "relay" {
			path = "none"
		}
		ps = append(ps, HeartbeatPeer{PeerID: p.PeerID, Path: path, LastHandshake: p.LastHandshake, RTTMs: p.RTTMs})
	}
	mode := "transport-test"
	if tunReady {
		mode = "vpn"
	}
	body := struct {
		Candidates []Candidate     `json:"candidates"`
		TUNReady   bool            `json:"tunnel_ready"`
		Mode       string          `json:"mode"`
		PeerStatus []HeartbeatPeer `json:"peer_status"`
		Version    int64           `json:"config_version"`
	}{candidates, tunReady, mode, ps, version}
	var out struct {
		Version int64 `json:"config_version"`
	}
	e := c.request(ctx, "POST", "/api/fabric/agent/heartbeat", body, &out)
	return out.Version, e
}
func Enroll(ctx context.Context, server, name, token string) (Identity, error) {
	var i Identity
	if name == "" || len(name) > 80 || strings.ContainsAny(name, "\r\n\x00") || len(token) < 20 || len(token) > 256 {
		return i, errors.New("invalid enrollment input")
	}
	c, e := NewControl(server, "")
	if e != nil {
		return i, e
	}
	priv, e := ecdh.X25519().GenerateKey(rand.Reader)
	if e != nil {
		return i, e
	}
	public := base64.StdEncoding.EncodeToString(priv.PublicKey().Bytes())
	body := struct {
		Token      string      `json:"enrollment_token"`
		Name       string      `json:"name"`
		OS         string      `json:"os"`
		Public     string      `json:"public_key"`
		Port       uint16      `json:"udp_port"`
		Candidates []Candidate `json:"candidates"`
	}{token, name, runtime.GOOS, public, 0, []Candidate{}}
	var out struct {
		PeerID      string `json:"peer_id"`
		DeviceToken string `json:"device_token"`
		IP          string `json:"virtual_ip"`
		Prefix      int    `json:"prefix_length"`
	}
	if e = c.request(ctx, "POST", "/api/fabric/enrollment", body, &out); e != nil {
		return i, e
	}
	if _, e = ParseID(out.PeerID); e != nil || len(out.DeviceToken) < 32 || len(out.DeviceToken) > 1024 {
		return i, errors.New("invalid enrollment response")
	}
	i = Identity{PeerID: out.PeerID, Name: name, ControlURL: c.base.String(), DeviceToken: out.DeviceToken, PrivateKey: base64.StdEncoding.EncodeToString(priv.Bytes()), PublicKey: public, VirtualIP: out.IP, PrefixLength: out.Prefix}
	return i, nil
}
