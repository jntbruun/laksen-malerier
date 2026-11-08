#!/bin/bash
# Bygger klientmoden uten Gradle: Minecraft 26.x er ikke obfuskert, så mixinen
# kompileres rett mot spillets egne klasser.
set -e
cd "$(dirname "$0")"
MC="$HOME/Library/Application Support/minecraft"
JDK="$MC/runtime/java-runtime-epsilon/mac-os-arm64/java-runtime-epsilon/jre.bundle/Contents/Home/bin"
# Every library the launcher has downloaded, for compiling only (nothing is bundled).
CP="$MC/versions/26.3/26.3.jar:$(find "$MC/libraries" -name '*.jar' | tr '\n' ':')"
rm -rf build && mkdir -p build/classes dist
"$JDK/javac" --release 25 -nowarn -proc:none -cp "$CP" -d build/classes $(find src -name '*.java')
cp resources/* build/classes/
"$JDK/jar" --create --file dist/laksen-stonecutter-1.1.0.jar -C build/classes .
echo "Ferdig: klientmod/dist/laksen-stonecutter-1.1.0.jar"
