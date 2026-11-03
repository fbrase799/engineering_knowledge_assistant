{{- define "eka.name" -}}
engineering-knowledge-assistant
{{- end -}}

{{- define "eka.labels" -}}
app.kubernetes.io/name: {{ include "eka.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
{{- end -}}
