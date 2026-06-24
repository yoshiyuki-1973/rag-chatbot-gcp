output "artifact_registry_repo" {
  value       = google_artifact_registry_repository.app_repo.name
  description = "Artifact Registry Repository Name"
}

output "db_connection_name" {
  value       = google_sql_database_instance.db_instance.connection_name
  description = "Cloud SQL Instance Connection Name"
}

output "backend_url" {
  value       = google_cloud_run_v2_service.backend.uri
  description = "Backend Cloud Run Service URL"
}

output "frontend_url" {
  value       = google_cloud_run_v2_service.frontend.uri
  description = "Frontend Cloud Run Service URL"
}
