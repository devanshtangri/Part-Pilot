export interface BackupDownloadResult {
  blob: Blob;
  filename: string;
}

export interface RestoreValidationResponse {
  status: "ready_for_review";
  validation_token: string;
  original_filename: string;
  backup_created_at_utc: string;
  validated_at_utc: string;
  expires_at_utc: string;
  format_version: 1;
  alembic_revision: "0007_projects_contract";
  archive_sha256: string;
  archive_size_bytes: number;
  database_sha256: string;
  database_size_bytes: number;
  user_count: number;
  active_user_count: number;
  sessions_present: boolean;
  warnings: string[];
}

export interface RestoreCommitResponse {
  status: "restart_scheduled";
  validation_token: string;
  message: string;
  sessions_will_be_invalidated: true;
  reauthentication_required: true;
}
