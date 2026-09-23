#!/bin/sh
set -eu
# Pass a simulator UUID from `xcrun simctl list devices available`.
if [ "$#" -lt 1 ]; then
    echo 'Usage: ./scripts/test-ui.sh SIMULATOR_UUID [additional xcodebuild arguments]' >&2
    exit 2
fi
simulator_id="$1"
shift
exec xcodebuild -project DominicanExpress.xcodeproj -scheme DominicanExpress \
    -destination "platform=iOS Simulator,id=$simulator_id" \
    -derivedDataPath /tmp/DominicanExpressDerivedData \
    -parallel-testing-enabled NO -collect-test-diagnostics never \
    CODE_SIGNING_ALLOWED=NO test "$@"
