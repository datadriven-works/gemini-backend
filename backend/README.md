# Explore Assistant Backend

## Overview

This Terraform configuration establishes a backend for the Looker Explore Assistant on Google Cloud Platform (GCP), facilitating interaction with the Gemini Pro model of Vertex AI. The setup supports a Cloud Function backend, which acts as a proxy/relay for running content through the model.

### What backend should I use?

The Cloud Function/Run backend is recommended for this deployment:

- Generally speaking, this approach is recommended for folks who want more development control on the backend
- Your programming language of choice can be used
- Workflows for custom codeflow like using custom models, combining models to improve results, fetching from external datastores, etc. are supported
- An HTTPS endpoint will be made available that can be leveraged external to Looker (_ie. external applications with a custom web app_)
- The endpoint needs to be public for Looker to reach it (_To Note: the repo implements a signature on the request for security. Otherwise putting the endpoint behind a Load Balancer or API Proxy is recommended. Keep in mind that Looker Extensions however, when not embedded are only accessible by authenticated Looker users._)

## Prerequisites

- Terraform installed on your machine.
- Access to a GCP account with permission to create and manage resources.
- A GCP project where the resources will be deployed.

## Configuration and Deployment

We are using terraform to setup the backend. By default, we will store the state locally. You can also host the terraform state inside the project itself by using a [remote backend](https://developer.hashicorp.com/terraform/language/settings/backends/remote). The configuration is passed on the command line since we want to use the project-id in the bucket name. Since the project-ids are globally unique, so will the storage bucket name.

To use the remote backend you can run `./init.sh remote` instead of `terraform init`. This will create the bucket in the project, and setup the terraform project to use it as a backend.

### Cloud Function Backend

First create a file that will contain the LOOKER_AUTH_TOKEN and place it at the root. This will be used by the cloud function locally, as well as the extension framework app. The value of this token will uploaded to the GCP project as secret to be used by the Cloud Function.

If in the `/backend` cd back to root (ie. `cd ..`) and run the following command:

```bash
openssl rand -base64 32 > .vertex_cf_auth_token
```

From the `/backend` directory run the following.

To deploy the Cloud Function backend:

```bash
cd terraform
export TF_VAR_project_id=(PASTE PROJECT ID HERE)
export TF_VAR_looker_auth_token=$(cat ../../.vertex_cf_auth_token)
gsutil mb -p $TF_VAR_project_id gs://${TF_VAR_project_id}-terraform-state/
terraform init -backend-config="bucket=${TF_VAR_project_id}-terraform-state"
terraform plan
terraform apply
```

## Deployment Notes

- Changes to the code in `cloud-function` will result in a zip file with a new hash. This hash is added to the environment variables for the cloud function, and a new hash will trigger the redeployment of the cloud function.

## Resources Created

- Google Cloud Functions or Cloud Run services
- Necessary IAM roles and permissions for the Looker Explore Assistant to operate
- Storage buckets for deploying cloud functions
- Artifact Registry for storing Docker images, if required

## Cleaning Up

To remove all resources created by this Terraform configuration, run:

```sh
terraform destroy
```

**Note:** This will delete all resources and data. Ensure you have backups if needed.

## Support

For issues, questions, or contributions, please open an issue in the GitHub repository where this configuration is hosted.
