#!/bin/bash
# Bygger Paper-pluginen uten Gradle. Trenger paper-api for 26.3 (hentes fra serverens libraries/).
set -e
cd "$(dirname "$0")"
MC="$HOME/Library/Application Support/minecraft"
JDK="$MC/runtime/java-runtime-epsilon/mac-os-arm64/java-runtime-epsilon/jre.bundle/Contents/Home/bin"
API="${PAPER_API:-$(ls lib/*.jar | tr "\n" ":")}"
rm -rf build && mkdir -p build/classes dist
"$JDK/javac" --release 25 -nowarn -proc:none -cp "$API" -d build/classes $(find src -name '*.java')
cp resources/* build/classes/
"$JDK/jar" --create --file dist/laksen-sno-paper-1.0.0.jar -C build/classes .
echo "Ferdig: paperplugin/dist/laksen-sno-paper-1.0.0.jar"
