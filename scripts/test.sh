#!/bin/sh
set -eu
# The explicit plugin path handles Swift Testing in standalone Command Line Tools.
developer_dir="$(xcode-select -p)"
plugin_path="$developer_dir/usr/lib/swift/host/plugins/testing"
if [ -d "$plugin_path" ]; then
    exec swift test -Xswiftc -plugin-path -Xswiftc "$plugin_path" "$@"
fi
exec swift test "$@"
