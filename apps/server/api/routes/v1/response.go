package v1

import "github.com/gin-gonic/gin"

// WriteData sends a successful JSON response wrapped in an Envelope.
func WriteData[T any](c *gin.Context, status int, data T) {
	c.JSON(status, Envelope[T]{Data: data})
}

// WriteDataWithMeta sends a paginated JSON response with PageMeta.
func WriteDataWithMeta[T any](c *gin.Context, status int, data T, meta PageMeta) {
	c.JSON(status, Envelope[T]{Data: data, Meta: &meta})
}

// WriteProblem sends a structured error response.
func WriteProblem(c *gin.Context, status int, p Problem) {
	c.JSON(status, gin.H{"error": p})
}
