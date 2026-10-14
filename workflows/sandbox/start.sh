#!/bin/sh
set -eu
node /opt/minori/prepare.cjs
exec n8n start
