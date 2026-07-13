package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// Ping handles the ping endpoint
func Ping(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"message": "pong",
	})
}
