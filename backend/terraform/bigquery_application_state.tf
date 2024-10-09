
resource "google_service_account" "looker-application-state-bq-sa" {
  account_id   = "looker-application-state-bq-sa"
  display_name = "Looker Explore Assistant BigQuery SA"
}

resource "google_project_iam_member" "iam_permission_bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = format("serviceAccount:%s", google_service_account.looker-application-state-bq-sa.email)
}

resource "google_project_iam_member" "iam_permission_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = format("serviceAccount:%s", google_service_account.looker-application-state-bq-sa.email)
}

resource "google_bigquery_dataset" "looker_application_state" {
  dataset_id    = "looker_application_state"
  friendly_name = "looker_application_state"
  description   = "application state for extension framework apps"
  location      = var.deployment_region
  depends_on    = [time_sleep.wait_after_apis_activate]
}

