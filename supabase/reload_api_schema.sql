-- Run only after schema.sql succeeds (optional; fixes "schema cache" errors).
notify pgrst, 'reload schema';
