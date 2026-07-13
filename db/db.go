package db

import (
	"database/sql"
	"errors"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/go-sql-driver/mysql"
	"opt360-portal-backend/config"
	"opt360-portal-backend/models"
)

var (
	db     *sql.DB
	dbOnce sync.Once
	dbErr  error

	uidDB       *sql.DB
	uidDBOnce   sync.Once
	uidDBErr    error
	opt360DBErr error

	portalDB     *sql.DB
	portalDBOnce sync.Once
	portalDBErr  error
)

// DBConfig holds database connection configuration. Pool settings are
// per-database on purpose — different databases in this app see very
// different traffic shapes (e.g. the portal DB is light auth lookups, the
// opt360 DB carries the heavy operator-search/listing traffic), so a single
// shared pool size wouldn't fit all three well.
type DBConfig struct {
	User     string
	Password string
	Host     string
	Port     int
	Database string

	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime time.Duration
}

// applyPoolSettings configures connection pooling on an already-opened *sql.DB,
// falling back to reasonable defaults for any zero-valued field.
func applyPoolSettings(database *sql.DB, config DBConfig) {
	maxOpen := config.MaxOpenConns
	if maxOpen <= 0 {
		maxOpen = 25
	}
	maxIdle := config.MaxIdleConns
	if maxIdle <= 0 {
		maxIdle = 5
	}
	lifetime := config.ConnMaxLifetime
	if lifetime <= 0 {
		lifetime = 5 * time.Minute
	}
	database.SetMaxOpenConns(maxOpen)
	database.SetMaxIdleConns(maxIdle)
	database.SetConnMaxLifetime(lifetime)
}

// InitDB initializes the database connection (operator360/opt_master).
//
// Loc is set to Asia/Kolkata here — and only here, not on the UID/portal
// connections — because opt_master's timestamp columns store IST wall-clock
// values. Without an explicit Loc, go-sql-driver/mysql defaults to time.UTC,
// mislabeling those IST values as UTC; the frontend then re-applies an
// Asia/Kolkata conversion on top for display, double-shifting the displayed
// time by +5:30. Setting Loc here means the driver anchors parsed times
// correctly at the source, so no downstream consumer needs special-casing.
func InitDB(config DBConfig) error {
	dbOnce.Do(func() {
		loc, locErr := time.LoadLocation("Asia/Kolkata")
		if locErr != nil {
			log.Printf("Failed to load Asia/Kolkata timezone, falling back to UTC: %v", locErr)
			loc = time.UTC
		}

		// Use mysql.Config to safely build connection string
		cfg := mysql.Config{
			User:                 config.User,
			Passwd:               config.Password,
			Net:                  "tcp",
			Addr:                 fmt.Sprintf("%s:%d", config.Host, config.Port),
			DBName:               config.Database,
			AllowNativePasswords: true,
			ParseTime:            true,
			Loc:                  loc,
		}

		db, dbErr = sql.Open("mysql", cfg.FormatDSN())
		if dbErr != nil {
			dbErr = fmt.Errorf("failed to open database connection: %w", dbErr)
			return
		}

		// Verify connection
		if err := db.Ping(); err != nil {
			dbErr = fmt.Errorf("failed to ping database: %w", err)
			db.Close()
			db = nil
			return
		}

		applyPoolSettings(db, config)
		log.Println("Database connection established successfully")
	})

	return dbErr
}

// GetDB returns the database connection
func GetDB() (*LoggedDB, error) {
	if db == nil {
		return nil, fmt.Errorf("database not initialized")
	}
	return newLoggedDB("opt360", db), nil
}

// InitUIDDB initializes the UID database connection
func InitUIDDB(config DBConfig) error {
	uidDBOnce.Do(func() {
		// Use mysql.Config to safely build connection string
		cfg := mysql.Config{
			User:                 config.User,
			Passwd:               config.Password,
			Net:                  "tcp",
			Addr:                 fmt.Sprintf("%s:%d", config.Host, config.Port),
			DBName:               config.Database,
			AllowNativePasswords: true,
			ParseTime:            true,
		}

		uidDB, uidDBErr = sql.Open("mysql", cfg.FormatDSN())
		if uidDBErr != nil {
			uidDBErr = fmt.Errorf("failed to open UID database connection: %w", uidDBErr)
			return
		}

		// Verify connection
		if err := uidDB.Ping(); err != nil {
			uidDBErr = fmt.Errorf("failed to ping UID database: %w", err)
			uidDB.Close()
			uidDB = nil
			return
		}

		applyPoolSettings(uidDB, config)
		log.Println("UID Database connection established successfully")
	})

	return uidDBErr
}

