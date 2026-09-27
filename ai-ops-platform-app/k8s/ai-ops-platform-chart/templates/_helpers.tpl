{{- define "aiops-platform.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "aiops-platform.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "aiops-platform.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "aiops-platform.namespace" -}}
{{- .Values.global.namespace -}}
{{- end -}}

{{- define "aiops-platform.databaseUrl" -}}
{{- printf "postgresql://%s:%s@%s.%s.svc.cluster.local:5432/%s" .Values.postgres.auth.username .Values.postgres.auth.password .Values.postgres.name .Values.global.namespace .Values.postgres.auth.database -}}
{{- end -}}
