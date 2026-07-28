package middleware

import (
	"log"
	"time"

	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

func RequestLogger() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		if raw := c.Request.URL.RawQuery; raw != "" {
			path = path + "?" + raw
		}

		c.Next()

		latency := time.Since(start).Round(time.Millisecond)
		status := c.Writer.Status()

		userID := "-"
		if u, exists := c.Get("user"); exists {
			if user, ok := u.(*models.User); ok {
				userID = user.ADID
			}
		}

		log.Printf("[HTTP] %s %s %d %s user=%s",
			c.Request.Method, path, status, latency, userID)
	}
}
