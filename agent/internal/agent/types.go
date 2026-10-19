package agent

import (
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"net/netip"
	"net/url"
	"strings"
)

const MaxWirePacket = 2048

type ID [16]byte

func ParseID(v string) (ID, error) {
	var id ID
	if len(v) != 36 || v[8] != '-' || v[13] != '-' || v[18] != '-' || v[23] != '-' {
		return id, errors.New("invalid peer UUID")
	}
	b, err := hex.DecodeString(strings.ReplaceAll(v, "-", ""))
	if err != nil || len(b) != 16 {
		return id, errors.New("invalid peer UUID")
	}
	copy(id[:], b)
	return id, nil
}
func (id ID) String() string {
	s := hex.EncodeToString(id[:])
	return s[:8] + "-" + s[8:12] + "-" + s[12:16] + "-" + s[16:20] + "-" + s[20:]
}

type Candidate struct {
	IP     string `json:"ip"`
	Port   uint16 `json:"port"`
	Source string `json:"-"`
}

type PublicCandidate struct {
	IP     string `json:"ip"`
	Port   uint16 `json:"port"`
	Source string `json:"source"`
}

func (c Candidate) Addr() (netip.AddrPort, error) {
	a, e := netip.ParseAddr(c.IP)
	if e != nil || !a.Is4() || a.IsUnspecified() || a.IsMulticast() || a.IsLinkLocalUnicast() || a == netip.MustParseAddr("255.255.255.255") || c.Port == 0 {
		return netip.AddrPort{}, errors.New("invalid IPv4 UDP candidate")
	}
	return netip.AddrPortFrom(a.Unmap(), c.Port), nil
}

type PeerConfig struct {
	PeerID     string      `json:"peer_id"`
	PublicKey  string      `json:"public_key"`
	VirtualIP  string      `json:"virtual_ip"`
	Candidates []Candidate `json:"candidates"`
	PairSecret string      `json:"pair_secret"`
	Connected  bool        `json:"connected"`
}
type NetworkConfig struct {
	PeerID            string       `json:"peer_id"`
	PublicKey         string       `json:"public_key"`
	VirtualIP         string       `json:"virtual_ip"`
	PrefixLength      int          `json:"prefix_length"`
	ConfigVersion     int64        `json:"config_version"`
	TTLSeconds        int          `json:"config_ttl_seconds"`
	HeartbeatInterval int          `json:"heartbeat_interval"`
	STUNServers       []string     `json:"stun_servers"`
	RelayURL          string       `json:"relay_url"`
	Peers             []PeerConfig `json:"peers"`
}
type Identity struct {
	PeerID       string `json:"peer_id"`
	Name         string `json:"name"`
	ControlURL   string `json:"control_url"`
	DeviceToken  string `json:"device_token"`
	PrivateKey   string `json:"private_key"`
	PublicKey    string `json:"public_key"`
	VirtualIP    string `json:"virtual_ip"`
	PrefixLength int    `json:"prefix_length"`
}
type PeerStatus struct {
	PeerID              string   `json:"peer_id"`
	IP                  string   `json:"ip"`
	Path                string   `json:"path"`
	RTTMs               *float64 `json:"rtt_ms,omitempty"`
	LastHandshake       int64    `json:"last_handshake,omitempty"`
	HandshakeAgeSeconds *int64   `json:"handshake_age_seconds,omitempty"`
	RxBytes             uint64   `json:"rx_bytes"`
	TxBytes             uint64   `json:"tx_bytes"`
}
type PublicStatus struct {
	SchemaVersion int               `json:"schema_version"`
	Provider      string            `json:"provider"`
	DeviceID      string            `json:"device_id"`
	Name          string            `json:"name"`
	ControlURL    string            `json:"control_url"`
	UpdatedAt     int64             `json:"updated_at"`
	Mode          string            `json:"mode"`
	ListenPort    uint16            `json:"listen_port"`
	Candidates    []PublicCandidate `json:"candidates,omitempty"`
	StatusError   string            `json:"status_error,omitempty"`
	Control       struct {
		Connected     bool  `json:"connected"`
		LastSuccessAt int64 `json:"last_success_at"`
	} `json:"control"`
	TUN struct {
		Ready bool   `json:"ready"`
		Name  string `json:"name"`
		IP    string `json:"ip"`
	} `json:"tun"`
	Peers []PeerStatus `json:"peers"`
}

