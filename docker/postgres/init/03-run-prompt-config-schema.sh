#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 -U postgres -d prompt_config -f /docker-entrypoint-initdb.d/02-prompt-config-schema.sql
