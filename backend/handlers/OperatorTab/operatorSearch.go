package OperatorTab

import (
	"database/sql"
	"log"
	"net/http"
	"strings"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// sortColumns whitelists the only columns a client may sort by — never
// interpolate a client-supplied string directly into ORDER BY.
var sortColumns = map[string]string{
	"risk_score": "risk_score",
	"last_sync":  "last_sync_timestamp",
}

// SearchOperators handles POST /api/operator_search.
//
// This is the single, unified replacement for the previously-separate
// operator_list, active_operator_list, inactive_operator_list, high_risk_operator,
// med_risk_operator, low_risk_operator, operator_list_with_risk and
// filter_operator_list endpoints. Sourced entirely from operator360.opt_master —
// no cross-cluster UID-DB join (see docs/VIEW_OPERATORS_REDESIGN_PLAN.md); status
// comes directly from opt_master.is_active.
//
// Body (all fields optional):
//
//	ro           – regional office to search. Defaults to the caller's own RO.
//	               Not access-restricted: any authenticated user may view any
//	               RO's operators (viewing is unrestricted; only feedback
//	               submission is RO-scoped).
//	state        – filter by state
//	district     – filter by district
//	id           – filter by operator id (exact match)
//	ea           – filter by ea name
//	ea_code      – filter by ea code (exact match — what the View Operators typeahead sends)
//	reg          – filter by registrar name
//	reg_code     – filter by registrar code (exact match — what the View Operators typeahead sends)
//	risk_bucket  – filter by risk bucket (High | Medium | Low | No)
//	status       – filter by status (active | inactive), from opt_master.is_active
//	sort_by      – risk_score | last_sync (default: none, falls back to id ASC)
//	sort_dir     – asc | desc (default: asc)
//	page         – page number (default 1)
//	page_size    – records per page (default 20, max 1000)
func SearchOperators(c *gin.Context) {

	// ── 1. Auth guard ──────────────────────────────────────────────────────────
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	// ── 2. Parse request body ─────────────────────────────────────────────────
	var req models.OperatorSearchRequest
	if err := c.ShouldBindJSON(&req); err != nil && err.Error() != "EOF" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}

	filterID := strings.TrimSpace(req.ID)

	// TechCentre/HeadQuarters users see all ROs by default (no RO filter) —
	// see models.ResolveRO. A normal user still defaults to their own RO —
	// except when searching by a specific operator ID with no explicit RO
	// given: knowing the exact ID shouldn't require also knowing/guessing
	// which RO it belongs to, so ID search stays global (no RO filter) for
	// every user unless they explicitly pick one.
	var filterRO string
	if filterID != "" && strings.TrimSpace(req.RO) == "" {
		filterRO = ""
	} else {
		filterRO = models.ResolveRO(strings.TrimSpace(req.RO), user)
	}
	filterState := strings.TrimSpace(req.State)
	filterDistrict := strings.TrimSpace(req.District)
	filterEA := strings.TrimSpace(req.EA)
	filterEACode := strings.TrimSpace(req.EACode)
	filterReg := strings.TrimSpace(req.Reg)
	filterRegCode := strings.TrimSpace(req.RegCode)
	filterRiskBucket := strings.TrimSpace(req.RiskBucket)
	filterStatus := strings.ToLower(strings.TrimSpace(req.Status))

	// ── 3. Pagination ──────────────────────────────────────────────────────────
	page := req.Page
	if page < 1 {
		page = 1
	}
	pageSize := req.PageSize
	if pageSize < 1 || pageSize > 1000 {
		pageSize = 20
	}
	offset := (page - 1) * pageSize

	// ── 4. Sort ────────────────────────────────────────────────────────────────
	orderBySQL := "ORDER BY id ASC"
	sortBy := strings.ToLower(strings.TrimSpace(req.SortBy))
	if col, ok := sortColumns[sortBy]; ok {
		dir := "ASC"
		if strings.EqualFold(strings.TrimSpace(req.SortDir), "desc") {
			dir = "DESC"
		}
		// Secondary sort by id keeps pagination stable when many rows tie on
		// the primary sort column (e.g. many operators share the same risk_bucket
		// but not necessarily the same risk_score/last_sync_timestamp — this is
		// just a safety net for ties, not expected to matter often).
		orderBySQL = "ORDER BY " + col + " " + dir + ", id ASC"
	}

	// ── 5. opt360 DB connection ────────────────────────────────────────────────
	opt360DB, err := db.GetDB()
	if err != nil {
		log.Printf("[SearchOperators] opt360 DB error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	// ── 6. Build WHERE ─────────────────────────────────────────────────────────
	var whereClauses []string
	var args []interface{}
	if filterRO != "" {
		whereClauses = append(whereClauses, "ro = ?")
		args = append(args, filterRO)
	}
	if filterState != "" {
		whereClauses = append(whereClauses, "state = ?")
		args = append(args, filterState)
	}
	if filterDistrict != "" {
		whereClauses = append(whereClauses, "district = ?")
		args = append(args, filterDistrict)
	}
	if filterID != "" {
		whereClauses = append(whereClauses, "id = ?")
		args = append(args, filterID)
	}
	if filterEA != "" {
		whereClauses = append(whereClauses, "ea = ?")
		args = append(args, filterEA)
	}
	if filterEACode != "" {
		whereClauses = append(whereClauses, "ea_code = ?")
		args = append(args, filterEACode)
	}
	if filterReg != "" {
		whereClauses = append(whereClauses, "reg = ?")
		args = append(args, filterReg)
	}
	if filterRegCode != "" {
		whereClauses = append(whereClauses, "reg_code = ?")
		args = append(args, filterRegCode)
	}
	if filterRiskBucket != "" {
		whereClauses = append(whereClauses, "risk_bucket = ?")
		args = append(args, filterRiskBucket)
	}
	if filterStatus == "active" {
		// opt_master.is_active is a numeric column where 1 means active and
		// every other value (including NULL) means inactive.
		whereClauses = append(whereClauses, "is_active = 1")
	} else if filterStatus == "inactive" {
		// NULL doesn't satisfy is_active <> 1 under SQL's three-valued logic, so
		// it has to be spelled out explicitly to count NULL as inactive too.
		whereClauses = append(whereClauses, "(is_active IS NULL OR is_active <> 1)")
	}

	var whereSQL string
	if len(whereClauses) > 0 {
		whereSQL = "WHERE " + strings.Join(whereClauses, " AND ")
	}
	fromSQL := "FROM operator360.opt_master"
	selectCols := `SELECT id, uid, name, phone, email, risk_score, risk_bucket, reg, reg_code, ea, ea_code, ro, district, state, last_sync_timestamp, data_path, is_active`

	// ── 7. Count ───────────────────────────────────────────────────────────────
	var total int
	countQuery := "SELECT COUNT(*) " + fromSQL + " " + whereSQL
	if cntErr := opt360DB.QueryRow(countQuery, args...).Scan(&total); cntErr != nil {
		log.Printf("[SearchOperators] Count query error: %v", cntErr)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to count records",
			"details": cntErr.Error(),
		})
		return
	}

	// ── 8. Fetch paginated data ────────────────────────────────────────────────
	operators := make([]models.SearchOperator, 0, pageSize)

	dataQuery := selectCols + " " + fromSQL + " " + whereSQL + " " + orderBySQL + " LIMIT ? OFFSET ?"
	dataArgs := append(args, pageSize, offset)
	rows, rErr := opt360DB.Query(dataQuery, dataArgs...)
	if rErr != nil {
		log.Printf("[SearchOperators] Data query error: %v", rErr)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch operator records",
			"details": rErr.Error(),
		})
		return
	}
	defer rows.Close()

	// ── 9. Scan rows ───────────────────────────────────────────────────────────
	for rows.Next() {
		var op models.SearchOperator
		var (
			uid               sql.NullString
			phone             sql.NullString
			email             sql.NullString
			riskScore         sql.NullFloat64
			riskBucket        sql.NullString
			reg               sql.NullString
			regCode           sql.NullString
			ea                sql.NullString
			eaCode            sql.NullString
			ro                sql.NullString
			district          sql.NullString
			state             sql.NullString
			lastSyncTimestamp sql.NullTime
			dataPath          sql.NullString
			isActive          sql.NullInt64
		)
		if err := rows.Scan(
			&op.ID, &uid, &op.Name, &phone, &email,
			&riskScore, &riskBucket,
			&reg, &regCode, &ea, &eaCode, &ro, &district, &state,
			&lastSyncTimestamp, &dataPath, &isActive,
		); err != nil {
			log.Printf("[SearchOperators] Row scan error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to process operator record",
				"details": err.Error(),
			})
			return
		}
		if uid.Valid {
			op.UID = uid.String
		}
		if phone.Valid {
			op.Phone = phone.String
		}
		if email.Valid {
			op.Email = email.String
		}
		if riskScore.Valid {
			op.RiskScore = &riskScore.Float64
		}
		if riskBucket.Valid {
			op.RiskBucket = &riskBucket.String
		}
		if reg.Valid {
			op.Reg = &reg.String
		}
		if regCode.Valid {
			op.RegCode = &regCode.String
		}
		if ea.Valid {
			op.EA = &ea.String
		}
		if eaCode.Valid {
			op.EACode = &eaCode.String
		}
		if ro.Valid {
			op.RO = &ro.String
		}
		if district.Valid {
			op.District = &district.String
		}
		if state.Valid {
			op.State = &state.String
		}
		if lastSyncTimestamp.Valid {
			op.LastSyncTimestamp = &lastSyncTimestamp.Time
		}
		if dataPath.Valid {
			op.DataPath = &dataPath.String
		}
		// Normalize opt_master's raw is_active (1/other/NULL) into "active"/"inactive"
		// so callers get a consistent value regardless of the underlying representation.
		normalizedStatus := "inactive"
		if isActive.Valid && isActive.Int64 == 1 {
			normalizedStatus = "active"
		}
		op.Status = &normalizedStatus
		operators = append(operators, op)
	}
	if err := rows.Err(); err != nil {
		log.Printf("[SearchOperators] Row iteration error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Error while reading operator records",
			"details": err.Error(),
		})
		return
	}

	// ── 10. Calculate total pages ──────────────────────────────────────────────
	totalPages := 0
	if total > 0 {
		totalPages = total / pageSize
		if total%pageSize != 0 {
			totalPages++
		}
	}

	appliedFilters := models.OperatorSearchAppliedFilters{
		RO:         filterRO,
		State:      filterState,
		District:   filterDistrict,
		ID:         filterID,
		EA:         filterEA,
		EACode:     filterEACode,
		Reg:        filterReg,
		RegCode:    filterRegCode,
		RiskBucket: filterRiskBucket,
		Status:     filterStatus,
		SortBy:     sortBy,
		SortDir:    strings.ToLower(strings.TrimSpace(req.SortDir)),
	}

	log.Printf(
		"[SearchOperators] ro=%s state=%q district=%q id=%q ea=%q ea_code=%q reg=%q reg_code=%q risk_bucket=%q status=%q sort=%q/%q → %d/%d records (page %d/%d)",
		filterRO, filterState, filterDistrict, filterID, filterEA, filterEACode, filterReg, filterRegCode, filterRiskBucket, filterStatus,
		appliedFilters.SortBy, appliedFilters.SortDir, len(operators), total, page, totalPages,
	)

	c.JSON(http.StatusOK, models.OperatorSearchResponse{
		Data:           operators,
		Total:          total,
		Page:           page,
		PageSize:       pageSize,
		TotalPages:     totalPages,
		AppliedFilters: appliedFilters,
	})
}
