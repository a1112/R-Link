package agent

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"time"
)

const (
	frameProbe  byte = 1
	frameReply  byte = 2
	frameData   byte = 3
	frameHeader      = 53
	frameMAC         = 32
	maxFrame         = frameHeader + MaxWirePacket + frameMAC
)

type envelope struct {
	kind     byte
	src, dst ID
	at       int64
	nonce    [8]byte
	payload  []byte
}

func randomNonce() ([8]byte, error) { var n [8]byte; _, e := rand.Read(n[:]); return n, e }
func packFrame(f envelope, key [32]byte) ([]byte, error) {
	if len(f.payload) > MaxWirePacket || f.kind < frameProbe || f.kind > frameData || (f.kind != frameData && len(f.payload) != 0) {
		return nil, errors.New("invalid transport frame")
	}
	b := make([]byte, frameHeader+len(f.payload)+frameMAC)
	copy(b, "RLF1")
	b[4] = f.kind
	copy(b[5:21], f.src[:])
	copy(b[21:37], f.dst[:])
	binary.BigEndian.PutUint64(b[37:45], uint64(f.at))
	copy(b[45:53], f.nonce[:])
	copy(b[53:], f.payload)
	h := hmac.New(sha256.New, key[:])
	h.Write(b[:len(b)-frameMAC])
	copy(b[len(b)-frameMAC:], h.Sum(nil))
	return b, nil
}
func unpackFrame(b []byte, key [32]byte, own, source ID, now time.Time) (envelope, error) {
	var f envelope
	if len(b) < frameHeader+frameMAC || len(b) > maxFrame || string(b[:4]) != "RLF1" || b[4] < frameProbe || b[4] > frameData {
		return f, errors.New("invalid frame")
	}
	h := hmac.New(sha256.New, key[:])
	h.Write(b[:len(b)-frameMAC])
	if !hmac.Equal(h.Sum(nil), b[len(b)-frameMAC:]) {
		return f, errors.New("frame authentication failed")
	}
	f.kind = b[4]
	copy(f.src[:], b[5:21])
	copy(f.dst[:], b[21:37])
	f.at = int64(binary.BigEndian.Uint64(b[37:45]))
	copy(f.nonce[:], b[45:53])
	f.payload = b[53 : len(b)-frameMAC]
	if f.src != source || f.dst != own {
		return f, errors.New("frame identity mismatch")
	}
	if f.at < now.UnixMilli()-30000 || f.at > now.UnixMilli()+30000 {
		return f, errors.New("expired frame")
	}
	if f.kind != frameData && len(f.payload) != 0 || f.kind == frameData && len(f.payload) == 0 {
		return f, errors.New("invalid frame payload")
	}
	return f, nil
}

// A bounded nonce cache supplements WireGuard's replay window for probes and
// prevents authenticated old UDP addresses from being learned a second time.
type nonceCache map[[8]byte]time.Time

func (c nonceCache) accept(n [8]byte, now time.Time) bool {
	for k, t := range c {
		if now.Sub(t) > 31*time.Second {
			delete(c, k)
		}
	}
	if _, ok := c[n]; ok {
		return false
	}
	if len(c) >= 8192 {
		return false
	}
	c[n] = now
	return true
}