// GetUIDDB returns the UID database connection
func GetUIDDB() (*LoggedDB, error) {
	if uidDB == nil {
		return nil, fmt.Errorf("UID database not initialized")
	}
	return newLoggedDB("uid", uidDB), nil
}

// InitPortalDB initializes the portal (strot_services) database connection
func InitPortalDB(config DBConfig) error {
	portalDBOnce.Do(func() {
		cfg := mysql.Config{
			User:                 config.User,
			Passwd:               config.Password,
			Net:                  "tcp",
			Addr:                 fmt.Sprintf("%s:%d", config.Host, config.Port),
			DBName:               config.Database,
			AllowNativePasswords: true,
			ParseTime:            true,
		}

		portalDB, portalDBErr = sql.Open("mysql", cfg.FormatDSN())
		if portalDBErr != nil {
			portalDBErr = fmt.Errorf("failed to open portal database connection: %w", portalDBErr)
			return
		}

		if err := portalDB.Ping(); err != nil {
			portalDBErr = fmt.Errorf("failed to ping portal database: %w", err)
			portalDB.Close()
			portalDB = nil
			return
		}

		applyPoolSettings(portalDB, config)
		log.Println("Portal Database connection established successfully")
	})
	return portalDBErr
}

// GetPortalDB returns the portal (strot_services) database connection
func GetPortalDB() (*LoggedDB, error) {
	if portalDB == nil {
		return nil, fmt.Errorf("portal database not initialized")
	}
	return newLoggedDB("portal", portalDB), nil
}

const userColumns = "user_id, user_name, `group`, role, email, status, last_login, created_at, created_by"

// rowScanner is satisfied by both *sql.Row and *sql.Rows.
type rowScanner interface {
	Scan(dest ...interface{}) error
}

// scanUser scans a row selected with userColumns into a models.User, handling
// the nullable profile columns (email/status/last_login/created_at/created_by)
// added for the Profile + My Team feature.
func scanUser(row rowScanner) (*models.User, error) {
	var user models.User
	var email, status, createdBy sql.NullString
	var lastLogin, createdAt sql.NullTime

	if err := row.Scan(
		&user.ADID, &user.Name, &user.RegionalOffice, &user.Role,
		&email, &status, &lastLogin, &createdAt, &createdBy,
	); err != nil {
		return nil, err
	}

	if email.Valid {
		user.Email = &email.String
	}
	if status.Valid {
		user.Status = status.String
	} else {
		user.Status = "active"
	}
	if lastLogin.Valid {
		user.LastLogin = &lastLogin.Time
	}
	if createdAt.Valid {
		user.CreatedAt = &createdAt.Time
	}
	if createdBy.Valid {
		user.CreatedBy = &createdBy.String
	}
	return &user, nil
}

// GetUserByADID retrieves user information from database
func GetUserByADID(adID string) (*models.User, error) {
	database, err := GetPortalDB()
	if err != nil {
		log.Printf("Database connection error: %v", err)
		return nil, err
	}

	query := `SELECT ` + userColumns + ` FROM ` + config.PortalUsersTableRef() + ` WHERE user_id = ?`

	log.Printf("Querying user with ADID: %s", adID)

	user, err := scanUser(database.QueryRow(query, adID))
	if err == sql.ErrNoRows {
		log.Printf("No user found with ADID: %s", adID)
		return nil, fmt.Errorf("user not found")
	}
	if err != nil {
		log.Printf("Query error for ADID '%s': %v", adID, err)
		return nil, fmt.Errorf("failed to query user: %w", err)
	}

	log.Printf("Successfully found user: %s (Role: %s, Group: %s)", user.Name, user.Role, user.RegionalOffice)
	return user, nil
}