func decodeKey(s string) ([32]byte, error) {
	var k [32]byte
	b, e := base64.StdEncoding.Strict().DecodeString(s)
	if e != nil || len(b) != 32 {
		return k, errors.New("invalid 32-byte key")
	}
	copy(k[:], b)
	if k == ([32]byte{}) {
		return k, errors.New("zero key")
	}
	return k, nil
}
func ValidateControlURL(raw string) (*url.URL, error) {
	u, e := url.Parse(raw)
	if e != nil || u.Host == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" {
		return nil, errors.New("invalid control URL")
	}
	if u.Scheme != "https" {
		a, e := netip.ParseAddr(u.Hostname())
		if u.Scheme != "http" || e != nil || !a.IsLoopback() {
			return nil, errors.New("HTTPS required except loopback test server")
		}
	}
	if strings.Contains(u.Path, "..") || strings.Contains(u.Path, "\\") {
		return nil, errors.New("invalid control path")
	}
	u.Path = strings.TrimRight(u.Path, "/")
	return u, nil
}
func (n NetworkConfig) Validate(i Identity) error {
	if n.PeerID != i.PeerID || n.PublicKey != i.PublicKey || n.VirtualIP != i.VirtualIP || n.PrefixLength != i.PrefixLength {
		return errors.New("control configuration changes enrolled identity")
	}
	if _, e := ParseID(n.PeerID); e != nil {
		return e
	}
	own, e := netip.ParseAddr(n.VirtualIP)
	if e != nil || !own.Is4() || !own.IsPrivate() || n.PrefixLength < 16 || n.PrefixLength > 30 {
		return errors.New("invalid virtual subnet")
	}
	if n.TTLSeconds < 15 || n.TTLSeconds > 45 || n.HeartbeatInterval < 5 || n.HeartbeatInterval > 15 || len(n.Peers) > 254 || len(n.STUNServers) > 8 {
		return errors.New("invalid control configuration limits")
	}
	base, e := ValidateControlURL(i.ControlURL)
	if e != nil {
		return e
	}
	relay, e := url.Parse(n.RelayURL)
	if e != nil || relay.User != nil || relay.RawQuery != "" || relay.Fragment != "" || relay.Host != base.Host || (base.Scheme == "https" && relay.Scheme != "wss") || (base.Scheme == "http" && relay.Scheme != "ws") || relay.Path != base.Path+"/api/fabric/relay" {
		return errors.New("invalid same-origin relay URL")
	}
	prefix := netip.PrefixFrom(own, n.PrefixLength).Masked()
	ids := map[string]bool{i.PeerID: true}
	ips := map[string]bool{i.VirtualIP: true}
	keys := map[string]bool{i.PublicKey: true}
	for _, p := range n.Peers {
		if _, e := ParseID(p.PeerID); e != nil {
			return e
		}
		if ids[p.PeerID] || ips[p.VirtualIP] || keys[p.PublicKey] {
			return errors.New("duplicate peer identity")
		}
		ids[p.PeerID] = true
		ips[p.VirtualIP] = true
		keys[p.PublicKey] = true
		if _, e := decodeKey(p.PublicKey); e != nil {
			return e
		}
		if _, e := decodeKey(p.PairSecret); e != nil {
			return e
		}
		a, e := netip.ParseAddr(p.VirtualIP)
		if e != nil || !prefix.Contains(a) {
			return errors.New("peer outside assigned subnet")
		}
		if len(p.Candidates) > 32 {
			return errors.New("too many candidates")
		}
		for _, c := range p.Candidates {
			if _, e := c.Addr(); e != nil {
				return e
			}
		}
	}
	for _, s := range n.STUNServers {
		u, e := url.Parse(s)
		if e != nil || u.Scheme != "stun" || u.User != nil || u.RawQuery != "" || u.Fragment != "" {
			return fmt.Errorf("invalid STUN server")
		}
		if u.Host == "" && u.Opaque == "" {
			return errors.New("empty STUN server")
		}
	}
	return nil
}
