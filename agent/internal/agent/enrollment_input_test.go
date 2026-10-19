package agent

import (
	"bytes"
	"strings"
	"testing"
)

func TestEnrollmentTokenReaderAcceptsOptionalWindowsUTF8BOMAndCRLF(t *testing.T) {
	token := strings.Repeat("aB09-_", 10) + "aB09" // Local-only 64-byte token fixture.
	for _, raw := range []string{token, token + "\n", token + "\r\n", " \t" + token + " \t\r\n", "\xef\xbb\xbf" + token + "\r\n", "\xef\xbb\xbf \t" + token + " \t\r\n"} {
		got, e := ReadEnrollmentToken(strings.NewReader(raw))
		if e != nil || got != token {
			t.Fatal("valid local enrollment fixture failed normalization")
		}
	}
}
func TestEnrollmentTokenRejectsUTF16UnknownBytesAndEmbeddedBOM(t *testing.T) {
	token := "LOCAL_FIXTURE_ONLY_abcdefghijklmnopqrstuvwxyz0123456789_-"
	utf16le := []byte{0xff, 0xfe}
	utf16be := []byte{0xfe, 0xff}
	noBOM := []byte{}
	for _, b := range []byte(token) {
		utf16le = append(utf16le, b, 0)
		utf16be = append(utf16be, 0, b)
		noBOM = append(noBOM, b, 0)
	}
	invalid := [][]byte{utf16le, utf16be, noBOM, []byte("\xef\xbb\xbf\xef\xbb\xbf" + token), []byte(" " + "\xef\xbb\xbf" + token), []byte(token[:10] + "\xef\xbb\xbf" + token[10:]), []byte(token + "\x00"), []byte(token + "\x1b"), []byte(token + "\x7f"), []byte("\xc2\xa0" + token), []byte(token + "\r"), []byte(token + "\v"), []byte(token + "\f"), []byte(token[:20] + "\n" + token[20:]), []byte(token + "="), []byte(token + "+"), []byte(token + "/"), []byte(strings.Repeat("A", 19)), []byte(strings.Repeat("A", 257))}
	for _, raw := range invalid {
		if _, e := NormalizeEnrollmentToken(raw); e == nil {
			t.Fatal("unsupported encoding/control/token format accepted")
		}
	}
	for _, raw := range [][]byte{utf16le, utf16be, noBOM, []byte(token + "\x00\r\n")} {
		if _, e := ReadEnrollmentToken(bytes.NewReader(raw)); e == nil {
			t.Fatal("reader accepted unsupported encoding")
		}
	}
}
