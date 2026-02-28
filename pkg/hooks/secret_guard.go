package hooks

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
)

type SecretLeakGuard struct {
	patterns []*regexp.Regexp
}

func NewSecretLeakGuard() *SecretLeakGuard {
	return &SecretLeakGuard{
		patterns: []*regexp.Regexp{
			regexp.MustCompile(`(?i)\bsk-[a-z0-9]{16,}\b`),
			regexp.MustCompile(`(?i)\bghp_[a-z0-9]{20,}\b`),
			regexp.MustCompile(`(?i)\bxox[baprs]-[a-z0-9-]{12,}\b`),
			regexp.MustCompile(`(?i)\bapi[_-]?key\s*[:=]\s*["']?[a-z0-9_\-]{12,}`),
			regexp.MustCompile(`(?i)-----begin [a-z ]*private key-----`),
		},
	}
}

func (g *SecretLeakGuard) BeforeTool(_ context.Context, in ToolInvocation) (ToolInvocation, error) {
	raw, _ := json.Marshal(in.Args)
	text := string(raw)
	if g.containsSecret(text) {
		return in, fmt.Errorf("blocked by hook: tool arguments appear to contain secrets")
	}
	return in, nil
}

func (g *SecretLeakGuard) BeforeOutbound(_ context.Context, msg OutboundMessage) (OutboundMessage, error) {
	if g.containsSecret(msg.Content) {
		return msg, fmt.Errorf("blocked by hook: outbound content appears to contain secrets")
	}
	return msg, nil
}

func (g *SecretLeakGuard) containsSecret(text string) bool {
	trimmed := strings.TrimSpace(text)
	if trimmed == "" {
		return false
	}
	for _, re := range g.patterns {
		if re.MatchString(trimmed) {
			return true
		}
	}
	return false
}
