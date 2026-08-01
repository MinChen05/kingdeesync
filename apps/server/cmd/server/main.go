package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	v1routes "github.com/kingdee-sync/go/api/routes/v1"
	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/datasource"
	"github.com/kingdee-sync/go/internal/db"
	"github.com/kingdee-sync/go/internal/gormdb"
	"github.com/kingdee-sync/go/internal/kind"
	runtimecontrol "github.com/kingdee-sync/go/internal/runtime"
	"github.com/kingdee-sync/go/internal/schedule"
	"github.com/kingdee-sync/go/internal/syncengine"
	"github.com/kingdee-sync/go/internal/task"
)

func main() {
	if os.Getenv("SYNC_CONFIG_DIR") == "" {
		if executable, err := os.Executable(); err == nil {
			candidate := defaultConfigDirectory(executable)
			if info, statErr := os.Stat(candidate); statErr == nil && info.IsDir() {
				_ = os.Setenv("SYNC_CONFIG_DIR", candidate)
			}
		}
	}

	// Load config
	cfg, err := config.Load("")
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}

	// Init database (sqlx for business tables)
	if err := db.Init(); err != nil {
		log.Fatalf("Doris database init failed: %v", err)
	} else {
		defer db.Close()
	}

	// Init GORM database (for Go internal tables: history, schedule, stats)
	if err := gormdb.Init(); err != nil {
		log.Printf("Error: gorm database init failed, aborting: %v", err)
		os.Exit(1)
	} else {
		defer gormdb.Close()
		// Auto-migrate Go internal tables
		if err := gormdb.AutoMigrate(); err != nil {
			log.Printf("Error: gorm auto-migrate failed, aborting: %v", err)
			os.Exit(1)
		}
		log.Println("[GORM] Auto-migration completed")

		// Seed form queries from form-queries.json if DB is empty
		if n := gormdb.MigrateFormQueriesFromJSON(); n > 0 {
			log.Printf("[GORM] Seeded %d form queries from JSON", n)
		}
	}

	// Init sync engine
	engine := syncengine.NewSyncEngine()
	if gormdb.DB != nil {
		if recovered, err := gormdb.RecoverAbnormalRuns(5 * time.Minute); err != nil {
			log.Printf("Warning: failed to recover abnormal runs: %v", err)
		} else if recovered > 0 {
			log.Printf("[RECOVERY] Recovered %d abnormal sync runs on startup", recovered)
		}
		if plans, err := engine.RecoverPendingAbnormalRuns(context.Background(), false); err != nil {
			log.Printf("Warning: failed to prepare abnormal recoveries: %v", err)
		} else {
			for _, plan := range plans {
				if plan.RunID != "" {
					log.Printf("[RECOVERY] Started recovery run %s for %s", plan.RunID, plan.OriginalRunID)
				}
			}
		}
	}

	// Init services
	_ = task.NewService(engine)
	_ = datasource.NewService()

	// Init scheduler
	if err := schedule.Init(engine); err != nil {
		log.Printf("Warning: scheduler init failed: %v", err)
	}

	// Start Kingdee session keepalive
	keepAliveClient := kind.NewKingdeeClient()
	keepAliveClient.StartSessionKeepAlive()

	// Store engine for schedule route reload
	schedule.SetEngine(engine)

	// Setup Gin
	gin.SetMode(gin.ReleaseMode)
	r := gin.Default()

	// CORS: restrict to configured origin(s) instead of wildcard
	allowOrigin := "http://localhost:8000"
	if cfg != nil && cfg.Server.CorsOrigin != "" {
		allowOrigin = cfg.Server.CorsOrigin
	}
	r.Use(func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", allowOrigin)
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	})
	// Health check: process alive
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// Readiness: config, SQLite, Doris connection, and Stream Load HTTP endpoint
	r.GET("/ready", func(c *gin.Context) {
		notReady := []string{}
		if gormdb.DB == nil {
			notReady = append(notReady, "SQLite not initialized")
		}
		if db.DB == nil {
			notReady = append(notReady, "Doris connection not initialized")
		} else if db.DB.Ping() != nil {
			notReady = append(notReady, "Doris ping failed")
		}
		// Verify Doris Stream Load HTTP endpoint is reachable.
		if cfg != nil {
			effDB := cfg.GetEffectiveDatabase()
			if effDB.Type == "mysql" && effDB.Host != "" {
				scheme := "http"
				if env := os.Getenv("DORIS_USE_HTTPS"); strings.ToLower(env) == "1" || strings.ToLower(env) == "true" {
					scheme = "https"
				}
				slURL := fmt.Sprintf("%s://%s:8030/api/", scheme, effDB.Host)
				probeClient := &http.Client{Timeout: 5 * time.Second}
				resp, probeErr := probeClient.Head(slURL)
				if probeErr != nil {
					notReady = append(notReady, fmt.Sprintf("Doris Stream Load endpoint unreachable: %v", probeErr))
				} else {
					resp.Body.Close()
				}
			}
		}
		if len(notReady) > 0 {
			c.JSON(503, gin.H{"status": "not_ready", "reasons": notReady})
			return
		}
		c.JSON(200, gin.H{"status": "ready"})
	})

	// Init API routes — v1 endpoints only
	// Legacy /api/* routes removed (frontend fully migrated to /api/v1/*)
	v1routes.InitRoutes(r, engine)

	// Serve frontend (registered AFTER API routes so API takes precedence)
	// 定位 frontend/dist：兼容从项目根或 go/ 目录启动，并以可执行文件所在目录兜底，
	// 避免因工作目录不同导致静态资源找不到。（原因：修复部署时 dist 定位依赖启动目录的问题）
	frontendDist := ""
	executable, _ := os.Executable()
	for _, dir := range frontendDistCandidates(executable) {
		if info, err := os.Stat(dir); err == nil && info.IsDir() {
			frontendDist = dir
			break
		}
	}
	if frontendDist != "" {
		serveIndex := func(c *gin.Context) {
			data, err := os.ReadFile(frontendDist + "/index.html")
			if err != nil {
				c.File(frontendDist + "/index.html")
				return
			}
			injection := "<script>!function(){var h=Error.prototype.toString;Error.prototype.toString=function(){var s=h.call(this);if(this.digest&&s.indexOf('321')>=0){console.error('[React Error Digest]',this.digest)}return s};window.addEventListener('error',function(e){if(e.error&&e.error.digest){console.error('[React Error]',e.error.digest)}})}();</script>"
			html := strings.Replace(string(data), "</head>", injection+"</head>", 1)
			c.Data(http.StatusOK, "text/html; charset=utf-8", []byte(html))
		}

		r.GET("/", serveIndex)

		// Serve favicon
		r.GET("/favicon.svg", func(c *gin.Context) {
			c.File(frontendDist + "/favicon.svg")
		})

		// SPA fallback: serve static assets and index.html for frontend routes
		r.NoRoute(func(c *gin.Context) {
			path := c.Request.URL.Path

			// API and health routes: return 404
			if strings.HasPrefix(path, "/api") || strings.HasPrefix(path, "/health") || strings.HasPrefix(path, "/ready") {
				c.JSON(404, gin.H{"ok": false, "error": "not found"})
				return
			}

			// Try to serve static file from frontend/dist
			staticPath := frontendDist + path
			if _, err := os.Stat(staticPath); err == nil {
				// index.html must go through the HTML response handler; other static files are safe.
				if path == "/index.html" {
					serveIndex(c)
					return
				}
				c.File(staticPath)
				return
			}

			// SPA fallback: serve index.html
			serveIndex(c)
		})
	}

	// Determine listen address: env > config > default
	addr := os.Getenv("LISTEN_ADDR")
	if addr == "" && cfg != nil && cfg.Server.Host != "" {
		addr = cfg.Server.Host
	}
	if addr == "" {
		addr = "0.0.0.0"
	}

	port := os.Getenv("LISTEN_PORT")
	if port == "" && cfg != nil && cfg.Server.Port != 0 {
		port = strconv.Itoa(cfg.Server.Port)
	}
	if port == "" {
		port = "8000"
	}

	listenAddr := fmt.Sprintf("%s:%s", addr, port)
	server := &http.Server{Addr: listenAddr, Handler: r}
	shutdown := runtimecontrol.NewShutdownCoordinator(scheduleController{}, engine)
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGTERM, os.Interrupt)
	defer signal.Stop(signals)
	go func() {
		if err := shutdown.WaitForSignal(context.Background(), signals); err != nil {
			log.Printf("[SHUTDOWN] Sync drain finished with error: %v", err)
		}
		serverCtx, cancel := context.WithTimeout(context.Background(), runtimecontrol.DefaultShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(serverCtx); err != nil {
			log.Printf("[SHUTDOWN] HTTP server shutdown failed: %v", err)
		}
	}()

	log.Printf("Starting server on %s (frontend: %s)", listenAddr, frontendDist)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Printf("Server failed: %v", err)
	}
}

func defaultConfigDirectory(executable string) string {
	return filepath.Join(filepath.Dir(executable), "packages", "sync-config")
}

func frontendDistCandidates(executable string) []string {
	candidates := []string{"apps/web/dist", "../apps/web/dist"}
	if executable != "" {
		candidates = append(candidates, filepath.Join(filepath.Dir(executable), "apps", "web", "dist"))
	}
	return candidates
}

type scheduleController struct{}

func (scheduleController) Pause() {
	schedule.Pause()
}
