const url = (process.env.REACT_APP_BACKEND_URL || "").trim();
if (!url) {
  console.error(
    "REACT_APP_BACKEND_URL is required for a production build. " +
      "Set it to the public API origin before running yarn build."
  );
  process.exit(1);
}
