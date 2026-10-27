#!/bin/sh
# Ship the current checkout to the jobs box and restart taskmill.
set -eu
HOST=${HOST:-jobs1.internal}
rsync -a --delete --exclude .git ./ "deploy@$HOST:/srv/taskmill/"
ssh "deploy@$HOST" 'cd /srv/taskmill && pip install -q -e . && sudo systemctl restart taskmill'
