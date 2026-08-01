package v1

import "regexp"

var (
	redactURLCredentials = regexp.MustCompile(`(?i)\b([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@`)
	redactAuthorization  = regexp.MustCompile(`(?i)\bauthorization\s*[:=]\s*(?:bearer\s+)?[^\s,;]+`)
	redactBearer         = regexp.MustCompile(`(?i)\bbearer\s+[^\s,;]+`)
	redactSecretValue    = regexp.MustCompile(`(?i)\b(password|pwd|token|access_token|api_key|client_secret|secret)\s*([:=])\s*(?:"[^"]*"|'[^']*'|[^\s,;]+)`)
)

// redactSyncLog removes credentials and secrets from log messages.
func redactSyncLog(value string) string {
	value = redactURLCredentials.ReplaceAllString(value, "$1***:***@")
	value = redactAuthorization.ReplaceAllString(value, "authorization: ***")
	value = redactBearer.ReplaceAllString(value, "Bearer ***")
	return redactSecretValue.ReplaceAllString(value, "$1$2***")
}
