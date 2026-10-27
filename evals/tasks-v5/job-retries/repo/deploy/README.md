# Deploying taskmill

Deploys run `deploy/release.sh`: it copies the new code, then restarts the
`taskmill` process from the procfile.

The database lives on the box at `/var/lib/taskmill/jobs.db`. Back it up with
`sqlite3 jobs.db ".backup jobs-$(date +%F).db"`; don't copy the file while
workers are running.
