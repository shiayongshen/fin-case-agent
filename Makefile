# Docker 相關命令

.PHONY: build up down restart logs clean

# 構建鏡像
build:
	docker compose build

# 啟動服務
up:
	docker compose up -d

# 停止服務
down:
	docker compose down

# 重啟服務
restart:
	docker compose restart

# 查看日誌
logs:
	docker compose logs -f compliance-app

# 清理所有（停止服務並刪除卷）
clean:
	docker compose down -v
	docker system prune -f

# 完全重建
rebuild:
	docker compose down -v
	docker compose build --no-cache
	docker compose up -d

# 進入容器
shell:
	docker compose exec compliance-app bash

# 查看服務狀態
status:
	docker compose ps