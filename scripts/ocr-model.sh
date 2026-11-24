#!/usr/bin/env bash
set -euo pipefail

readonly VERCEL_PROVIDER="vercel-ai-gateway"
readonly VERCEL_URL="https://ai-gateway.vercel.sh/v1"
readonly VERCEL_KEY_COMMAND="printenv AI_GATEWAY_API_KEY"

usage() {
	cat >&2 <<'EOF'
usage:
  scripts/ocr-model.sh vercel MODEL_ID
  scripts/ocr-model.sh openai-codex

MODEL_ID must be a Vercel AI Gateway model identifier such as
provider/model-name. Set AI_GATEWAY_API_KEY in the environment before
running OCR reviews through the gateway.
EOF
	exit 2
}

fail() {
	printf 'ocr-model: %s\n' "$1" >&2
	exit 2
}

[[ $# -ge 1 ]] || usage

case "$1" in
	vercel)
		[[ $# -eq 2 ]] || usage
		model_id="$2"
		[[ "$model_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:/-]*$ ]] ||
			fail "invalid model identifier: $model_id"
		command -v ocr >/dev/null 2>&1 || fail "ocr is not installed or not on PATH"

		# Keep gateway details on its named provider. Do not change the saved
		# ChatGPT subscription model or unrelated OCR settings.
		ocr config set "custom_providers.${VERCEL_PROVIDER}.url" "$VERCEL_URL" >/dev/null
		ocr config set "custom_providers.${VERCEL_PROVIDER}.protocol" openai >/dev/null
		ocr config set "custom_providers.${VERCEL_PROVIDER}.api_key_cmd" "$VERCEL_KEY_COMMAND" >/dev/null
		ocr config set "custom_providers.${VERCEL_PROVIDER}.model" "$model_id" >/dev/null
		ocr config set provider "$VERCEL_PROVIDER" >/dev/null
		printf 'OCR provider set to Vercel AI Gateway (%s).\n' "$model_id"
		;;
	openai-codex)
		[[ $# -eq 1 ]] || usage
		command -v ocr >/dev/null 2>&1 || fail "ocr is not installed or not on PATH"

		# OCR's chatgpt provider uses its saved ChatGPT subscription login.
		# Selecting it does not alter its provider-specific model or auth.
		ocr config set provider chatgpt >/dev/null
		printf 'OCR provider set to the saved ChatGPT subscription configuration.\n'
		;;
	*)
		usage
		;;
esac
