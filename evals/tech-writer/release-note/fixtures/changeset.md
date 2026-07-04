# Changeset — export scheduler

- Added a nightly export job that writes account activity to CSV at 02:00 UTC.
- Users can now download the previous day's export from Settings → Data.
- Exports older than 30 days are auto-deleted.
- No action required for existing users; the first export lands the night after
  this release.
