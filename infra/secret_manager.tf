locals {
  secret_names = toset([
    "LINE_CHANNEL_SECRET",
    "LINE_CHANNEL_ACCESS_TOKEN",
    "LINE_USER_ID",
    "ALLOWED_LINE_USER_ID",
    "ADMIN_TOKEN",
    "AUTH_SECRET",
    "APP_URL",
    "GEMINI_API_KEY",
    "GOOGLE_TOKEN_JSON",
    "GOOGLE_CREDENTIALS_JSON",
  ])
}

resource "google_secret_manager_secret" "app_secrets" {
  for_each  = local.secret_names
  secret_id = each.key

  replication {
    auto {}
  }
}
