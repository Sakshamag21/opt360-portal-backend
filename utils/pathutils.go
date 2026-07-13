package utils

import "strings"

// ToPascalCase converts a space-separated string to PascalCase for S3 path construction.
// "Uttar Pradesh" → "UttarPradesh", "DELHI" → "Delhi", "delhi" → "Delhi"
func ToPascalCase(s string) string {
	words := strings.Fields(s)
	for i, w := range words {
		if len(w) > 0 {
			words[i] = strings.ToUpper(w[:1]) + strings.ToLower(w[1:])
		}
	}
	return strings.Join(words, "")
}
