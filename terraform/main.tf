terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. 必要な API サービスの有効化
locals {
  apis = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com"
  ]
}

resource "google_project_service" "enabled_apis" {
  for_each           = toset(local.apis)
  service            = each.key
  disable_on_destroy = false
}

# 2. Artifact Registry Docker リポジトリの作成
resource "google_artifact_registry_repository" "app_repo" {
  location      = var.region
  repository_id = "rag-chatbot-images"
  description   = "Docker repository for RAG Chatbot app"
  format        = "DOCKER"

  depends_on = [google_project_service.enabled_apis]
}

# 3. Cloud SQL for PostgreSQL の作成
resource "google_sql_database_instance" "db_instance" {
  name             = "rag-db-${var.environment}"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-f1-micro" # 開発・検証コストを抑えるため最小構成
    ip_configuration {
      ipv4_enabled = true # ローカルの Auth Proxy や Ingest 接続用にパブリックIPを有効化
    }
  }

  deletion_protection = false # ポートフォリオ/検証用のため削除保護はオフに設定

  depends_on = [google_project_service.enabled_apis]
}

resource "google_sql_database" "database" {
  name     = "rag_chatbot"
  instance = google_sql_database_instance.db_instance.name
}

resource "google_sql_user" "db_user" {
  name     = "app_user"
  instance = google_sql_database_instance.db_instance.name
  password = var.db_password
}

# 4. IAM サービスアカウントの作成
resource "google_service_account" "app_sa" {
  account_id   = "rag-chatbot-sa-${var.environment}"
  display_name = "RAG Chatbot App Service Account (${var.environment})"
}

# サービスアカウントへ Vertex AI ユーザーロールを付与
resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

# サービスアカウントへ Cloud SQL クライアントロールを付与
resource "google_project_iam_member" "cloud_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

# 5. バックエンド API (Cloud Run)
resource "google_cloud_run_v2_service" "backend" {
  name     = "rag-chatbot-backend-${var.environment}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.app_sa.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app_repo.repository_id}/backend:latest"

      ports {
        container_port = 8000
      }

      env {
        name  = "DATABASE_URL"
        value = "postgresql://app_user:${var.db_password}@/rag_chatbot?host=/cloudsql/${var.project_id}:${var.region}:${google_sql_database_instance.db_instance.name}"
      }
      env {
        name  = "USE_VERTEX_AI"
        value = "true"
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_LOCATION"
        value = var.region
      }
      env {
        name  = "LLM_PROVIDER"
        value = "gemini"
      }
      env {
        name  = "CORS_ORIGINS"
        value = var.cors_origins
      }
    }

    # Cloud SQL 接続の設定
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.db_instance.connection_name]
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image
    ]
  }

  depends_on = [
    google_sql_database_instance.db_instance,
    google_artifact_registry_repository.app_repo
  ]
}

# 全ユーザーへバックエンドの公開アクセスを付与 (run.invoker)
resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  name     = google_cloud_run_v2_service.backend.name
  location = google_cloud_run_v2_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# 6. フロントエンド UI (Cloud Run)
resource "google_cloud_run_v2_service" "frontend" {
  name     = "rag-chatbot-frontend-${var.environment}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app_repo.repository_id}/frontend:latest"

      ports {
        container_port = 3000
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image
    ]
  }

  depends_on = [
    google_cloud_run_v2_service.backend,
    google_artifact_registry_repository.app_repo
  ]
}

# 全ユーザーへフロントエンドの公開アクセスを付与 (run.invoker)
resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  name     = google_cloud_run_v2_service.frontend.name
  location = google_cloud_run_v2_service.frontend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
