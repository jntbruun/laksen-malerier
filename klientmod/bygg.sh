#!/bin/bash
# Bygger klientmoden uten Gradle: Minecraft 26.x er ikke obfuskert, så mixinen
# kompileres rett mot spillets egne klasser.
set -e
cd "$(dirname "$0")"
MC="$HOME/Library/Application Support/minecraft"
JDK="$MC/runtime/java-runtime-epsilon/mac-os-arm64/java-runtime-epsilon/jre.bundle/Contents/Home/bin"
CP="$MC/versions/26.3/26.3.jar:$(ls "$MC"/libraries/net/fabricmc/sponge-mixin/*/sponge-mixin-*.jar | head -1)"
rm -rf build && mkdir -p build/classes dist
"$JDK/javac" --release 25 -nowarn -proc:none -cp "$CP" -d build/classes $(find src -name '*.java')
cp resources/* build/classes/
"$JDK/jar" --create --file dist/laksen-stonecutter-1.0.0.jar -C build/classes .
echo "Ferdig: klientmod/dist/laksen-stonecutter-1.0.0.jar"
