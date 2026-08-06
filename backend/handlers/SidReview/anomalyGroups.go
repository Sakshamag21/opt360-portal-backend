package SidReview

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"sort"
	"strings"

	"opt360-portal-backend/config"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)

// GetAnomalyGroups handles GET /api/anomaly_groups — the distinct
// feature_group values behind one operator's anomalous packets, used to
// populate the Anomalous Packets tab's group filter dropdown (see
// GetAnamolousSIDs's own feature_group filter, which this list feeds).
func GetAnomalyGroups(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	optID := c.Query("opt_id")
	if optID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "opt_id query parameter is required"})
		return
	}

	groups, err := fetchAnomalyGroupsFromClickHouse(optID)
	if err == nil {
		log.Printf("[GetAnomalyGroups] Serving %d groups from ClickHouse opt_id=%s user=%s", len(groups), optID, user.ADID)
		c.JSON(http.StatusOK, gin.H{
			"operator_id":    optID,
			"anomaly_groups": groups,
			"requested_by":   user.ADID,
		})
		return
	}
	log.Printf("[GetAnomalyGroups] ClickHouse lookup failed opt_id=%s: %v. Falling back to S3.", optID, err)

	groups, err = fetchAnomalyGroupsFromS3(optID)
	if err != nil {
		log.Printf("[GetAnomalyGroups] S3 fallback failed opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":       "Anomaly groups not found",
			"operator_id": optID,
			"details":     err.Error(),
		})
		return
	}

	log.Printf("[GetAnomalyGroups] Serving %d groups from S3 opt_id=%s user=%s", len(groups), optID, user.ADID)
	c.JSON(http.StatusOK, gin.H{
		"operator_id":    optID,
		"anomaly_groups": groups,
		"requested_by":   user.ADID,
	})
}

// fetchAnomalyGroupsFromClickHouse returns the distinct, non-empty
// feature_group values for optID's anomalous packets.
func fetchAnomalyGroupsFromClickHouse(optID string) ([]string, error) {
	conn, err := db.GetClickHouseDB()
	if err != nil {
		return nil, err
	}

	ctx, cancel := context.WithTimeout(context.Background(), clickHouseQueryTimeout)
	defer cancel()

	rows, err := conn.Query(ctx, `
		SELECT DISTINCT feature_group
		FROM operator360.anomalous_packets_v2_rmt
		WHERE opt_id = ? AND feature_group != ''
		ORDER BY feature_group
	`, optID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	groups := make([]string, 0)
	for rows.Next() {
		var g string
		if err := rows.Scan(&g); err != nil {
			return nil, err
		}
		groups = append(groups, g)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return groups, nil
}

// fetchAnomalyGroupsFromS3 mirrors GetAnamolousSIDs' own S3 fallback
// flattening of anomaly_sid.json, extracting the distinct feature_group
// values instead of full records.
func fetchAnomalyGroupsFromS3(optID string) ([]string, error) {
	dataPath, err := db.GetDataPathByOptID(optID)
	if err != nil {
		return nil, err
	}

	s3Cfg := config.GetDefaultS3Config()
	fileName := strings.TrimSuffix(dataPath, "/") + "/anomaly_sid.json"

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		return nil, err
	}

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(fileName),
	})
	if err != nil {
		return nil, err
	}
	defer result.Body.Close()

	body, err := io.ReadAll(result.Body)
	if err != nil {
		return nil, err
	}

	var rawData map[string]interface{}
	if err := json.Unmarshal(body, &rawData); err != nil {
		return nil, err
	}

	seen := make(map[string]struct{})
	for _, operatorData := range rawData {
		operatorMap, ok := operatorData.(map[string]interface{})
		if !ok {
			continue
		}
		for _, categoryData := range operatorMap {
			categoryMap, ok := categoryData.(map[string]interface{})
			if !ok {
				continue
			}
			for _, sidData := range categoryMap {
				sidMap, ok := sidData.(map[string]interface{})
				if !ok {
					continue
				}
				if fg, ok := sidMap["feature_group"].(string); ok && fg != "" {
					seen[fg] = struct{}{}
				}
			}
		}
	}

	groups := make([]string, 0, len(seen))
	for g := range seen {
		groups = append(groups, g)
	}
	sort.Strings(groups)
	return groups, nil
}
