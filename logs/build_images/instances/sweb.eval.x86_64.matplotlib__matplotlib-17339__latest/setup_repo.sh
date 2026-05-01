#!/bin/bash
set -euxo pipefail
git clone -o origin  --single-branch https://github.com/matplotlib/matplotlib /testbed
chmod -R 777 /testbed
cd /testbed
git reset --hard 67d04a8cce36674ad784da6427d2b0aab9b804dc
git remote remove origin
TARGET_TIMESTAMP=$(git show -s --format=%ci 67d04a8cce36674ad784da6427d2b0aab9b804dc)
git tag -l | while read tag; do TAG_COMMIT=$(git rev-list -n 1 "$tag"); TAG_TIME=$(git show -s --format=%ci "$TAG_COMMIT"); if [[ "$TAG_TIME" > "$TARGET_TIMESTAMP" ]]; then git tag -d "$tag"; fi; done
git reflog expire --expire=now --all
git gc --prune=now --aggressive
AFTER_TIMESTAMP=$(date -d "$TARGET_TIMESTAMP + 1 second" '+%Y-%m-%d %H:%M:%S')
COMMIT_COUNT=$(git log --oneline --all --since="$AFTER_TIMESTAMP" | wc -l)
[ "$COMMIT_COUNT" -eq 0 ] || exit 1
source /opt/miniconda3/bin/activate
conda activate testbed
echo "Current environment: $CONDA_DEFAULT_ENV"
apt-get -y update && apt-get -y upgrade && DEBIAN_FRONTEND=noninteractive apt-get install -y imagemagick ffmpeg texlive texlive-latex-extra texlive-fonts-recommended texlive-xetex texlive-luatex cm-super dvipng libfreetype6-dev libpng-dev libqhull-dev
MPLLOCALFREETYPE=0 MPLLOCALQHULL=0 python -m pip install --no-build-isolation -e ".[dev]"
git config --global user.email setup@swebench.config
git config --global user.name SWE-bench
git commit --allow-empty -am SWE-bench