// GetAllUsers retrieves all users from database
func GetAllUsers() ([]models.User, error) {
	database, err := GetPortalDB()
	if err != nil {
		return nil, err
	}

	query := `SELECT ` + userColumns + ` FROM ` + config.PortalUsersTableRef()

	rows, err := database.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query users: %w", err)
	}
	defer rows.Close()

	var users []models.User
	for rows.Next() {
		user, err := scanUser(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan user: %w", err)
		}
		users = append(users, *user)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating rows: %w", err)
	}

	return users, nil
}

// UpdateUserGroup updates the group field for a user identified by user_id
func UpdateUserGroup(userID string, group string) error {
	database, err := GetPortalDB()
	if err != nil {
		log.Printf("Database connection error: %v", err)
		return err
	}

	query := `UPDATE ` + config.PortalUsersTableRef() + ` SET ` + "`group`" + ` = ? WHERE user_id = ?`

	log.Printf("Updating group for user_id: %s to: %s", userID, group)

	result, err := database.Exec(query, group, userID)
	if err != nil {
		log.Printf("Failed to update group for user_id '%s': %v", userID, err)
		return fmt.Errorf("failed to update user group: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		log.Printf("Failed to get rows affected: %v", err)
		return fmt.Errorf("failed to verify update: %w", err)
	}

	if rowsAffected == 0 {
		log.Printf("No user found with user_id: %s", userID)
		return fmt.Errorf("user not found")
	}

	log.Printf("Successfully updated group for user_id: %s", userID)
	return nil
}

// GetUsersByGroup retrieves all users belonging to a given group ("My Team" list).
func GetUsersByGroup(group string) ([]models.User, error) {
	database, err := GetPortalDB()
	if err != nil {
		return nil, err
	}

	query := `SELECT ` + userColumns + ` FROM ` + config.PortalUsersTableRef() + ` WHERE ` + "`group`" + ` = ? ORDER BY user_name`

	rows, err := database.Query(query, group)
	if err != nil {
		return nil, fmt.Errorf("failed to query users by group: %w", err)
	}
	defer rows.Close()

	users := make([]models.User, 0)
	for rows.Next() {
		user, err := scanUser(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan user: %w", err)
		}
		users = append(users, *user)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating rows: %w", err)
	}

	return users, nil
}

// ErrDuplicateUser is returned by CreateUser when the ad_id already exists.
var ErrDuplicateUser = fmt.Errorf("user already exists")

// CreateUser onboards a new portal user. Status is always "active" on creation.
func CreateUser(user models.User) error {
	database, err := GetPortalDB()
	if err != nil {
		log.Printf("Database connection error: %v", err)
		return err
	}

	query := `
		INSERT INTO ` + config.PortalUsersTableRef() + ` (user_id, user_name, ` + "`group`" + `, role, email, status, created_by)
		VALUES (?, ?, ?, ?, ?, 'active', ?)
	`

	_, err = database.Exec(query, user.ADID, user.Name, user.RegionalOffice, user.Role, user.Email, user.CreatedBy)
	if err != nil {
		var mysqlErr *mysql.MySQLError
		if errors.As(err, &mysqlErr) && mysqlErr.Number == 1062 {
			return ErrDuplicateUser
		}
		log.Printf("Failed to create user '%s': %v", user.ADID, err)
		return fmt.Errorf("failed to create user: %w", err)
	}

	log.Printf("Successfully onboarded user_id: %s (role=%s, group=%s, created_by=%v)", user.ADID, user.Role, user.RegionalOffice, user.CreatedBy)
	return nil
}

// UpdateUserStatus sets a user's active/inactive status.
func UpdateUserStatus(adID, status string) error {
	return updateUserField("status", adID, status)
}

// UpdateUserRole sets a user's role.
func UpdateUserRole(adID, role string) error {
	return updateUserField("role", adID, role)
}

// UpdateUserEmail sets a user's email address.
func UpdateUserEmail(adID, email string) error {
	return updateUserField("email", adID, email)
}

// updateUserField updates a single named column in opt360_portal_users for one user.
// column is always one of a small fixed set of caller-supplied literals (never
// user-controlled input), so this is safe despite the string-built column name.
func updateUserField(column, adID, value string) error {
	database, err := GetPortalDB()
	if err != nil {
		log.Printf("Database connection error: %v", err)
		return err
	}

	query := `UPDATE ` + config.PortalUsersTableRef() + ` SET ` + column + ` = ? WHERE user_id = ?`

	result, err := database.Exec(query, value, adID)
	if err != nil {
		log.Printf("Failed to update %s for user_id '%s': %v", column, adID, err)
		return fmt.Errorf("failed to update user %s: %w", column, err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to verify update: %w", err)
	}
	if rowsAffected == 0 {
		return fmt.Errorf("user not found")
	}

	log.Printf("Successfully updated %s for user_id: %s", column, adID)
	return nil
}

// UpdateLastLogin stamps a user's last_login to the current time. Called once per
// session from the Profile fetch (see handlers/Profile) rather than on every
// authenticated request, to avoid a DB write on every API call.
func UpdateLastLogin(adID string) error {
	database, err := GetPortalDB()
	if err != nil {
		return err
	}
	_, err = database.Exec(`UPDATE `+config.PortalUsersTableRef()+` SET last_login = NOW() WHERE user_id = ?`, adID)
	if err != nil {
		log.Printf("Failed to update last_login for user_id '%s': %v", adID, err)
		return fmt.Errorf("failed to update last_login: %w", err)
	}
	return nil
}

// InsertMarkAnomaly inserts a new anomaly record into mark_anomaly table
func InsertMarkAnomaly(anomaly *models.MarkAnomaly) error {
	database, err := GetPortalDB()
	if err != nil {
		log.Printf("Database connection error: %v", err)
		return err
	}

	query := `
		INSERT INTO ` + config.MarkAnomalyTableRef() + ` (
			eid, anomaly_category, anomaly_code, anomaly_name, error_category,
			date_created, enrolnment_type, opt_district, opt_state, opt_id,
			pkt_source, pkt_updt_type, remarks, station_machine_code, station_no
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	log.Printf("Inserting anomaly record for EID: %s", anomaly.EID)

	_, err = database.Exec(query,
		anomaly.EID,
		anomaly.AnomalyCategory,
		anomaly.AnomalyCode,
		anomaly.AnomalyName,
		anomaly.ErrorCategory,
		anomaly.DateCreated,
		anomaly.EnrolmentType,
		anomaly.OptDistrict,
		anomaly.OptState,
		anomaly.OptID,
		anomaly.PktSource,
		anomaly.PktUpdtType,
		anomaly.Remarks,
		anomaly.StationMachineCode,
		anomaly.StationNo,
	)

	if err != nil {
		log.Printf("Failed to insert anomaly record for EID '%s': %v", anomaly.EID, err)
		return fmt.Errorf("failed to insert anomaly: %w", err)
	}

	log.Printf("Successfully inserted anomaly record for EID: %s", anomaly.EID)
	return nil
}

// GetDataPathByOptID retrieves the data_path for a single operator from opt_master.
// This is the source of truth for where an operator's files live in S3 and
// must be used instead of deriving the path from RO/State/District/OptID.
func GetDataPathByOptID(optID string) (string, error) {
	database, err := GetDB()
	if err != nil {
		log.Printf("DB connection error: %v", err)
		return "", err
	}

	var dataPath sql.NullString
	err = database.QueryRow("SELECT data_path FROM operator360.opt_master WHERE id = ?", optID).Scan(&dataPath)
	if err == sql.ErrNoRows {
		return "", fmt.Errorf("operator not found: %s", optID)
	}
	if err != nil {
		return "", fmt.Errorf("failed to query data_path for operator '%s': %w", optID, err)
	}
	if !dataPath.Valid || dataPath.String == "" {
		return "", fmt.Errorf("data_path not set for operator: %s", optID)
	}

	return dataPath.String, nil
}

// Close closes the database connection
func Close() error {
	if db != nil {
		return db.Close()
	}
	return nil
}
