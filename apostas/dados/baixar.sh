#!/bin/bash
# football-data.co.uk: ligas principais (por temporada) e ligas extras (arquivo único)
LIGAS="E0 E1 E2 E3 EC SC0 SC1 SC2 SC3 D1 D2 I1 I2 SP1 SP2 F1 F2 N1 B1 P1 T1 G1"
TEMPS="1213 1314 1415 1516 1617 1718 1819 1920 2021 2122 2223 2324 2425 2526"
baixa() { f=$1_$2.csv; [ -s $f ] || curl -s -L -f -m 60 -o $f "https://www.football-data.co.uk/mmz4281/$2/$1.csv"; true; }
export -f baixa
for l in $LIGAS; do for t in $TEMPS; do echo "$l $t"; done; done | xargs -P 8 -n 2 bash -c 'baixa "$0" "$1"'
for x in ARG AUT BRA CHN DNK FIN IRL JPN MEX NOR POL ROU RUS SWE SWZ USA; do
  [ -s extra_$x.csv ] || curl -s -L -f -m 60 -o extra_$x.csv "https://www.football-data.co.uk/new/$x.csv"
done
