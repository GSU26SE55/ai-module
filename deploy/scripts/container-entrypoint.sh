#!/bin/sh
set -eu

data_dir="${AI_DATA_DIR:-/data}"
kb_root="${AI_KB_ROOT:-${data_dir}/kb}"
seed_dir="/app/models/embeddings"

mkdir -p \
  "${kb_root}/releases" \
  "${AI_PRESCRIPTION_HISTORY_DIR:-${data_dir}/prescription-history}" \
  "${AI_CLASSIFICATION_FEEDBACK_DIR:-${data_dir}/classification-feedback}"

if [ "${AI_BOOTSTRAP_KB:-true}" = "true" ]; then
  kb_revision="$(sha256sum "${seed_dir}/manifest.json" | cut -d ' ' -f 1)"
  kb_release="${kb_root}/releases/${kb_revision}"
  if [ ! -f "${kb_release}/.complete" ]; then
    mkdir -p "${kb_release}"
    cp -R "${seed_dir}/." "${kb_release}/"
    printf '%s\n' "${kb_revision}" > "${kb_release}/.complete"
  fi
  ln -sfn "${kb_release}" "${kb_root}/current"
fi

exec "$@"
