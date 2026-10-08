package agent

import (
	"context"
	"errors"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type WSRelay struct {
	mu         sync.Mutex
	write      sync.Mutex
	ws         *websocket.Conn
	url, token string
	bind       *Bind
}

func NewWSRelay(url, token string, b *Bind) *WSRelay {
	return &WSRelay{url: url, token: token, bind: b}
}
func (r *WSRelay) Connected() bool { r.mu.Lock(); defer r.mu.Unlock(); return r.ws != nil }
func (r *WSRelay) disconnect(ws *websocket.Conn) {
	r.mu.Lock()
	if r.ws == ws {
		r.ws = nil
	}
	r.mu.Unlock()
	_ = ws.Close()
}
func (r *WSRelay) Close() {
	r.mu.Lock()
	ws := r.ws
	r.ws = nil
	r.mu.Unlock()
	if ws != nil {
		_ = ws.Close()
	}
}
func (r *WSRelay) Run(ctx context.Context) {
	backoff := time.Second
	for ctx.Err() == nil {
		dialer := websocket.Dialer{HandshakeTimeout: 8 * time.Second, ReadBufferSize: 4096, WriteBufferSize: 4096, Proxy: nil}
		header := http.Header{}
		header.Set("Authorization", "Bearer "+r.token)
		ws, resp, e := dialer.DialContext(ctx, r.url, header)
		if resp != nil && resp.Body != nil {
			_ = resp.Body.Close()
		}
		if e != nil {
			select {
			case <-ctx.Done():
				return
			case <-time.After(backoff):
			}
			if backoff < 15*time.Second {
				backoff *= 2
			}
			continue
		}
		backoff = time.Second
		ws.SetReadLimit(4096)
		_ = ws.SetReadDeadline(time.Now().Add(40 * time.Second))
		ws.SetPongHandler(func(string) error { return ws.SetReadDeadline(time.Now().Add(40 * time.Second)) })
		r.mu.Lock()
		r.ws = ws
		r.mu.Unlock()
		stop := make(chan struct{})
		go func() {
			ticker := time.NewTicker(15 * time.Second)
			defer ticker.Stop()
			for {
				select {
				case <-stop:
					return
				case <-ctx.Done():
					_ = ws.Close()
					return
				case <-ticker.C:
					r.write.Lock()
					e := ws.WriteControl(websocket.PingMessage, nil, time.Now().Add(2*time.Second))
					r.write.Unlock()
					if e != nil {
						_ = ws.Close()
						return
					}
				}
			}
		}()
		for ctx.Err() == nil {
			kind, frame, e := ws.ReadMessage()
			if e != nil {
				break
			}
			if kind != websocket.BinaryMessage || len(frame) < 16+frameHeader+frameMAC || len(frame) > 16+maxFrame {
				_ = ws.Close()
				break
			}
			var src ID
			copy(src[:], frame[:16])
			r.bind.ReceiveRelay(src, frame[16:])
		}
		close(stop)
		r.disconnect(ws)
	}
}
func (r *WSRelay) Send(ctx context.Context, dst ID, payload []byte) error {
	if len(payload) < frameHeader+frameMAC || len(payload) > maxFrame {
		return errors.New("relay payload out of range")
	}
	r.mu.Lock()
	ws := r.ws
	r.mu.Unlock()
	if ws == nil {
		return errors.New("relay disconnected")
	}
	r.write.Lock()
	defer r.write.Unlock()
	deadline := time.Now().Add(2 * time.Second)
	if d, ok := ctx.Deadline(); ok && d.Before(deadline) {
		deadline = d
	}
	_ = ws.SetWriteDeadline(deadline)
	frame := make([]byte, 16+len(payload))
	copy(frame, dst[:])
	copy(frame[16:], payload)
	e := ws.WriteMessage(websocket.BinaryMessage, frame)
	if e != nil {
		r.disconnect(ws)
	}
	return e
}
