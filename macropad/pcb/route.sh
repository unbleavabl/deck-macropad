#!/usr/bin/env bash
# Place (build_pcb.py), autoroute (freerouting), fill the GND pours, DRC, and
# export JLCPCB Gerbers + drill files as deck-gerbers.zip, and preview renders.
set -euo pipefail
cd "$(dirname "$0")"
# freerouting 2.5 needs Java 25: `mise install java@temurin-25` (1.9 on Java 21 gave up with nets unrouted)
JAR=${FREEROUTING_JAR:-$HOME/.cache/freerouting/freerouting-2.5.0.jar}
JAVA=${JAVA:-$(mise where java@temurin-25 2>/dev/null)/bin/java}
quiet() { grep -v 'property.h' || true; }

python3 build_pcb.py 2>&1 | quiet
"$JAVA" -jar "$JAR" -de deck.dsn -do deck.ses -mp 200 --gui.enabled=false 2>&1 | grep -E 'Auto-routing stage completed|ERROR' | sed 's/.*\] //' || true
python3 - <<'EOF' 2>&1 | quiet
import pcbnew
b = pcbnew.LoadBoard("deck-unrouted.kicad_pcb")
assert pcbnew.ImportSpecctraSES(b, "deck.ses"), "SES import failed"
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save("deck.kicad_pcb")
EOF
kicad-cli pcb drc --severity-error --exit-code-violations -o drc.rpt deck.kicad_pcb 2>&1 | quiet
rm -rf gerbers && mkdir gerbers
kicad-cli pcb export gerbers -o gerbers/ -l F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts deck.kicad_pcb 2>&1 | quiet
kicad-cli pcb export drill -o gerbers/ deck.kicad_pcb 2>&1 | quiet
rm -f deck-gerbers.zip && (cd gerbers && zip -q ../deck-gerbers.zip *)
for side in top bottom; do
    kicad-cli pcb render --side $side -w 2000 -h 1300 --quality basic -o preview-$side.png deck.kicad_pcb 2>&1 | grep -v -E "property.h|Successfully|Rendering" || true
done
# 1:1 paper check: print at 100 %, cut out, hold against the plate's underside
kicad-cli pcb export pdf -o fit-check-1to1.pdf -l Edge.Cuts,F.Cu,F.Silkscreen --mode-single deck.kicad_pcb 2>&1 | quiet
rm -rf logs gerbers deck.dsn deck.ses deck.kicad_prl deck-unrouted.*
echo "done: deck.kicad_pcb, drc.rpt, deck-gerbers.zip"
