package agent

import (
	"bufio"
	"bytes"
	"errors"
	"io"
	"strings"
	"unicode/utf8"
)

// ReadEnrollmentToken reads exactly one input line. It never logs or includes
// the token in an error. Windows UTF-8 writers may emit a BOM before that line.
func ReadEnrollmentToken(source io.Reader) (string, error) {
	reader := bufio.NewReaderSize(io.LimitReader(source, 1025), 1025)
	line, err := reader.ReadBytes('\n')
	if err != nil && err != io.EOF {
		return "", errors.New("cannot read enrollment token")
	}
	if len(line) == 0 {
		return "", errors.New("missing enrollment token")
	}
	return NormalizeEnrollmentToken(line)
}

func NormalizeEnrollmentToken(line []byte) (string, error) {
	invalid := errors.New("invalid enrollment token encoding or format")
	if len(line) > 1024 {
		return "", invalid
	}
	if bytes.HasPrefix(line, []byte{0xef, 0xbb, 0xbf}) {
		line = line[3:]
	}
	if !utf8.Valid(line) {
		return "", invalid
	}
	// Only a single terminal LF or CRLF is a line delimiter. UTF-16 NULs,
	// repeated/embedded BOMs and other Unicode/control input stay invalid.
	if len(line) > 0 && line[len(line)-1] == '\n' {
		line = line[:len(line)-1]
		if len(line) > 0 && line[len(line)-1] == '\r' {
			line = line[:len(line)-1]
		}
	}
	for _, b := range line {
		if b >= 127 || (b < 32 && b != '\t') {
			return "", invalid
		}
	}
	token := strings.TrimSpace(string(line))
	if len(token) < 20 || len(token) > 256 {
		return "", invalid
	}
	for _, b := range []byte(token) {
		if !(b >= 'a' && b <= 'z' || b >= 'A' && b <= 'Z' || b >= '0' && b <= '9' || b == '_' || b == '-') {
			return "", invalid
		}
	}
	return token, nil
}
