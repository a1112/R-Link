#!/usr/bin/env bash
# The former script generated an obsolete NetBird deployment. Keep this
# explicit exit so old bookmarks cannot silently install an invalid server.
echo '该脚本的旧版 NetBird 部署流程已失效。请按 https://docs.netbird.io/selfhosted/selfhosted-quickstart 部署，再配置 R-Link 的 R_LINK_NETBIRD_URL 和 R_LINK_NETBIRD_TOKEN。' >&2
exit 1
