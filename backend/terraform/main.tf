terraform {
  backend "gcs" {
    prefix  = "terraform/state/root"
  }
}

provider "google" {
  project = var.project_id
}

provider "google-beta" {
  project = var.project_id
}

module "base-project-services" {

  source                      = "terraform-google-modules/project-factory/google//modules/project_services"
  version                     = "14.2.1"
  disable_services_on_destroy = false

  project_id  = var.project_id
  enable_apis = true

  activate_apis = [
    "serviceusage.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "aiplatform.googleapis.com",
  ]
}

resource "time_sleep" "wait_after_basic_apis_activate" {
  depends_on      = [module.base-project-services]
  create_duration = "120s"
}


module "cf-backend-project-services" {
  source                      = "terraform-google-modules/project-factory/google//modules/project_services"
  version                     = "14.2.1"
  disable_services_on_destroy = false

  project_id  = var.project_id
  enable_apis = true

  activate_apis = [
    "cloudapis.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "run.googleapis.com",
    "storage-api.googleapis.com",
    "storage.googleapis.com",
    "compute.googleapis.com",
    "secretmanager.googleapis.com",
  ]

  depends_on = [module.base-project-services, time_sleep.wait_after_basic_apis_activate]
}


resource "time_sleep" "wait_after_apis_activate" {
  depends_on      = [
    time_sleep.wait_after_basic_apis_activate, 
    module.cf-backend-project-services,
  ]
  create_duration = "120s"
}

module "cloud_run_backend" {
  source                 = "./cloud_function"
  project_id             = var.project_id
  deployment_region      = var.deployment_region
  cloud_run_service_name = var.cloud_run_service_name

  depends_on = [time_sleep.wait_after_apis_activate]
}
