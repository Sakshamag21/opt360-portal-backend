package routes

import (
	"opt360-portal-backend/middleware"

	"opt360-portal-backend/handlers/AnamolyIndicators"
	"opt360-portal-backend/handlers/Anomaly"
	"opt360-portal-backend/handlers/Feedback"
	"opt360-portal-backend/handlers/LandingPage"
	"opt360-portal-backend/handlers/OperatorDetailView"
	"opt360-portal-backend/handlers/OperatorTab"
	"opt360-portal-backend/handlers/Profile"
	"opt360-portal-backend/handlers/RegionEvaluation"
	"opt360-portal-backend/handlers/SidReview"
	"opt360-portal-backend/handlers/Team"
	"opt360-portal-backend/handlers/User"

	"github.com/gin-gonic/gin"
)

func SetupRoutes(router *gin.Engine) {

	// Apply CORS and request logger globally
	router.Use(middleware.CORS())
	router.Use(middleware.RequestLogger())

	// Protected routes - require authentication
	api := router.Group("/api")
	api.Use(middleware.AuthMiddleware())
	{

		api.GET("/user/info", User.GetUserInfo)
		api.POST("/update_ro", User.UpdateRO)
		api.GET("/kpi", LandingPage.GetKPIData)
		api.GET("/ro_risk_dist", LandingPage.GetRORiskDist)
		api.GET("/highest_risk_opt", LandingPage.GetHighestRiskOperator)
		api.GET("/featureAnalysis", LandingPage.GetFeatureAnalysis)
		api.GET("/get_state_district", LandingPage.GetStateDistrict)
		api.GET("/get_ea_registrar", LandingPage.GetEARegistrar)
		api.GET("/geteaandreg", LandingPage.GetEaAndReg)
		api.POST("/selected_eas", LandingPage.GetSelectedEAs)
		api.GET("/top10eav1", LandingPage.GetTop10EAsV1)
		api.GET("/top10regv1", LandingPage.GetTop10regV1)
		api.GET("/all_eas", LandingPage.GetAllEAs)
		api.POST("/selected_registrars", LandingPage.GetSelectedRegistrars)
		api.GET("/all_registrars", LandingPage.GetAllRegistrars)
		api.POST("/operator_search", OperatorTab.SearchOperators)
		api.POST("/operator_filters", OperatorTab.GetOperatorFilters)
		api.GET("/operator_details", OperatorDetailView.GetOperatorDetails)
		api.GET("/operator_features", OperatorDetailView.GetOperatorFeatures)
		api.GET("/search_operator_packets", SidReview.SearchOperatorPacketsBySID)
		api.GET("/anamolous_sids", SidReview.GetAnamolousSIDs)
		api.POST("/sid/batch_get", SidReview.GetSIDBatchValues)
		api.POST("/feedback", Feedback.SubmitFeedback)
		api.GET("/anamoly_indicators", AnamolyIndicators.GetAnamolyIndicators)
		api.GET("/operator_risk_details", OperatorDetailView.GetOperatorRiskDetails)
		api.GET("/region_evaluation_count", RegionEvaluation.GetRegionEvaluationCount)
		api.POST("/report_anomaly", Anomaly.ReportAnomaly)

		// Profile + My Team (RBAC) — see docs/RBAC_PLAN.md. Kept POST-only per
		// instruction, including reads, rather than mixing in GET/PATCH.
		api.POST("/profile", Profile.GetProfile)
		api.POST("/profile/update_email", Profile.UpdateEmail)
		api.POST("/team", Team.GetTeam)
		api.POST("/team/onboard", Team.OnboardUser)
		api.POST("/team/update", Team.UpdateUser)

	}
}
